"""多判据拓扑结果、热力图和 Port_family 建议页。"""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sipi_sparam_core.topology import TopologyReport

from quick_tdsnr.domain.project_models import (
    MetricEvaluation,
    TopologyAnalysis,
    TopologyDraft,
    TopologyMetricDraft,
)


class TopologyPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("topologyPage")
        self._analysis: TopologyAnalysis | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        heading = QLabel("拓扑识别")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        self.status_label = QLabel("尚未执行拓扑识别")
        self.status_label.setObjectName("topologyStatusLabel")
        self.metric_combo = QComboBox()
        self.metric_combo.setObjectName("topologyMetricCombo")
        self.metric_combo.currentTextChanged.connect(self._render_selected_metric)
        top.addWidget(heading)
        top.addStretch()
        top.addWidget(QLabel("查看判据:"))
        top.addWidget(self.metric_combo)
        layout.addLayout(top)
        layout.addWidget(self.status_label)

        upper = QHBoxLayout()
        evaluation_group = QGroupBox("S/Y/Z 判据比较")
        evaluation_layout = QVBoxLayout(evaluation_group)
        self.evaluation_table = QTableWidget(0, 6)
        self.evaluation_table.setObjectName("topologyEvaluationTable")
        self.evaluation_table.setHorizontalHeaderLabels(
            ["判据", "评分", "可信", "跨文件一致", "联通簇", "孤立端口"]
        )
        self.evaluation_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        evaluation_layout.addWidget(self.evaluation_table)
        upper.addWidget(evaluation_group, stretch=3)

        warnings_group = QGroupBox("确认事项")
        warnings_layout = QVBoxLayout(warnings_group)
        self.warning_text = QTextEdit()
        self.warning_text.setObjectName("topologyWarnings")
        self.warning_text.setReadOnly(True)
        warnings_layout.addWidget(self.warning_text)
        upper.addWidget(warnings_group, stretch=2)
        layout.addLayout(upper, stretch=2)

        lower = QHBoxLayout()
        mapping_group = QGroupBox("Port_family 建议映射")
        mapping_layout = QVBoxLayout(mapping_group)
        self.mapping_table = QTableWidget()
        self.mapping_table.setObjectName("mappingProposalTable")
        self.mapping_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        mapping_layout.addWidget(self.mapping_table)
        self.source_notice = QLabel("family1/source 尚未确认")
        self.source_notice.setStyleSheet("color: #b45f06; font-weight: 600;")
        mapping_layout.addWidget(self.source_notice)
        lower.addWidget(mapping_group, stretch=2)

        heatmap_group = QGroupBox("参数矩阵热力图")
        heatmap_layout = QVBoxLayout(heatmap_group)
        self.figure = Figure(figsize=(7.2, 4.2), layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setObjectName("topologyHeatmapCanvas")
        heatmap_layout.addWidget(self.canvas)
        lower.addWidget(heatmap_group, stretch=3)
        layout.addLayout(lower, stretch=3)

    def set_running(self) -> None:
        self.status_label.setText("正在预检文件并比较 S/Y/Z 拓扑…")
        self.status_label.setStyleSheet("color: #3f6f9f;")

    def clear(self) -> None:
        self._analysis = None
        self.status_label.setText("尚未执行拓扑识别")
        self.status_label.setStyleSheet("")
        self.evaluation_table.setRowCount(0)
        self.warning_text.clear()
        self.metric_combo.clear()
        self.mapping_table.setRowCount(0)
        self.mapping_table.setColumnCount(0)
        self.source_notice.setText("family1/source 尚未确认")
        self.figure.clear()
        self.canvas.draw_idle()

    def set_analysis(self, analysis: TopologyAnalysis) -> None:
        self._analysis = analysis
        recommended = analysis.recommended_metric or "无"
        color = {"高": "#268447", "中": "#b45f06", "低": "#b23b3b"}[analysis.confidence]
        self.status_label.setText(
            f"推荐判据：{recommended}；置信度：{analysis.confidence}；"
            f"实际频点：{analysis.actual_frequency_ghz:.6g} GHz"
        )
        self.status_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.status_label.setProperty("confidence", analysis.confidence)
        self.status_label.setToolTip(
            {"高": "S/Y/Z 中至少两种判据得到相同可信拓扑。",
             "中": "只有一种可信判据，必须人工确认。",
             "低": "未形成可信拓扑，不能自动接受映射。"}[analysis.confidence]
        )
        self._render_evaluations()
        self.warning_text.setPlainText("\n".join(analysis.warnings) or "无待确认告警")
        self.metric_combo.blockSignals(True)
        self.metric_combo.clear()
        for metric in ("S", "Y", "Z"):
            label = f"{metric}（推荐）" if metric == analysis.recommended_metric else metric
            self.metric_combo.addItem(label, metric)
        recommended_index = max(0, ("S", "Y", "Z").index(analysis.recommended_metric)) if analysis.recommended_metric else 0
        self.metric_combo.setCurrentIndex(recommended_index)
        self.metric_combo.blockSignals(False)
        self._render_selected_metric()

    def draft(self) -> TopologyDraft | None:
        if self._analysis is None:
            return None
        metrics = []
        for metric in ("S", "Y", "Z"):
            evaluation = self._analysis.evaluations[metric]
            report = self._analysis.reports[metric][0]
            matrix = np.asarray(
                self._analysis.matrix_snapshots[metric], dtype=float
            )
            metrics.append(
                TopologyMetricDraft(
                    metric=metric,
                    score=evaluation.score,
                    plausible=evaluation.plausible,
                    file_consistent=evaluation.file_consistent,
                    signature=evaluation.signature,
                    reasons=evaluation.reasons,
                    channel_count=len(report.channels),
                    isolated_ports=tuple(report.isolated_ports),
                    proposal=self._analysis.proposals.get(metric),
                    matrix=tuple(tuple(float(value) for value in row) for row in matrix),
                )
            )
        return TopologyDraft(
            metrics=tuple(metrics),
            recommended_metric=self._analysis.recommended_metric,
            confidence=self._analysis.confidence,
            warnings=self._analysis.warnings,
            actual_frequency_ghz=self._analysis.actual_frequency_ghz,
        )

    def load_draft(self, draft: TopologyDraft) -> TopologyAnalysis:
        reports = {}
        evaluations = {}
        proposals = {}
        matrices = {}
        for item in draft.metrics:
            nports = len(item.matrix)
            reports[item.metric] = (
                TopologyReport(
                    n_ports=nports,
                    band_ghz=(draft.actual_frequency_ghz, draft.actual_frequency_ghz),
                    low_freq_ghz=draft.actual_frequency_ghz,
                    y_threshold_siemens=0.0,
                    s_threshold_db=0.0,
                    channels=[object() for _ in range(item.channel_count)],
                    isolated_ports=list(item.isolated_ports),
                    metric=item.metric,
                ),
            )
            evaluations[item.metric] = MetricEvaluation(
                metric=item.metric,
                score=item.score,
                plausible=item.plausible,
                file_consistent=item.file_consistent,
                signature=item.signature,
                reasons=item.reasons,
            )
            proposals[item.metric] = item.proposal
            matrices[item.metric] = np.asarray(item.matrix, dtype=float)
        analysis = TopologyAnalysis(
            reports=reports,
            evaluations=evaluations,
            proposals=proposals,
            recommended_metric=draft.recommended_metric,
            confidence=draft.confidence,
            warnings=draft.warnings,
            actual_frequency_ghz=draft.actual_frequency_ghz,
            matrix_snapshots=matrices,
        )
        self.set_analysis(analysis)
        return analysis

    def _render_evaluations(self) -> None:
        assert self._analysis is not None
        self.evaluation_table.setRowCount(3)
        for row, metric in enumerate(("S", "Y", "Z")):
            evaluation = self._analysis.evaluations[metric]
            report = self._analysis.reports[metric][0]
            values = (
                metric,
                f"{evaluation.score:.0f}",
                "是" if evaluation.plausible else "否",
                "是" if evaluation.file_consistent else "否",
                str(len(report.channels)),
                ", ".join(map(str, report.isolated_ports)) or "无",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.evaluation_table.setItem(row, column, item)
        self.evaluation_table.resizeColumnsToContents()

    def _selected_metric(self) -> str:
        return str(self.metric_combo.currentData() or "S")

    def _render_selected_metric(self, _text: str = "") -> None:
        self._render_mapping()
        self._render_heatmap()

    def _render_mapping(self, _text: str = "") -> None:
        if self._analysis is None:
            return
        proposal = self._analysis.proposals.get(self._selected_metric())
        if proposal is None:
            self.mapping_table.clear()
            self.mapping_table.setRowCount(0)
            self.mapping_table.setColumnCount(0)
            self.source_notice.setText("该判据无法形成完整的矩形 Port_family 映射")
            return
        self.mapping_table.setRowCount(proposal.line_count)
        self.mapping_table.setColumnCount(proposal.family_count)
        self.mapping_table.setHorizontalHeaderLabels(
            [f"family{index}" for index in range(1, proposal.family_count + 1)]
        )
        self.mapping_table.setVerticalHeaderLabels(
            [f"Line {index}" for index in range(1, proposal.line_count + 1)]
        )
        for row, ports in enumerate(proposal.rows):
            for column, port in enumerate(ports):
                item = QTableWidgetItem(f"P{port}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.mapping_table.setItem(row, column, item)
        self.mapping_table.resizeColumnsToContents()
        self.source_notice.setText(
            "family1/source 尚未确认：拓扑 hub 不等于真实 driver，请在下一步确认。"
        )

    def _render_heatmap(self) -> None:
        assert self._analysis is not None
        self.figure.clear()
        metric = self._selected_metric()
        axis = self.figure.add_subplot(1, 1, 1)
        values = np.asarray(self._analysis.matrix_snapshots[metric], dtype=float)
        display = np.log10(np.maximum(values, 1e-20))
        lower_triangle = np.ma.array(
            display,
            mask=np.triu(np.ones_like(display, dtype=bool)),
        )
        image = axis.imshow(lower_triangle, cmap="viridis", origin="upper")
        axis.set_title(f"log10 |{metric}|  @ {self._analysis.actual_frequency_ghz:.6g} GHz")
        axis.set_xlabel("Port")
        axis.set_ylabel("Port")
        nports = values.shape[0]
        step = max(1, int(np.ceil(nports / 8)))
        ticks = np.arange(0, nports, step, dtype=int)
        if ticks[-1] != nports - 1:
            ticks = np.append(ticks, nports - 1)
        labels = [str(int(position) + 1) for position in ticks]
        axis.set_xticks(ticks, labels)
        axis.set_yticks(ticks, labels)
        self.figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
        self.canvas.draw_idle()
