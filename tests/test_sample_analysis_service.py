from __future__ import annotations

import numpy as np
import skrf as rf

from quick_tdsnr.domain.project_models import SampleRecord, TimeDomainSettings
from quick_tdsnr.services.sample_analysis_service import SampleAnalysisService


def _network(scale: float = 1.0) -> rf.Network:
    frequency = rf.Frequency(0, 10, 11, unit="GHz")
    s = np.zeros((11, 2, 2), dtype=complex)
    s[:, 1, 0] = scale * (0.5 + 0.1j)
    return rf.Network(frequency=frequency, s=s, z0=50.0)


def _sample(index: int) -> SampleRecord:
    return SampleRecord(
        f"sample-{index}", "run", "input.s2p", "input-hash", f"C{index}",
        "family2", (1, 2), "in_memory",
    )


def test_frequency_trace_and_lru_are_bounded_for_many_samples():
    service = SampleAnalysisService(max_cached_networks=3)
    memory = {}
    samples = [_sample(index) for index in range(50)]
    for index, sample in enumerate(samples):
        memory[(sample.input_path, sample.case_id)] = _network(1.0 + index / 100.0)
        trace = service.frequency_trace(
            sample, 1, 2, parameter="S", display_mode="db", in_memory=memory
        )
        assert trace.values.shape == (11,)
    assert service.networks.size == 3
    expected = 20 * np.log10(abs((1.49) * (0.5 + 0.1j)))
    assert np.allclose(trace.values, expected)


def test_time_waveform_is_persisted_and_reused(tmp_path, monkeypatch):
    service = SampleAnalysisService()
    sample = _sample(1)
    memory = {(sample.input_path, sample.case_id): _network()}
    settings = TimeDomainSettings(100.0, 20.0, 10.0, 256)
    first = service.time_waveform(
        sample, 1, 2, settings, cache_dir=tmp_path, in_memory=memory
    )
    assert first.cache_path.is_file()

    def fail_if_recomputed(*_args, **_kwargs):
        raise AssertionError("缓存命中后不应重新计算")

    monkeypatch.setattr(
        "quick_tdsnr.services.sample_analysis_service.SNRAnalysisService.pulse_waveform",
        fail_if_recomputed,
    )
    second = service.time_waveform(
        sample, 1, 2, settings, cache_dir=tmp_path, in_memory=memory
    )
    assert np.array_equal(second.time_ps, first.time_ps)
    assert np.array_equal(second.waveform, first.waveform)
    assert second.cache_path == first.cache_path


def test_aggregate_statistics_reports_percentiles():
    class Result:
        def __init__(self, value):
            self.signal = value
            self.direct_noise = value + 1
            self.xtalk_noise = value + 2
            self.total_noise = value + 3
            self.snr = value + 4

    summary = SampleAnalysisService.aggregate_statistics([Result(1.0), Result(3.0)])
    assert summary["signal"]["mean"] == 2.0
    assert summary["signal"]["p50"] == 2.0
    assert summary["snr"]["max"] == 7.0

