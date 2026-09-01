"""运行工作区、样本目录和可安全清理的派生缓存。"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

from quick_tdsnr.domain.project_models import (
    JobItemResult,
    JobManifest,
    RenormalizationRun,
    SampleCatalog,
    SampleRecord,
)


class SampleWorkspaceService:
    CATALOG_SCHEMA = "quick_tdsnr_sample_catalog_v1"

    @staticmethod
    def default_root(input_paths: tuple[str, ...] | list[str]) -> Path:
        if not input_paths:
            raise ValueError("无法为没有输入文件的项目建立工作区")
        input_parent = Path(input_paths[0]).expanduser().resolve().parent
        if os.access(input_parent, os.W_OK):
            return input_parent / "qtsnr_runs"
        local_app_data = os.environ.get("LOCALAPPDATA")
        fallback = (
            Path(local_app_data)
            if local_app_data
            else Path.home() / "AppData" / "Local"
        )
        return fallback / "Quick_TDSNR" / "workspace"

    @staticmethod
    def create_run_workspace(
        root: str | Path,
        run_id: str,
        *,
        started_at: datetime | None = None,
    ) -> Path:
        base = Path(root).expanduser().resolve()
        stamp = (started_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
        workspace = base / f"{stamp}_{run_id[:8]}"
        if workspace.exists():
            workspace = base / f"{stamp}_{run_id[:8]}_{uuid.uuid4().hex[:4]}"
        for relative in (
            "sparams",
            "derived/waveforms",
            "derived/statistics",
            "exports",
        ):
            (workspace / relative).mkdir(parents=True, exist_ok=True)
        return workspace

    @staticmethod
    def _sample_id(run_id: str, input_sha256: str, case_id: str) -> str:
        payload = f"{run_id}\0{input_sha256}\0{case_id}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:20]

    @classmethod
    def catalog_from_run(cls, run: RenormalizationRun) -> SampleCatalog:
        samples = tuple(
            SampleRecord(
                sample_id=cls._sample_id(
                    run.manifest.run_id, item.input_sha256, item.case_id
                ),
                run_id=run.manifest.run_id,
                input_path=item.input_path,
                input_sha256=item.input_sha256,
                case_id=item.case_id,
                target_family=item.target_family,
                kept_ports=item.kept_ports,
                status=item.status,
                output_path=item.output_path,
                output_sha256=item.output_sha256,
                resistance_ohm=item.resistance_ohm,
                cio_pf=item.cio_pf,
            )
            for item in run.manifest.items
        )
        return SampleCatalog(
            schema=cls.CATALOG_SCHEMA,
            run_id=run.manifest.run_id,
            workspace_path=str(run.workspace_path) if run.workspace_path else None,
            samples=samples,
        )

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, object]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return path

    @classmethod
    def write_catalog(
        cls, catalog: SampleCatalog, path: str | Path | None = None
    ) -> Path:
        if path is None:
            if not catalog.workspace_path:
                raise ValueError("没有工作区时必须明确指定样本目录路径")
            destination = Path(catalog.workspace_path) / "sample_catalog.json"
        else:
            destination = Path(path).expanduser().resolve()
        return cls._atomic_json(destination, asdict(catalog))

    @classmethod
    def load_catalog(cls, path: str | Path) -> SampleCatalog:
        source = Path(path).expanduser().resolve()
        if source.is_dir():
            source = source / "sample_catalog.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("schema") != cls.CATALOG_SCHEMA:
            raise ValueError(f"不支持的样本目录格式：{payload.get('schema')}")
        samples = tuple(
            SampleRecord(
                **{
                    **item,
                    "kept_ports": tuple(int(port) for port in item["kept_ports"]),
                }
            )
            for item in payload.get("samples", [])
        )
        return SampleCatalog(
            schema=payload["schema"],
            run_id=payload["run_id"],
            workspace_path=payload.get("workspace_path"),
            samples=samples,
        )

    @classmethod
    def load_run(cls, catalog_path: str | Path) -> RenormalizationRun:
        catalog_source = Path(catalog_path).expanduser().resolve()
        catalog = cls.load_catalog(catalog_source)
        if not catalog.workspace_path:
            raise ValueError("样本目录没有关联运行工作区")
        workspace = Path(catalog.workspace_path).expanduser().resolve()
        manifest_path = workspace / "run_manifest.json"
        if not manifest_path.is_file():
            manifest_path = workspace / "renormalization_manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        items = tuple(
            JobItemResult(
                input_path=str(item["input_path"]),
                input_sha256=str(item["input_sha256"]),
                case_id=str(item["case_id"]),
                target_family=str(item["target_family"]),
                kept_ports=tuple(int(port) for port in item["kept_ports"]),
                status=str(item["status"]),
                output_path=item.get("output_path"),
                output_sha256=item.get("output_sha256"),
                error=item.get("error"),
                resistance_ohm=item.get("resistance_ohm"),
                cio_pf=item.get("cio_pf"),
            )
            for item in payload.get("items", [])
        )
        manifest = JobManifest(
            schema=str(payload["schema"]),
            run_id=str(payload["run_id"]),
            planned=int(payload["planned"]),
            saved=int(payload["saved"]),
            in_memory=int(payload["in_memory"]),
            failed=int(payload["failed"]),
            cancelled=int(payload["cancelled"]),
            items=items,
        )
        return RenormalizationRun(
            manifest,
            {},
            manifest_path,
            workspace_path=workspace,
            catalog_path=catalog_source,
        )

    @classmethod
    def set_visibility(
        cls, catalog: SampleCatalog, sample_ids: set[str], visible: bool
    ) -> SampleCatalog:
        updated = replace(
            catalog,
            samples=tuple(
                replace(item, visible=visible)
                if item.sample_id in sample_ids
                else item
                for item in catalog.samples
            ),
        )
        if updated.workspace_path:
            cls.write_catalog(updated)
        return updated

    @staticmethod
    def waveform_cache_dir(catalog: SampleCatalog) -> Path | None:
        if not catalog.workspace_path:
            return None
        return Path(catalog.workspace_path) / "derived" / "waveforms"

    @classmethod
    def clear_derived_cache(cls, workspace: str | Path) -> Path:
        root = Path(workspace).expanduser().resolve()
        catalog_path = root / "sample_catalog.json"
        if not catalog_path.is_file():
            raise ValueError("目标不是可识别的 Quick_TDSNR 运行工作区")
        catalog = cls.load_catalog(catalog_path)
        if Path(catalog.workspace_path or "").resolve() != root:
            raise ValueError("样本目录记录的工作区与目标路径不一致")
        derived = (root / "derived").resolve()
        if derived.parent != root:
            raise ValueError("派生缓存路径越出运行工作区")
        if derived.exists():
            shutil.rmtree(derived)
        (derived / "waveforms").mkdir(parents=True)
        (derived / "statistics").mkdir(parents=True)
        return derived
