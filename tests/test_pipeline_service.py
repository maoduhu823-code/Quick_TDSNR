from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import skrf as rf

from quick_tdsnr.domain.project_models import ConfirmedMapping, ProjectConfig, ProjectInput, TimeDomainSettings
from quick_tdsnr.services.pipeline_service import PipelineService
from quick_tdsnr.services.renormalization_job import RenormalizationJob
from quick_tdsnr.services.sweep_planning_service import SweepPlanningService
from quick_tdsnr.ui.application import create_application
from quick_tdsnr.ui.pages.result_page import ResultPage


def _input(path: Path) -> ProjectInput:
    path.write_bytes(b"pipeline")
    return ProjectInput(str(path), hashlib.sha256(b"pipeline").hexdigest())


def _network() -> rf.Network:
    frequency = rf.Frequency(0, 10, 11, unit="GHz")
    s = np.zeros((11, 6, 6), dtype=complex)
    for index in range(11):
        s[index, 1, 0] = 0.8
        s[index, 3, 2] = 0.75
        s[index, 5, 4] = 0.7
        s[index, 3, 0] = 0.1
        s[index, 5, 0] = 0.05
    return rf.Network(frequency=frequency, s=s, z0=50.0)


def _config(path: Path) -> ProjectConfig:
    mapping = ConfirmedMapping(((1, 3, 5), (2, 4, 6)), ("family1", "family2", "family3"), "family1")
    return ProjectConfig(
        (_input(path),), mapping, ("family2",),
        {"family1": (50.0,), "family2": (50.0,), "family3": (50.0,)},
        {"family1": 0.0, "family2": 0.0, "family3": 0.0}, "S", 0.1,
    )


def test_pipeline_analyzes_all_victims_and_exports_flat_reports(tmp_path):
    config = _config(tmp_path / "input.s6p")
    plan = SweepPlanningService().build_plan(config)
    run = RenormalizationJob(network_loader=lambda _path: _network()).run(
        config, plan, output_dir=tmp_path / "renorm"
    )
    progress = []
    pipeline = PipelineService().analyse_run(
        run,
        TimeDomainSettings(20.0, 4.0, 1.0, 256, "peak", 0, 2, 0.1),
        on_progress=lambda done, total, case: progress.append((done, total, case)),
    )
    assert pipeline.result_count == 2
    assert not pipeline.failed_outputs
    assert len(progress) == 1 and progress[0][0:2] == (1, 1)
    exported = PipelineService.export(pipeline, tmp_path / "reports", "batch")
    payload = json.loads(exported.json_path.read_text(encoding="utf-8"))
    assert payload["algorithm_version"] == "parallel_sparam_snr_v1"
    assert payload["result_count"] == 2
    assert exported.csv_path.read_text(encoding="utf-8-sig").splitlines()[0].startswith("line,")


def test_result_page_filters_and_opens_selected_waveform_dialog(tmp_path):
    app = create_application(["qts-test"])
    config = _config(tmp_path / "input.s6p")
    plan = SweepPlanningService().build_plan(config)
    run = RenormalizationJob(network_loader=lambda _path: _network()).run(config, plan, output_dir=tmp_path / "renorm")
    result = PipelineService().analyse_run(run, TimeDomainSettings(20.0, 4.0, 1.0, 256, "peak", 0, 2, 0.1))
    page = ResultPage()
    page.set_results(result.results)
    app.processEvents()
    assert page.table.rowCount() == 2
    page.filter_edit.setText("VTF3,1")
    app.processEvents()
    assert page.table.rowCount() == 1
    page.table.selectRow(0)
    app.processEvents()
    assert page.plot_button.isEnabled()
    assert not hasattr(page, "canvas")
    page.plot_button.click()
    app.processEvents()
    assert page._plot_dialog.isVisible()
    assert len(page._plot_dialog.figure.axes) == 4
    page.close()


def test_pipeline_accepts_in_memory_renormalization_results(tmp_path):
    config = _config(tmp_path / "input.s6p")
    plan = SweepPlanningService().build_plan(config)
    run = RenormalizationJob(network_loader=lambda _path: _network()).run(
        config, plan, write_outputs=False, keep_networks=True
    )
    result = PipelineService().analyse_run(
        run, TimeDomainSettings(20.0, 4.0, 1.0, 256, "peak", 0, 2, 0.1)
    )
    assert result.result_count == 2
    assert {item.case_id for item in result.results} == {plan.cases[0].case_id}
    assert all(item.sample_id for item in result.results)
