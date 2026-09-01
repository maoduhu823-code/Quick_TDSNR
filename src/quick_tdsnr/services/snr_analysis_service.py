"""1 驱41 时域响应、cursor 和并行线 SNR 分析。"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import skrf as rf
from sipi_sparam_core.snr import (
    MAIN_CURSOR_METHODS,
    WindowPeak,
    combine_noise,
    find_main_cursor,
    find_window_peak,
    make_cursor_times,
)
from sipi_sparam_core.time_response import pulse_response_from_transfer
from sipi_sparam_core.transfer import network_voltage_transfer

from quick_tdsnr.domain.project_models import (
    AggressorSNRResult,
    LineEndpoint,
    TimeDomainSettings,
    VictimSNRResult,
)


ALGORITHM_VERSION = "parallel_sparam_snr_v1"


class SNRAnalysisService:
    @staticmethod
    def validate_settings(settings: TimeDomainSettings) -> None:
        values = (settings.ui_ps, settings.rise_time_ps, settings.dt_ps)
        if any(not math.isfinite(value) or value <= 0 for value in values):
            raise ValueError("ui、rise_time、dt 必须为有限正数")
        if int(settings.n_points) < 4:
            raise ValueError("n_points 必须不小于 4")
        if settings.main_method not in MAIN_CURSOR_METHODS:
            raise ValueError(f"未知 main cursor 方法：{settings.main_method}")
        if settings.num_pre < 0 or settings.num_post < 0:
            raise ValueError("pre/post cursor 数量不能为负数")
        if not math.isfinite(settings.noise_window_half_ui) or not 0 <= settings.noise_window_half_ui < 0.5:
            raise ValueError("noise_window_half_ui 必须满足 0 <= value < 0.5")

    @staticmethod
    def _pulse(network: rf.Network, tx_port: int, rx_port: int, settings: TimeDomainSettings):
        if not 1 <= tx_port <= network.nports or not 1 <= rx_port <= network.nports:
            raise ValueError(f"端口越界：VTF{rx_port},{tx_port}")
        transfer = network_voltage_transfer(network, rx_port, tx_port)
        return pulse_response_from_transfer(
            np.asarray(network.f, dtype=float),
            transfer,
            ui_ps=settings.ui_ps,
            rise_time_ps=settings.rise_time_ps,
            dt_ps=settings.dt_ps,
            n_points=settings.n_points,
        )

    def pulse_waveform(
        self,
        network: rf.Network,
        tx_port: int,
        rx_port: int,
        settings: TimeDomainSettings,
    ):
        """为样本工作台生成任意 Tx/Rx 的时域波形。"""
        self.validate_settings(settings)
        time_ps, waveform = self._pulse(network, tx_port, rx_port, settings)
        return (
            np.asarray(time_ps, dtype=float),
            np.asarray(waveform, dtype=float),
        )

    def analyse_victim(
        self,
        network: rf.Network,
        victim: LineEndpoint,
        aggressors: Iterable[LineEndpoint],
        settings: TimeDomainSettings,
    ) -> VictimSNRResult:
        self.validate_settings(settings)
        time_ps, direct = self._pulse(network, victim.tx_port, victim.rx_port, settings)
        main_idx = find_main_cursor(direct, settings.main_method)
        main_time_ps = float(time_ps[main_idx])
        signal = abs(float(direct[main_idx]))
        cursor_times = make_cursor_times(
            main_time_ps, settings.ui_ps, settings.num_pre, settings.num_post
        )
        half_width_ps = settings.noise_window_half_ui * settings.ui_ps
        direct_peaks = tuple(
            find_window_peak(time_ps, direct, delta, center, half_width_ps)
            for delta, center in cursor_times.items()
            if delta != 0
        )
        aggressor_results: list[AggressorSNRResult] = []
        aggressor_waveforms: dict[int, np.ndarray] = {}
        for aggressor in aggressors:
            _, waveform = self._pulse(network, aggressor.tx_port, victim.rx_port, settings)
            peaks = tuple(
                find_window_peak(time_ps, waveform, delta, center, half_width_ps)
                for delta, center in cursor_times.items()
            )
            aggressor_results.append(
                AggressorSNRResult(
                    line=aggressor.line,
                    name=aggressor.name,
                    tx_port=aggressor.tx_port,
                    rx_port=victim.rx_port,
                    transfer_function=f"VTF{victim.rx_port},{aggressor.tx_port}",
                    noise=float(sum(peak.abs_value for peak in peaks)),
                    cursor_peaks=peaks,
                )
            )
            aggressor_waveforms[aggressor.line] = waveform
        direct_noise, xtalk_noise, total_noise, snr = combine_noise(
            signal,
            (peak.abs_value for peak in direct_peaks),
            ([peak.abs_value for peak in result.cursor_peaks] for result in aggressor_results),
        )
        warnings = tuple(self.frequency_coverage_warnings(network, settings.dt_ps))
        return VictimSNRResult(
            line=victim.line,
            name=victim.name,
            tx_port=victim.tx_port,
            rx_port=victim.rx_port,
            transfer_function=f"VTF{victim.rx_port},{victim.tx_port}",
            main_method=settings.main_method,
            main_index=main_idx,
            main_time_ps=main_time_ps,
            signal=signal,
            direct_noise=direct_noise,
            xtalk_noise=xtalk_noise,
            total_noise=total_noise,
            snr=snr,
            cursor_times_ps=cursor_times,
            direct_cursor_peaks=direct_peaks,
            aggressors=tuple(aggressor_results),
            time_ps=time_ps,
            direct_waveform=direct,
            aggressor_waveforms=aggressor_waveforms,
            warnings=warnings,
        )

    @staticmethod
    def frequency_coverage_warnings(network: rf.Network, dt_ps: float) -> list[str]:
        target_fmax = 1.0 / (2.0 * dt_ps * 1e-12)
        source_fmax = float(network.f[-1])
        if target_fmax > source_fmax * 1.001:
            return [
                f"目标 Nyquist 频率 {target_fmax / 1e9:.3f} GHz 高于文件最高频率 "
                f"{source_fmax / 1e9:.3f} GHz，将发生高频外推"
            ]
        if target_fmax < source_fmax * 0.95:
            return [
                f"目标 Nyquist 频率 {target_fmax / 1e9:.3f} GHz 低于文件最高频率 "
                f"{source_fmax / 1e9:.3f} GHz，高频数据不会进入时域结果"
            ]
        return []
