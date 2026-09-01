"""VTF 时域与 cursor 参数配置页。"""

from __future__ import annotations

from qtpy.QtCore import Signal
from qtpy.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from quick_tdsnr.domain.project_models import TimeDomainDraft, TimeDomainSettings
from quick_tdsnr.services.snr_analysis_service import SNRAnalysisService


class TimeDomainPage(QWidget):
    settings_confirmed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("时域与 SNR")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(heading)
        layout.addWidget(QLabel("设置 VTF→irFFT→脉冲响应和 main/pre/post cursor 搜索参数。"))
        group = QGroupBox("时域参数")
        form = QFormLayout(group)
        self.ui_edit, self.rise_edit, self.dt_edit = QLineEdit("100"), QLineEdit("20"), QLineEdit("10")
        self.points_edit, self.pre_edit, self.post_edit = QLineEdit("256"), QLineEdit("3"), QLineEdit("20")
        self.half_ui_edit = QLineEdit("0.1")
        self.main_combo = QComboBox()
        self.main_combo.addItem("半高中心", "half_height_center")
        self.main_combo.addItem("绝对峰值", "peak")
        for label, widget in (("数据 UI (ps)", self.ui_edit), ("上升时间 (ps)", self.rise_edit),
                              ("时间步长 dt (ps)", self.dt_edit), ("FFT 点数", self.points_edit),
                              ("main cursor 方法", self.main_combo), ("pre cursor 数", self.pre_edit),
                              ("post cursor 数", self.post_edit), ("Noise 窗口半宽 (UI)", self.half_ui_edit)):
            form.addRow(label, widget)
        layout.addWidget(group)
        self.status_label = QLabel("请检查参数")
        self.status_label.setObjectName("timeDomainSettingsStatus")
        layout.addWidget(self.status_label)
        self.confirm_button = QPushButton("确认时域与 SNR 参数")
        self.confirm_button.clicked.connect(self._emit_settings)
        self.confirm_button.setVisible(False)
        layout.addWidget(self.confirm_button)
        layout.addStretch()

    def settings(self) -> TimeDomainSettings:
        try:
            settings = TimeDomainSettings(float(self.ui_edit.text()), float(self.rise_edit.text()), float(self.dt_edit.text()),
                                          int(self.points_edit.text()), str(self.main_combo.currentData()),
                                          int(self.pre_edit.text()), int(self.post_edit.text()), float(self.half_ui_edit.text()))
        except ValueError as exc:
            raise ValueError("时域参数必须为数字") from exc
        SNRAnalysisService.validate_settings(settings)
        return settings

    def draft(self) -> TimeDomainDraft:
        return TimeDomainDraft(
            ui_text=self.ui_edit.text(),
            rise_text=self.rise_edit.text(),
            dt_text=self.dt_edit.text(),
            points_text=self.points_edit.text(),
            main_method=str(self.main_combo.currentData()),
            pre_text=self.pre_edit.text(),
            post_text=self.post_edit.text(),
            half_ui_text=self.half_ui_edit.text(),
        )

    def load_draft(self, draft: TimeDomainDraft) -> None:
        self.ui_edit.setText(draft.ui_text)
        self.rise_edit.setText(draft.rise_text)
        self.dt_edit.setText(draft.dt_text)
        self.points_edit.setText(draft.points_text)
        self.pre_edit.setText(draft.pre_text)
        self.post_edit.setText(draft.post_text)
        self.half_ui_edit.setText(draft.half_ui_text)
        index = self.main_combo.findData(draft.main_method)
        self.main_combo.setCurrentIndex(max(0, index))

    def is_valid(self) -> bool:
        try:
            self.settings()
        except ValueError:
            return False
        return True

    def _emit_settings(self) -> None:
        try:
            settings = self.settings()
        except ValueError as exc:
            self.status_label.setText(str(exc))
            self.status_label.setStyleSheet("color: #b45f06;")
            return
        self.status_label.setText("时域与 SNR 参数已确认")
        self.status_label.setStyleSheet("color: #268447;")
        self.settings_confirmed.emit(settings)
