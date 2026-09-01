from __future__ import annotations

from dataclasses import replace

import pytest

from quick_tdsnr.domain.project_models import (
    ConfirmedMapping,
    ProjectConfig,
    ProjectInput,
)
from quick_tdsnr.services.sweep_planning_service import (
    SweepPlanningService,
    parse_cio_pf,
    parse_positive_candidates,
    validate_mapping,
)


def _config() -> ProjectConfig:
    families = ("family1", "family2", "family3")
    return ProjectConfig(
        inputs=(ProjectInput("demo.s12p", "abc"), ProjectInput("demo2.s12p", "def")),
        mapping=ConfirmedMapping(
            rows=((1, 5, 9), (2, 6, 10), (3, 7, 11), (4, 8, 12)),
            family_ids=families,
            source_family="family1",
        ),
        target_families=("family2", "family3"),
        resistance_candidates={
            "family1": (40.0, 50.0),
            "family2": (45.0,),
            "family3": (50.0, 55.0),
        },
        cio_pf={"family1": 0.0, "family2": 0.2, "family3": 0.3},
        topology_metric="S",
        topology_frequency_ghz=0.1,
    )


def test_parameter_parsing_accepts_chinese_comma_and_spaces():
    assert parse_positive_candidates("40， 45,50  55") == (40.0, 45.0, 50.0, 55.0)
    assert parse_cio_pf("0") == 0.0


@pytest.mark.parametrize("text", ["", "0", "-1", "nan", "inf", "50,50", "abc"])
def test_resistance_candidates_reject_invalid_values(text):
    with pytest.raises(ValueError):
        parse_positive_candidates(text)


@pytest.mark.parametrize("text", ["", "-0.1", "nan", "inf", "abc"])
def test_cio_rejects_invalid_values(text):
    with pytest.raises(ValueError):
        parse_cio_pf(text)


@pytest.mark.parametrize(
    "rows,source,match",
    [
        (((1, 2), (2, 4)), "family1", "重复"),
        (((1, 2), (3, 5)), "family1", "缺少"),
        (((1, 2), (3, 4)), "", "source"),
        (((1, 2), (3,)), "family1", "矩形"),
    ],
)
def test_mapping_validation_rejects_duplicate_missing_source_and_nonrectangular(
    rows, source, match
):
    mapping = ConfirmedMapping(rows, ("family1", "family2"), source)
    with pytest.raises(ValueError, match=match):
        validate_mapping(mapping, 4)


def test_plan_count_order_and_ids_are_reproducible():
    service = SweepPlanningService()
    first = service.build_plan(_config())
    second = service.build_plan(_config())
    assert first == second
    assert first.case_count == 8
    assert first.estimated_output_files == 16
    assert [case.target_family for case in first.cases] == ["family2"] * 4 + ["family3"] * 4
    assert len({case.case_id for case in first.cases}) == 8


def test_plan_rejects_source_as_target_and_empty_target():
    service = SweepPlanningService()
    with pytest.raises(ValueError, match="至少"):
        service.build_plan(replace(_config(), target_families=()))
    with pytest.raises(ValueError, match="source"):
        service.build_plan(replace(_config(), target_families=("family1",)))
