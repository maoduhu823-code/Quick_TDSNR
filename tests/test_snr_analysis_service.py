from __future__ import annotations

import numpy as np
import pytest
import skrf as rf

from quick_tdsnr.domain.project_models import LineEndpoint, TimeDomainSettings
from quick_tdsnr.services.snr_analysis_service import SNRAnalysisService


def _network() -> rf.Network:
    frequency = rf.Frequency(0, 10, 11, unit="GHz")
    s = np.zeros((11, 4, 4), dtype=complex)
    s[:, 1, 0] = 0.8
    s[:, 1, 2] = 0.1
    s[:, 1, 3] = 0.05
    return rf.Network(frequency=frequency, s=s, z0=50.0)


def _settings(**changes) -> TimeDomainSettings:
    values = dict(
        ui_ps=20.0,
        rise_time_ps=4.0,
        dt_ps=1.0,
        n_points=256,
        main_method="peak",
        num_pre=1,
        num_post=2,
        noise_window_half_ui=0.1,
    )
    values.update(changes)
    return TimeDomainSettings(**values)


def test_victim_analysis_returns_structured_signal_noise_and_waveforms():
    service = SNRAnalysisService()
    result = service.analyse_victim(
        _network(),
        LineEndpoint(1, 1, 2, "Line 1"),
        (LineEndpoint(2, 3, 2, "Line 2"), LineEndpoint(3, 4, 2, "Line 3")),
        _settings(),
    )
    assert result.transfer_function == "VTF2,1"
    assert result.signal > 0
    assert result.total_noise >= result.direct_noise >= 0
    assert result.xtalk_noise > 0
    assert result.snr > 0
    assert result.main_index == int(np.argmax(np.abs(result.direct_waveform)))
    assert len(result.direct_cursor_peaks) == 3
    assert len(result.aggressors) == 2
    assert set(result.aggressor_waveforms) == {2, 3}


def test_no_aggressors_and_frequency_warning_are_explicit():
    service = SNRAnalysisService()
    result = service.analyse_victim(
        _network(),
        LineEndpoint(1, 1, 2, "Line 1"),
        (),
        _settings(dt_ps=0.01, num_pre=0, num_post=0),
    )
    assert result.xtalk_noise == 0
    assert result.warnings and "Nyquist" in result.warnings[0]


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"ui_ps": 0}, "有限正数"),
        ({"n_points": 2}, "不小于"),
        ({"main_method": "bad"}, "未知"),
        ({"num_pre": -1}, "负数"),
        ({"noise_window_half_ui": 0.5}, "0 <="),
    ],
)
def test_invalid_time_domain_settings_are_rejected(changes, match):
    with pytest.raises(ValueError, match=match):
        SNRAnalysisService().analyse_victim(
            _network(), LineEndpoint(1, 1, 2, "Line 1"), (), _settings(**changes)
        )


def test_cursor_window_out_of_range_is_not_silently_undercounted():
    with pytest.raises(ValueError, match="超出"):
        SNRAnalysisService().analyse_victim(
            _network(),
            LineEndpoint(1, 1, 2, "Line 1"),
            (),
            _settings(num_pre=0, num_post=100),
        )
