"""文件导入和拓扑预检参数页。"""

from __future__ import annotations

import math
from pathlib import Path

from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class InputPage(QWidget):
    analyse_requested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("inputPage")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("文件导入")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        description = QLabel(
            "选择一批原始 Touchstone 文件。预检完成后自动比较 S/Y/Z 拓扑，"
            "再生成 Port_family 建议。"
        )
        description.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(description)

        files_group = QGroupBox("原始 S 参数文件")
        files_layout = QVBoxLayout(files_group)
        self.file_list = QListWidget()
        self.file_list.setObjectName("inputFileList")
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("添加文件")
        self.add_button.clicked.connect(self._browse_files)
        self.remove_button = QPushButton("移除选中")
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.file_list.clear)
        for button in (self.add_button, self.remove_button, self.clear_button):
            buttons.addWidget(button)
        buttons.addStretch()
        files_layout.addWidget(self.file_list)
        files_layout.addLayout(buttons)
        self.preflight_table = QTableWidget(0, 6)
        self.preflight_table.setObjectName("preflightTable")
        self.preflight_table.setHorizontalHeaderLabels(
            ["文件", "端口", "频点数", "频率范围 (GHz)", "端口名", "状态"]
        )
        self.preflight_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preflight_table.setVisible(False)
        files_layout.addWidget(self.preflight_table)
        layout.addWidget(files_group, stretch=1)

        settings_group = QGroupBox("拓扑预识别")
        settings_layout = QGridLayout(settings_group)
        settings_layout.addWidget(QLabel("探测频点 (GHz):"), 0, 0)
        self.frequency_edit = QLineEdit("0.1")
        self.frequency_edit.setObjectName("topologyFrequencyEdit")
        settings_layout.addWidget(self.frequency_edit, 0, 1)
        settings_layout.addWidget(QLabel("断崖阈值 (dB):"), 1, 0)
        self.cliff_edit = QLineEdit()
        self.cliff_edit.setObjectName("topologyCliffEdit")
        self.cliff_edit.setPlaceholderText("留空使用 S/Y/Z 各自默认值")
        settings_layout.addWidget(self.cliff_edit, 1, 1)
        self.analyse_button = QPushButton("预检文件并识别拓扑")
        self.analyse_button.setObjectName("analyseTopologyButton")
        self.analyse_button.setFixedHeight(42)
        self.analyse_button.clicked.connect(self._emit_request)
        settings_layout.addWidget(self.analyse_button, 0, 2, 2, 1)
        settings_layout.setColumnStretch(3, 1)
        layout.addWidget(settings_group)

    def files(self) -> list[str]:
        return [self.file_list.item(index).text() for index in range(self.file_list.count())]

    def set_files(self, paths: list[str | Path]) -> None:
        self.file_list.clear()
        for path in paths:
            self.file_list.addItem(str(Path(path).expanduser().resolve()))

    def add_files(self, paths: list[str | Path]) -> None:
        existing = set(self.files())
        for path in paths:
            resolved = str(Path(path).expanduser().resolve())
            if resolved not in existing:
                self.file_list.addItem(resolved)
                existing.add(resolved)

    def set_busy(self, busy: bool) -> None:
        for widget in (
            self.add_button,
            self.remove_button,
            self.clear_button,
            self.analyse_button,
            self.frequency_edit,
            self.cliff_edit,
        ):
            widget.setEnabled(not busy)

    def set_preflight_batch(self, batch) -> None:
        """展示结构化预检结果；不从日志文本反向解析元数据。"""
        self.preflight_table.setRowCount(len(batch.files))
        for row, info in enumerate(batch.files):
            values = (
                info.name,
                str(info.nports),
                str(info.nfreq),
                f"{info.f_start_ghz:.6g} ~ {info.f_stop_ghz:.6g}",
                "完整" if len(info.port_names) == info.nports else "缺失",
                "通过",
            )
            for column, value in enumerate(values):
                self.preflight_table.setItem(row, column, QTableWidgetItem(value))
        self.preflight_table.resizeColumnsToContents()
        self.preflight_table.setVisible(bool(batch.files))

    def _browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择原始 Touchstone 文件",
            "",
            "Touchstone (*.s*p);;所有文件 (*)",
        )
        if paths:
            self.add_files(paths)

    def _remove_selected(self) -> None:
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def _emit_request(self) -> None:
        paths = self.files()
        if not paths:
            QMessageBox.warning(self, "输入错误", "请先选择至少一个 Touchstone 文件。")
            return
        try:
            frequency_ghz = float(self.frequency_edit.text())
            if not math.isfinite(frequency_ghz) or frequency_ghz < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "输入错误", "拓扑探测频点必须为非负数。")
            return
        cliff_text = self.cliff_edit.text().strip()
        try:
            cliff_db = None if not cliff_text else float(cliff_text)
            if cliff_db is not None and (
                not math.isfinite(cliff_db) or cliff_db <= 0
            ):
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "输入错误", "断崖阈值必须为正数或留空。")
            return
        self.analyse_requested.emit(
            {
                "paths": paths,
                "low_freq_ghz": frequency_ghz,
                "min_cliff_db": cliff_db,
            }
        )
