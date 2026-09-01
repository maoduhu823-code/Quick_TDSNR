"""样本工作台的按需 Network、频域曲线和时域派生缓存。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import uuid

import numpy as np
import skrf as rf
from sipi_sparam_core.touchstone_io import apply_port_name_patch, apply_qs_s_def_patch
from sipi_sparam_core.transfer import network_voltage_transfer

from quick_tdsnr.domain.project_models import (
    FrequencyTrace,
    SampleRecord,
    TimeDomainSettings,
    TimeWaveformResult,
)
from quick_tdsnr.services.snr_analysis_service import ALGORITHM_VERSION, SNRAnalysisService


class NetworkLRUCache:
    """只保留最近使用的少量 Network，避免样本数决定常驻内存。"""

    def __init__(self, max_items: int = 3) -> None:
        if max_items < 1:
            raise ValueError("Network缓存数量必须大于0")
        self.max_items = int(max_items)
        self._items: OrderedDict[str, rf.Network] = OrderedDict()
        self._verified_files: dict[str, tuple[int, int]] = {}

    @staticmethod
    def _load(path: str) -> rf.Network:
        network = rf.Network(path)
        apply_qs_s_def_patch(network, path)
        apply_port_name_patch(network, path)
        return network

    def get(
        self,
        sample: SampleRecord,
        in_memory: dict[tuple[str, str], object] | None = None,
    ) -> rf.Network:
        key = sample.output_sha256 or sample.sample_id
        memory_key = (sample.input_path, sample.case_id)
        if not (in_memory and memory_key in in_memory) and sample.output_path:
            path = Path(sample.output_path)
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            if sample.output_sha256 and self._verified_files.get(key) != signature:
                with path.open("rb") as handle:
                    actual = hashlib.file_digest(handle, "sha256").hexdigest()
                if actual != sample.output_sha256:
                    self.invalidate(sample)
                    raise ValueError(f"样本文件指纹已变化：{path.name}")
                self._verified_files[key] = signature
        cached = self._items.pop(key, None)
        if cached is not None:
            self._items[key] = cached
            return cached
        if in_memory and memory_key in in_memory:
            network = in_memory[memory_key]
        elif sample.output_path:
            network = self._load(sample.output_path)
        else:
            raise ValueError(f"样本没有可读取的数据：{sample.display_name}")
        self._items[key] = network
        while len(self._items) > self.max_items:
            self._items.popitem(last=False)
        return network

    def clear(self) -> None:
        self._items.clear()
        self._verified_files.clear()

    def invalidate(self, sample: SampleRecord) -> None:
        key = sample.output_sha256 or sample.sample_id
        self._items.pop(key, None)
        self._verified_files.pop(key, None)

    @property
    def size(self) -> int:
        return len(self._items)


class SampleAnalysisService:
    DISPLAY_MODES = ("db", "magnitude", "phase_deg", "real", "imag")
    PARAMETERS = ("S", "VTF")

    def __init__(self, *, max_cached_networks: int = 3) -> None:
        self.networks = NetworkLRUCache(max_cached_networks)

    @staticmethod
    def _validate_ports(network: rf.Network, tx_port: int, rx_port: int) -> None:
        if not 1 <= tx_port <= network.nports or not 1 <= rx_port <= network.nports:
            raise ValueError(
                f"端口越界：Tx={tx_port}, Rx={rx_port}，样本端口数={network.nports}"
            )

    def frequency_trace(
        self,
        sample: SampleRecord,
        tx_port: int,
        rx_port: int,
        *,
        parameter: str = "S",
        display_mode: str = "db",
        in_memory: dict[tuple[str, str], object] | None = None,
    ) -> FrequencyTrace:
        network = self.networks.get(sample, in_memory)
        self._validate_ports(network, tx_port, rx_port)
        parameter = parameter.upper()
        if parameter not in self.PARAMETERS:
            raise ValueError(f"不支持的频域参数：{parameter}")
        if display_mode not in self.DISPLAY_MODES:
            raise ValueError(f"不支持的显示方式：{display_mode}")
        if parameter == "S":
            complex_values = np.asarray(
                network.s[:, rx_port - 1, tx_port - 1], dtype=complex
            )
        else:
            complex_values = np.asarray(
                network_voltage_transfer(network, rx_port, tx_port), dtype=complex
            )
        if display_mode == "db":
            values = 20.0 * np.log10(np.maximum(np.abs(complex_values), 1e-20))
        elif display_mode == "magnitude":
            values = np.abs(complex_values)
        elif display_mode == "phase_deg":
            values = np.unwrap(np.angle(complex_values)) * 180.0 / np.pi
        elif display_mode == "real":
            values = complex_values.real
        else:
            values = complex_values.imag
        return FrequencyTrace(
            sample_id=sample.sample_id,
            label=sample.display_name,
            tx_port=tx_port,
            rx_port=rx_port,
            parameter=parameter,
            display_mode=display_mode,
            frequency_ghz=np.asarray(network.f, dtype=float) / 1e9,
            values=np.asarray(values, dtype=float),
        )

    @staticmethod
    def settings_hash(settings: TimeDomainSettings) -> str:
        payload = {
            "algorithm_version": ALGORITHM_VERSION,
            "settings": asdict(settings),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _waveform_cache_path(
        sample: SampleRecord,
        tx_port: int,
        rx_port: int,
        settings_hash: str,
        cache_dir: str | Path | None,
    ) -> Path | None:
        if cache_dir is None:
            return None
        source_key = sample.output_sha256 or sample.sample_id
        key = hashlib.sha256(
            f"{source_key}\0{tx_port}\0{rx_port}\0{settings_hash}".encode()
        ).hexdigest()[:24]
        return Path(cache_dir).expanduser().resolve() / f"waveform_{key}.npz"

    @staticmethod
    def _write_waveform(path: Path, time_ps: np.ndarray, waveform: np.ndarray) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("wb") as handle:
                np.savez_compressed(handle, time_ps=time_ps, waveform=waveform)
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def time_waveform(
        self,
        sample: SampleRecord,
        tx_port: int,
        rx_port: int,
        settings: TimeDomainSettings,
        *,
        cache_dir: str | Path | None = None,
        in_memory: dict[tuple[str, str], object] | None = None,
    ) -> TimeWaveformResult:
        settings_hash = self.settings_hash(settings)
        cache_path = self._waveform_cache_path(
            sample, tx_port, rx_port, settings_hash, cache_dir
        )
        if cache_path and cache_path.is_file():
            try:
                with np.load(cache_path, allow_pickle=False) as cached:
                    time_ps = np.asarray(cached["time_ps"], dtype=float)
                    waveform = np.asarray(cached["waveform"], dtype=float)
                return TimeWaveformResult(
                    sample.sample_id,
                    sample.display_name,
                    tx_port,
                    rx_port,
                    settings_hash,
                    time_ps,
                    waveform,
                    cache_path=cache_path,
                )
            except (OSError, ValueError, KeyError):
                cache_path.unlink(missing_ok=True)
        network = self.networks.get(sample, in_memory)
        self._validate_ports(network, tx_port, rx_port)
        time_ps, waveform = SNRAnalysisService().pulse_waveform(
            network, tx_port, rx_port, settings
        )
        warnings = tuple(SNRAnalysisService.frequency_coverage_warnings(network, settings.dt_ps))
        if cache_path:
            self._write_waveform(cache_path, time_ps, waveform)
        return TimeWaveformResult(
            sample.sample_id,
            sample.display_name,
            tx_port,
            rx_port,
            settings_hash,
            time_ps,
            waveform,
            warnings,
            cache_path,
        )

    @staticmethod
    def aggregate_statistics(results) -> dict[str, dict[str, float]]:
        metrics = {
            "signal": [item.signal for item in results],
            "direct_noise": [item.direct_noise for item in results],
            "xtalk_noise": [item.xtalk_noise for item in results],
            "total_noise": [item.total_noise for item in results],
            "snr": [item.snr for item in results],
            "snr_db": [
                20.0 * np.log10(item.snr) if item.snr > 0 else -np.inf
                for item in results
            ],
        }
        summary: dict[str, dict[str, float]] = {}
        for name, raw_values in metrics.items():
            values = np.asarray(raw_values, dtype=float)
            if not values.size:
                continue
            summary[name] = {
                "count": float(values.size),
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "p5": float(np.percentile(values, 5)),
                "p50": float(np.percentile(values, 50)),
                "p95": float(np.percentile(values, 95)),
                "max": float(np.max(values)),
            }
        return summary

    @staticmethod
    def aggregate_aggressors(results) -> dict[tuple[int, int], dict[str, float]]:
        grouped: dict[tuple[int, int], list[float]] = {}
        for result in results:
            for aggressor in result.aggressors:
                grouped.setdefault((result.line, aggressor.line), []).append(
                    float(aggressor.noise)
                )
        summary: dict[tuple[int, int], dict[str, float]] = {}
        for key, raw_values in grouped.items():
            values = np.asarray(raw_values, dtype=float)
            summary[key] = {
                "count": float(values.size),
                "mean": float(np.mean(values)),
                "min": float(np.min(values)),
                "p50": float(np.percentile(values, 50)),
                "p95": float(np.percentile(values, 95)),
                "max": float(np.max(values)),
            }
        return summary
