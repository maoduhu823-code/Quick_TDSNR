from __future__ import annotations

import numpy as np
from qtpy.QtWidgets import QGroupBox

from quick_tdsnr.domain.project_models import (
    FrequencyTrace,
    SampleCatalog,
    SampleRecord,
    TimeWaveformResult,
)
from quick_tdsnr.ui.application import create_application
from quick_tdsnr.ui.pages.sample_workspace_page import SampleWorkspacePage


def _catalog(count: int = 50) -> SampleCatalog:
    return SampleCatalog(
        "quick_tdsnr_sample_catalog_v1",
        "run-id",
        None,
        tuple(
            SampleRecord(
                f"sample-{index}", "run-id", "input.s2p", "hash", f"C{index:03d}",
                "family2", (1, 2), "saved", f"C:/samples/sample_{index:02d}.s2p",
                f"hash-{index}", {"family2": 40.0 + index}, {"family2": 0.1},
            )
            for index in range(count)
        ),
    )


def test_sample_workspace_lists_filters_and_checks_50_samples():
    app = create_application(["qts-test"])
    page = SampleWorkspacePage()
    page.set_catalog(_catalog())
    app.processEvents()
    assert page.model.rowCount() == 50
    assert len(page.model.checked_samples()) == 1
    assert "C:/samples" not in page.model.data(page.model.index(0), 0)

    page.select_all_button.click()
    app.processEvents()
    assert len(page.model.checked_samples()) == 50
    page.search_edit.setText("C049")
    app.processEvents()
    assert page.model.rowCount() == 1
    page.clear_selection_button.click()
    app.processEvents()
    assert len(page.model.checked_samples()) == 49


def test_sample_workspace_opens_frequency_and_time_plot_dialogs():
    app = create_application(["qts-test"])
    page = SampleWorkspacePage()
    page.show()
    page.set_catalog(_catalog(1))
    frequency = np.linspace(0, 10, 11)
    trace = FrequencyTrace("sample-0", "sample", 1, 2, "S", "db", frequency, -frequency)
    page.frequency_panel.set_traces((trace,))
    waveform = TimeWaveformResult(
        "sample-0", "sample", 1, 2, "settings", frequency, np.sin(frequency)
    )
    page.time_panel.set_waveforms((waveform,))
    app.processEvents()
    assert not hasattr(page.frequency_panel, "canvas")
    assert not hasattr(page.time_panel, "canvas")
    assert page.frequency_panel._plot_dialog.isVisible()
    assert page.time_panel._plot_dialog.isVisible()
    assert len(page.frequency_panel._plot_dialog.figure.axes) == 1
    assert len(page.time_panel._plot_dialog.figure.axes) == 1
    assert page.tabs.count() == 2
    page.close()


def test_workspace_prioritizes_sample_list_and_has_no_embedded_plot_canvas():
    app = create_application(["qts-test"])
    page = SampleWorkspacePage()
    page.resize(900, 670)
    page.show()
    app.processEvents()

    sample_height, analysis_height = page.workspace_splitter.sizes()
    total_height = sample_height + analysis_height
    assert total_height > 0
    assert 0.55 <= sample_height / total_height <= 0.65
    assert page.sample_list.height() >= 150

    frequency_controls = page.frequency_panel.findChild(
        QGroupBox, "frequencyControlsGroup"
    )
    assert frequency_controls is not None
    assert not hasattr(page.frequency_panel, "canvas")

    page.tabs.setCurrentIndex(1)
    app.processEvents()
    time_controls = page.time_panel.findChild(
        QGroupBox, "timeControlsGroup"
    )
    assert time_controls is not None
    assert not hasattr(page.time_panel, "canvas")
    assert not hasattr(page, "statistics_panel")
    page.close()
