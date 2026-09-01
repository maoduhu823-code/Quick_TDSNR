from __future__ import annotations

import json
from dataclasses import replace

import pytest

from quick_tdsnr.domain.project_models import (
    PROJECT_FILE_SCHEMA_VERSION,
    ConfirmedMapping,
    FamilyMappingProposal,
    MappingDraft,
    ProjectConfig,
    ProjectInput,
    ProjectSnapshot,
    SweepFamilyDraft,
    TimeDomainDraft,
    TopologyDraft,
    TopologyMetricDraft,
)
from quick_tdsnr.services.project_file_service import ProjectFileService


def _config(path, digest="abc") -> ProjectConfig:
    return ProjectConfig(
        inputs=(ProjectInput(str(path), digest),),
        mapping=ConfirmedMapping(((1, 3), (2, 4)), ("family1", "family2"), "family1"),
        target_families=("family2",),
        resistance_candidates={"family1": (50.0,), "family2": (45.0, 55.0)},
        cio_pf={"family1": 0.0, "family2": 0.2},
        topology_metric="Z",
        topology_frequency_ghz=0.1,
    )


def test_project_config_round_trip(tmp_path):
    source = tmp_path / "demo.s4p"
    source.write_bytes(b"demo")
    config = _config(source)
    project = ProjectFileService.save(config, tmp_path / "demo.qtsnr.json")
    assert ProjectFileService.load(project) == config
    payload = json.loads(project.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "geometry" not in payload
    assert "cache" not in payload


@pytest.mark.parametrize(
    "payload,match",
    [({}, "schema_version"), ({"schema_version": 999}, "高于"), ({"schema_version": 0}, "不支持")],
)
def test_project_config_version_errors_are_explicit(tmp_path, payload, match):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        ProjectFileService.load(path)


def test_stale_input_detects_content_change_and_missing_file(tmp_path):
    import hashlib

    source = tmp_path / "demo.s4p"
    source.write_bytes(b"before")
    digest = hashlib.sha256(b"before").hexdigest()
    config = _config(source, digest)
    assert ProjectFileService.stale_inputs(config) == ()
    source.write_bytes(b"after")
    assert ProjectFileService.stale_inputs(config) == (str(source),)
    source.unlink()
    assert ProjectFileService.stale_inputs(config) == (str(source),)


def test_phase_snapshot_round_trip_preserves_partial_invalid_drafts(tmp_path):
    topology = TopologyDraft(
        metrics=tuple(
            TopologyMetricDraft(
                metric, 90.0, True, True, ((1, 2),), (), 1, (),
                FamilyMappingProposal(((1, 2),), 2, 1, "高"),
                ((0.0, 0.5), (0.5, 0.0)),
            )
            for metric in ("S", "Y", "Z")
        ),
        recommended_metric="S",
        confidence="高",
        warnings=("test",),
        actual_frequency_ghz=0.1,
    )
    snapshot = ProjectSnapshot(
        schema_version=PROJECT_FILE_SCHEMA_VERSION,
        saved_at="",
        current_phase=6,
        input_paths=(str(tmp_path / "draft.s4p"),),
        topology_frequency_text="bad-frequency",
        topology_cliff_text="12",
        topology_draft=topology,
        mapping_draft=MappingDraft(
            (("1", "bad"), ("2", "4")), ("family1", "family2"), "", 4
        ),
        sweep_drafts=(SweepFamilyDraft("family1", "40, bad", "0.1", False),),
        time_domain_draft=TimeDomainDraft(ui_text="invalid"),
        output_root=str(tmp_path / "outputs"),
        write_outputs=False,
    )
    path = ProjectFileService.save_snapshot(snapshot, tmp_path / "partial.qtsnr.json")
    restored = ProjectFileService.load_snapshot(path)
    assert restored.current_phase == 6
    assert restored.mapping_draft.rows[0][1] == "bad"
    assert restored.topology_draft.recommended_metric == "S"
    assert restored.topology_draft.metrics[0].matrix[1][0] == 0.5
    assert restored.sweep_drafts[0].resistance_text == "40, bad"
    assert restored.time_domain_draft.ui_text == "invalid"
    assert not restored.write_outputs
    assert not list(tmp_path.glob(".*.tmp"))


def test_legacy_v1_project_loads_as_phase_snapshot(tmp_path):
    source = tmp_path / "demo.s4p"
    source.write_bytes(b"demo")
    legacy = ProjectFileService.save(_config(source), tmp_path / "legacy.qtsnr.json")
    snapshot = ProjectFileService.load_snapshot(legacy)
    assert snapshot.schema_version == PROJECT_FILE_SCHEMA_VERSION
    assert snapshot.current_phase == 3
    assert snapshot.mapping_draft.source_family == "family1"
    assert snapshot.sweep_drafts[1].resistance_text == "45, 55"
