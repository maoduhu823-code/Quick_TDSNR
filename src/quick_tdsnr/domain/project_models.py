"""文件预检和拓扑建议使用的纯数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sipi_sparam_core.topology import TopologyReport


@dataclass(frozen=True)
class InputFileInfo:
    path: Path
    name: str
    size_bytes: int
    mtime_ns: int
    sha256: str
    nports: int
    nfreq: int
    f_start_ghz: float
    f_stop_ghz: float
    s_def: str
    has_complex_z0: bool
    port_names: tuple[str, ...]


@dataclass(frozen=True)
class PreflightBatch:
    files: tuple[InputFileInfo, ...]
    errors: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def compatible(self) -> bool:
        return bool(self.files) and not self.errors and len({item.nports for item in self.files}) == 1


@dataclass(frozen=True)
class FamilyMappingProposal:
    rows: tuple[tuple[int, ...], ...]
    family_count: int
    line_count: int
    confidence: str
    source_family_index: int | None = None
    unresolved_ports: tuple[int, ...] = ()

    @property
    def requires_source_confirmation(self) -> bool:
        return self.source_family_index is None


@dataclass(frozen=True)
class MetricEvaluation:
    metric: str
    score: float
    plausible: bool
    file_consistent: bool
    signature: tuple[tuple[int, ...], ...]
    reasons: tuple[str, ...]


@dataclass
class TopologyAnalysis:
    reports: dict[str, tuple[TopologyReport, ...]]
    evaluations: dict[str, MetricEvaluation]
    proposals: dict[str, FamilyMappingProposal | None]
    recommended_metric: str | None
    confidence: str
    warnings: tuple[str, ...]
    actual_frequency_ghz: float
    matrix_snapshots: dict[str, np.ndarray]

    @property
    def recommended_proposal(self) -> FamilyMappingProposal | None:
        if self.recommended_metric is None:
            return None
        return self.proposals.get(self.recommended_metric)


PROJECT_SCHEMA_VERSION = 1
PROJECT_FILE_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class MappingDraft:
    rows: tuple[tuple[str, ...], ...]
    family_ids: tuple[str, ...]
    source_family: str
    nports: int


@dataclass(frozen=True)
class SweepFamilyDraft:
    family_id: str
    resistance_text: str
    cio_text: str
    target: bool


@dataclass(frozen=True)
class TimeDomainDraft:
    ui_text: str = "100"
    rise_text: str = "20"
    dt_text: str = "10"
    points_text: str = "256"
    main_method: str = "half_height_center"
    pre_text: str = "3"
    post_text: str = "20"
    half_ui_text: str = "0.1"


@dataclass(frozen=True)
class TopologyMetricDraft:
    metric: str
    score: float
    plausible: bool
    file_consistent: bool
    signature: tuple[tuple[int, ...], ...]
    reasons: tuple[str, ...]
    channel_count: int
    isolated_ports: tuple[int, ...]
    proposal: FamilyMappingProposal | None
    matrix: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class TopologyDraft:
    metrics: tuple[TopologyMetricDraft, ...]
    recommended_metric: str | None
    confidence: str
    warnings: tuple[str, ...]
    actual_frequency_ghz: float


@dataclass(frozen=True)
class ProjectSnapshot:
    schema_version: int
    saved_at: str
    current_phase: int
    input_paths: tuple[str, ...]
    topology_frequency_text: str
    topology_cliff_text: str
    project_inputs: tuple["ProjectInput", ...] = ()
    topology_draft: TopologyDraft | None = None
    mapping_draft: MappingDraft | None = None
    sweep_drafts: tuple[SweepFamilyDraft, ...] = ()
    topology_metric: str = "S"
    topology_frequency_ghz: float = 0.1
    time_domain_draft: TimeDomainDraft = field(default_factory=TimeDomainDraft)
    output_root: str = ""
    write_outputs: bool = True
    sample_catalog_path: str | None = None


@dataclass(frozen=True)
class ConfirmedMapping:
    """用户确认后的 Port_family 矩形映射。"""

    rows: tuple[tuple[int, ...], ...]
    family_ids: tuple[str, ...]
    source_family: str

    @property
    def nports(self) -> int:
        return sum(len(row) for row in self.rows)

    @property
    def family_ports(self) -> dict[str, tuple[int, ...]]:
        return {
            family_id: tuple(row[column] for row in self.rows)
            for column, family_id in enumerate(self.family_ids)
        }


@dataclass(frozen=True)
class ProjectInput:
    path: str
    sha256: str


@dataclass(frozen=True)
class ProjectConfig:
    inputs: tuple[ProjectInput, ...]
    mapping: ConfirmedMapping
    target_families: tuple[str, ...]
    resistance_candidates: dict[str, tuple[float, ...]]
    cio_pf: dict[str, float]
    topology_metric: str
    topology_frequency_ghz: float
    schema_version: int = PROJECT_SCHEMA_VERSION


@dataclass(frozen=True)
class SweepCase:
    case_id: str
    target_family: str
    resistance_ohm: dict[str, float]
    cio_pf: dict[str, float]


@dataclass(frozen=True)
class SweepPlan:
    cases: tuple[SweepCase, ...]
    input_count: int

    @property
    def case_count(self) -> int:
        return len(self.cases)

    @property
    def estimated_output_files(self) -> int:
        return self.input_count * self.case_count


@dataclass(frozen=True)
class JobProgress:
    completed: int
    total: int
    input_name: str
    case_id: str
    message: str


@dataclass(frozen=True)
class JobItemResult:
    input_path: str
    input_sha256: str
    case_id: str
    target_family: str
    kept_ports: tuple[int, ...]
    status: str
    output_path: str | None = None
    output_sha256: str | None = None
    error: str | None = None
    resistance_ohm: dict[str, float] | None = None
    cio_pf: dict[str, float] | None = None


@dataclass(frozen=True)
class JobManifest:
    schema: str
    run_id: str
    planned: int
    saved: int
    in_memory: int
    failed: int
    cancelled: int
    items: tuple[JobItemResult, ...]

    @property
    def accounted(self) -> int:
        return self.saved + self.in_memory + self.failed + self.cancelled


@dataclass
class RenormalizationRun:
    manifest: JobManifest
    networks: dict[tuple[str, str], object]
    manifest_path: Path | None
    workspace_path: Path | None = None
    catalog_path: Path | None = None


@dataclass(frozen=True)
class SampleRecord:
    sample_id: str
    run_id: str
    input_path: str
    input_sha256: str
    case_id: str
    target_family: str
    kept_ports: tuple[int, ...]
    status: str
    output_path: str | None = None
    output_sha256: str | None = None
    resistance_ohm: dict[str, float] | None = None
    cio_pf: dict[str, float] | None = None
    visible: bool = True

    @property
    def display_name(self) -> str:
        if self.output_path:
            return Path(self.output_path).name
        return f"{Path(self.input_path).stem}_{self.case_id}"

    @property
    def nports(self) -> int:
        return len(self.kept_ports)


@dataclass(frozen=True)
class SampleCatalog:
    schema: str
    run_id: str
    workspace_path: str | None
    samples: tuple[SampleRecord, ...]

    @property
    def available(self) -> tuple[SampleRecord, ...]:
        return tuple(
            sample
            for sample in self.samples
            if sample.visible and sample.status in {"saved", "in_memory"}
        )


@dataclass(frozen=True)
class FrequencyTrace:
    sample_id: str
    label: str
    tx_port: int
    rx_port: int
    parameter: str
    display_mode: str
    frequency_ghz: object
    values: object


@dataclass(frozen=True)
class TimeWaveformResult:
    sample_id: str
    label: str
    tx_port: int
    rx_port: int
    settings_hash: str
    time_ps: object
    waveform: object
    warnings: tuple[str, ...] = ()
    cache_path: Path | None = None


@dataclass(frozen=True)
class LineEndpoint:
    line: int
    tx_port: int
    rx_port: int
    name: str


@dataclass(frozen=True)
class TimeDomainSettings:
    ui_ps: float
    rise_time_ps: float
    dt_ps: float
    n_points: int
    main_method: str = "half_height_center"
    num_pre: int = 3
    num_post: int = 20
    noise_window_half_ui: float = 0.1


@dataclass(frozen=True)
class AggressorSNRResult:
    line: int
    name: str
    tx_port: int
    rx_port: int
    transfer_function: str
    noise: float
    cursor_peaks: tuple[object, ...]


@dataclass(frozen=True)
class VictimSNRResult:
    line: int
    name: str
    tx_port: int
    rx_port: int
    transfer_function: str
    main_method: str
    main_index: int
    main_time_ps: float
    signal: float
    direct_noise: float
    xtalk_noise: float
    total_noise: float
    snr: float
    cursor_times_ps: dict[int, float]
    direct_cursor_peaks: tuple[object, ...]
    aggressors: tuple[AggressorSNRResult, ...]
    time_ps: object
    direct_waveform: object
    aggressor_waveforms: dict[int, object]
    warnings: tuple[str, ...] = ()
    sample_id: str | None = None
    case_id: str | None = None
    input_path: str | None = None
    output_path: str | None = None
    settings_hash: str | None = None


@dataclass(frozen=True)
class PipelineResult:
    results: tuple[VictimSNRResult, ...]
    failed_outputs: tuple[tuple[str, str], ...] = ()
    json_path: Path | None = None
    csv_path: Path | None = None

    @property
    def result_count(self) -> int:
        return len(self.results)
