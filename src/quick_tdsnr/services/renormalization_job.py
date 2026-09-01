"""批量重归一化执行器：进度、取消、失败隔离和 manifest。"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import uuid
from collections.abc import Callable

import numpy as np
import skrf as rf
from sipi_sparam_core.renormalization import (
    BatchRenormalizationCase,
    renormalize_family_case,
    write_touchstone_with_z0,
)
from sipi_sparam_core.touchstone_io import apply_port_name_patch, apply_qs_s_def_patch
from threadpoolctl import threadpool_limits

from quick_tdsnr.domain.project_models import (
    JobItemResult,
    JobManifest,
    JobProgress,
    ProjectConfig,
    RenormalizationRun,
    SweepCase,
    SweepPlan,
)
from quick_tdsnr.services.sample_workspace_service import SampleWorkspaceService


ProgressCallback = Callable[[JobProgress], None]
CancelCallback = Callable[[], bool]


class RenormalizationJob:
    MANIFEST_SCHEMA = "quick_tdsnr_renormalization_v1"

    def __init__(self, *, network_loader: Callable[[str], rf.Network] | None = None) -> None:
        self._network_loader = network_loader or self._load_network

    @staticmethod
    def _load_network(path: str) -> rf.Network:
        network = rf.Network(path)
        apply_qs_s_def_patch(network, path)
        apply_port_name_patch(network, path)
        return network

    @staticmethod
    def _core_case(case: SweepCase) -> BatchRenormalizationCase:
        return BatchRenormalizationCase(
            target_family=case.target_family,
            resistance_ohm=case.resistance_ohm,
            cio_pf=case.cio_pf,
        )

    @staticmethod
    def _output_name(input_path: str, input_sha256: str, case: SweepCase, config: ProjectConfig) -> str:
        source = Path(input_path)
        source_stem = source.stem
        duplicate_stem = sum(
            Path(item.path).stem.casefold() == source_stem.casefold()
            for item in config.inputs
        ) > 1
        if duplicate_stem:
            source_stem += f"_I{input_sha256[:8]}"

        family_tokens = "_".join(
            "R"
            + RenormalizationJob._number_token(case.resistance_ohm[family_id])
            + "C"
            + RenormalizationJob._number_token(case.cio_pf[family_id])
            for family_id in config.mapping.family_ids
        )
        target_index = "".join(character for character in case.target_family if character.isdigit())
        target_token = target_index or case.target_family
        output_nports = len(config.mapping.rows) * 2
        return f"{source_stem}_T{target_token}_{family_tokens}.s{output_nports}p"

    @staticmethod
    def _number_token(value: float) -> str:
        return f"{float(value):g}".replace("-", "m").replace(".", "p")

    @staticmethod
    def _atomic_write(network: rf.Network, path: Path) -> tuple[Path, str]:
        token = uuid.uuid4().hex
        temporary = path.with_name(f".{path.name}.{token}.tmp")
        try:
            write_touchstone_with_z0(network, temporary)
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return path, digest

    @staticmethod
    def _write_manifest(
        manifest: JobManifest, output_dir: Path, name: str = "renormalization_manifest.json"
    ) -> Path:
        path = output_dir / name
        temporary = output_dir / f".renormalization_manifest.{uuid.uuid4().hex}.tmp"
        try:
            temporary.write_text(
                json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return path

    def run(
        self,
        config: ProjectConfig,
        plan: SweepPlan,
        *,
        output_dir: str | Path | None = None,
        write_outputs: bool = True,
        keep_networks: bool = False,
        workspace_layout: bool = False,
        should_cancel: CancelCallback | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> RenormalizationRun:
        if plan.input_count != len(config.inputs):
            raise ValueError("扫描计划的输入数与项目配置不一致")
        if not write_outputs and not keep_networks:
            raise ValueError("至少启用写盘或内存结果中的一种")
        destination_root = Path(output_dir).expanduser().resolve() if output_dir else None
        run_id = uuid.uuid4().hex
        workspace_path: Path | None = None
        destination = destination_root
        if write_outputs:
            if destination_root is None:
                raise ValueError("写盘时必须指定输出目录")
            if workspace_layout:
                workspace_path = SampleWorkspaceService.create_run_workspace(
                    destination_root, run_id
                )
                destination = workspace_path / "sparams"
            assert destination is not None
            destination.mkdir(parents=True, exist_ok=True)

        total = len(config.inputs) * len(plan.cases)
        items: list[JobItemResult] = []
        networks: dict[tuple[str, str], rf.Network] = {}
        family_ports = {
            family: list(ports) for family, ports in config.mapping.family_ports.items()
        }
        completed = 0

        def cancelled() -> bool:
            return bool(should_cancel and should_cancel())

        def add_cancelled(start_input: int, start_case: int = 0) -> None:
            for input_index in range(start_input, len(config.inputs)):
                case_begin = start_case if input_index == start_input else 0
                item = config.inputs[input_index]
                for case in plan.cases[case_begin:]:
                    items.append(
                        JobItemResult(
                            input_path=item.path,
                            input_sha256=item.sha256,
                            case_id=case.case_id,
                            target_family=case.target_family,
                            kept_ports=tuple(
                                family_ports[config.mapping.source_family]
                                + family_ports[case.target_family]
                            ),
                            status="cancelled",
                            error="用户取消",
                            resistance_ohm=case.resistance_ohm,
                            cio_pf=case.cio_pf,
                        )
                    )

        with threadpool_limits(limits=1):
            for input_index, input_item in enumerate(config.inputs):
                if cancelled():
                    add_cancelled(input_index)
                    break
                try:
                    actual_digest = hashlib.sha256(Path(input_item.path).read_bytes()).hexdigest()
                    if actual_digest != input_item.sha256:
                        raise ValueError("输入文件指纹已变化，请重新预检")
                    network = self._network_loader(input_item.path)
                    z_matrix = np.asarray(network.z, dtype=complex).copy()
                except Exception as exc:
                    for case in plan.cases:
                        items.append(
                            JobItemResult(
                                input_path=input_item.path,
                                input_sha256=input_item.sha256,
                                case_id=case.case_id,
                                target_family=case.target_family,
                                kept_ports=tuple(
                                    family_ports[config.mapping.source_family]
                                    + family_ports[case.target_family]
                                ),
                                status="failed",
                                error=f"输入加载失败：{exc}",
                                resistance_ohm=case.resistance_ohm,
                                cio_pf=case.cio_pf,
                            )
                        )
                        completed += 1
                        if on_progress is not None:
                            on_progress(
                                JobProgress(
                                    completed=completed,
                                    total=total,
                                    input_name=Path(input_item.path).name,
                                    case_id=case.case_id,
                                    message=f"{completed}/{total} 失败",
                                )
                            )
                    continue

                for case_index, case in enumerate(plan.cases):
                    if cancelled():
                        add_cancelled(input_index, case_index)
                        input_index = len(config.inputs)
                        break
                    kept_ports = tuple(
                        family_ports[config.mapping.source_family]
                        + family_ports[case.target_family]
                    )
                    try:
                        result_network = renormalize_family_case(
                            network,
                            family_ports,
                            self._core_case(case),
                            source_family=config.mapping.source_family,
                            z_matrix=z_matrix,
                        )
                        output_path = None
                        output_sha256 = None
                        if write_outputs:
                            assert destination is not None
                            output_path_obj, output_sha256 = self._atomic_write(
                                result_network,
                                destination
                                / self._output_name(
                                    input_item.path, input_item.sha256, case, config
                                ),
                            )
                            output_path = str(output_path_obj)
                        if keep_networks:
                            networks[(input_item.path, case.case_id)] = result_network
                        status = "saved" if write_outputs else "in_memory"
                        items.append(
                            JobItemResult(
                                input_path=input_item.path,
                                input_sha256=input_item.sha256,
                                case_id=case.case_id,
                                target_family=case.target_family,
                                kept_ports=kept_ports,
                                status=status,
                                output_path=output_path,
                                output_sha256=output_sha256,
                                resistance_ohm=case.resistance_ohm,
                                cio_pf=case.cio_pf,
                            )
                        )
                    except Exception as exc:
                        items.append(
                            JobItemResult(
                                input_path=input_item.path,
                                input_sha256=input_item.sha256,
                                case_id=case.case_id,
                                target_family=case.target_family,
                                kept_ports=kept_ports,
                            status="failed",
                            error=str(exc),
                            resistance_ohm=case.resistance_ohm,
                            cio_pf=case.cio_pf,
                        )
                        )
                    completed += 1
                    if on_progress is not None:
                        on_progress(
                            JobProgress(
                                completed=completed,
                                total=total,
                                input_name=Path(input_item.path).name,
                                case_id=case.case_id,
                                message=f"{completed}/{total}",
                            )
                        )
                else:
                    continue
                break

        counts = {status: sum(item.status == status for item in items) for status in ("saved", "in_memory", "failed", "cancelled")}
        manifest = JobManifest(
            schema=self.MANIFEST_SCHEMA,
            run_id=run_id,
            planned=total,
            saved=counts["saved"],
            in_memory=counts["in_memory"],
            failed=counts["failed"],
            cancelled=counts["cancelled"],
            items=tuple(items),
        )
        if manifest.accounted != total:
            raise RuntimeError(
                f"manifest 计数不守恒：planned={total}, accounted={manifest.accounted}"
            )
        manifest_dir = workspace_path or destination
        manifest_name = "run_manifest.json" if workspace_path else "renormalization_manifest.json"
        manifest_path = (
            self._write_manifest(manifest, manifest_dir, manifest_name)
            if write_outputs and manifest_dir
            else None
        )
        run = RenormalizationRun(
            manifest,
            networks,
            manifest_path,
            workspace_path=workspace_path,
        )
        if workspace_path is not None:
            catalog = SampleWorkspaceService.catalog_from_run(run)
            run.catalog_path = SampleWorkspaceService.write_catalog(catalog)
        return run
