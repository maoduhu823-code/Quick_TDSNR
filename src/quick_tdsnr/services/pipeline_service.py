"""把 Phase 5 输出批量送入 Phase 6 SNR，并导出可追溯报告。"""

from __future__ import annotations

import csv
from dataclasses import replace
import json
import math
import os
from pathlib import Path
from collections.abc import Callable
import uuid

import numpy as np
import skrf as rf

from quick_tdsnr.domain.project_models import (
    LineEndpoint,
    PipelineResult,
    TimeDomainSettings,
    VictimSNRResult,
)
from quick_tdsnr.services.snr_analysis_service import ALGORITHM_VERSION, SNRAnalysisService
from quick_tdsnr.services.sample_analysis_service import SampleAnalysisService
from quick_tdsnr.services.sample_workspace_service import SampleWorkspaceService


class PipelineService:
    def __init__(self, snr_service: SNRAnalysisService | None = None) -> None:
        self.snr_service = snr_service or SNRAnalysisService()

    def analyse_run(
        self,
        run,
        settings: TimeDomainSettings,
        *,
        should_cancel: Callable[[], bool] | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> PipelineResult:
        available = [
            item
            for item in run.manifest.items
            if (item.status == "saved" and item.output_path)
            or (
                item.status == "in_memory"
                and (item.input_path, item.case_id) in run.networks
            )
        ]
        catalog = SampleWorkspaceService.catalog_from_run(run)
        samples = {
            (sample.input_path, sample.case_id): sample for sample in catalog.samples
        }
        settings_hash = SampleAnalysisService.settings_hash(settings)
        results: list[VictimSNRResult] = []
        failures: list[tuple[str, str]] = []
        for index, item in enumerate(available, start=1):
            if should_cancel is not None and should_cancel():
                break
            try:
                if item.status == "in_memory":
                    network = run.networks[(item.input_path, item.case_id)]
                else:
                    network = rf.Network(item.output_path)
                line_count = len(item.kept_ports) // 2
                lines = tuple(
                    LineEndpoint(line, line, line + line_count, f"Line {line}")
                    for line in range(1, line_count + 1)
                )
                for victim in lines:
                    aggressors = tuple(line for line in lines if line.line != victim.line)
                    result = self.snr_service.analyse_victim(
                        network, victim, aggressors, settings
                    )
                    sample = samples[(item.input_path, item.case_id)]
                    results.append(
                        replace(
                            result,
                            sample_id=sample.sample_id,
                            case_id=item.case_id,
                            input_path=item.input_path,
                            output_path=item.output_path,
                            settings_hash=settings_hash,
                        )
                    )
            except Exception as exc:
                failures.append((item.output_path or item.case_id, str(exc)))
            if on_progress is not None:
                on_progress(index, len(available), item.case_id)
        return PipelineResult(tuple(results), tuple(failures))

    @staticmethod
    def _flat_row(result: VictimSNRResult) -> dict[str, object]:
        return {
            "line": result.line,
            "name": result.name,
            "tx_port": result.tx_port,
            "rx_port": result.rx_port,
            "transfer_function": result.transfer_function,
            "main_method": result.main_method,
            "main_index": result.main_index,
            "main_time_ps": result.main_time_ps,
            "signal": result.signal,
            "direct_noise": result.direct_noise,
            "xtalk_noise": result.xtalk_noise,
            "total_noise": result.total_noise,
            "snr": result.snr,
            "warnings": ";".join(result.warnings),
            "sample_id": result.sample_id or "",
            "case_id": result.case_id or "",
            "input_path": result.input_path or "",
            "output_path": result.output_path or "",
            "settings_hash": result.settings_hash or "",
            "snr_db": 20.0 * math.log10(result.snr) if result.snr > 0 else -math.inf,
        }

    @staticmethod
    def _export_waveforms(result: PipelineResult, output_dir: Path) -> None:
        waveform_dir = output_dir / "waveforms"
        waveform_dir.mkdir(parents=True, exist_ok=True)
        for item in result.results:
            sample_id = item.sample_id or "unspecified"
            settings = (item.settings_hash or "no_settings")[:8]
            path = waveform_dir / f"snr_{sample_id}_L{item.line}_{settings}.npz"
            temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            payload = {
                "time_ps": np.asarray(item.time_ps, dtype=float),
                "direct": np.asarray(item.direct_waveform, dtype=float),
            }
            for line, waveform in item.aggressor_waveforms.items():
                payload[f"aggressor_L{line}"] = np.asarray(waveform, dtype=float)
            try:
                with temporary.open("wb") as handle:
                    np.savez_compressed(handle, **payload)
                os.replace(temporary, path)
            finally:
                if temporary.exists():
                    temporary.unlink()

    @staticmethod
    def export(result: PipelineResult, output_dir: str | Path, stem: str = "qtsnr") -> PipelineResult:
        destination = Path(output_dir).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        PipelineService._export_waveforms(result, destination)
        report_destination = destination / "statistics" if destination.name == "derived" else destination
        report_destination.mkdir(parents=True, exist_ok=True)
        rows = [PipelineService._flat_row(item) for item in result.results]
        payload = {
            "algorithm_version": ALGORITHM_VERSION,
            "result_count": len(rows),
            "failed_outputs": [list(item) for item in result.failed_outputs],
            "results": rows,
        }
        json_path = report_destination / f"{stem}_results.json"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        csv_path = report_destination / f"{stem}_summary.csv"
        fields = list(rows[0]) if rows else [
            "line", "name", "tx_port", "rx_port", "transfer_function", "main_method",
            "main_index", "main_time_ps", "signal", "direct_noise", "xtalk_noise", "total_noise", "snr", "warnings"
        ]
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return PipelineResult(result.results, result.failed_outputs, json_path, csv_path)
