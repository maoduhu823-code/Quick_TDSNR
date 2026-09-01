"""频域、时域和 SNR 结果使用的独立 Matplotlib 绘图窗口。"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg,
    NavigationToolbar2QT,
)
from matplotlib.figure import Figure
from qtpy.QtWidgets import QDialog, QVBoxLayout, QWidget


class PlotDialog(QDialog):
    """可缩放、平移和保存图片的非模态绘图对话框。"""

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        *,
        figsize: tuple[float, float] = (10.5, 6.5),
    ) -> None:
        super().__init__(parent)
        self.setObjectName("plotDialog")
        self.setWindowTitle(title)
        self.setModal(False)
        self.resize(1120, 760)
        self.setMinimumSize(720, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.figure = Figure(figsize=figsize, layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

    def present(self, title: str | None = None) -> None:
        if title:
            self.setWindowTitle(title)
        self.canvas.draw_idle()
        self.show()
        self.raise_()
        self.activateWindow()
