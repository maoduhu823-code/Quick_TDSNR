"""SNR 结果工作台：筛选、排序和弹窗查看目标线曲线。"""

from __future__ import annotations

import math

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from quick_tdsnr.ui.plot_dialog import PlotDialog


class ResultPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._results = ()
        self._plot_dialog: PlotDialog | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("逐结果")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(heading)
        top = QHBoxLayout()
        top.addWidget(QLabel("筛选:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("按线号、VTF 或 main 方法搜索")
        self.filter_edit.textChanged.connect(self._apply_filter)
        top.addWidget(self.filter_edit, stretch=1)
        self.summary_label = QLabel("尚无结果")
        top.addWidget(self.summary_label)
        self.plot_button = QPushButton("查看所选曲线")
        self.plot_button.setEnabled(False)
        self.plot_button.clicked.connect(self._show_selected_plot)
        top.addWidget(self.plot_button)
        layout.addLayout(top)

        table_group = QGroupBox("结果表")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget(0, 12)
        self.table.setObjectName("snrResultTable")
        self.table.setHorizontalHeaderLabels(
            [
                "样本", "case", "Line", "VTF", "main (ps)", "Signal",
                "直通 Noise", "串扰 Noise", "总 Noise", "SNR", "SNR (dB)", "警告",
            ]
        )
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(lambda _item: self._show_selected_plot())
        table_layout.addWidget(self.table)
        layout.addWidget(table_group, stretch=1)

    def set_results(self, results) -> None:
        self._results = tuple(results)
        self._apply_filter()

    def _apply_filter(self, _text: str = "") -> None:
        query = self.filter_edit.text().strip().lower()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for result in self._results:
            haystack = (
                f"{result.sample_id or ''} {result.case_id or ''} {result.line} "
                f"{result.transfer_function} {result.main_method}"
            ).lower()
            if query and query not in haystack:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = (
                (result.sample_id or "")[:8], result.case_id or "", result.line,
                result.transfer_function, f"{result.main_time_ps:.6g}",
                f"{result.signal:.6g}", f"{result.direct_noise:.6g}",
                f"{result.xtalk_noise:.6g}", f"{result.total_noise:.6g}",
                f"{result.snr:.6g}",
                f"{20.0 * math.log10(result.snr):.6g}" if result.snr > 0 else "−∞",
                ";".join(result.warnings),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, result)
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.summary_label.setText(f"显示 {self.table.rowCount()} / {len(self._results)} 条")
        if self.table.rowCount():
            self.table.selectRow(0)
        else:
            self.plot_button.setEnabled(False)

    def _selection_changed(self) -> None:
        self.plot_button.setEnabled(bool(self.table.selectedItems()))

    def _show_selected_plot(self) -> None:
        rows = self.table.selectedItems()
        if not rows:
            return
        result = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if self._plot_dialog is None:
            self._plot_dialog = PlotDialog("SNR 结果曲线", self, figsize=(11.0, 7.0))
        figure = self._plot_dialog.figure
        figure.clear()
        axes = figure.subplots(2, 2)

        axis = axes[0, 0]
        axis.plot(result.time_ps, result.direct_waveform, label="direct")
        for line, waveform in result.aggressor_waveforms.items():
            axis.plot(result.time_ps, waveform, alpha=0.45, label=f"L{line}")
        axis.set_xlabel("时间 (ps)")
        axis.set_ylabel("响应")
        axis.set_title(f"线 {result.line}  {result.transfer_function}")
        axis.legend(fontsize=8, ncol=2)

        axes[0, 1].plot(
            [peak.cursor_delta for peak in result.direct_cursor_peaks],
            [peak.abs_value for peak in result.direct_cursor_peaks],
            marker="o",
        )
        axes[0, 1].set_title("直通游标噪声")
        axes[0, 1].set_xlabel("游标")
        axes[0, 1].set_ylabel("|V|")

        aggressor_lines = [item.line for item in result.aggressors]
        axes[1, 0].bar(aggressor_lines, [item.noise for item in result.aggressors])
        axes[1, 0].set_title("串扰线噪声")
        axes[1, 0].set_xlabel("线号")

        axes[1, 1].bar(
            ["Signal", "Direct", "Xtalk", "Total", "SNR"],
            [
                result.signal, result.direct_noise, result.xtalk_noise,
                result.total_noise, result.snr,
            ],
        )
        axes[1, 1].set_title("关键指标")
        self._plot_dialog.present(
            f"线 {result.line} — {result.transfer_function} SNR 结果"
        )
