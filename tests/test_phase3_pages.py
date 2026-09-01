import numpy as np
import skrf as rf

from quick_tdsnr.services.topology_inference_service import TopologyInferenceService
from quick_tdsnr.ui.application import create_application
from quick_tdsnr.ui.pages.input_page import InputPage
from quick_tdsnr.ui.pages.topology_page import TopologyPage


def _network() -> rf.Network:
    frequency = rf.Frequency(0.1, 1.0, 3, unit="GHz")
    s = np.zeros((3, 6, 6), dtype=complex)
    for ports in ((0, 2, 4), (1, 3, 5)):
        for left in ports:
            for right in ports:
                if left != right:
                    s[:, left, right] = 0.6
    return rf.Network(frequency=frequency, s=s, z0=50.0)


def test_input_page_emits_validated_request(tmp_path):
    app = create_application(["qts-test"])
    page = InputPage()
    received = []
    page.analyse_requested.connect(received.append)
    path = tmp_path / "demo.s2p"
    page.set_files([path])
    page.frequency_edit.setText("0.2")
    page.cliff_edit.setText("12")
    page._emit_request()
    app.processEvents()
    assert received[0]["paths"] == [str(path.resolve())]
    assert received[0]["low_freq_ghz"] == 0.2
    assert received[0]["min_cliff_db"] == 12.0


def test_topology_page_renders_evaluations_mapping_and_heatmaps():
    app = create_application(["qts-test"])
    analysis = TopologyInferenceService().analyse({"demo": _network()})
    page = TopologyPage()
    page.resize(1000, 700)
    page.show()
    app.processEvents()
    page.set_analysis(analysis)
    app.processEvents()
    try:
        assert page.evaluation_table.rowCount() == 3
        assert page.mapping_table.rowCount() == 2
        assert page.mapping_table.columnCount() == 3
        assert len(page.figure.axes) == 2  # selected heatmap + colorbar
        assert "family1/source" in page.source_notice.text()
        assert page.status_label.property("confidence") == analysis.confidence
        first_heatmap = page.figure.axes[0]
        assert first_heatmap.get_xticklabels()[0].get_text() == "1"
        assert first_heatmap.get_yticklabels()[0].get_text() == "1"
        mask = np.ma.getmaskarray(first_heatmap.images[0].get_array())
        assert np.all(mask[np.triu_indices(mask.shape[0])])
        assert not mask[1, 0]
        draft = page.draft()
        restored_page = TopologyPage()
        restored_page.load_draft(draft)
        app.processEvents()
        assert restored_page.status_label.text() == page.status_label.text()
        assert restored_page.mapping_table.rowCount() == page.mapping_table.rowCount()
        assert np.allclose(
            restored_page._analysis.matrix_snapshots["S"],
            analysis.matrix_snapshots["S"],
        )
        restored_page.close()
    finally:
        page.close()
