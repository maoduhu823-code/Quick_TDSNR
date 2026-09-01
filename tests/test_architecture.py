from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "quick_tdsnr"


def test_domain_and_services_do_not_import_qt():
    forbidden = re.compile(r"(?m)^\s*(?:from|import)\s+(?:PyQt\d*|PySide\d*|qtpy)\b")
    for folder_name in ("domain", "services"):
        for path in (SOURCE_ROOT / folder_name).rglob("*.py"):
            assert forbidden.search(path.read_text(encoding="utf-8")) is None, path


def test_no_module_forces_matplotlib_backend():
    forbidden = re.compile(r"matplotlib\.use\s*\(")
    for path in SOURCE_ROOT.rglob("*.py"):
        assert forbidden.search(path.read_text(encoding="utf-8")) is None, path


def test_expected_layer_directories_exist():
    for folder_name in ("domain", "services", "infra", "ui"):
        assert (SOURCE_ROOT / folder_name / "__init__.py").is_file()

