"""支持拖放交换和撤销/恢复的端口映射表。"""

from __future__ import annotations

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QUndoCommand, QUndoStack
from qtpy.QtWidgets import QAbstractItemView, QTableWidget


class _SwapCellsCommand(QUndoCommand):
    def __init__(self, table: "MappingTable", first: tuple[int, int], second: tuple[int, int]):
        super().__init__("交换端口")
        self.table = table
        self.first = first
        self.second = second

    def _swap(self) -> None:
        first_item = self.table.item(*self.first)
        second_item = self.table.item(*self.second)
        first_text = first_item.text() if first_item else ""
        second_text = second_item.text() if second_item else ""
        self.table._set_cell_text(*self.first, second_text)
        self.table._set_cell_text(*self.second, first_text)
        self.table.mapping_changed.emit()

    def redo(self) -> None:
        self._swap()

    def undo(self) -> None:
        self._swap()


class MappingTable(QTableWidget):
    mapping_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.undo_stack = QUndoStack(self)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.itemChanged.connect(lambda _item: self.mapping_changed.emit())

    def _set_cell_text(self, row: int, column: int, text: str) -> None:
        self.blockSignals(True)
        item = self.item(row, column)
        if item is None:
            from qtpy.QtWidgets import QTableWidgetItem

            item = QTableWidgetItem()
            self.setItem(row, column, item)
        item.setText(text)
        self.blockSignals(False)

    def swap_cells(self, first: tuple[int, int], second: tuple[int, int]) -> None:
        if first == second:
            return
        self.undo_stack.push(_SwapCellsCommand(self, first, second))

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        source = self.currentItem()
        target = self.itemAt(event.position().toPoint())
        if source is None or target is None:
            event.ignore()
            return
        self.swap_cells((source.row(), source.column()), (target.row(), target.column()))
        event.acceptProposedAction()
