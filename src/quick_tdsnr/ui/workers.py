"""耗时服务的 Qt worker。"""

from __future__ import annotations

from qtpy.QtCore import QThread, Signal

from quick_tdsnr.services.input_preflight_service import InputPreflightService
from quick_tdsnr.services.topology_inference_service import TopologyInferenceService
from quick_tdsnr.services.renormalization_job import RenormalizationJob
from quick_tdsnr.services.pipeline_service import PipelineService
from quick_tdsnr.services.sample_analysis_service import SampleAnalysisService


class TopologyAnalysisWorker(QThread):
    progress = Signal(str)
    completed = Signal(object, object)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, request: dict, parent=None) -> None:
        super().__init__(parent)
        self.request = dict(request)

    def run(self) -> None:
        try:
            self.progress.emit("正在读取 Touchstone 文件…")
            preflight = InputPreflightService()
            batch = preflight.inspect_files(
                self.request["paths"], should_cancel=self.isInterruptionRequested
            )
            if batch.errors:
                details = "；".join(f"{path}: {error}" for path, error in batch.errors.items())
                raise ValueError(f"文件预检失败：{details}")
            if not batch.compatible:
                raise ValueError("输入文件不兼容，请检查端口数和预检告警。")
            if self.isInterruptionRequested():
                raise RuntimeError("拓扑识别已取消")
            self.progress.emit("正在比较 S/Y/Z 拓扑…")
            analysis = TopologyInferenceService().analyse(
                preflight.network_map(batch),
                low_freq_ghz=float(self.request["low_freq_ghz"]),
                min_cliff_db=self.request.get("min_cliff_db"),
                should_cancel=self.isInterruptionRequested,
            )
            self.completed.emit(batch, analysis)
        except Exception as exc:
            if self.isInterruptionRequested():
                self.cancelled.emit("拓扑识别已取消")
            else:
                self.failed.emit(str(exc))


class RenormalizationWorker(QThread):
    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, config, plan, output_dir: str, write_outputs: bool, parent=None):
        super().__init__(parent)
        self.config = config
        self.plan = plan
        self.output_dir = output_dir
        self.write_outputs = write_outputs

    def run(self) -> None:
        try:
            run = RenormalizationJob().run(
                self.config,
                self.plan,
                output_dir=self.output_dir if self.write_outputs else None,
                write_outputs=self.write_outputs,
                keep_networks=not self.write_outputs,
                workspace_layout=self.write_outputs,
                should_cancel=self.isInterruptionRequested,
                on_progress=self.progress.emit,
            )
            if self.isInterruptionRequested() and run.manifest.cancelled:
                self.cancelled.emit("重归一化已取消")
            self.completed.emit(run)
        except Exception as exc:
            if self.isInterruptionRequested():
                self.cancelled.emit("重归一化已取消")
            else:
                self.failed.emit(str(exc))


class SNRWorker(QThread):
    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, run, settings, output_dir: str, parent=None):
        super().__init__(parent)
        self.run_data = run
        self.settings = settings
        self.output_dir = output_dir

    def run(self) -> None:
        try:
            def report(done, total, case_id):
                self.progress.emit((done, total, case_id))

            result = PipelineService().analyse_run(
                self.run_data,
                self.settings,
                should_cancel=self.isInterruptionRequested,
                on_progress=report,
            )
            if self.isInterruptionRequested():
                self.cancelled.emit("时域 SNR 已取消")
            destination = (
                self.run_data.workspace_path / "derived"
                if self.run_data.workspace_path is not None
                else self.output_dir
            )
            self.completed.emit(PipelineService.export(result, destination))
        except Exception as exc:
            if self.isInterruptionRequested():
                self.cancelled.emit("时域 SNR 已取消")
            else:
                self.failed.emit(str(exc))


class FrequencyAnalysisWorker(QThread):
    progress = Signal(object)
    completed = Signal(object, object)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, service, samples, request, in_memory=None, parent=None):
        super().__init__(parent)
        self.service = service
        self.samples = tuple(samples)
        self.request = dict(request)
        self.in_memory = in_memory or {}

    def run(self) -> None:
        traces = []
        try:
            for index, sample in enumerate(self.samples, start=1):
                if self.isInterruptionRequested():
                    self.cancelled.emit("频域绘图已取消")
                    return
                traces.append(
                    self.service.frequency_trace(
                        sample,
                        int(self.request["tx_port"]),
                        int(self.request["rx_port"]),
                        parameter=str(self.request["parameter"]),
                        display_mode=str(self.request["display_mode"]),
                        in_memory=self.in_memory,
                    )
                )
                self.progress.emit((index, len(self.samples), sample.display_name))
            self.completed.emit(tuple(traces), self.request)
        except Exception as exc:
            self.failed.emit(str(exc))


class TimeWaveformWorker(QThread):
    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(
        self,
        service: SampleAnalysisService,
        samples,
        tx_port: int,
        rx_port: int,
        settings,
        cache_dir,
        in_memory=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.samples = tuple(samples)
        self.tx_port = tx_port
        self.rx_port = rx_port
        self.settings = settings
        self.cache_dir = cache_dir
        self.in_memory = in_memory or {}

    def run(self) -> None:
        waveforms = []
        try:
            for index, sample in enumerate(self.samples, start=1):
                if self.isInterruptionRequested():
                    self.cancelled.emit("时域波形生成已取消")
                    return
                waveforms.append(
                    self.service.time_waveform(
                        sample,
                        self.tx_port,
                        self.rx_port,
                        self.settings,
                        cache_dir=self.cache_dir,
                        in_memory=self.in_memory,
                    )
                )
                self.progress.emit((index, len(self.samples), sample.display_name))
            self.completed.emit(tuple(waveforms))
        except Exception as exc:
            self.failed.emit(str(exc))
