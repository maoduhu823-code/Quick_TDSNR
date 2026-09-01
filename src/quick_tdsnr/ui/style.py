"""与 Quick_Sparam 一致的集中视觉样式。"""

from __future__ import annotations

import sys


APP_STYLESHEET = """
QWidget {
    font-size: 13px;
}
QGroupBox {
    font-weight: 600;
    border: 1px solid #cfd1d6;
    border-radius: 4px;
    margin-top: 9px;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 9px;
    padding: 0 4px;
}
QPushButton {
    font-size: 14px;
    padding: 7px 8px;
    border: 1px solid #c5c7cc;
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #f6f7fa, stop:1 #dadbde);
    min-width: 80px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #e7e8eb, stop:1 #cbcccf);
}
QPushButton:disabled {
    color: #8e9096;
    background: #ececef;
}
QListWidget, QListView, QTableWidget, QTextEdit {
    border: 1px solid #cccccc;
    border-radius: 3px;
    background: #ffffff;
}
QListWidget::item {
    padding: 6px;
}
QListWidget::item:selected {
    color: #202124;
    background: #dce8f7;
}
QListView::item {
    padding: 6px;
}
QListView::item:selected {
    color: #202124;
    background: #dce8f7;
}
QSplitter::handle:horizontal {
    background: #d4d6db;
    border-left: 1px solid #c2c4c9;
    border-right: 1px solid #c2c4c9;
}
QSplitter::handle:horizontal:hover {
    background: #b9bcc3;
}
QSplitter::handle:vertical {
    background: #d4d6db;
    border-top: 1px solid #c2c4c9;
    border-bottom: 1px solid #c2c4c9;
}
QSplitter::handle:vertical:hover {
    background: #b9bcc3;
}
QProgressBar {
    border: 1px solid #c5c7cc;
    border-radius: 3px;
    text-align: center;
}
QProgressBar::chunk {
    background: #7aa6d8;
}
"""


def configure_matplotlib() -> None:
    """设置中文字体和负号，不强制 matplotlib 后端。"""
    import matplotlib

    matplotlib.rcParams["axes.unicode_minus"] = False
    matplotlib.rcParams["mathtext.fontset"] = "stix"
    if sys.platform == "win32":
        matplotlib.rcParams["font.sans-serif"] = ["SimHei"]
    else:
        matplotlib.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei"]
