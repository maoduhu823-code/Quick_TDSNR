"""生成样本的列表管理及频域、时域两页工作台。"""

from __future__ import annotations

from qtpy.QtCore import QAbstractListModel, QModelIndex, Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from quick_tdsnr.domain.project_models import SampleCatalog, TimeDomainSettings
from quick_tdsnr.services.snr_analysis_service import SNRAnalysisService
from quick_tdsnr.ui.plot_dialog import PlotDialog


class SampleListModel(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._catalog: SampleCatalog | None = None
        self._visible = []
        self._checked: set[str] = set()
        self._query = ""
        self._display_mode = "compact"

    def rowCount(self, _parent=QModelIndex()) -> int:
        return len(self._visible)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._visible):
            return None
        sample = self._visible[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return sample
        if role == Qt.ItemDataRole.ToolTipRole:
            return sample.output_path or sample.input_path
        if role == Qt.ItemDataRole.CheckStateRole:
            return (
                Qt.CheckState.Checked
                if sample.sample_id in self._checked
                else Qt.CheckState.Unchecked
            )
        if role == Qt.ItemDataRole.DisplayRole:
            if self._display_mode == "path":
                name = sample.output_path or sample.display_name
            elif self._display_mode == "filename":
                name = sample.display_name
            else:
                name = sample.case_id
            r_value = (sample.resistance_ohm or {}).get(sample.target_family)
            c_value = (sample.cio_pf or {}).get(sample.target_family)
            r_text = "—" if r_value is None else f"{r_value:g}Ω"
            c_text = "—" if c_value is None else f"{c_value:g}pF"
            case_suffix = "" if self._display_mode == "compact" else f"  |  {sample.case_id}"
            return f"{name}{case_suffix}  |  {sample.target_family}  R={r_text}  Cio={c_text}  |  {sample.nports}P"
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.CheckStateRole or not index.isValid():
            return False
        sample = self._visible[index.row()]
        if value == Qt.CheckState.Checked.value:
            self._checked.add(sample.sample_id)
        else:
            self._checked.discard(sample.sample_id)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        return True

    def set_catalog(self, catalog: SampleCatalog) -> None:
        self.beginResetModel()
        self._catalog = catalog
        available_ids = {sample.sample_id for sample in catalog.available}
        self._checked.intersection_update(available_ids)
        if not self._checked and catalog.available:
            self._checked.add(catalog.available[0].sample_id)
        self._rebuild()
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._catalog = None
        self._visible = []
        self._checked.clear()
        self.endResetModel()

    def set_query(self, query: str) -> None:
        self.beginResetModel()
        self._query = query.strip().lower()
        self._rebuild()
        self.endResetModel()

    def set_display_mode(self, mode: str) -> None:
        if mode not in {"compact", "filename", "path"}:
            raise ValueError(f"未知样本显示模式：{mode}")
        self._display_mode = mode
        if self._visible:
            self.dataChanged.emit(
                self.index(0), self.index(len(self._visible) - 1), [Qt.ItemDataRole.DisplayRole]
            )

    def _rebuild(self) -> None:
        source = self._catalog.available if self._catalog else ()
        self._visible = [
            sample
            for sample in source
            if not self._query
            or self._query
            in " ".join(
                (
                    sample.display_name,
                    sample.output_path or "",
                    sample.case_id,
                    sample.target_family,
                    sample.status,
                )
            ).lower()
        ]

    def set_all_checked(self, checked: bool) -> None:
        if checked:
            self._checked.update(sample.sample_id for sample in self._visible)
        else:
            self._checked.difference_update(sample.sample_id for sample in self._visible)
        if self._visible:
            self.dataChanged.emit(
                self.index(0), self.index(len(self._visible) - 1),
                [Qt.ItemDataRole.CheckStateRole],
            )

    def checked_samples(self):
        if not self._catalog:
            return ()
        return tuple(
            sample for sample in self._catalog.available if sample.sample_id in self._checked
        )

    @property
    def catalog(self) -> SampleCatalog | None:
        return self._catalog


class FrequencyPanel(QWidget):
    plot_requested = Signal()

    DISPLAY_LABELS = {
        "db": "幅值 (dB)",
        "magnitude": "线性幅值",
        "phase_deg": "相位 (deg)",
        "real": "实部",
        "imag": "虚部",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._plot_dialog: PlotDialog | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        controls_group = QGroupBox("频域设置")
        controls_group.setObjectName("frequencyControlsGroup")
        controls = QGridLayout(controls_group)
        controls.setColumnStretch(1, 1)
        controls.setColumnStretch(3, 1)
        self.tx_spin, self.rx_spin = QSpinBox(), QSpinBox()
        for spin in (self.tx_spin, self.rx_spin):
            spin.setRange(1, 9999)
            spin.setKeyboardTracking(False)
            spin.setMinimumWidth(64)
        self.rx_spin.setValue(2)
        self.parameter_combo = QComboBox()
        self.parameter_combo.addItems(["S", "VTF"])
        self.display_combo = QComboBox()
        for code, label in self.DISPLAY_LABELS.items():
            self.display_combo.addItem(label, code)
        self.auto_range = QCheckBox("频率自动范围")
        self.auto_range.setChecked(True)
        self.f_start = QDoubleSpinBox()
        self.f_stop = QDoubleSpinBox()
        for spin in (self.f_start, self.f_stop):
            spin.setRange(0.0, 1_000_000.0)
            spin.setDecimals(6)
            spin.setSuffix(" GHz")
            spin.setEnabled(False)
        self.f_stop.setValue(50.0)
        self.auto_range.toggled.connect(lambda checked: self._set_range_enabled(not checked))
        controls.addWidget(QLabel("Tx"), 0, 0)
        controls.addWidget(self.tx_spin, 0, 1)
        controls.addWidget(QLabel("Rx"), 0, 2)
        controls.addWidget(self.rx_spin, 0, 3)
        controls.addWidget(QLabel("参数"), 1, 0)
        controls.addWidget(self.parameter_combo, 1, 1)
        controls.addWidget(QLabel("显示"), 1, 2)
        controls.addWidget(self.display_combo, 1, 3)
        controls.addWidget(self.auto_range, 2, 0, 1, 4)
        controls.addWidget(QLabel("起点"), 3, 0)
        controls.addWidget(self.f_start, 3, 1, 1, 3)
        controls.addWidget(QLabel("终点"), 4, 0)
        controls.addWidget(self.f_stop, 4, 1, 1, 3)
        self.plot_button = QPushButton("绘制频域曲线")
        self.plot_button.clicked.connect(self.plot_requested)
        controls.addWidget(self.plot_button, 5, 0, 1, 4)
        self.status_label = QLabel("勾选样本并设置 Tx/Rx")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("frequencyStatusLabel")
        controls.addWidget(self.status_label, 6, 0, 1, 4)
        layout.addWidget(controls_group)
        layout.addStretch()

    def _set_range_enabled(self, enabled: bool) -> None:
        self.f_start.setEnabled(enabled)
        self.f_stop.setEnabled(enabled)

    def request(self) -> dict[str, object]:
        if not self.auto_range.isChecked() and self.f_stop.value() <= self.f_start.value():
            raise ValueError("频率终点必须大于起点")
        return {
            "tx_port": self.tx_spin.value(),
            "rx_port": self.rx_spin.value(),
            "parameter": self.parameter_combo.currentText(),
            "display_mode": str(self.display_combo.currentData()),
            "frequency_range": None if self.auto_range.isChecked() else (self.f_start.value(), self.f_stop.value()),
        }

    def set_busy(self, busy: bool) -> None:
        self.plot_button.setEnabled(not busy)
        self.status_label.setText("正在读取样本并生成频域曲线…" if busy else self.status_label.text())

    def set_traces(self, traces, frequency_range=None) -> None:
        traces = tuple(traces)
        if self._plot_dialog is None:
            self._plot_dialog = PlotDialog("频域曲线", self)
        figure = self._plot_dialog.figure
        figure.clear()
        axis = figure.add_subplot(1, 1, 1)
        for trace in traces:
            axis.plot(trace.frequency_ghz, trace.values, label=trace.label)
        axis.set_xlabel("频率 (GHz)")
        mode = traces[0].display_mode if traces else "db"
        axis.set_ylabel(self.DISPLAY_LABELS.get(mode, mode))
        title = "频域曲线"
        if traces:
            title = f"{traces[0].parameter}{traces[0].rx_port},{traces[0].tx_port} 频域曲线"
            axis.set_title(title)
        if frequency_range:
            axis.set_xlim(*frequency_range)
        axis.grid(True, alpha=0.25)
        if traces:
            axis.legend(fontsize=8, ncol=2)
        self.status_label.setText(f"已在独立窗口显示 {len(traces)} 个样本")
        self._plot_dialog.present(title)

    def clear(self) -> None:
        self.status_label.setText("勾选样本并设置 Tx/Rx")
        if self._plot_dialog is not None:
            self._plot_dialog.close()
            self._plot_dialog.figure.clear()


class TimePanel(QWidget):
    plot_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._plot_dialog: PlotDialog | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        controls_group = QGroupBox("时域设置")
        controls_group.setObjectName("timeControlsGroup")
        controls = QGridLayout(controls_group)
        controls.setColumnStretch(1, 1)
        controls.setColumnStretch(3, 1)
        self.tx_spin, self.rx_spin = QSpinBox(), QSpinBox()
        for spin in (self.tx_spin, self.rx_spin):
            spin.setRange(1, 9999)
            spin.setKeyboardTracking(False)
            spin.setMinimumWidth(64)
        self.rx_spin.setValue(2)
        self.ui_edit, self.rise_edit, self.dt_edit = QLineEdit("100"), QLineEdit("20"), QLineEdit("10")
        self.points_edit = QLineEdit("256")
        self.pre_edit, self.post_edit = QLineEdit("3"), QLineEdit("20")
        self.half_ui_edit = QLineEdit("0.1")
        for edit in (
            self.ui_edit, self.rise_edit, self.dt_edit, self.points_edit,
            self.pre_edit, self.post_edit, self.half_ui_edit,
        ):
            edit.setMinimumWidth(58)
        self.main_combo = QComboBox()
        self.main_combo.addItem("半高中心", "half_height_center")
        self.main_combo.addItem("绝对峰值", "peak")
        controls.addWidget(QLabel("Tx"), 0, 0)
        controls.addWidget(self.tx_spin, 0, 1)
        controls.addWidget(QLabel("Rx"), 0, 2)
        controls.addWidget(self.rx_spin, 0, 3)
        controls.addWidget(QLabel("UI (ps)"), 1, 0)
        controls.addWidget(self.ui_edit, 1, 1)
        controls.addWidget(QLabel("Rise (ps)"), 1, 2)
        controls.addWidget(self.rise_edit, 1, 3)
        controls.addWidget(QLabel("dt (ps)"), 2, 0)
        controls.addWidget(self.dt_edit, 2, 1)
        controls.addWidget(QLabel("FFT点数"), 2, 2)
        controls.addWidget(self.points_edit, 2, 3)
        controls.addWidget(QLabel("主光标"), 3, 0)
        controls.addWidget(self.main_combo, 3, 1, 1, 3)
        controls.addWidget(QLabel("前游标"), 4, 0)
        controls.addWidget(self.pre_edit, 4, 1)
        controls.addWidget(QLabel("后游标"), 4, 2)
        controls.addWidget(self.post_edit, 4, 3)
        controls.addWidget(QLabel("Noise窗口半宽 (UI)"), 5, 0, 1, 2)
        controls.addWidget(self.half_ui_edit, 5, 2)
        self.plot_button = QPushButton("生成时域波形")
        self.plot_button.clicked.connect(self.plot_requested)
        controls.addWidget(self.plot_button, 5, 3)
        self.status_label = QLabel("波形会按样本指纹、Tx/Rx和设置自动缓存")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("timeStatusLabel")
        controls.addWidget(self.status_label, 6, 0, 1, 4)
        layout.addWidget(controls_group)
        layout.addStretch()

    def request(self) -> tuple[int, int, TimeDomainSettings]:
        try:
            settings = TimeDomainSettings(
                float(self.ui_edit.text()), float(self.rise_edit.text()), float(self.dt_edit.text()),
                int(self.points_edit.text()), str(self.main_combo.currentData()),
                int(self.pre_edit.text()), int(self.post_edit.text()), float(self.half_ui_edit.text()),
            )
        except ValueError as exc:
            raise ValueError("时域参数必须为数字") from exc
        SNRAnalysisService.validate_settings(settings)
        return self.tx_spin.value(), self.rx_spin.value(), settings

    def set_busy(self, busy: bool) -> None:
        self.plot_button.setEnabled(not busy)
        self.status_label.setText("正在生成并缓存时域波形…" if busy else self.status_label.text())

    def set_waveforms(self, waveforms) -> None:
        waveforms = tuple(waveforms)
        if self._plot_dialog is None:
            self._plot_dialog = PlotDialog("时域波形", self)
        figure = self._plot_dialog.figure
        figure.clear()
        axis = figure.add_subplot(1, 1, 1)
        for result in waveforms:
            axis.plot(result.time_ps, result.waveform, label=result.label)
        axis.set_xlabel("时间 (ps)")
        axis.set_ylabel("响应")
        title = "时域波形"
        if waveforms:
            title = f"S{waveforms[0].rx_port},{waveforms[0].tx_port} 时域波形"
            axis.set_title(title)
        axis.grid(True, alpha=0.25)
        if waveforms:
            axis.legend(fontsize=8, ncol=2)
        cached = sum(result.cache_path is not None for result in waveforms)
        self.status_label.setText(
            f"已在独立窗口显示 {len(waveforms)} 个样本；{cached} 个已持久化缓存"
        )
        self._plot_dialog.present(title)

    def clear(self) -> None:
        self.status_label.setText("波形会按样本指纹、Tx/Rx和设置自动缓存")
        if self._plot_dialog is not None:
            self._plot_dialog.close()
            self._plot_dialog.figure.clear()


class SampleWorkspacePage(QWidget):
    frequency_requested = Signal(object, object)
    time_requested = Signal(object, object)
    catalog_open_requested = Signal(str)
    clear_cache_requested = Signal(str)
    visibility_requested = Signal(object, bool)
    open_workspace_requested = Signal(str)
    checked_samples_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.workspace_splitter = QSplitter(Qt.Orientation.Vertical)
        self.workspace_splitter.setObjectName("sampleWorkspaceSplitter")
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setHandleWidth(6)
        self.sample_group = QGroupBox("生成的 S 参数样本")
        self.sample_group.setObjectName("generatedSamplesGroup")
        sample_layout = QVBoxLayout(self.sample_group)
        toolbar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("按文件名、case、family或状态筛选")
        self.display_combo = QComboBox()
        self.display_combo.addItem("简洁", "compact")
        self.display_combo.addItem("文件名", "filename")
        self.display_combo.addItem("完整路径", "path")
        self.select_all_button = QPushButton("勾选全部")
        self.clear_selection_button = QPushButton("取消勾选")
        self.open_catalog_button = QPushButton("打开运行")
        self.open_workspace_button = QPushButton("打开目录")
        self.hide_checked_button = QPushButton("移出列表")
        self.restore_hidden_button = QPushButton("恢复隐藏")
        self.clear_cache_button = QPushButton("清理派生缓存")
        for widget in (
            QLabel("筛选"), self.search_edit, self.display_combo,
            self.open_catalog_button, self.open_workspace_button,
        ):
            toolbar.addWidget(widget)
        sample_layout.addLayout(toolbar)
        actions = QHBoxLayout()
        for widget in (
            self.select_all_button, self.clear_selection_button,
            self.hide_checked_button, self.restore_hidden_button,
            self.clear_cache_button,
        ):
            actions.addWidget(widget)
        actions.addStretch()
        sample_layout.addLayout(actions)
        self.model = SampleListModel(self)
        self.sample_list = QListView()
        self.sample_list.setObjectName("generatedSampleList")
        self.sample_list.setModel(self.model)
        self.sample_list.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.sample_list.setUniformItemSizes(True)
        sample_layout.addWidget(self.sample_list)
        self.sample_summary = QLabel("尚无生成样本")
        sample_layout.addWidget(self.sample_summary)
        self.workspace_splitter.addWidget(self.sample_group)

        self.tabs = QTabWidget()
        self.frequency_panel = FrequencyPanel()
        self.time_panel = TimePanel()
        self.tabs.addTab(self.frequency_panel, "频域")
        self.tabs.addTab(self.time_panel, "时域")
        self.workspace_splitter.addWidget(self.tabs)
        self.workspace_splitter.setStretchFactor(0, 2)
        self.workspace_splitter.setStretchFactor(1, 1)
        self.workspace_splitter.setSizes([650, 350])
        layout.addWidget(self.workspace_splitter, stretch=1)

        self.search_edit.textChanged.connect(self.model.set_query)
        self.display_combo.currentIndexChanged.connect(
            lambda _index: self.model.set_display_mode(
                str(self.display_combo.currentData())
            )
        )
        self.select_all_button.clicked.connect(lambda: self._set_all_checked(True))
        self.clear_selection_button.clicked.connect(lambda: self._set_all_checked(False))
        self.open_catalog_button.clicked.connect(self._choose_catalog)
        self.open_workspace_button.clicked.connect(self._request_open_workspace)
        self.hide_checked_button.clicked.connect(self._request_hide_checked)
        self.restore_hidden_button.clicked.connect(self._request_restore_hidden)
        self.clear_cache_button.clicked.connect(self._request_clear_cache)
        self.frequency_panel.plot_requested.connect(self._request_frequency)
        self.time_panel.plot_requested.connect(self._request_time)
        self.model.dataChanged.connect(lambda *_args: self._emit_checked_samples())

    def set_catalog(self, catalog: SampleCatalog) -> None:
        self.model.set_catalog(catalog)
        self.sample_summary.setText(
            f"可用 {len(catalog.available)} / 共 {len(catalog.samples)} 个样本；run={catalog.run_id[:8]}"
        )
        max_ports = max((sample.nports for sample in catalog.available), default=1)
        for spin in (
            self.frequency_panel.tx_spin, self.frequency_panel.rx_spin,
            self.time_panel.tx_spin, self.time_panel.rx_spin,
        ):
            spin.setMaximum(max_ports)
        self._emit_checked_samples()

    def clear(self) -> None:
        self.model.clear()
        self.sample_summary.setText("尚无生成样本")
        self.frequency_panel.clear()
        self.time_panel.clear()
        self._emit_checked_samples()

    def _emit_checked_samples(self) -> None:
        self.checked_samples_changed.emit(
            {sample.sample_id for sample in self.model.checked_samples()}
        )

    def _set_all_checked(self, checked: bool) -> None:
        self.model.set_all_checked(checked)
        self._emit_checked_samples()

    def _request_frequency(self) -> None:
        samples = self.model.checked_samples()
        if not samples:
            self.frequency_panel.status_label.setText("请至少勾选一个样本")
            return
        try:
            request = self.frequency_panel.request()
        except ValueError as exc:
            self.frequency_panel.status_label.setText(str(exc))
            return
        self.frequency_requested.emit(samples, request)

    def _request_time(self) -> None:
        samples = self.model.checked_samples()
        if not samples:
            self.time_panel.status_label.setText("请至少勾选一个样本")
            return
        try:
            tx_port, rx_port, settings = self.time_panel.request()
        except ValueError as exc:
            self.time_panel.status_label.setText(str(exc))
            return
        self.time_requested.emit(samples, (tx_port, rx_port, settings))

    def _choose_catalog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开 Quick_TDSNR 运行", "", "样本目录 (sample_catalog.json)"
        )
        if path:
            self.catalog_open_requested.emit(path)

    def _request_clear_cache(self) -> None:
        catalog = self.model.catalog
        if catalog and catalog.workspace_path:
            self.clear_cache_requested.emit(catalog.workspace_path)

    def _request_hide_checked(self) -> None:
        samples = self.model.checked_samples()
        if samples:
            self.visibility_requested.emit(
                {sample.sample_id for sample in samples}, False
            )

    def _request_restore_hidden(self) -> None:
        catalog = self.model.catalog
        if catalog:
            hidden = {sample.sample_id for sample in catalog.samples if not sample.visible}
            if hidden:
                self.visibility_requested.emit(hidden, True)

    def _request_open_workspace(self) -> None:
        catalog = self.model.catalog
        if catalog and catalog.workspace_path:
            self.open_workspace_requested.emit(catalog.workspace_path)
