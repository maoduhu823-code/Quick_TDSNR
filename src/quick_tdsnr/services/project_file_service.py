"""Quick_TDSNR 项目配置的版本化 JSON 往返和指纹检查。"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid

from quick_tdsnr.domain.project_models import (
    PROJECT_SCHEMA_VERSION,
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
from quick_tdsnr.services.sweep_planning_service import SweepPlanningService


class ProjectFileService:
    @staticmethod
    def _atomic_write(target: Path, payload: dict[str, object]) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return target

    @staticmethod
    def save(config: ProjectConfig, path: str | Path) -> Path:
        # 在落盘前生成计划，确保不会保存无法执行的配置。
        SweepPlanningService().build_plan(config)
        target = Path(path).expanduser().resolve()
        payload = asdict(config)
        payload["schema_version"] = PROJECT_SCHEMA_VERSION
        return ProjectFileService._atomic_write(target, payload)

    @staticmethod
    def save_snapshot(snapshot: ProjectSnapshot, path: str | Path) -> Path:
        if snapshot.schema_version != PROJECT_FILE_SCHEMA_VERSION:
            raise ValueError(
                f"项目快照版本必须为 {PROJECT_FILE_SCHEMA_VERSION}"
            )
        target = Path(path).expanduser().resolve()
        payload = asdict(snapshot)
        payload["schema_version"] = PROJECT_FILE_SCHEMA_VERSION
        payload["saved_at"] = datetime.now(timezone.utc).isoformat()
        return ProjectFileService._atomic_write(target, payload)

    @staticmethod
    def load(path: str | Path) -> ProjectConfig:
        source = Path(path).expanduser().resolve()
        payload = json.loads(source.read_text(encoding="utf-8"))
        if "schema_version" not in payload:
            raise ValueError("项目文件缺少 schema_version")
        version = payload["schema_version"]
        if version > PROJECT_SCHEMA_VERSION:
            raise ValueError(
                f"项目文件版本 {version} 高于当前支持版本 {PROJECT_SCHEMA_VERSION}"
            )
        if version != PROJECT_SCHEMA_VERSION:
            raise ValueError(f"尚不支持项目文件版本 {version}")
        mapping_payload = payload["mapping"]
        mapping = ConfirmedMapping(
            rows=tuple(tuple(int(port) for port in row) for row in mapping_payload["rows"]),
            family_ids=tuple(mapping_payload["family_ids"]),
            source_family=mapping_payload["source_family"],
        )
        config = ProjectConfig(
            inputs=tuple(ProjectInput(**item) for item in payload["inputs"]),
            mapping=mapping,
            target_families=tuple(payload["target_families"]),
            resistance_candidates={
                key: tuple(float(value) for value in values)
                for key, values in payload["resistance_candidates"].items()
            },
            cio_pf={key: float(value) for key, value in payload["cio_pf"].items()},
            topology_metric=payload["topology_metric"],
            topology_frequency_ghz=float(payload["topology_frequency_ghz"]),
            schema_version=version,
        )
        SweepPlanningService().build_plan(config)
        return config

    @staticmethod
    def load_snapshot(path: str | Path) -> ProjectSnapshot:
        source = Path(path).expanduser().resolve()
        payload = json.loads(source.read_text(encoding="utf-8"))
        if "schema_version" not in payload:
            raise ValueError("项目文件缺少 schema_version")
        version = int(payload["schema_version"])
        if version > PROJECT_FILE_SCHEMA_VERSION:
            raise ValueError(
                f"项目文件版本 {version} 高于当前支持版本 {PROJECT_FILE_SCHEMA_VERSION}"
            )
        if version == PROJECT_SCHEMA_VERSION:
            return ProjectFileService.snapshot_from_config(
                ProjectFileService.load(source)
            )
        if version != PROJECT_FILE_SCHEMA_VERSION:
            raise ValueError(f"尚不支持项目文件版本 {version}")
        mapping_payload = payload.get("mapping_draft")
        mapping = None
        if mapping_payload:
            mapping = MappingDraft(
                rows=tuple(
                    tuple(str(value) for value in row)
                    for row in mapping_payload.get("rows", [])
                ),
                family_ids=tuple(mapping_payload.get("family_ids", [])),
                source_family=str(mapping_payload.get("source_family", "")),
                nports=int(mapping_payload.get("nports", 0)),
            )
        topology_payload = payload.get("topology_draft")
        topology_draft = None
        if topology_payload:
            metric_drafts = []
            for item in topology_payload.get("metrics", []):
                proposal_payload = item.get("proposal")
                proposal = None
                if proposal_payload:
                    proposal = FamilyMappingProposal(
                        rows=tuple(
                            tuple(int(port) for port in row)
                            for row in proposal_payload.get("rows", [])
                        ),
                        family_count=int(proposal_payload["family_count"]),
                        line_count=int(proposal_payload["line_count"]),
                        confidence=str(proposal_payload["confidence"]),
                        source_family_index=proposal_payload.get("source_family_index"),
                        unresolved_ports=tuple(
                            int(port)
                            for port in proposal_payload.get("unresolved_ports", [])
                        ),
                    )
                metric_drafts.append(
                    TopologyMetricDraft(
                        metric=str(item["metric"]),
                        score=float(item["score"]),
                        plausible=bool(item["plausible"]),
                        file_consistent=bool(item["file_consistent"]),
                        signature=tuple(
                            tuple(int(port) for port in row)
                            for row in item.get("signature", [])
                        ),
                        reasons=tuple(str(value) for value in item.get("reasons", [])),
                        channel_count=int(item.get("channel_count", 0)),
                        isolated_ports=tuple(
                            int(port) for port in item.get("isolated_ports", [])
                        ),
                        proposal=proposal,
                        matrix=tuple(
                            tuple(float(value) for value in row)
                            for row in item.get("matrix", [])
                        ),
                    )
                )
            topology_draft = TopologyDraft(
                metrics=tuple(metric_drafts),
                recommended_metric=topology_payload.get("recommended_metric"),
                confidence=str(topology_payload.get("confidence", "低")),
                warnings=tuple(
                    str(value) for value in topology_payload.get("warnings", [])
                ),
                actual_frequency_ghz=float(
                    topology_payload.get("actual_frequency_ghz", 0.1)
                ),
            )
        time_payload = payload.get("time_domain_draft") or {}
        return ProjectSnapshot(
            schema_version=version,
            saved_at=str(payload.get("saved_at", "")),
            current_phase=max(0, min(6, int(payload.get("current_phase", 0)))),
            input_paths=tuple(str(value) for value in payload.get("input_paths", [])),
            topology_frequency_text=str(payload.get("topology_frequency_text", "0.1")),
            topology_cliff_text=str(payload.get("topology_cliff_text", "")),
            project_inputs=tuple(
                ProjectInput(path=str(item["path"]), sha256=str(item["sha256"]))
                for item in payload.get("project_inputs", [])
            ),
            topology_draft=topology_draft,
            mapping_draft=mapping,
            sweep_drafts=tuple(
                SweepFamilyDraft(
                    family_id=str(item["family_id"]),
                    resistance_text=str(item.get("resistance_text", "50")),
                    cio_text=str(item.get("cio_text", "0")),
                    target=bool(item.get("target", False)),
                )
                for item in payload.get("sweep_drafts", [])
            ),
            topology_metric=str(payload.get("topology_metric", "S")),
            topology_frequency_ghz=float(payload.get("topology_frequency_ghz", 0.1)),
            time_domain_draft=TimeDomainDraft(**{
                field_name: str(time_payload.get(field_name, default))
                for field_name, default in (
                    ("ui_text", "100"), ("rise_text", "20"),
                    ("dt_text", "10"), ("points_text", "256"),
                    ("main_method", "half_height_center"), ("pre_text", "3"),
                    ("post_text", "20"), ("half_ui_text", "0.1"),
                )
            }),
            output_root=str(payload.get("output_root", "")),
            write_outputs=bool(payload.get("write_outputs", True)),
            sample_catalog_path=(
                str(payload["sample_catalog_path"])
                if payload.get("sample_catalog_path")
                else None
            ),
        )

    @staticmethod
    def snapshot_from_config(config: ProjectConfig) -> ProjectSnapshot:
        drafts = tuple(
            SweepFamilyDraft(
                family_id=family_id,
                resistance_text=", ".join(
                    f"{value:g}" for value in config.resistance_candidates[family_id]
                ),
                cio_text=f"{config.cio_pf[family_id]:g}",
                target=family_id in config.target_families,
            )
            for family_id in config.mapping.family_ids
        )
        mapping = MappingDraft(
            rows=tuple(tuple(str(port) for port in row) for row in config.mapping.rows),
            family_ids=config.mapping.family_ids,
            source_family=config.mapping.source_family,
            nports=config.mapping.nports,
        )
        return ProjectSnapshot(
            schema_version=PROJECT_FILE_SCHEMA_VERSION,
            saved_at="",
            current_phase=3,
            input_paths=tuple(item.path for item in config.inputs),
            topology_frequency_text=f"{config.topology_frequency_ghz:g}",
            topology_cliff_text="",
            project_inputs=config.inputs,
            mapping_draft=mapping,
            sweep_drafts=drafts,
            topology_metric=config.topology_metric,
            topology_frequency_ghz=config.topology_frequency_ghz,
        )

    @staticmethod
    def stale_inputs(config: ProjectConfig) -> tuple[str, ...]:
        return ProjectFileService.stale_project_inputs(config.inputs)

    @staticmethod
    def stale_project_inputs(inputs: tuple[ProjectInput, ...]) -> tuple[str, ...]:
        stale: list[str] = []
        for item in inputs:
            path = Path(item.path)
            if not path.is_file():
                stale.append(item.path)
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != item.sha256:
                stale.append(item.path)
        return tuple(stale)
