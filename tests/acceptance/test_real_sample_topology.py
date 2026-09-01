import json
from pathlib import Path

import pytest

from quick_tdsnr.services.input_preflight_service import InputPreflightService
from quick_tdsnr.services.topology_inference_service import TopologyInferenceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "dev_samples.local.json"


def _sample_path() -> Path:
    if not REGISTRY_PATH.exists():
        pytest.skip("未配置本机真实样例")
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return Path(registry["phase1_real_sample"]["path"])


def test_real_s24p_recommends_eight_by_three_mapping_and_keeps_metric_conflict():
    preflight = InputPreflightService()
    batch = preflight.inspect_files([_sample_path()])
    assert batch.compatible
    result = TopologyInferenceService().analyse(preflight.network_map(batch))

    assert result.recommended_metric in {"S", "Z"}
    assert result.confidence == "高"
    proposal = result.recommended_proposal
    assert proposal is not None
    assert proposal.line_count == 8
    assert proposal.family_count == 3
    assert proposal.rows[0] == (1, 9, 17)
    assert proposal.rows[-1] == (8, 16, 24)
    assert proposal.requires_source_confirmation
    assert result.evaluations["Y"].signature != result.evaluations[result.recommended_metric].signature
    assert any("Y 判据" in warning for warning in result.warnings)

