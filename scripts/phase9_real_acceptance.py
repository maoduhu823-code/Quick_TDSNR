"""使用本机登记的真实24端口样本执行 Phase 9 的50样本验收。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import time

from quick_tdsnr.domain.project_models import (
    ConfirmedMapping,
    ProjectConfig,
    ProjectInput,
    SweepCase,
    SweepPlan,
    TimeDomainSettings,
)
from quick_tdsnr.services.renormalization_job import RenormalizationJob
from quick_tdsnr.services.sample_analysis_service import SampleAnalysisService
from quick_tdsnr.services.sample_workspace_service import SampleWorkspaceService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    registry = json.loads(
        (PROJECT_ROOT / "dev_samples.local.json").read_text(encoding="utf-8")
    )
    input_path = Path(registry["phase1_real_sample"]["path"]).resolve()
    input_sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()
    mapping = ConfirmedMapping(
        tuple((line, line + 8, line + 16) for line in range(1, 9)),
        ("family1", "family2", "family3"),
        "family1",
    )
    config = ProjectConfig(
        (ProjectInput(str(input_path), input_sha256),),
        mapping,
        ("family2",),
        {"family1": (50.0,), "family2": tuple(float(value) for value in range(40, 90)), "family3": (50.0,)},
        {"family1": 0.0, "family2": 0.0, "family3": 0.0},
        "S",
        0.1,
    )
    cases = tuple(
        SweepCase(
            f"R{value:02d}",
            "family2",
            {"family1": 50.0, "family2": float(value), "family3": 50.0},
            {"family1": 0.0, "family2": 0.0, "family3": 0.0},
        )
        for value in range(40, 90)
    )
    plan = SweepPlan(cases, 1)
    with tempfile.TemporaryDirectory(prefix="quick_tdsnr_phase9_") as temporary:
        started = time.perf_counter()
        run = RenormalizationJob().run(
            config,
            plan,
            output_dir=Path(temporary) / "qtsnr_runs",
            workspace_layout=True,
        )
        renormalization_seconds = time.perf_counter() - started
        catalog = SampleWorkspaceService.load_catalog(run.catalog_path)
        assert len(catalog.available) == 50

        service = SampleAnalysisService(max_cached_networks=3)
        started = time.perf_counter()
        traces = [
            service.frequency_trace(sample, 1, 9, parameter="S", display_mode="db")
            for sample in catalog.available
        ]
        frequency_seconds = time.perf_counter() - started
        assert service.networks.size == 3
        assert all(len(trace.frequency_ghz) == 500 for trace in traces)

        cache_dir = SampleWorkspaceService.waveform_cache_dir(catalog)
        started = time.perf_counter()
        waveforms = [
            service.time_waveform(
                sample,
                1,
                9,
                TimeDomainSettings(100.0, 20.0, 10.0, 256),
                cache_dir=cache_dir,
            )
            for sample in catalog.available
        ]
        time_seconds = time.perf_counter() - started
        assert len(list(cache_dir.glob("waveform_*.npz"))) == 50
        assert all(len(item.time_ps) == 256 for item in waveforms)

        print(
            json.dumps(
                {
                    "input": str(input_path),
                    "samples": len(catalog.available),
                    "saved": run.manifest.saved,
                    "renormalization_seconds": round(renormalization_seconds, 3),
                    "frequency_seconds": round(frequency_seconds, 3),
                    "time_seconds": round(time_seconds, 3),
                    "network_lru_size": service.networks.size,
                    "waveform_cache_files": len(list(cache_dir.glob("waveform_*.npz"))),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
