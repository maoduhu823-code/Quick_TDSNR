from __future__ import annotations

from quick_tdsnr.domain.project_models import JobItemResult, JobManifest, RenormalizationRun
from quick_tdsnr.ui.application import create_application
from quick_tdsnr.ui.pages.execution_page import ExecutionPage


def test_execution_page_shows_plan_and_manifest_summary():
    app = create_application(["qts-test"])
    page = ExecutionPage()

    class Plan:
        case_count = 2
        input_count = 3
        estimated_output_files = 6

    page.set_plan(object(), Plan())
    assert page.start_button.isEnabled()
    assert "6 项" in page.summary_label.text()
    manifest = JobManifest(
        schema="quick_tdsnr_renormalization_v1",
        run_id="run",
        planned=2,
        saved=1,
        in_memory=0,
        failed=1,
        cancelled=0,
        items=(
            JobItemResult("a.s6p", "a", "C1", "family2", (1, 2), "saved", "out.s4p", "hash"),
            JobItemResult("a.s6p", "a", "C2", "family3", (1, 2), "failed", error="bad"),
        ),
    )
    page.set_result(RenormalizationRun(manifest, {}, None))
    app.processEvents()
    assert page.content_tabs.count() == 2
    assert page.content_tabs.currentIndex() == 0
    assert page.content_tabs.tabText(0) == "样本工作台"
    assert "失败 1" in page.content_tabs.tabText(page.detail_tab_index)
    assert page.result_table.rowCount() == 2
    assert "成功 1" in page.summary_label.text()
    assert page.result_table.item(1, 4).text() == "bad"
