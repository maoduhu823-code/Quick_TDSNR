from __future__ import annotations

import shutil
import subprocess

import pytest

from quick_tdsnr import __version__
from quick_tdsnr.launcher import DEFAULT_TEST_PROJECT, build_parser, main


def test_parser_uses_qts_program_name():
    assert build_parser().prog == "qts"


def test_registered_qts_command_reports_version():
    command = shutil.which("qts")
    assert command is not None, "editable install 后应注册 qts 命令"
    completed = subprocess.run(
        [command, "--version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == f"Quick_TDSNR {__version__}"


def test_version_action_exits_cleanly(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"Quick_TDSNR {__version__}"


def test_test_mode_launches_default_project(monkeypatch):
    from quick_tdsnr.ui import application

    captured = {}

    def fake_run_gui(*, project_path):
        captured["project_path"] = project_path
        return 0

    monkeypatch.setattr(application, "run_gui", fake_run_gui)

    assert main(["-test"]) == 0
    assert captured["project_path"] == DEFAULT_TEST_PROJECT


def test_runtime_check_imports_complete_main_window():
    assert main(["--runtime-check"]) == 0
