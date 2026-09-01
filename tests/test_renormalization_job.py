from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import skrf as rf

from quick_tdsnr.domain.project_models import ConfirmedMapping, ProjectConfig, ProjectInput
from quick_tdsnr.services.renormalization_job import RenormalizationJob
from quick_tdsnr.services.sweep_planning_service import SweepPlanningService


def _network() -> rf.Network:
    frequency = rf.Frequency(1, 2, 3, unit="GHz")
    s = np.zeros((3, 6, 6), dtype=complex)
    network = rf.Network(frequency=frequency, s=s, z0=50.0)
    network.port_names = [f"P{index}" for index in range(1, 7)]
    return network


def _write_input(path: Path, content: bytes = b"fingerprint") -> ProjectInput:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return ProjectInput(str(path), hashlib.sha256(content).hexdigest())


def _config(inputs: tuple[ProjectInput, ...]) -> ProjectConfig:
    mapping = ConfirmedMapping(
        rows=((1, 3, 5), (2, 4, 6)),
        family_ids=("family1", "family2", "family3"),
        source_family="family1",
    )
    return ProjectConfig(
        inputs=inputs,
        mapping=mapping,
        target_families=("family2", "family3"),
        resistance_candidates={
            "family1": (50.0,), "family2": (45.0,), "family3": (55.0,)
        },
        cio_pf={"family1": 0.0, "family2": 0.2, "family3": 0.3},
        topology_metric="S",
        topology_frequency_ghz=0.1,
    )


def test_in_memory_batch_precomputes_input_z_exactly_once(tmp_path, monkeypatch):
    input_item = _write_input(tmp_path / "input.s6p")
    config = _config((input_item,))
    plan = SweepPlanningService().build_plan(config)

    class FakeNetwork:
        nports = 6
        z_reads = 0

        @property
        def z(self):
            self.z_reads += 1
            return np.zeros((3, 6, 6), dtype=complex)

    network = FakeNetwork()
    received_z = []

    def fake_renormalize(_network, _ports, _case, *, source_family, z_matrix):
        assert source_family == "family1"
        received_z.append(z_matrix)
        return object()

    monkeypatch.setattr(
        "quick_tdsnr.services.renormalization_job.renormalize_family_case",
        fake_renormalize,
    )
    run = RenormalizationJob(network_loader=lambda _path: network).run(
        config, plan, write_outputs=False, keep_networks=True
    )
    assert network.z_reads == 1
    assert len(received_z) == plan.case_count == 2
    assert run.manifest.in_memory == 2
    assert run.manifest.accounted == run.manifest.planned


def test_batch_writes_traceable_unique_outputs_and_manifest(tmp_path):
    first = _write_input(tmp_path / "a" / "same.s6p", b"first")
    second = _write_input(tmp_path / "b" / "same.s6p", b"second")
    config = _config((first, second))
    plan = SweepPlanningService().build_plan(config)
    output = tmp_path / "output"
    run = RenormalizationJob(network_loader=lambda _path: _network()).run(
        config, plan, output_dir=output, write_outputs=True
    )
    assert run.manifest.planned == 4
    assert run.manifest.saved == 4
    assert run.manifest.failed == run.manifest.cancelled == 0
    paths = [Path(item.output_path) for item in run.manifest.items]
    assert len(set(paths)) == 4
    assert all("_I" in path.name for path in paths)
    assert all(path.is_file() and path.suffix == ".s4p" for path in paths)
    assert all(item.output_sha256 for item in run.manifest.items)
    assert all(item.kept_ports in ((1, 2, 3, 4), (1, 2, 5, 6)) for item in run.manifest.items)
    loaded = rf.Network(str(paths[0]))
    assert loaded.nports == 4
    manifest_payload = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["schema"] == RenormalizationJob.MANIFEST_SCHEMA
    assert manifest_payload["planned"] == 4
    assert not list(output.glob(".*.tmp"))


def test_single_input_name_omits_hash_and_pairs_each_family_r_with_c(tmp_path):
    input_item = _write_input(tmp_path / "parallel line_1d2line.s6p")
    config = _config((input_item,))
    plan = SweepPlanningService().build_plan(config)

    name = RenormalizationJob._output_name(
        input_item.path, input_item.sha256, plan.cases[0], config
    )

    assert name == (
        "parallel line_1d2line_T2_R50C0_R45C0p2_R55C0p3.s4p"
    )


def test_case_write_failure_is_isolated_and_later_case_continues(tmp_path, monkeypatch):
    item = _write_input(tmp_path / "input.s6p")
    config = _config((item,))
    plan = SweepPlanningService().build_plan(config)
    job = RenormalizationJob(network_loader=lambda _path: _network())
    original = job._atomic_write
    calls = 0

    def fail_first(network, path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("模拟写盘失败")
        return original(network, path)

    monkeypatch.setattr(job, "_atomic_write", fail_first)
    run = job.run(config, plan, output_dir=tmp_path / "out")
    assert run.manifest.failed == 1
    assert run.manifest.saved == 1
    assert run.manifest.accounted == 2
    assert "模拟写盘失败" in run.manifest.items[0].error


def test_cancellation_at_case_boundary_preserves_count_conservation(tmp_path):
    item = _write_input(tmp_path / "input.s6p")
    config = _config((item,))
    plan = SweepPlanningService().build_plan(config)
    progress = []
    run = RenormalizationJob(network_loader=lambda _path: _network()).run(
        config,
        plan,
        write_outputs=False,
        keep_networks=True,
        should_cancel=lambda: bool(progress),
        on_progress=progress.append,
    )
    assert run.manifest.in_memory == 1
    assert run.manifest.cancelled == 1
    assert run.manifest.accounted == run.manifest.planned == 2


def test_changed_input_fingerprint_fails_all_cases_before_loading(tmp_path):
    item = _write_input(tmp_path / "input.s6p", b"before")
    config = _config((item,))
    plan = SweepPlanningService().build_plan(config)
    Path(item.path).write_bytes(b"after")
    loaded = []
    run = RenormalizationJob(network_loader=lambda path: loaded.append(path)).run(
        config, plan, write_outputs=False, keep_networks=True
    )
    assert not loaded
    assert run.manifest.failed == 2
    assert all("指纹已变化" in result.error for result in run.manifest.items)


def test_job_rejects_plan_input_mismatch_and_missing_destination(tmp_path):
    item = _write_input(tmp_path / "input.s6p")
    config = _config((item,))
    plan = SweepPlanningService().build_plan(config)
    from dataclasses import replace

    job = RenormalizationJob(network_loader=lambda _path: _network())
    with pytest.raises(ValueError, match="输入数"):
        job.run(config, replace(plan, input_count=2), write_outputs=False, keep_networks=True)
    with pytest.raises(ValueError, match="输出目录"):
        job.run(config, plan, write_outputs=True)
