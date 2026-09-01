import numpy as np
import pytest
import skrf as rf

from quick_tdsnr.services.topology_inference_service import (
    AnalysisCancelled,
    TopologyInferenceService,
)


def _parallel_three_family_network(lines: int = 4) -> rf.Network:
    nports = lines * 3
    frequency = rf.Frequency(0.1, 1.0, 3, unit="GHz")
    s = np.zeros((3, nports, nports), dtype=complex)
    for line in range(lines):
        ports = (line, line + lines, line + 2 * lines)
        for left in ports:
            for right in ports:
                if left != right:
                    s[:, left, right] = 0.6
    return rf.Network(frequency=frequency, s=s, z0=50.0)


def test_inference_builds_rectangular_mapping_and_requires_source_confirmation():
    network = _parallel_three_family_network()
    result = TopologyInferenceService().analyse({"demo": network})
    proposal = result.recommended_proposal
    assert proposal is not None
    assert proposal.family_count == 3
    assert proposal.line_count == 4
    assert proposal.rows == ((1, 5, 9), (2, 6, 10), (3, 7, 11), (4, 8, 12))
    assert proposal.requires_source_confirmation


def test_inference_rejects_invalid_parameters():
    network = _parallel_three_family_network()
    service = TopologyInferenceService()
    with pytest.raises(ValueError, match="频点"):
        service.analyse({"demo": network}, low_freq_ghz=-1.0)
    with pytest.raises(ValueError, match="断崖"):
        service.analyse({"demo": network}, min_cliff_db=0.0)
    with pytest.raises(ValueError, match="频点"):
        service.analyse({"demo": network}, low_freq_ghz=float("nan"))
    with pytest.raises(ValueError, match="断崖"):
        service.analyse({"demo": network}, min_cliff_db=float("inf"))


def test_inference_honours_cancellation():
    network = _parallel_three_family_network()
    with pytest.raises(AnalysisCancelled):
        TopologyInferenceService().analyse(
            {"demo": network}, should_cancel=lambda: True
        )
