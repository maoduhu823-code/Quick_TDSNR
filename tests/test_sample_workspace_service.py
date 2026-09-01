from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import skrf as rf

from quick_tdsnr.domain.project_models import (
    ConfirmedMapping,
    JobItemResult,
    JobManifest,
    ProjectConfig,
    ProjectInput,
    RenormalizationRun,
    SweepCase,
    SweepPlan,
)
from quick_tdsnr.services.renormalization_job import RenormalizationJob
from quick_tdsnr.services.sample_workspace_service import SampleWorkspaceService


def _network() -> rf.Network:
    frequency = rf.Frequency(0, 10, 11, unit="GHz")
    s = np.zeros((11, 2, 2), dtype=complex)
    s[:, 1, 0] = 0.8
    return rf.Network(frequency=frequency, s=s, z0=50.0)


def _config(path: Path) -> ProjectConfig:
    path.write_bytes(b"input")
    digest = hashlib.sha256(b"input").hexdigest()
    return ProjectConfig(
        (ProjectInput(str(path), digest),),
        ConfirmedMapping(((1, 2),), ("family1", "family2"), "family1"),
        ("family2",),
        {"family1": (50.0,), "family2": (50.0,)},
        {"family1": 0.0, "family2": 0.0},
        "S",
        0.1,
    )


def test_workspace_layout_is_run_isolated_and_catalog_is_recoverable(tmp_path):
    config = _config(tmp_path / "input.s2p")
    case = SweepCase(
        "C001", "family2", {"family1": 50.0, "family2": 50.0},
        {"family1": 0.0, "family2": 0.0},
    )
    plan = SweepPlan((case,), 1)
    job = RenormalizationJob(network_loader=lambda _path: _network())
    first = job.run(config, plan, output_dir=tmp_path / "qtsnr_runs", workspace_layout=True)
    second = job.run(config, plan, output_dir=tmp_path / "qtsnr_runs", workspace_layout=True)

    assert first.workspace_path != second.workspace_path
    assert first.manifest_path.name == "run_manifest.json"
    assert Path(first.manifest.items[0].output_path).parent.name == "sparams"
    assert first.catalog_path.is_file()
    restored = SampleWorkspaceService.load_catalog(first.catalog_path)
    assert restored.run_id == first.manifest.run_id
    assert len(restored.available) == 1
    assert restored.available[0].resistance_ohm["family2"] == 50.0
    recovered_run = SampleWorkspaceService.load_run(first.catalog_path)
    assert recovered_run.manifest == first.manifest
    assert recovered_run.workspace_path == first.workspace_path


def test_catalog_handles_50_samples_and_clear_only_removes_derived(tmp_path):
    workspace = SampleWorkspaceService.create_run_workspace(tmp_path, "a" * 32)
    items = []
    for index in range(50):
        path = workspace / "sparams" / f"sample_{index:02d}.s2p"
        path.write_text("sample", encoding="utf-8")
        items.append(
            JobItemResult(
                "input.s2p", "input-hash", f"C{index:03d}", "family2", (1, 2),
                "saved", str(path), f"hash-{index}", resistance_ohm={"family2": 40.0 + index},
                cio_pf={"family2": 0.1},
            )
        )
    manifest = JobManifest(
        RenormalizationJob.MANIFEST_SCHEMA, "a" * 32, 50, 50, 0, 0, 0, tuple(items)
    )
    run = RenormalizationRun(manifest, {}, workspace / "run_manifest.json", workspace)
    catalog = SampleWorkspaceService.catalog_from_run(run)
    catalog_path = SampleWorkspaceService.write_catalog(catalog)
    waveform = workspace / "derived" / "waveforms" / "cached.npz"
    waveform.write_bytes(b"cache")

    restored = SampleWorkspaceService.load_catalog(catalog_path)
    assert len(restored.available) == 50
    hidden_id = restored.available[0].sample_id
    updated = SampleWorkspaceService.set_visibility(restored, {hidden_id}, False)
    assert len(updated.available) == 49
    assert len(SampleWorkspaceService.load_catalog(catalog_path).available) == 49
    SampleWorkspaceService.clear_derived_cache(workspace)
    assert not waveform.exists()
    assert all(Path(sample.output_path).is_file() for sample in restored.available)
    assert catalog_path.is_file()
