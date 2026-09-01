from pathlib import Path

import numpy as np
import pytest
import skrf as rf

from quick_tdsnr.services.input_preflight_service import InputPreflightService


def _write_network(path: Path, nports: int = 4) -> Path:
    frequency = rf.Frequency(0, 2, 3, unit="GHz")
    network = rf.Network(
        frequency=frequency,
        s=np.zeros((3, nports, nports), dtype=complex),
        z0=50.0,
    )
    network.name = path.stem
    network.write_touchstone(dir=str(path.parent), form="ri")
    return path


def test_preflight_loads_metadata_and_caches_network(tmp_path):
    path = _write_network(tmp_path / "demo.s4p")
    service = InputPreflightService()
    info = service.inspect_file(path)
    assert info.path == path.resolve()
    assert info.nports == 4
    assert info.nfreq == 3
    assert info.f_start_ghz == pytest.approx(0.0)
    assert info.f_stop_ghz == pytest.approx(2.0)
    assert len(info.sha256) == 64
    assert service.get_network(path).nports == 4


def test_preflight_reports_mismatched_port_counts(tmp_path):
    first = _write_network(tmp_path / "first.s2p", nports=2)
    second = _write_network(tmp_path / "second.s4p", nports=4)
    batch = InputPreflightService().inspect_files([first, second])
    assert not batch.compatible
    assert any("端口数不一致" in message for message in batch.warnings)


def test_preflight_ignores_duplicate_paths(tmp_path):
    path = _write_network(tmp_path / "demo.s2p", nports=2)
    batch = InputPreflightService().inspect_files([path, path])
    assert len(batch.files) == 1
    assert any("重复文件" in message for message in batch.warnings)


def test_preflight_collects_missing_file_error(tmp_path):
    missing = tmp_path / "missing.s2p"
    batch = InputPreflightService().inspect_files([missing])
    assert not batch.compatible
    assert str(missing.resolve()) in batch.errors


def test_preflight_cancellation_stops_subsequent_file_scheduling(tmp_path, monkeypatch):
    paths = [tmp_path / f"file{index}.s2p" for index in range(3)]
    service = InputPreflightService()
    inspected = []

    def inspect_file(path):
        inspected.append(Path(path))
        raise ValueError("demo")

    monkeypatch.setattr(service, "inspect_file", inspect_file)
    checks = iter((False, True))
    with pytest.raises(RuntimeError, match="已取消"):
        service.inspect_files(paths, should_cancel=lambda: next(checks))
    assert inspected == [paths[0]]
