"""QApplication 创建与主窗口启动。"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from qtpy.QtGui import QFont, QIcon
from qtpy.QtWidgets import QApplication

from quick_tdsnr import __version__
from quick_tdsnr.infra.logging_setup import configure_logging
from quick_tdsnr.infra.resource_path import resource_path
from quick_tdsnr.ui.style import APP_STYLESHEET, configure_matplotlib


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName("Quick_TDSNR")
    app.setApplicationVersion(__version__)
    if sys.platform == "win32":
        app.setFont(QFont("Microsoft YaHei", 10))
    else:
        app.setFont(QFont("WenQuanYi Zen Hei", 10))
    icon = QIcon(str(resource_path("resources/quick_tdsnr.ico")))
    if not icon.isNull():
        app.setWindowIcon(icon)
    app.setStyleSheet(APP_STYLESHEET)
    configure_matplotlib()
    return app


def run_gui(
    argv: Sequence[str] | None = None,
    *,
    project_path: str | Path | None = None,
) -> int:
    configure_logging()
    app = create_application(argv)
    from quick_tdsnr.ui.main_window import QuickTDSNRMainWindow

    window = QuickTDSNRMainWindow(initial_project_path=project_path)
    window.show()
    return app.exec()
