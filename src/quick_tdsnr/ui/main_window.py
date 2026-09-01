"""Quick_TDSNR 主窗口。"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QAction, QDesktopServices, QKeySequence
from qtpy.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from quick_tdsnr import __version__
from quick_tdsnr.ui.pages.input_page import InputPage
from quick_tdsnr.ui.pages.mapping_page import MappingPage
from quick_tdsnr.ui.pages.sweep_page import SweepPage
from quick_tdsnr.ui.pages.topology_page import TopologyPage
from quick_tdsnr.ui.workers import (
    FrequencyAnalysisWorker,
    RenormalizationWorker,
    SNRWorker,
    TimeWaveformWorker,
    TopologyAnalysisWorker,
)
from quick_tdsnr.ui.pages.execution_page import ExecutionPage
from quick_tdsnr.ui.pages.snr_statistics_page import SNRStatisticsPage
from quick_tdsnr.ui.pages.time_domain_page import TimeDomainPage
from quick_tdsnr.services.project_file_service import ProjectFileService
from quick_tdsnr.services.sample_analysis_service import SampleAnalysisService
from quick_tdsnr.services.sample_workspace_service import SampleWorkspaceService
from quick_tdsnr.domain.project_models import (
    PROJECT_FILE_SCHEMA_VERSION,
    ConfirmedMapping,
    ProjectInput,
    ProjectSnapshot,
    TimeDomainDraft,
)


USER_PHASES = (
    ("文件导入", "选择一批原始 Touchstone 文件，并完成基础元数据预检。"),
    ("拓扑识别", "识别 p2p / multi-drop、联通簇和孤立端口。"),
    ("Port_family 确认", "检查拓扑建议，确认 source family 并修正端口映射。"),
    ("参数扫描", "设置各 family 的 R、Cio、目标 Rank 和 case 组合。"),
    ("时域与 SNR", "设置 UI、上升时间、时间步长、cursor 与 Noise 规则。"),
    ("执行与波形", "执行重归一化，管理样本并检查频域、时域和失败项。"),
    ("SNR 统计", "运行 SNR，查看二维热力图、汇总、逐串扰和逐结果。"),
)


class QuickTDSNRMainWindow(QMainWindow):
    """三栏工作流主窗口。"""

    def __init__(self, initial_project_path: str | Path | None = None) -> None:
        super().__init__()
        self.setObjectName("quickTDSNRMainWindow")
        self._base_window_title = f"Quick_TDSNR {__version__}  封装SIPI开发部"
        self.setWindowTitle(self._base_window_title)
        self.resize(1600, 800)
        self.setMinimumSize(1100, 650)
        self._sample_analysis_service = SampleAnalysisService(max_cached_networks=3)
        self._restoring_project = False
        self._build_ui()
        self._build_project_shortcuts()
        self._select_phase(0)
        self.append_log("Quick_TDSNR 已启动。")
        if initial_project_path is not None:
            self._load_project_file(initial_project_path)

    def _build_project_shortcuts(self) -> None:
        self.save_project_action = QAction("保存项目", self)
        self.save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_project_action.triggered.connect(self._save_project)
        self.addAction(self.save_project_action)
        self.open_project_action = QAction("打开项目", self)
        self.open_project_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_project_action.triggered.connect(self._open_project)
        self.addAction(self.open_project_action)
        self.save_project_as_action = QAction("项目另存为", self)
        self.save_project_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.save_project_as_action.triggered.connect(self._save_project_as)
        self.addAction(self.save_project_as_action)

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("mainSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([240, 910, 450])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 12)
        splitter.setStretchFactor(2, 6)
        self.setCentralWidget(splitter)
        self.input_page.analyse_requested.connect(self._start_topology_analysis)
        self.mapping_page.mapping_confirmed.connect(self._mapping_confirmed)
        self.sweep_page.plan_confirmed.connect(self._plan_confirmed)
        self.execution_page.start_requested.connect(self._start_renormalization)
        self.time_domain_page.settings_confirmed.connect(self._time_domain_confirmed)
        self.snr_statistics_page.snr_requested.connect(self._start_snr_from_statistics)
        workspace = self.execution_page.sample_workspace
        workspace.frequency_requested.connect(self._start_frequency_analysis)
        workspace.time_requested.connect(self._start_time_waveforms)
        workspace.catalog_open_requested.connect(self._open_sample_catalog)
        workspace.clear_cache_requested.connect(self._clear_sample_cache)
        workspace.visibility_requested.connect(self._set_sample_visibility)
        workspace.open_workspace_requested.connect(self._open_sample_workspace)
        workspace.checked_samples_changed.connect(
            self.snr_statistics_page.set_checked_sample_ids
        )
        self.cancel_button.clicked.connect(self._cancel_running_task)

        status = QStatusBar()
        status.setObjectName("statusBar")
        status.showMessage("就绪")
        self.setStatusBar(status)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("leftPanel")
        panel.setMinimumWidth(210)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 10, 6)
        layout.setSpacing(10)

        project_group = QGroupBox("项目")
        project_layout = QVBoxLayout(project_group)
        for text in ("新建项目", "打开项目", "保存项目", "项目另存为"):
            button = QPushButton(text)
            button.setFixedHeight(38 if text == "新建项目" else 32)
            if text == "新建项目":
                self.new_project_button = button
                button.clicked.connect(self._new_project)
            elif text == "打开项目":
                self.open_project_button = button
                button.clicked.connect(self._open_project)
            elif text == "保存项目":
                self.save_project_button = button
                button.clicked.connect(self._save_project)
            else:
                self.save_project_as_button = button
                button.clicked.connect(self._save_project_as)
            project_layout.addWidget(button)
        layout.addWidget(project_group)

        phase_group = QGroupBox("分析流程")
        phase_layout = QVBoxLayout(phase_group)
        self.phase_list = QListWidget()
        self.phase_list.setObjectName("phaseList")
        for index, (title, _) in enumerate(USER_PHASES, start=1):
            self.phase_list.addItem(f"{index}. {title}")
        self.phase_list.currentRowChanged.connect(self._select_phase)
        phase_layout.addWidget(self.phase_list)
        layout.addWidget(phase_group, stretch=1)
        return panel

    def _build_center_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("centerPanel")
        panel.setMinimumWidth(560)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("phasePageStack")
        self.input_page = InputPage()
        self.topology_page = TopologyPage()
        self.mapping_page = MappingPage()
        self.sweep_page = SweepPage()
        self.page_stack.addWidget(self.input_page)
        self.page_stack.addWidget(self.topology_page)
        self.page_stack.addWidget(self.mapping_page)
        self.page_stack.addWidget(self.sweep_page)
        for index, (title, description) in enumerate(USER_PHASES[4:5], start=5):
            page = TimeDomainPage()
            page.setObjectName(f"phasePage{index}")
            self.time_domain_page = page
            self.page_stack.addWidget(page)
            continue
            page_layout = QVBoxLayout(page)
            group = QGroupBox(f"{index}. {title}")
            group_layout = QVBoxLayout(group)
            heading = QLabel(title)
            heading.setStyleSheet("font-size: 20px; font-weight: 600;")
            description_label = QLabel(description)
            description_label.setWordWrap(True)
            description_label.setStyleSheet("color: #55575c; padding: 8px 0;")
            placeholder = QLabel("该页面将在对应开发 Phase 中启用。")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(
                "border: 1px dashed #b8bbc1; border-radius: 4px; "
                "color: #777a80; background: #fafafa; min-height: 300px;"
            )
            group_layout.addWidget(heading)
            group_layout.addWidget(description_label)
            group_layout.addWidget(placeholder, stretch=1)
            page_layout.addWidget(group)
            self.page_stack.addWidget(page)
        self.execution_page = ExecutionPage()
        self.page_stack.addWidget(self.execution_page)
        self.snr_statistics_page = SNRStatisticsPage()
        self.page_stack.addWidget(self.snr_statistics_page)
        layout.addWidget(self.page_stack, stretch=1)

        navigation = QHBoxLayout()
        self.previous_button = QPushButton("上一步")
        self.previous_button.setObjectName("previousButton")
        self.previous_button.clicked.connect(self._go_previous)
        self.next_button = QPushButton("下一步")
        self.next_button.setObjectName("nextButton")
        self.next_button.clicked.connect(self._go_next)
        navigation.addStretch()
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.next_button)
        layout.addLayout(navigation)
        return panel

    def _start_topology_analysis(self, request: dict) -> None:
        running = getattr(self, "_active_worker", None)
        if running is not None and running.isRunning():
            return
        self.input_page.set_busy(True)
        self._topology_succeeded = False
        self.topology_page.set_running()
        self.progress_bar.setRange(0, 0)
        self.cancel_button.setEnabled(True)
        self.append_log(f"开始预检 {len(request['paths'])} 个文件。")
        worker = TopologyAnalysisWorker(request, self)
        self._topology_worker = worker
        self._active_worker = worker
        worker.progress.connect(self.append_log)
        worker.completed.connect(self._topology_completed)
        worker.failed.connect(self._topology_failed)
        worker.cancelled.connect(self._topology_cancelled)
        worker.finished.connect(self._topology_finished)
        worker.start()

    def _topology_completed(self, batch, analysis) -> None:
        self._topology_succeeded = True
        self._preflight_batch = batch
        self._topology_analysis = analysis
        self._project_inputs = tuple(
            ProjectInput(str(item.path), item.sha256) for item in batch.files
        )
        self.input_page.set_preflight_batch(batch)
        self.topology_page.set_analysis(analysis)
        self.input_count_label.setText(f"输入文件：{len(batch.files)}")
        proposal = analysis.recommended_proposal
        if proposal is None:
            self.mapping_status_label.setText("端口映射：需要人工处理")
        else:
            self.mapping_status_label.setText(
                f"建议映射：{proposal.line_count} 线 × {proposal.family_count} families"
            )
            self.mapping_page.set_proposal(proposal)
        self.append_log(
            f"拓扑识别完成：推荐 {analysis.recommended_metric or '无'} 判据，"
            f"置信度 {analysis.confidence}。"
        )
        self._select_phase(1)

    def _topology_failed(self, message: str) -> None:
        self.append_log(f"[失败] {message}")
        self.statusBar().showMessage(message)

    def _topology_cancelled(self, message: str) -> None:
        self.append_log(message)
        self.statusBar().showMessage(message)

    def _topology_finished(self) -> None:
        self.input_page.set_busy(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if self._topology_succeeded else 0)
        self.cancel_button.setEnabled(False)
        if getattr(self, "_active_worker", None) is getattr(self, "_topology_worker", None):
            self._active_worker = None

    def _cancel_running_task(self) -> None:
        worker = getattr(self, "_active_worker", None)
        if worker is None:
            worker = getattr(self, "_topology_worker", None)
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            self.append_log("已请求取消当前任务，将在当前数值步骤结束后停止。")

    def _mapping_confirmed(self, mapping) -> None:
        self._confirmed_mapping = mapping
        if hasattr(self, "_preflight_batch") and hasattr(self, "_topology_analysis"):
            self.sweep_page.set_context(
                mapping, self._preflight_batch, self._topology_analysis
            )
        elif hasattr(self, "_project_config"):
            previous = self._project_config
            self.sweep_page.set_mapping(
                mapping,
                inputs=previous.inputs,
                metric=previous.topology_metric,
                frequency_ghz=previous.topology_frequency_ghz,
            )
        elif hasattr(self, "_project_inputs"):
            self.sweep_page.set_mapping(
                mapping,
                inputs=self._project_inputs,
                metric=getattr(self, "_restored_topology_metric", "S"),
                frequency_ghz=getattr(
                    self, "_restored_topology_frequency_ghz", 0.1
                ),
            )
        else:
            self.append_log("映射缺少对应的文件预检结果，请重新识别拓扑。")
            return
        self.mapping_status_label.setText(
            f"端口映射：{len(mapping.rows)} 线 × {len(mapping.family_ids)} families，"
            f"source={mapping.source_family}"
        )
        self.append_log(f"已确认 Port_family 映射，source={mapping.source_family}。")
        self._select_phase(3)

    def _plan_confirmed(self, config, plan) -> None:
        self._project_config = config
        self._sweep_plan = plan
        self.case_count_label.setText(
            f"计划 cases：{plan.case_count}（预计输出 {plan.estimated_output_files}）"
        )
        self.append_log(
            f"扫描计划已确认：{plan.case_count} cases，"
            f"预计 {plan.estimated_output_files} 个输出。"
        )
        self.execution_page.set_plan(config, plan)
        self._select_phase(4)

    def _time_domain_confirmed(self, settings) -> None:
        self._time_domain_settings = settings
        self.append_log("时域与 SNR 参数已确认。")
        if hasattr(self, "_renormalization_run"):
            self.snr_statistics_page.set_snr_ready(
                self._renormalization_run, settings
            )

    def _start_renormalization(self, config, plan, output_dir: str, write_outputs: bool) -> None:
        running = getattr(self, "_active_worker", None)
        if running is not None and running.isRunning():
            return
        if write_outputs and not output_dir:
            self.append_log("请指定输出目录。")
            return
        worker = RenormalizationWorker(config, plan, output_dir, write_outputs, self)
        self._renormalization_worker = worker
        self._active_worker = worker
        self.execution_page.set_running(True)
        self.progress_bar.setRange(0, plan.estimated_output_files)
        self.progress_bar.setValue(0)
        self.cancel_button.setEnabled(True)
        worker.progress.connect(self._renormalization_progress)
        worker.completed.connect(self._renormalization_completed)
        worker.failed.connect(self._renormalization_failed)
        worker.cancelled.connect(self._renormalization_cancelled)
        worker.finished.connect(self._renormalization_finished)
        self.append_log(f"开始重归一化：{plan.estimated_output_files} 项。")
        worker.start()

    def _renormalization_progress(self, progress) -> None:
        self.progress_bar.setValue(progress.completed)
        self.append_log(f"重归一化 {progress.message}：{progress.case_id}")

    def _renormalization_completed(self, run) -> None:
        self._renormalization_run = run
        self._active_sample_catalog = SampleWorkspaceService.catalog_from_run(run)
        self.execution_page.set_result(run)
        self.snr_statistics_page.set_catalog(self._active_sample_catalog)
        if hasattr(self, "_time_domain_settings"):
            self.snr_statistics_page.set_snr_ready(run, self._time_domain_settings)
        self.append_log(
            f"重归一化完成：成功 {run.manifest.saved + run.manifest.in_memory}，"
            f"失败 {run.manifest.failed}，取消 {run.manifest.cancelled}。"
        )
        self._autosave_checkpoint()

    def _renormalization_failed(self, message: str) -> None:
        self.append_log(f"重归一化失败：{message}")
        self.statusBar().showMessage(message)

    def _renormalization_cancelled(self, message: str) -> None:
        self.append_log(message)
        self.statusBar().showMessage(message)

    def _renormalization_finished(self) -> None:
        self.execution_page.set_running(False)
        self.cancel_button.setEnabled(False)
        if getattr(self, "_active_worker", None) is getattr(self, "_renormalization_worker", None):
            self._active_worker = None

    def _start_snr_from_statistics(self, run, settings) -> None:
        self._start_snr(run, settings, self.execution_page.output_edit.text().strip())

    def _start_snr(self, run, settings, output_dir: str) -> None:
        running = getattr(self, "_active_worker", None)
        if running is not None and running.isRunning():
            return
        worker = SNRWorker(run, settings, output_dir, self)
        self._snr_worker = worker
        self._active_worker = worker
        self.snr_statistics_page.set_snr_running(True)
        self.progress_bar.setRange(
            0, max(1, run.manifest.saved + run.manifest.in_memory)
        )
        self.progress_bar.setValue(0)
        self.cancel_button.setEnabled(True)
        worker.progress.connect(self._snr_progress)
        worker.completed.connect(self._snr_completed)
        worker.failed.connect(self._snr_failed)
        worker.cancelled.connect(self._snr_cancelled)
        worker.finished.connect(self._snr_finished)
        worker.start()
        self.append_log("开始时域 SNR 分析。")

    def _snr_progress(self, progress) -> None:
        done, total, case_id = progress
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.snr_statistics_page.set_progress(done, total, case_id)
        self.append_log(f"SNR {done}/{total}：{case_id}")

    def _snr_completed(self, result) -> None:
        self._pipeline_result = result
        self.snr_statistics_page.set_results(result.results)
        self.execution_page.summary_label.setText(
            self.execution_page.summary_label.text()
            + f"；SNR 结果 {result.result_count} 条"
        )
        self.append_log(f"时域 SNR 完成：{result.result_count} 条。")
        self._select_phase(6)
        self._autosave_checkpoint()

    def _snr_failed(self, message: str) -> None:
        self.snr_statistics_page.set_error(f"时域 SNR 失败：{message}")
        self.append_log(f"时域 SNR 失败：{message}")

    def _snr_cancelled(self, message: str) -> None:
        self.snr_statistics_page.set_error(message)
        self.append_log(message)

    def _snr_finished(self) -> None:
        self.snr_statistics_page.set_snr_running(False)
        self.cancel_button.setEnabled(False)
        if getattr(self, "_active_worker", None) is getattr(self, "_snr_worker", None):
            self._active_worker = None

    def _start_frequency_analysis(self, samples, request) -> None:
        running = getattr(self, "_active_worker", None)
        if running is not None and running.isRunning():
            return
        in_memory = getattr(getattr(self, "_renormalization_run", None), "networks", {})
        worker = FrequencyAnalysisWorker(
            self._sample_analysis_service, samples, request, in_memory, self
        )
        self._frequency_worker = worker
        self._active_worker = worker
        self.execution_page.sample_workspace.frequency_panel.set_busy(True)
        self.progress_bar.setRange(0, len(samples))
        self.progress_bar.setValue(0)
        self.cancel_button.setEnabled(True)
        worker.progress.connect(self._sample_analysis_progress)
        worker.completed.connect(self._frequency_completed)
        worker.failed.connect(self._sample_analysis_failed)
        worker.cancelled.connect(self._sample_analysis_cancelled)
        worker.finished.connect(self._frequency_finished)
        worker.start()

    def _frequency_completed(self, traces, request) -> None:
        self.execution_page.sample_workspace.frequency_panel.set_traces(
            traces, request.get("frequency_range")
        )
        self.append_log(f"频域曲线完成：{len(traces)} 个样本。")

    def _frequency_finished(self) -> None:
        self.execution_page.sample_workspace.frequency_panel.set_busy(False)
        self._sample_worker_finished(self._frequency_worker)

    def _start_time_waveforms(self, samples, request) -> None:
        running = getattr(self, "_active_worker", None)
        if running is not None and running.isRunning():
            return
        tx_port, rx_port, settings = request
        catalog = self.execution_page.sample_workspace.model.catalog
        cache_dir = SampleWorkspaceService.waveform_cache_dir(catalog) if catalog else None
        in_memory = getattr(getattr(self, "_renormalization_run", None), "networks", {})
        worker = TimeWaveformWorker(
            self._sample_analysis_service,
            samples,
            tx_port,
            rx_port,
            settings,
            cache_dir,
            in_memory,
            self,
        )
        self._time_waveform_worker = worker
        self._active_worker = worker
        self.execution_page.sample_workspace.time_panel.set_busy(True)
        self.progress_bar.setRange(0, len(samples))
        self.progress_bar.setValue(0)
        self.cancel_button.setEnabled(True)
        worker.progress.connect(self._sample_analysis_progress)
        worker.completed.connect(self._time_waveforms_completed)
        worker.failed.connect(self._sample_analysis_failed)
        worker.cancelled.connect(self._sample_analysis_cancelled)
        worker.finished.connect(self._time_waveforms_finished)
        worker.start()

    def _time_waveforms_completed(self, waveforms) -> None:
        self.execution_page.sample_workspace.time_panel.set_waveforms(waveforms)
        self.append_log(f"时域波形完成：{len(waveforms)} 个样本。")

    def _time_waveforms_finished(self) -> None:
        self.execution_page.sample_workspace.time_panel.set_busy(False)
        self._sample_worker_finished(self._time_waveform_worker)

    def _sample_analysis_progress(self, progress) -> None:
        done, total, name = progress
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.statusBar().showMessage(f"样本分析 {done}/{total}：{name}")

    def _sample_analysis_failed(self, message: str) -> None:
        self.append_log(f"样本分析失败：{message}")
        self.statusBar().showMessage(message)

    def _sample_analysis_cancelled(self, message: str) -> None:
        self.append_log(message)
        self.statusBar().showMessage(message)

    def _sample_worker_finished(self, worker) -> None:
        self.cancel_button.setEnabled(False)
        if getattr(self, "_active_worker", None) is worker:
            self._active_worker = None

    def _open_sample_catalog(self, path: str) -> None:
        try:
            catalog = SampleWorkspaceService.load_catalog(path)
            run = SampleWorkspaceService.load_run(path)
        except Exception as exc:
            self.append_log(f"打开运行失败：{exc}")
            return
        self._renormalization_run = run
        self._active_sample_catalog = catalog
        self.execution_page.set_result(run)
        self.snr_statistics_page.set_catalog(catalog)
        if hasattr(self, "_time_domain_settings"):
            self.snr_statistics_page.set_snr_ready(run, self._time_domain_settings)
        self.append_log(
            f"已恢复运行 {catalog.run_id[:8]}：{len(catalog.available)} 个样本。"
        )

    def _clear_sample_cache(self, workspace: str) -> None:
        target = str(Path(workspace).expanduser().resolve() / "derived")
        answer = QMessageBox.question(
            self,
            "清理派生缓存",
            f"将清理可重新生成的时域波形和统计缓存：\n{target}\n\n"
            "Touchstone、manifest和原始输入不会被删除。",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            SampleWorkspaceService.clear_derived_cache(workspace)
        except Exception as exc:
            self.append_log(f"清理派生缓存失败：{exc}")
            return
        self.append_log(f"已清理派生缓存：{target}")

    def _set_sample_visibility(self, sample_ids, visible: bool) -> None:
        catalog = self.execution_page.sample_workspace.model.catalog
        if catalog is None:
            return
        try:
            updated = SampleWorkspaceService.set_visibility(
                catalog, set(sample_ids), visible
            )
        except Exception as exc:
            self.append_log(f"更新样本列表失败：{exc}")
            return
        self._active_sample_catalog = updated
        self.execution_page.sample_workspace.set_catalog(updated)
        self.snr_statistics_page.set_catalog(updated)
        action = "恢复" if visible else "移出列表"
        self.append_log(f"已{action} {len(sample_ids)} 个样本；磁盘文件未改变。")
        self._autosave_checkpoint()

    def _open_sample_workspace(self, workspace: str) -> None:
        path = Path(workspace).expanduser().resolve()
        if not path.is_dir():
            self.append_log(f"运行目录不存在：{path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _new_project(self) -> None:
        self._reset_project_state(clear_project_path=True)
        self.append_log("已新建空项目。")

    def _reset_project_state(
        self, *, clear_project_path: bool, select_first_phase: bool = True
    ) -> None:
        self.input_page.set_files([])
        self.input_page.preflight_table.setVisible(False)
        self.topology_page.clear()
        self.input_page.frequency_edit.setText("0.1")
        self.input_page.cliff_edit.clear()
        self.mapping_page.table.setRowCount(0)
        self.mapping_page.table.setColumnCount(0)
        self.mapping_page.source_combo.clear()
        self.sweep_page.table.setRowCount(0)
        self.sweep_page._mapping = None
        self.sweep_page._inputs = ()
        self.time_domain_page.load_draft(TimeDomainDraft())
        self.execution_page.reset()
        self.snr_statistics_page.reset()
        for name in (
            "_preflight_batch", "_topology_analysis", "_confirmed_mapping",
            "_project_config", "_sweep_plan", "_time_domain_settings",
            "_project_inputs", "_restored_topology_metric",
            "_restored_topology_frequency_ghz", "_renormalization_run",
            "_pipeline_result", "_active_sample_catalog",
        ):
            if hasattr(self, name):
                delattr(self, name)
        self._sample_analysis_service.networks.clear()
        self.input_count_label.setText("输入文件：0")
        self.mapping_status_label.setText("端口映射：未配置")
        self.case_count_label.setText("计划 cases：0")
        if clear_project_path and hasattr(self, "_current_project_path"):
            delattr(self, "_current_project_path")
        self._update_project_title()
        if select_first_phase:
            self._select_phase(0)

    def _snapshot_from_ui(self) -> ProjectSnapshot:
        project_inputs = getattr(self, "_project_inputs", ())
        if not project_inputs and hasattr(self, "_project_config"):
            project_inputs = self._project_config.inputs
        mapping_draft = self.mapping_page.draft()
        sweep_drafts = self.sweep_page.drafts()
        if hasattr(self, "_topology_analysis"):
            metric = self._topology_analysis.recommended_metric or "S"
            frequency_ghz = self._topology_analysis.actual_frequency_ghz
        elif self.sweep_page._mapping is not None:
            metric = self.sweep_page._metric
            frequency_ghz = self.sweep_page._frequency_ghz
        else:
            metric = getattr(self, "_restored_topology_metric", "S")
            try:
                frequency_ghz = float(self.input_page.frequency_edit.text())
            except ValueError:
                frequency_ghz = 0.1
        catalog_path = None
        catalog = self.execution_page.sample_workspace.model.catalog
        if catalog and catalog.workspace_path:
            candidate = Path(catalog.workspace_path) / "sample_catalog.json"
            if candidate.is_file():
                catalog_path = str(candidate)
        return ProjectSnapshot(
            schema_version=PROJECT_FILE_SCHEMA_VERSION,
            saved_at="",
            current_phase=self.page_stack.currentIndex(),
            input_paths=tuple(self.input_page.files()),
            topology_frequency_text=self.input_page.frequency_edit.text(),
            topology_cliff_text=self.input_page.cliff_edit.text(),
            project_inputs=tuple(project_inputs),
            topology_draft=self.topology_page.draft(),
            mapping_draft=mapping_draft,
            sweep_drafts=sweep_drafts,
            topology_metric=metric,
            topology_frequency_ghz=frequency_ghz,
            time_domain_draft=self.time_domain_page.draft(),
            output_root=self.execution_page.output_edit.text(),
            write_outputs=self.execution_page.write_checkbox.isChecked(),
            sample_catalog_path=catalog_path,
        )

    def _save_project(self) -> None:
        path = getattr(self, "_current_project_path", None)
        if path is None:
            self._save_project_as()
            return
        self._write_project_snapshot(path)

    def _save_project_as(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self, "项目另存为", "", "Quick_TDSNR 项目 (*.qtsnr.json)"
        )
        if not selected:
            return
        self._write_project_snapshot(Path(selected).expanduser().resolve())

    def _write_project_snapshot(self, path: Path) -> None:
        try:
            saved = ProjectFileService.save_snapshot(self._snapshot_from_ui(), path)
        except Exception as exc:
            self.append_log(f"无法保存项目：{exc}")
            return
        self._current_project_path = saved
        self._update_project_title()
        self.append_log(f"项目已保存：{saved}")

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开 Quick_TDSNR 项目", "", "Quick_TDSNR 项目 (*.qtsnr.json)"
        )
        if not path:
            return
        self._load_project_file(path)

    def _load_project_file(self, path: str | Path) -> bool:
        project_path = Path(path).expanduser().resolve()
        try:
            snapshot = ProjectFileService.load_snapshot(project_path)
            self._apply_project_snapshot(snapshot, project_path)
        except Exception as exc:
            self.append_log(f"项目打开失败：{project_path}；{exc}")
            return False
        return True

    def _apply_project_snapshot(
        self, snapshot: ProjectSnapshot, project_path: Path
    ) -> None:
        self._restoring_project = True
        try:
            self._reset_project_state(
                clear_project_path=False, select_first_phase=False
            )
            self._current_project_path = project_path
            self._update_project_title()
            self.input_page.set_files(list(snapshot.input_paths))
            self.input_page.frequency_edit.setText(snapshot.topology_frequency_text)
            self.input_page.cliff_edit.setText(snapshot.topology_cliff_text)
            self._project_inputs = snapshot.project_inputs
            self._restored_topology_metric = snapshot.topology_metric
            self._restored_topology_frequency_ghz = snapshot.topology_frequency_ghz
            self.input_count_label.setText(f"输入文件：{len(snapshot.input_paths)}")
            if snapshot.topology_draft is not None:
                self._topology_analysis = self.topology_page.load_draft(
                    snapshot.topology_draft
                )

            valid_mapping: ConfirmedMapping | None = None
            if snapshot.mapping_draft is not None:
                self.mapping_page.load_draft(snapshot.mapping_draft)
                try:
                    valid_mapping = self.mapping_page.confirmed_mapping()
                except ValueError:
                    valid_mapping = None
                if valid_mapping is not None:
                    self._confirmed_mapping = valid_mapping
                    self.mapping_status_label.setText(
                        f"端口映射：{len(valid_mapping.rows)} 线 × "
                        f"{len(valid_mapping.family_ids)} families，"
                        f"source={valid_mapping.source_family}"
                    )

            valid_plan = False
            if valid_mapping is not None and snapshot.project_inputs:
                self.sweep_page.load_drafts(
                    valid_mapping,
                    inputs=snapshot.project_inputs,
                    metric=snapshot.topology_metric,
                    frequency_ghz=snapshot.topology_frequency_ghz,
                    drafts=snapshot.sweep_drafts,
                )
                try:
                    config, plan = self.sweep_page.current_plan()
                except ValueError:
                    pass
                else:
                    self._project_config = config
                    self._sweep_plan = plan
                    self.case_count_label.setText(
                        f"计划 cases：{plan.case_count}（预计输出 {plan.estimated_output_files}）"
                    )
                    self.execution_page.set_plan(config, plan)
                    valid_plan = True

            self.time_domain_page.load_draft(snapshot.time_domain_draft)
            valid_time = self.time_domain_page.is_valid()
            if valid_time:
                self._time_domain_settings = self.time_domain_page.settings()
            self.execution_page.output_edit.setText(snapshot.output_root)
            self.execution_page._auto_output = not bool(snapshot.output_root)
            self.execution_page.write_checkbox.setChecked(snapshot.write_outputs)

            run_restored = False
            if snapshot.sample_catalog_path:
                catalog_path = Path(snapshot.sample_catalog_path)
                if catalog_path.is_file():
                    run = SampleWorkspaceService.load_run(catalog_path)
                    self._renormalization_run = run
                    self._active_sample_catalog = SampleWorkspaceService.load_catalog(
                        catalog_path
                    )
                    self.execution_page.set_result(run)
                    self.snr_statistics_page.set_catalog(self._active_sample_catalog)
                    if valid_time:
                        self.snr_statistics_page.set_snr_ready(
                            run, self._time_domain_settings
                        )
                    run_restored = True

            stale = ProjectFileService.stale_project_inputs(snapshot.project_inputs)
            resume_phase = snapshot.current_phase
            if stale or (resume_phase > 0 and not snapshot.project_inputs):
                resume_phase = 0
            elif resume_phase == 1 and snapshot.topology_draft is None:
                resume_phase = 0
            elif resume_phase > 1 and snapshot.mapping_draft is None:
                resume_phase = 0
            elif resume_phase > 2 and valid_mapping is None:
                resume_phase = 2
            elif resume_phase > 3 and not valid_plan:
                resume_phase = 3
            elif resume_phase > 4 and not valid_time:
                resume_phase = 4
            if run_restored:
                resume_phase = max(5, resume_phase)
            self._select_phase(resume_phase)
            if stale:
                self.append_log(
                    "输入文件已变化或缺失，已恢复设置但必须重新预检："
                    + "；".join(stale)
                )
            else:
                self.append_log(
                    f"项目已恢复到 Phase {resume_phase + 1}：{project_path}"
                )
        finally:
            self._restoring_project = False

    def _autosave_checkpoint(self) -> None:
        path = getattr(self, "_current_project_path", None)
        if path is None or self._restoring_project:
            return
        try:
            ProjectFileService.save_snapshot(self._snapshot_from_ui(), path)
        except Exception as exc:
            self.append_log(f"阶段检查点自动保存失败：{exc}")
        else:
            self.statusBar().showMessage(f"阶段检查点已保存：{Path(path).name}")

    def _update_project_title(self) -> None:
        path = getattr(self, "_current_project_path", None)
        suffix = f" — {Path(path).name}" if path else ""
        self.setWindowTitle(self._base_window_title + suffix)

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("rightPanel")
        panel.setMinimumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(10)

        summary_group = QGroupBox("任务摘要")
        summary_layout = QVBoxLayout(summary_group)
        self.current_phase_label = QLabel()
        self.current_phase_label.setObjectName("currentPhaseLabel")
        self.input_count_label = QLabel("输入文件：0")
        self.mapping_status_label = QLabel("端口映射：未配置")
        self.case_count_label = QLabel("计划 cases：0")
        for label in (
            self.current_phase_label,
            self.input_count_label,
            self.mapping_status_label,
            self.case_count_label,
        ):
            summary_layout.addWidget(label)
        layout.addWidget(summary_group)

        progress_group = QGroupBox("运行进度")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("pipelineProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.cancel_button = QPushButton("取消任务")
        self.cancel_button.setEnabled(False)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.cancel_button)
        layout.addWidget(progress_group)

        log_group = QGroupBox("信息输出")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setObjectName("logOutput")
        self.log_output.setReadOnly(True)
        clear_button = QPushButton("清除输出")
        clear_button.clicked.connect(self.log_output.clear)
        log_layout.addWidget(self.log_output, stretch=1)
        log_layout.addWidget(clear_button)
        layout.addWidget(log_group, stretch=1)
        return panel

    def _select_phase(self, index: int) -> None:
        if index < 0:
            index = 0
        index = min(index, len(USER_PHASES) - 1)
        if self.phase_list.currentRow() != index:
            self.phase_list.setCurrentRow(index)
        self.page_stack.setCurrentIndex(index)
        self.current_phase_label.setText(
            f"当前步骤：{index + 1}/{len(USER_PHASES)} {USER_PHASES[index][0]}"
        )
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < len(USER_PHASES) - 1)
        next_labels = {
            2: "确认映射并下一步",
            3: "确认计划并下一步",
            4: "确认设置并下一步",
            5: "进入 SNR 统计",
            6: "完成",
        }
        self.next_button.setText(next_labels.get(index, "下一步"))
        if self.statusBar() is not None:
            self.statusBar().showMessage(USER_PHASES[index][1])
        self._autosave_checkpoint()

    def _go_previous(self) -> None:
        self._select_phase(self.page_stack.currentIndex() - 1)

    def _go_next(self) -> None:
        current = self.page_stack.currentIndex()
        if current == 2:
            if not self.mapping_page.is_valid():
                self.append_log("请先修正映射并明确确认 source family。")
                return
            self.mapping_page._emit_confirmation()
            return
        if current == 3:
            if not self.sweep_page.build_button.isEnabled():
                self.append_log("请先完成有效的参数扫描配置。")
                return
            self.sweep_page._confirm_plan()
            return
        if current == 4:
            if not self.time_domain_page.is_valid():
                self.append_log("请先修正时域与 SNR 参数。")
                return
            self.time_domain_page._emit_settings()
            self._select_phase(5)
            return
        self._select_phase(current + 1)

    def append_log(self, message: str) -> None:
        self.log_output.append(message)
