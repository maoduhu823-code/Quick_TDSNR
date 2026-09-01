from __future__ import annotations

from types import SimpleNamespace

import pytest

from quick_tdsnr.domain.project_models import SampleCatalog, SampleRecord
from quick_tdsnr.services.snr_statistics_service import SNRStatisticsService


def _catalog() -> SampleCatalog:
    samples = []
    index = 0
    for r2 in (40.0, 60.0):
        for r3 in (50.0, 120.0):
            samples.append(
                SampleRecord(
                    f"sample-{index}", "run", "input.s24p", "input-hash",
                    f"C{index:03d}", "family2", tuple(range(1, 17)), "saved",
                    f"sample-{index}.s16p", f"hash-{index}",
                    {"family1": 34.0, "family2": r2, "family3": r3},
                    {"family1": 0.8, "family2": 0.5, "family3": 0.8},
                )
            )
            index += 1
    return SampleCatalog("quick_tdsnr_sample_catalog_v1", "run", None, tuple(samples))


def _results(catalog: SampleCatalog):
    rows = []
    for index, sample in enumerate(catalog.samples):
        for line, snr in ((1, 2.0 + index), (2, 4.0 + index)):
            rows.append(
                SimpleNamespace(
                    sample_id=sample.sample_id,
                    case_id=sample.case_id,
                    line=line,
                    snr=snr,
                    signal=snr + 1.0,
                    direct_noise=1.0 / snr,
                    xtalk_noise=2.0 / snr,
                    total_noise=3.0 / snr,
                )
            )
    return tuple(rows)


def test_detects_only_varying_r_and_cio_dimensions():
    catalog = _catalog()
    dimensions = SNRStatisticsService.scan_dimensions(catalog)
    assert [dimension.key for dimension in dimensions] == [
        "resistance_ohm:family2",
        "resistance_ohm:family3",
    ]
    assert dimensions[0].values == (40.0, 60.0)
    assert dimensions[1].values == (50.0, 120.0)


@pytest.mark.parametrize(
    ("metric", "aggregation", "expected"),
    [
        ("snr", "worst", 2.0),
        ("snr", "best", 4.0),
        ("snr", "mean", 3.0),
        ("direct_noise", "worst", 0.5),
        ("direct_noise", "best", 0.25),
        ("direct_noise", "mean", 0.375),
    ],
)
def test_heatmap_best_worst_and_mean_follow_metric_direction(
    metric, aggregation, expected
):
    catalog = _catalog()
    dimensions = SNRStatisticsService.scan_dimensions(catalog)
    heatmap = SNRStatisticsService.heatmap(
        catalog,
        _results(catalog),
        x_dimension=dimensions[0],
        y_dimension=dimensions[1],
        metric=metric,
        aggregation=aggregation,
        target_family="family2",
    )
    cell = next(item for item in heatmap.cells if item.x == 40.0 and item.y == 50.0)
    assert cell.value == pytest.approx(expected)
    assert cell.count == 2
    if aggregation == "mean":
        assert cell.representative_line is None
    else:
        assert cell.representative_line in {1, 2}
