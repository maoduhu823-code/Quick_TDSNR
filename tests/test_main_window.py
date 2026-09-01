from __future__ import annotations

import sys
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from qtpy.QtWidgets import QApplication

from quick_tdsnr.ui.application import create_application
from quick_tdsnr.ui.main_window import QuickTDSNRMainWindow, USER_PHASES
from quick_tdsnr.domain.project_models import (
    ConfirmedMapping,
    ProjectConfig,
    ProjectInput,
    TimeDomainDraft,
)
from quick_tdsnr.services.project_file_service import ProjectFileService


def test_main_window_has_qs_style_three_column_workflow():
    app = create_application(["qts-test"])
    assert isinstance(app, QApplication)
    expected_font = "Microsoft YaHei" if sys.platform == "win32" else "WenQuanYi Zen Hei"
    assert app.font().family() == expected_font
    window = QuickTDSNRMainWindow()
    window.show()
    app.processEvents()
    try:
        splitter = window.findChild(object, "mainSplitter")
        assert splitter is not None
        assert splitter.count() == 3
        assert window.phase_list.count() == len(USER_PHASES) == 7
        assert window.page_stack.count() == 7
        assert window.log_output.isReadOnly()
        assert "Quick_TDSNR" in window.windowTitle()
        assert window.minimumWidth() >= 1100
        assert window.save_project_action.shortcut() == "Ctrl+S"
        assert window.open_project_action.shortcut() == "Ctrl+O"
        assert window.save_project_as_action.shortcut() == "Ctrl+Shift+S"
    finally:
        window.close()
        app.processEvents()


def test_phase_navigation_updates_page_and_button_state():
    app = create_application(["qts-test"])
    window = QuickTDSNRMainWindow()
    try:
        window.phase_list.setCurrentRow(2)
        app.processEvents()
        assert window.page_stack.currentIndex() == 2
        assert "Port_family" in window.current_phase_label.text()
        assert window.previous_button.isEnabled()
        assert window.next_button.isEnabled()
        assert window.next_button.text() == "确认映射并下一步"

        window.phase_list.setCurrentRow(3)
        app.processEvents()
        assert window.next_button.text() == "确认计划并下一步"

        window.phase_list.setCurrentRow(5)
        app.processEvents()
        assert window.next_button.isEnabled()
        assert window.next_button.text() == "进入 SNR 统计"

        window.phase_list.setCurrentRow(6)
        app.processEvents()
        assert not window.next_button.isEnabled()
    finally:
        window.close()


def test_project_snapshot_restores_phase_settings_and_plan(tmp_path):
    app = create_application(["qts-test"])
    source = tmp_path / "demo.s4p"
    source.write_bytes(b"demo")
    config = ProjectConfig(
        (ProjectInput(str(source), hashlib.sha256(b"demo").hexdigest()),),
        ConfirmedMapping(((1, 3), (2, 4)), ("family1", "family2"), "family1"),
        ("family2",),
        {"family1": (50.0,), "family2": (45.0, 55.0)},
        {"family1": 0.0, "family2": 0.2},
        "Z",
        0.2,
    )
    snapshot = replace(
        ProjectFileService.snapshot_from_config(config),
        current_phase=4,
        time_domain_draft=TimeDomainDraft(
            ui_text="80", rise_text="16", dt_text="4", points_text="512",
            main_method="peak", pre_text="2", post_text="8", half_ui_text="0.15",
        ),
        output_root=str(tmp_path / "qtsnr_runs"),
    )
    project_path = tmp_path / "restore.qtsnr.json"
    ProjectFileService.save_snapshot(snapshot, project_path)
    window = QuickTDSNRMainWindow(initial_project_path=project_path)
    try:
        app.processEvents()
        assert window.page_stack.currentIndex() == 4
        assert window.mapping_page.confirmed_mapping() == config.mapping
        assert window.sweep_page.current_plan()[0] == config
        assert window.time_domain_page.ui_edit.text() == "80"
        assert window.time_domain_page.main_combo.currentData() == "peak"
        assert window.execution_page.output_edit.text() == str(tmp_path / "qtsnr_runs")
        assert project_path.name in window.windowTitle()
    finally:
        window.close()


def test_saved_project_auto_updates_current_phase_checkpoint(tmp_path):
    app = create_application(["qts-test"])
    window = QuickTDSNRMainWindow()
    project_path = tmp_path / "checkpoint.qtsnr.json"
    try:
        window._current_project_path = project_path
        window.input_page.set_files([tmp_path / "draft.s4p"])
        window._select_phase(2)
        app.processEvents()
        payload = json.loads(project_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 2
        assert payload["current_phase"] == 2
        assert payload["input_paths"] == [str((tmp_path / "draft.s4p").resolve())]
    finally:
        window.close()
