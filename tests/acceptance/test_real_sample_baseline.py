from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import skrf as rf


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "dev_samples.local.json"


def _sample_config() -> dict:
    if not REGISTRY_PATH.exists():
        pytest.skip("未配置本机真实样例 dev_samples.local.json")
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return registry["phase1_real_sample"]


def test_supplied_s24p_matches_phase1_baseline():
    config = _sample_config()
    path = Path(config["path"])
    assert path.is_file(), path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == config["sha256"]

    network = rf.Network(str(path))
    assert network.nports == config["nports"] == 24
    assert len(network.f) == config["nfreq"] == 500
    assert float(network.f[0] / 1e9) == pytest.approx(config["f_start_ghz"])
    assert float(network.f[-1] / 1e9) == pytest.approx(config["f_stop_ghz"])
    assert network.s_def == config["s_def"] == "power"
    assert not np.any(np.abs(np.asarray(network.z0).imag) > 1e-15)
    assert network.port_names is not None
    assert len(network.port_names) == 24
    assert len(set(network.port_names)) == 24


def test_supplied_s24p_has_three_groups_of_eight_named_ports():
    config = _sample_config()
    network = rf.Network(config["path"])
    assert config["port_family_shape"] == [3, 8]
    groups = [network.port_names[index : index + 8] for index in range(0, 24, 8)]
    assert all(len(group) == 8 for group in groups)
    assert all("custom" in name for name in groups[0])
    assert all("L1_trace_" in name for name in groups[1])
    assert all("L2_trace_" in name for name in groups[2])

