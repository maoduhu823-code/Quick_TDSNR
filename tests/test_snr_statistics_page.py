from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from quick_tdsnr.domain.project_models import SampleCatalog, SampleRecord
from quick_tdsnr.ui.application import create_application
from quick_tdsnr.ui.pages.snr_statistics_page import SNRStatisticsPage


def _catalog() -> SampleCatalog:
    samples = []
    for index, (r2, r3) in enumerate(
        ((40.0, 50.0), (40.0, 120.0), (60.0, 50.0), (60.0, 120.0))
    ):
        samples.append(
            SampleRecord(
                f"sample-{index}", "run", "input.s24p", "input-hash",
                f"C{index:03d}", "family2", tuple(range(1, 17)), "saved",
                f"sample-{index}.s16p", f"hash-{index}",
                {"family1": 34.0, "family2": r2, "family3": r3},
                {"family1": 0.8, "family2": 0.5, "family3": 0.8},
            )
        )
    return SampleCatalog("quick_tdsnr_sample_catalog_v1", "run", None, tuple(samples))


def _results(catalog: SampleCatalog):
    rows = []
    for index, sample in enumerate(catalog.samples):
        for line, snr in ((1, 2.0 + index), (2, 4.0 + index)):
            rows.append(
                SimpleNamespace(
                    sample_id=sample.sample_id, case_id=sample.case_id, line=line,
                    transfer_function=f"VTF{line + 8},{line}", main_method="peak",
                    main_time_ps=190.0, signal=snr + 1.0,
                    direct_noise=1.0 / snr, xtalk_noise=2.0 / snr,
                    total_noise=3.0 / snr, snr=snr, warnings=(), aggressors=(),
                )
            )
    return tuple(rows)


def test_statistics_page_defaults_to_worst_and_auto_selects_two_dimensions():
    app = create_application(["qts-test"])
    page = SNRStatisticsPage()
    catalog = _catalog()
    page.set_catalog(catalog)
    page.set_results(_results(catalog))
    app.processEvents()

    heatmap = page.statistics_panel.heatmap_panel
    assert heatmap.aggregation_combo.currentData() == "worst"
    assert not heatmap.x_combo.isVisible()
    assert not heatmap.y_combo.isVisible()
    assert heatmap.table.rowCount() == 2
    assert heatmap.table.columnCount() == 2
    heatmap.metric_combo.setCurrentIndex(heatmap.metric_combo.findData("snr"))
    app.processEvents()
    assert heatmap.table.item(0, 0).text() == "2"

    heatmap.aggregation_combo.setCurrentIndex(
        heatmap.aggregation_combo.findData("best")
    )
    app.processEvents()
    assert heatmap.table.item(0, 0).text() == "4"

    heatmap.aggregation_combo.setCurrentIndex(
        heatmap.aggregation_combo.findData("mean")
    )
    app.processEvents()
    assert heatmap.table.item(0, 0).text() == "3"
    assert page.statistics_panel.detail_tabs.count() == 4
    page.close()


def test_statistics_scope_is_explicit_and_empty_selection_means_empty():
    app = create_application(["qts-test"])
    page = SNRStatisticsPage()
    catalog = _catalog()
    page.set_catalog(catalog)
    page.set_results(_results(catalog))
    page.scope_combo.setCurrentIndex(page.scope_combo.findData("checked"))
    page.set_checked_sample_ids(set())
    app.processEvents()
    assert "显示 0 / 8 条" in page.summary_label.text()
    assert page.statistics_panel.result_page.table.rowCount() == 0
    page.close()


def test_more_than_two_dimensions_show_axis_and_fixed_value_controls():
    app = create_application(["qts-test"])
    base = _catalog()
    catalog = replace(
        base,
        samples=tuple(
            replace(
                sample,
                cio_pf={
                    **sample.cio_pf,
                    "family2": 0.5 if index < 2 else 1.0,
                },
            )
            for index, sample in enumerate(base.samples)
        ),
    )
    page = SNRStatisticsPage()
    page.set_catalog(catalog)
    page.set_results(_results(catalog))
    app.processEvents()
    heatmap = page.statistics_panel.heatmap_panel
    assert not heatmap.x_combo.isHidden()
    assert not heatmap.y_combo.isHidden()
    assert not heatmap.fixed_group.isHidden()
    assert len(heatmap._fixed_combos) == 1
    page.close()
