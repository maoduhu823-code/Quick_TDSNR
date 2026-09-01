"""独立的第七步 SNR 统计、热力图和逐结果页面。"""

from __future__ import annotations

import math

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from quick_tdsnr.domain.project_models import SampleCatalog
from quick_tdsnr.services.sample_analysis_service import SampleAnalysisService
from quick_tdsnr.services.snr_statistics_service import SNRStatisticsService
from quick_tdsnr.ui.pages.result_page import ResultPage


class HeatmapPanel(QWidget):
    METRICS = (
        ("SNR (dB)", "snr_db"),
        ("线性 SNR", "snr"),
        ("Signal", "signal"),
        ("直通 Noise", "direct_noise"),
        ("串扰 Noise", "xtalk_noise"),
        ("总 Noise", "total_noise"),
    )
    AGGREGATIONS = (
        ("最差", "worst"),
        ("最好", "best"),
        ("平均", "mean"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._catalog: SampleCatalog | None = None
        self._results = ()
        self._dimensions = ()
        self._fixed_combos: dict[str, QComboBox] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        controls = QGroupBox("热力图设置")
        controls_layout = QHBoxLayout(controls)

        controls_layout.addWidget(QLabel("目标输出:"))
        self.target_combo = QComboBox()
        self.target_combo.setObjectName("heatmapTargetCombo")
        self.target_combo.currentIndexChanged.connect(self._redraw)
        controls_layout.addWidget(self.target_combo)

        controls_layout.addWidget(QLabel("指标:"))
        self.metric_combo = QComboBox()
        self.metric_combo.setObjectName("heatmapMetricCombo")
        for label, key in self.METRICS:
            self.metric_combo.addItem(label, key)
        self.metric_combo.currentIndexChanged.connect(self._redraw)
        controls_layout.addWidget(self.metric_combo)

        controls_layout.addWidget(QLabel("聚合:"))
        self.aggregation_combo = QComboBox()
        self.aggregation_combo.setObjectName("heatmapAggregationCombo")
        for label, key in self.AGGREGATIONS:
            self.aggregation_combo.addItem(label, key)
        self.aggregation_combo.currentIndexChanged.connect(self._redraw)
        controls_layout.addWidget(self.aggregation_combo)
        controls_layout.addStretch()
        layout.addWidget(controls)

        self.dimension_group = QGroupBox("二维扫描参数")
        dimension_layout = QHBoxLayout(self.dimension_group)
        self.auto_dimension_label = QLabel("等待样本数据")
        self.auto_dimension_label.setObjectName("heatmapAutoDimensionLabel")
        dimension_layout.addWidget(self.auto_dimension_label)
        self.x_label = QLabel("X轴:")
        self.x_combo = QComboBox()
        self.x_combo.setObjectName("heatmapXAxisCombo")
        self.y_label = QLabel("Y轴:")
        self.y_combo = QComboBox()
        self.y_combo.setObjectName("heatmapYAxisCombo")
        for widget in (self.x_label, self.x_combo, self.y_label, self.y_combo):
            dimension_layout.addWidget(widget)
        dimension_layout.addStretch()
        self.x_combo.currentIndexChanged.connect(self._axes_changed)
        self.y_combo.currentIndexChanged.connect(self._axes_changed)
        layout.addWidget(self.dimension_group)

        self.fixed_group = QGroupBox("其余维度固定值")
        self.fixed_layout = QFormLayout(self.fixed_group)
        self.fixed_group.setVisible(False)
        layout.addWidget(self.fixed_group)

        self.status_label = QLabel("SNR 完成后生成二维热力图")
        self.status_label.setObjectName("heatmapStatusLabel")
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 0)
        self.table.setObjectName("snrHeatmapTable")
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

    def set_data(self, catalog: SampleCatalog | None, results) -> None:
        self._catalog = catalog
        self._results = tuple(results)
        sample_ids = {
            result.sample_id for result in self._results if result.sample_id is not None
        }
        self._dimensions = (
            SNRStatisticsService.scan_dimensions(catalog, sample_ids)
            if catalog is not None
            else ()
        )
        self._populate_targets()
        self._populate_dimensions()
        self._redraw()

    def clear(self) -> None:
        self.set_data(None, ())

    def _populate_targets(self) -> None:
        previous = self.target_combo.currentData()
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        if self._catalog is not None:
            result_ids = {result.sample_id for result in self._results}
            targets = sorted(
                {
                    sample.target_family
                    for sample in self._catalog.available
                    if sample.sample_id in result_ids
                }
            )
            for target in targets:
                self.target_combo.addItem(target, target)
        index = self.target_combo.findData(previous)
        self.target_combo.setCurrentIndex(max(0, index))
        self.target_combo.blockSignals(False)
        self.target_combo.setEnabled(self.target_combo.count() > 1)

    def _populate_dimensions(self) -> None:
        previous_x = self.x_combo.currentData()
        previous_y = self.y_combo.currentData()
        for combo in (self.x_combo, self.y_combo):
            combo.blockSignals(True)
            combo.clear()
            for dimension in self._dimensions:
                combo.addItem(dimension.label, dimension.key)
        x_index = self.x_combo.findData(previous_x)
        y_index = self.y_combo.findData(previous_y)
        self.x_combo.setCurrentIndex(max(0, x_index))
        self.y_combo.setCurrentIndex(
            max(0, y_index) if y_index >= 0 else (1 if len(self._dimensions) > 1 else 0)
        )
        for combo in (self.x_combo, self.y_combo):
            combo.blockSignals(False)

        selectable = len(self._dimensions) > 2
        for widget in (self.x_label, self.x_combo, self.y_label, self.y_combo):
            widget.setVisible(selectable)
        if len(self._dimensions) == 2:
            self.auto_dimension_label.setText(
                f"自动：X={self._dimensions[0].label}；Y={self._dimensions[1].label}"
            )
            self.auto_dimension_label.setVisible(True)
        elif len(self._dimensions) > 2:
            self.auto_dimension_label.setVisible(False)
        else:
            self.auto_dimension_label.setText("至少需要两个有多个取值的扫描参数")
            self.auto_dimension_label.setVisible(True)
        self._rebuild_fixed_filters()

    def _axes_changed(self, *_args) -> None:
        if self.x_combo.currentData() == self.y_combo.currentData() and self.y_combo.count() > 1:
            self.y_combo.blockSignals(True)
            self.y_combo.setCurrentIndex((self.x_combo.currentIndex() + 1) % self.y_combo.count())
            self.y_combo.blockSignals(False)
        self._rebuild_fixed_filters()
        self._redraw()

    def _rebuild_fixed_filters(self) -> None:
        while self.fixed_layout.rowCount():
            self.fixed_layout.removeRow(0)
        self._fixed_combos = {}
        selected = {self.x_combo.currentData(), self.y_combo.currentData()}
        fixed_dimensions = [
            dimension for dimension in self._dimensions if dimension.key not in selected
        ]
        for dimension in fixed_dimensions:
            combo = QComboBox()
            combo.setObjectName(f"heatmapFixed_{dimension.key.replace(':', '_')}")
            for value in dimension.values:
                combo.addItem(f"{value:g}", value)
            combo.currentIndexChanged.connect(self._redraw)
            self.fixed_layout.addRow(dimension.label, combo)
            self._fixed_combos[dimension.key] = combo
        self.fixed_group.setVisible(bool(fixed_dimensions))

    def _dimension(self, key: str | None):
        return next((dimension for dimension in self._dimensions if dimension.key == key), None)

    def _redraw(self, *_args) -> None:
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        if self._catalog is None or not self._results:
            self.status_label.setText("尚无 SNR 结果")
            return
        if len(self._dimensions) < 2:
            self.status_label.setText("扫描参数中不足两个变化维度，无法生成二维热力图")
            return
        x_dimension = self._dimension(self.x_combo.currentData()) or self._dimensions[0]
        y_dimension = self._dimension(self.y_combo.currentData()) or self._dimensions[1]
        fixed_values = {
            key: float(combo.currentData()) for key, combo in self._fixed_combos.items()
        }
        data = SNRStatisticsService.heatmap(
            self._catalog,
            self._results,
            x_dimension=x_dimension,
            y_dimension=y_dimension,
            metric=str(self.metric_combo.currentData()),
            aggregation=str(self.aggregation_combo.currentData()),
            target_family=self.target_combo.currentData(),
            fixed_values=fixed_values,
        )
        x_values = x_dimension.values
        y_values = y_dimension.values
        self.table.setColumnCount(len(x_values))
        self.table.setRowCount(len(y_values))
        self.table.setHorizontalHeaderLabels([f"{value:g}" for value in x_values])
        self.table.setVerticalHeaderLabels([f"{value:g}" for value in y_values])
        cells = {(cell.x, cell.y): cell for cell in data.cells}
        finite_values = [cell.value for cell in data.cells if math.isfinite(cell.value)]
        minimum = min(finite_values, default=0.0)
        maximum = max(finite_values, default=0.0)
        metric_label = self.metric_combo.currentText()
        aggregation_label = self.aggregation_combo.currentText()
        for row, y_value in enumerate(y_values):
            for column, x_value in enumerate(x_values):
                cell = cells.get((x_value, y_value))
                if cell is None:
                    item = QTableWidgetItem("—")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(row, column, item)
                    continue
                item = QTableWidgetItem(self._format_value(cell.value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(Qt.ItemDataRole.UserRole, cell)
                item.setToolTip(
                    f"{aggregation_label}{metric_label}: {self._format_value(cell.value)}\n"
                    f"结果数: {cell.count}\ncase: {', '.join(cell.case_ids)}"
                    + (
                        f"\n对应 Victim: Line {cell.representative_line}"
                        if cell.representative_line is not None
                        else ""
                    )
                )
                if math.isfinite(cell.value):
                    ratio = 0.5 if maximum == minimum else (
                        (cell.value - minimum) / (maximum - minimum)
                    )
                    item.setBackground(self._heat_color(ratio))
                self.table.setItem(row, column, item)
        self.dimension_group.setTitle(
            f"二维扫描参数 — X: {x_dimension.label}；Y: {y_dimension.label}"
        )
        self.status_label.setText(
            f"{aggregation_label}{metric_label}；格点范围 "
            f"{self._format_value(minimum)} – {self._format_value(maximum)}；"
            f"共 {len(data.cells)} 个有效格点"
        )

    @staticmethod
    def _format_value(value: float) -> str:
        if not math.isfinite(value):
            return "∞" if value > 0 else "−∞"
        return f"{value:.6g}"

    @staticmethod
    def _heat_color(ratio: float) -> QColor:
        ratio = min(1.0, max(0.0, float(ratio)))
        low = (235, 243, 251)
        high = (76, 136, 199)
        return QColor(
            *[
                round(start + (end - start) * ratio)
                for start, end in zip(low, high, strict=True)
            ]
        )

    def _selection_changed(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        cell = items[0].data(Qt.ItemDataRole.UserRole)
        if cell is None:
            return
        detail = f"case={', '.join(cell.case_ids)}；结果 {cell.count} 条"
        if cell.representative_line is not None:
            detail += f"；对应 Victim=Line {cell.representative_line}"
        self.status_label.setText(detail)


class StatisticsPanel(QWidget):
    METRIC_LABELS = {
        "signal": "Signal",
        "direct_noise": "直通 Noise",
        "xtalk_noise": "串扰 Noise",
        "total_noise": "总 Noise",
        "snr": "线性 SNR",
        "snr_db": "SNR (dB)",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.detail_tabs = QTabWidget()
        self.detail_tabs.setObjectName("statisticsDetailTabs")
        self.heatmap_panel = HeatmapPanel()
        self.detail_tabs.addTab(self.heatmap_panel, "热力图")
        self.summary_table = QTableWidget(0, 9)
        self.summary_table.setHorizontalHeaderLabels(
            ["指标", "数量", "平均", "标准差", "最小", "P5", "P50", "P95", "最大"]
        )
        self.summary_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.detail_tabs.addTab(self.summary_table, "汇总指标")
        self.aggressor_table = QTableWidget(0, 8)
        self.aggressor_table.setHorizontalHeaderLabels(
            ["Victim", "Aggressor", "数量", "平均Noise", "最小", "P50", "P95", "最大"]
        )
        self.aggressor_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.detail_tabs.addTab(self.aggressor_table, "逐串扰")
        self.result_page = ResultPage()
        self.detail_tabs.addTab(self.result_page, "逐结果")
        layout.addWidget(self.detail_tabs, stretch=1)

    def set_data(self, catalog: SampleCatalog | None, results) -> None:
        results = tuple(results)
        self.heatmap_panel.set_data(catalog, results)
        self.result_page.set_results(results)
        summary = SampleAnalysisService.aggregate_statistics(results)
        self.summary_table.setRowCount(len(summary))
        for row, (metric, values) in enumerate(summary.items()):
            cells = (
                self.METRIC_LABELS.get(metric, metric), int(values["count"]),
                values["mean"], values["std"], values["min"], values["p5"],
                values["p50"], values["p95"], values["max"],
            )
            for column, value in enumerate(cells):
                text = str(value) if column < 2 else f"{float(value):.6g}"
                self.summary_table.setItem(row, column, QTableWidgetItem(text))
        self.summary_table.resizeColumnsToContents()
        aggressors = SampleAnalysisService.aggregate_aggressors(results)
        self.aggressor_table.setRowCount(len(aggressors))
        for row, ((victim, aggressor), values) in enumerate(aggressors.items()):
            cells = (
                victim, aggressor, int(values["count"]), values["mean"],
                values["min"], values["p50"], values["p95"], values["max"],
            )
            for column, value in enumerate(cells):
                text = str(value) if column < 3 else f"{float(value):.6g}"
                self.aggressor_table.setItem(row, column, QTableWidgetItem(text))
        self.aggressor_table.resizeColumnsToContents()


class SNRStatisticsPage(QWidget):
    snr_requested = Signal(object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._catalog: SampleCatalog | None = None
        self._results = ()
        self._checked_sample_ids: set[str] = set()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        titlebar = QHBoxLayout()
        heading = QLabel("SNR 统计")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        titlebar.addWidget(heading)
        titlebar.addStretch()
        self.summary_label = QLabel("尚无 SNR 结果")
        self.summary_label.setObjectName("snrStatisticsSummaryLabel")
        titlebar.addWidget(self.summary_label)
        layout.addLayout(titlebar)

        controls = QGroupBox("统计运行与范围")
        controls_layout = QHBoxLayout(controls)
        self.run_button = QPushButton("运行时域 SNR")
        self.run_button.setObjectName("runSNRButton")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self._emit_snr)
        controls_layout.addWidget(self.run_button)
        controls_layout.addWidget(QLabel("统计范围:"))
        self.scope_combo = QComboBox()
        self.scope_combo.setObjectName("snrStatisticsScopeCombo")
        self.scope_combo.addItem("全部样本", "all")
        self.scope_combo.addItem("第六步已勾选样本", "checked")
        self.scope_combo.currentIndexChanged.connect(self._refresh)
        controls_layout.addWidget(self.scope_combo)
        self.scope_label = QLabel("尚无样本")
        self.scope_label.setObjectName("snrStatisticsScopeLabel")
        controls_layout.addWidget(self.scope_label)
        controls_layout.addStretch()
        layout.addWidget(controls)

        self.statistics_panel = StatisticsPanel()
        layout.addWidget(self.statistics_panel, stretch=1)

    def set_catalog(self, catalog: SampleCatalog) -> None:
        self._catalog = catalog
        available_ids = {sample.sample_id for sample in catalog.available}
        self._checked_sample_ids.intersection_update(available_ids)
        self._refresh()

    def set_checked_sample_ids(self, sample_ids) -> None:
        self._checked_sample_ids = set(sample_ids)
        self._refresh()

    def set_snr_ready(self, run, settings) -> None:
        self._renormalization_run = run
        self._snr_settings = settings
        self.run_button.setEnabled(True)
        self.summary_label.setText("样本已就绪，可运行 SNR")

    def set_snr_running(self, running: bool) -> None:
        self.run_button.setEnabled(
            not running and hasattr(self, "_renormalization_run")
        )
        if running:
            self.summary_label.setText("正在运行时域 SNR…")

    def set_progress(self, done: int, total: int, case_id: str) -> None:
        self.summary_label.setText(f"SNR {done}/{total}：{case_id}")

    def set_results(self, results) -> None:
        self._results = tuple(results)
        self._refresh()

    def set_error(self, message: str) -> None:
        self.summary_label.setText(message)

    def reset(self) -> None:
        self._catalog = None
        self._results = ()
        self._checked_sample_ids.clear()
        for name in ("_renormalization_run", "_snr_settings"):
            if hasattr(self, name):
                delattr(self, name)
        self.run_button.setEnabled(False)
        self.scope_combo.setCurrentIndex(0)
        self.scope_label.setText("尚无样本")
        self.summary_label.setText("尚无 SNR 结果")
        self.statistics_panel.set_data(None, ())

    def _filtered_results(self):
        if self.scope_combo.currentData() == "checked":
            return tuple(
                result
                for result in self._results
                if result.sample_id in self._checked_sample_ids
            )
        return self._results

    def _refresh(self, *_args) -> None:
        filtered = self._filtered_results()
        total_samples = len(self._catalog.available) if self._catalog else 0
        if self.scope_combo.currentData() == "checked":
            scope_count = len(self._checked_sample_ids)
            self.scope_label.setText(f"已勾选 {scope_count} / {total_samples} 个样本")
        else:
            self.scope_label.setText(f"全部 {total_samples} 个样本")
        self.statistics_panel.set_data(self._catalog, filtered)
        if self._results:
            self.summary_label.setText(
                f"显示 {len(filtered)} / {len(self._results)} 条 SNR 结果"
            )

    def _emit_snr(self) -> None:
        if hasattr(self, "_renormalization_run") and hasattr(self, "_snr_settings"):
            self.snr_requested.emit(self._renormalization_run, self._snr_settings)
