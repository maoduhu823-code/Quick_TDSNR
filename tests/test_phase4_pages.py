from __future__ import annotations

from pathlib import Path
import time

from quick_tdsnr.domain.project_models import FamilyMappingProposal, ProjectInput
from quick_tdsnr.ui.application import create_application
from quick_tdsnr.ui.pages.mapping_page import MappingPage
from quick_tdsnr.ui.pages.sweep_page import SweepPage


def _proposal(lines: int = 4) -> FamilyMappingProposal:
    return FamilyMappingProposal(
        rows=tuple((line, line + lines, line + 2 * lines) for line in range(1, lines + 1)),
        family_count=3,
        line_count=lines,
        confidence="高",
    )


def test_mapping_page_requires_source_and_marks_duplicate_cells():
    app = create_application(["qts-test"])
    page = MappingPage()
    page.set_proposal(_proposal())
    assert not page.is_valid()
    assert not page.confirm_button.isEnabled()
    assert page.confirm_button.isHidden()

    page.source_combo.setCurrentIndex(1)
    app.processEvents()
    assert page.is_valid()
    assert page.confirm_button.isEnabled()

    page.table.item(0, 0).setText("2")
    app.processEvents()
    assert not page.is_valid()
    assert page.table.item(0, 0).background().color().name() == "#ffe3b3"
    assert page.table.item(1, 0).background().color().name() == "#ffe3b3"


def test_mapping_cell_swap_supports_undo_and_redo():
    app = create_application(["qts-test"])
    page = MappingPage()
    page.set_proposal(_proposal())
    before = (page.table.item(0, 0).text(), page.table.item(0, 1).text())
    page.table.swap_cells((0, 0), (0, 1))
    app.processEvents()
    assert (page.table.item(0, 0).text(), page.table.item(0, 1).text()) == before[::-1]
    page.table.undo_stack.undo()
    assert (page.table.item(0, 0).text(), page.table.item(0, 1).text()) == before
    page.table.undo_stack.redo()
    assert (page.table.item(0, 0).text(), page.table.item(0, 1).text()) == before[::-1]


def test_sweep_page_previews_and_emits_reproducible_plan():
    app = create_application(["qts-test"])
    mapping_page = MappingPage()
    mapping_page.set_proposal(_proposal())
    mapping_page.source_combo.setCurrentIndex(1)
    mapping = mapping_page.confirmed_mapping()

    page = SweepPage()
    page.set_mapping(
        mapping,
        inputs=(ProjectInput(str(Path("demo.s12p")), "abc"),),
        metric="S",
        frequency_ghz=0.1,
    )
    page.table.cellWidget(0, 1).setText("40，50")
    page.table.cellWidget(1, 1).setText("45, 55")
    page.table.cellWidget(2, 1).setText("50")
    app.processEvents()
    config, first = page.current_plan()
    _, second = page.current_plan()
    assert config.mapping == mapping
    assert first == second
    assert first.case_count == 8
    assert first.estimated_output_files == 8
    assert "8 cases" in page.preview_label.text()
    assert page.build_button.isEnabled()
    assert page.build_button.isHidden()


def test_sweep_page_rejects_invalid_parameter_before_confirm():
    app = create_application(["qts-test"])
    mapping_page = MappingPage()
    mapping_page.set_proposal(_proposal())
    mapping_page.source_combo.setCurrentIndex(1)
    page = SweepPage()
    page.set_mapping(
        mapping_page.confirmed_mapping(),
        inputs=(ProjectInput("demo.s12p", "abc"),),
        metric="S",
        frequency_ghz=0.1,
    )
    page.table.cellWidget(1, 1).setText("nan")
    app.processEvents()
    assert not page.build_button.isEnabled()
    assert "有限正数" in page.preview_label.text()


def test_mapping_page_handles_typical_s40p_table_smoothly():
    app = create_application(["qts-test"])
    page = MappingPage()
    proposal = FamilyMappingProposal(
        rows=tuple((line, line + 20) for line in range(1, 21)),
        family_count=2,
        line_count=20,
        confidence="高",
    )
    started = time.monotonic()
    page.set_proposal(proposal)
    page.source_combo.setCurrentIndex(1)
    page.show()
    for row in range(20):
        page.table.scrollToItem(page.table.item(row, 1))
        page.table.item(row, 1).setText(str(row + 21))
        app.processEvents()
    elapsed = time.monotonic() - started
    try:
        assert page.is_valid()
        assert elapsed < 2.0
    finally:
        page.close()
