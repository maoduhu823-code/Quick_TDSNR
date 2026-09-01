"""重归一化执行页：输出目录、进度和 manifest 摘要。"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from quick_tdsnr.ui.pages.sample_workspace_page import SampleWorkspacePage
from quick_tdsnr.services.sample_workspace_service import SampleWorkspaceService


class ExecutionPage(QWidget):
    start_requested = Signal(object, object, str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._config = None
        self._plan = None
        self._auto_output = True
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        titlebar = QHBoxLayout()
        heading = QLabel("执行与波形")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        titlebar.addWidget(heading)
        titlebar.addStretch()
        self.summary_label = QLabel("尚未确认扫描计划")
        self.summary_label.setObjectName("executionSummaryLabel")
        titlebar.addWidget(self.summary_label)
        layout.addLayout(titlebar)

        settings = QGroupBox("执行设置")
        settings_layout = QHBoxLayout(settings)
        settings_layout.addWidget(QLabel("输出目录:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("确认扫描计划后自动使用输入文件旁的 qtsnr_runs")
        self.output_edit.setObjectName("renormalizationOutputEdit")
        settings_layout.addWidget(self.output_edit, stretch=1)
        browse = QPushButton("浏览")
        browse.clicked.connect(self._browse)
        settings_layout.addWidget(browse)
        self.write_checkbox = QCheckBox("写出 Touchstone")
        self.write_checkbox.setChecked(True)
        settings_layout.addWidget(self.write_checkbox)
        self.start_button = QPushButton("开始重归一化")
        self.start_button.setObjectName("startRenormalizationButton")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._emit_start)
        settings_layout.addWidget(self.start_button)
        layout.addWidget(settings)

        self.content_tabs = QTabWidget()
        self.content_tabs.setObjectName("executionContentTabs")
        self.sample_workspace = SampleWorkspacePage()
        self.content_tabs.addTab(self.sample_workspace, "样本工作台")

        detail_page = QWidget()
        detail_layout = QVBoxLayout(detail_page)
        detail_layout.addWidget(
            QLabel("这里保留文件/case级状态和错误；日常分析请使用“样本工作台”。")
        )
        self.result_table = QTableWidget(0, 5)
        self.result_table.setObjectName("renormalizationResultTable")
        self.result_table.setHorizontalHeaderLabels(
            ["输入", "case", "状态", "输出", "错误"]
        )
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        detail_layout.addWidget(self.result_table, stretch=1)
        self.detail_tab_index = self.content_tabs.addTab(detail_page, "运行明细")
        layout.addWidget(self.content_tabs, stretch=1)

    def set_plan(self, config, plan) -> None:
        self._config = config
        self._plan = plan
        inputs = getattr(config, "inputs", ())
        if self._auto_output and inputs:
            root = SampleWorkspaceService.default_root(
                [item.path for item in inputs]
            )
            self.output_edit.setText(str(root))
        self.start_button.setEnabled(True)
        self.summary_label.setText(
            f"待执行：{plan.case_count} cases × {plan.input_count} 输入 = "
            f"{plan.estimated_output_files} 项"
        )

    def reset(self) -> None:
        self._config = None
        self._plan = None
        self.start_button.setEnabled(False)
        self.summary_label.setText("尚未确认扫描计划")
        self.result_table.setRowCount(0)
        self.sample_workspace.clear()
        self.content_tabs.setCurrentIndex(0)

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running and self._plan is not None)
        self.output_edit.setEnabled(not running)
        self.write_checkbox.setEnabled(not running)

    def set_result(self, run) -> None:
        manifest = run.manifest
        self.summary_label.setText(
            f"完成：成功 {manifest.saved + manifest.in_memory}，"
            f"失败 {manifest.failed}，取消 {manifest.cancelled}"
        )
        self.result_table.setRowCount(len(manifest.items))
        for row, item in enumerate(manifest.items):
            values = (
                Path(item.input_path).name,
                item.case_id,
                item.status,
                item.output_path or "",
                item.error or "",
            )
            for column, value in enumerate(values):
                self.result_table.setItem(row, column, QTableWidgetItem(value))
        self.result_table.resizeColumnsToContents()
        detail_title = "运行明细"
        if manifest.failed or manifest.cancelled:
            detail_title += f"（失败 {manifest.failed} / 取消 {manifest.cancelled}）"
        self.content_tabs.setTabText(self.detail_tab_index, detail_title)
        self.content_tabs.setCurrentIndex(0)
        catalog = SampleWorkspaceService.catalog_from_run(run)
        self.sample_workspace.set_catalog(catalog)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择重归一化输出目录")
        if path:
            self.output_edit.setText(path)
            self._auto_output = False

    def _emit_start(self) -> None:
        if self._config is not None and self._plan is not None:
            self.start_requested.emit(
                self._config,
                self._plan,
                self.output_edit.text().strip(),
                self.write_checkbox.isChecked(),
            )
