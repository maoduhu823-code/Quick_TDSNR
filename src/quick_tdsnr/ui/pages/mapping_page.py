"""Port_family 映射编辑、source 确认和校验页。"""

from __future__ import annotations

from qtpy.QtCore import Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from quick_tdsnr.domain.project_models import (
    ConfirmedMapping,
    FamilyMappingProposal,
    MappingDraft,
)
from quick_tdsnr.services.sweep_planning_service import validate_mapping
from quick_tdsnr.ui.widgets.mapping_table import MappingTable


_PROBLEM_COLOR = QColor("#ffe3b3")
_NORMAL_COLOR = QColor("#ffffff")


class MappingPage(QWidget):
    mapping_confirmed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._nports = 0
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Port_family 确认")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        description = QLabel(
            "拓扑只能给出同一物理线的端口簇，不能从互易 S 参数确定真实 driver。"
            "请检查映射，并明确选择 source family。"
        )
        description.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(description)

        group = QGroupBox("可编辑映射（拖放单元格可交换端口）")
        group_layout = QVBoxLayout(group)
        self.table = MappingTable()
        self.table.setObjectName("confirmedMappingTable")
        self.table.mapping_changed.connect(self._validate_display)
        group_layout.addWidget(self.table)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("source family:"))
        self.source_combo = QComboBox()
        self.source_combo.setObjectName("sourceFamilyCombo")
        self.source_combo.currentIndexChanged.connect(self._validate_display)
        controls.addWidget(self.source_combo)
        self.undo_button = QPushButton("撤销")
        self.redo_button = QPushButton("恢复")
        self.undo_button.clicked.connect(self.table.undo_stack.undo)
        self.redo_button.clicked.connect(self.table.undo_stack.redo)
        self.table.undo_stack.canUndoChanged.connect(self.undo_button.setEnabled)
        self.table.undo_stack.canRedoChanged.connect(self.redo_button.setEnabled)
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(False)
        controls.addWidget(self.undo_button)
        controls.addWidget(self.redo_button)
        controls.addStretch()
        group_layout.addLayout(controls)
        layout.addWidget(group, stretch=1)

        footer = QHBoxLayout()
        self.stats_label = QLabel("尚未加载拓扑建议")
        self.stats_label.setObjectName("mappingStatsLabel")
        self.confirm_button = QPushButton("确认映射并进入参数扫描")
        self.confirm_button.setObjectName("confirmMappingButton")
        self.confirm_button.setEnabled(False)
        self.confirm_button.clicked.connect(self._emit_confirmation)
        self.confirm_button.setVisible(False)
        footer.addWidget(self.stats_label)
        footer.addStretch()
        footer.addWidget(self.confirm_button)
        layout.addLayout(footer)

    def set_proposal(self, proposal: FamilyMappingProposal) -> None:
        families = tuple(f"family{index}" for index in range(1, proposal.family_count + 1))
        mapping = ConfirmedMapping(proposal.rows, families, "")
        self.load_mapping(mapping, require_source=True)

    def load_mapping(self, mapping: ConfirmedMapping, *, require_source: bool = False) -> None:
        draft = MappingDraft(
            rows=tuple(tuple(str(port) for port in row) for row in mapping.rows),
            family_ids=mapping.family_ids,
            source_family="" if require_source else mapping.source_family,
            nports=mapping.nports,
        )
        self.load_draft(draft)

    def load_draft(self, draft: MappingDraft) -> None:
        self._nports = draft.nports
        self.table.blockSignals(True)
        self.table.setRowCount(len(draft.rows))
        self.table.setColumnCount(len(draft.family_ids))
        self.table.setHorizontalHeaderLabels(list(draft.family_ids))
        self.table.setVerticalHeaderLabels(
            [f"Line {index}" for index in range(1, len(draft.rows) + 1)]
        )
        for row, ports in enumerate(draft.rows):
            for column, port in enumerate(ports):
                self.table.setItem(row, column, QTableWidgetItem(str(port)))
        self.table.blockSignals(False)
        self.table.undo_stack.clear()
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        self.source_combo.addItem("请选择…", None)
        for family_id in draft.family_ids:
            self.source_combo.addItem(family_id, family_id)
        if draft.source_family in draft.family_ids:
            self.source_combo.setCurrentIndex(
                draft.family_ids.index(draft.source_family) + 1
            )
        self.source_combo.blockSignals(False)
        self._validate_display()

    def draft(self) -> MappingDraft | None:
        if not self.table.rowCount() or not self.table.columnCount():
            return None
        rows = tuple(
            tuple(
                self.table.item(row, column).text()
                if self.table.item(row, column)
                else ""
                for column in range(self.table.columnCount())
            )
            for row in range(self.table.rowCount())
        )
        return MappingDraft(
            rows=rows,
            family_ids=self._family_ids(),
            source_family=str(self.source_combo.currentData() or ""),
            nports=self._nports,
        )

    def _family_ids(self) -> tuple[str, ...]:
        return tuple(
            self.table.horizontalHeaderItem(column).text()
            for column in range(self.table.columnCount())
        )

    def confirmed_mapping(self) -> ConfirmedMapping:
        rows: list[tuple[int, ...]] = []
        for row in range(self.table.rowCount()):
            values: list[int] = []
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                text = item.text().strip() if item else ""
                if not text:
                    raise ValueError("映射存在空单元格")
                try:
                    values.append(int(text.removeprefix("P").removeprefix("p")))
                except ValueError as exc:
                    raise ValueError(f"端口必须是整数：{text}") from exc
            rows.append(tuple(values))
        source = self.source_combo.currentData()
        mapping = ConfirmedMapping(tuple(rows), self._family_ids(), str(source or ""))
        validate_mapping(mapping, self._nports)
        return mapping

    def is_valid(self) -> bool:
        try:
            self.confirmed_mapping()
        except ValueError:
            return False
        return True

    def _validate_display(self, *_args) -> None:
        texts: list[tuple[QTableWidgetItem, int | None]] = []
        values: list[int] = []
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item is None:
                    item = QTableWidgetItem("")
                    self.table.setItem(row, column, item)
                try:
                    value = int(item.text().strip().removeprefix("P").removeprefix("p"))
                except ValueError:
                    value = None
                texts.append((item, value))
                if value is not None:
                    values.append(value)
        duplicates = {value for value in values if values.count(value) > 1}
        self.table.blockSignals(True)
        for item, value in texts:
            problem = value is None or value in duplicates or not 1 <= value <= self._nports
            item.setBackground(_PROBLEM_COLOR if problem else _NORMAL_COLOR)
        self.table.blockSignals(False)
        try:
            self.confirmed_mapping()
            message = f"通过：{self._nports} 个端口全部覆盖，source 已确认"
            valid = True
        except ValueError as exc:
            message = str(exc)
            valid = False
        self.stats_label.setText(message)
        self.stats_label.setStyleSheet("color: #268447;" if valid else "color: #b45f06;")
        self.confirm_button.setEnabled(valid)

    def _emit_confirmation(self) -> None:
        mapping = self.confirmed_mapping()
        self.mapping_confirmed.emit(mapping)
