"""重归一化参数轴、目标 family 和 case 预览页。"""

from __future__ import annotations

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from quick_tdsnr.domain.project_models import (
    ConfirmedMapping,
    ProjectConfig,
    ProjectInput,
    SweepFamilyDraft,
)
from quick_tdsnr.services.sweep_planning_service import (
    SweepPlanningService,
    parse_cio_pf,
    parse_positive_candidates,
)


class SweepPage(QWidget):
    plan_confirmed = Signal(object, object)
    LARGE_PLAN_THRESHOLD = 1000

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mapping: ConfirmedMapping | None = None
        self._inputs: tuple[ProjectInput, ...] = ()
        self._metric = "S"
        self._frequency_ghz = 0.1
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("参数扫描")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(heading)
        layout.addWidget(QLabel("为每个 family 输入 R 候选轴和 Cio，并选择要生成 1驱1 结果的目标 family。"))

        group = QGroupBox("扫描轴")
        group_layout = QVBoxLayout(group)
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("sweepParameterTable")
        self.table.setHorizontalHeaderLabels(
            ["Port_family", "R 候选 (Ω)", "Cio (pF)", "作为目标"]
        )
        group_layout.addWidget(self.table)
        layout.addWidget(group, stretch=1)

        summary = QHBoxLayout()
        self.preview_label = QLabel("请先确认 Port_family 映射")
        self.preview_label.setObjectName("sweepPreviewLabel")
        self.build_button = QPushButton("确认扫描计划")
        self.build_button.setObjectName("buildSweepPlanButton")
        self.build_button.setEnabled(False)
        self.build_button.clicked.connect(self._confirm_plan)
        self.build_button.setVisible(False)
        summary.addWidget(self.preview_label)
        summary.addStretch()
        summary.addWidget(self.build_button)
        layout.addLayout(summary)

    def set_context(self, mapping, batch, analysis) -> None:
        inputs = tuple(ProjectInput(str(item.path), item.sha256) for item in batch.files)
        self.set_mapping(
            mapping,
            inputs=inputs,
            metric=analysis.recommended_metric or "S",
            frequency_ghz=analysis.actual_frequency_ghz,
        )

    def set_mapping(
        self,
        mapping: ConfirmedMapping,
        *,
        inputs: tuple[ProjectInput, ...],
        metric: str,
        frequency_ghz: float,
    ) -> None:
        self._mapping = mapping
        self._inputs = inputs
        self._metric = metric
        self._frequency_ghz = frequency_ghz
        self.table.setRowCount(len(mapping.family_ids))
        for row, family_id in enumerate(mapping.family_ids):
            family_item = QTableWidgetItem(family_id)
            family_item.setFlags(family_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, family_item)
            resistance = QLineEdit("50")
            resistance.setObjectName(f"resistance_{family_id}")
            cio = QLineEdit("0")
            cio.setObjectName(f"cio_{family_id}")
            target = QCheckBox()
            target.setObjectName(f"target_{family_id}")
            target.setChecked(family_id != mapping.source_family)
            target.setEnabled(family_id != mapping.source_family)
            resistance.textChanged.connect(self._refresh_preview)
            cio.textChanged.connect(self._refresh_preview)
            target.toggled.connect(self._refresh_preview)
            self.table.setCellWidget(row, 1, resistance)
            self.table.setCellWidget(row, 2, cio)
            self.table.setCellWidget(row, 3, target)
        self.table.resizeColumnsToContents()
        self._refresh_preview()

    def load_config(self, config: ProjectConfig) -> None:
        self.set_mapping(
            config.mapping,
            inputs=config.inputs,
            metric=config.topology_metric,
            frequency_ghz=config.topology_frequency_ghz,
        )
        for row, family_id in enumerate(config.mapping.family_ids):
            resistance = self.table.cellWidget(row, 1)
            cio = self.table.cellWidget(row, 2)
            target = self.table.cellWidget(row, 3)
            resistance.setText(", ".join(f"{value:g}" for value in config.resistance_candidates[family_id]))
            cio.setText(f"{config.cio_pf[family_id]:g}")
            target.setChecked(family_id in config.target_families)
        self._refresh_preview()

    def drafts(self) -> tuple[SweepFamilyDraft, ...]:
        if self._mapping is None:
            return ()
        return tuple(
            SweepFamilyDraft(
                family_id=family_id,
                resistance_text=self.table.cellWidget(row, 1).text(),
                cio_text=self.table.cellWidget(row, 2).text(),
                target=self.table.cellWidget(row, 3).isChecked(),
            )
            for row, family_id in enumerate(self._mapping.family_ids)
        )

    def load_drafts(
        self,
        mapping: ConfirmedMapping,
        *,
        inputs: tuple[ProjectInput, ...],
        metric: str,
        frequency_ghz: float,
        drafts: tuple[SweepFamilyDraft, ...],
    ) -> None:
        self.set_mapping(
            mapping,
            inputs=inputs,
            metric=metric,
            frequency_ghz=frequency_ghz,
        )
        by_family = {item.family_id: item for item in drafts}
        for row, family_id in enumerate(mapping.family_ids):
            draft = by_family.get(family_id)
            if draft is None:
                continue
            self.table.cellWidget(row, 1).setText(draft.resistance_text)
            self.table.cellWidget(row, 2).setText(draft.cio_text)
            self.table.cellWidget(row, 3).setChecked(draft.target)
        self._refresh_preview()

    def current_config(self) -> ProjectConfig:
        if self._mapping is None:
            raise ValueError("请先确认 Port_family 映射")
        resistance: dict[str, tuple[float, ...]] = {}
        cio_pf: dict[str, float] = {}
        targets: list[str] = []
        for row, family_id in enumerate(self._mapping.family_ids):
            resistance[family_id] = parse_positive_candidates(
                self.table.cellWidget(row, 1).text()
            )
            cio_pf[family_id] = parse_cio_pf(self.table.cellWidget(row, 2).text())
            if self.table.cellWidget(row, 3).isChecked():
                targets.append(family_id)
        return ProjectConfig(
            inputs=self._inputs,
            mapping=self._mapping,
            target_families=tuple(targets),
            resistance_candidates=resistance,
            cio_pf=cio_pf,
            topology_metric=self._metric,
            topology_frequency_ghz=self._frequency_ghz,
        )

    def current_plan(self):
        config = self.current_config()
        return config, SweepPlanningService().build_plan(config)

    def _refresh_preview(self, *_args) -> None:
        try:
            _config, plan = self.current_plan()
            text = (
                f"{plan.case_count} cases × {plan.input_count} 输入 = "
                f"预计 {plan.estimated_output_files} 个输出"
            )
            if plan.estimated_output_files > self.LARGE_PLAN_THRESHOLD:
                text += "（大批量，执行前需再次确认）"
            self.preview_label.setText(text)
            self.preview_label.setStyleSheet("color: #268447;")
            self.build_button.setEnabled(True)
        except ValueError as exc:
            self.preview_label.setText(str(exc))
            self.preview_label.setStyleSheet("color: #b45f06;")
            self.build_button.setEnabled(False)

    def _confirm_plan(self) -> None:
        config, plan = self.current_plan()
        if plan.estimated_output_files > self.LARGE_PLAN_THRESHOLD:
            answer = QMessageBox.question(
                self,
                "确认大批量计划",
                f"预计生成 {plan.estimated_output_files} 个输出，是否继续？",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.plan_confirmed.emit(config, plan)
