"""SNR 统计页的扫描维度识别和二维格点聚合。"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np

from quick_tdsnr.domain.project_models import SampleCatalog, SampleRecord


@dataclass(frozen=True)
class ScanDimension:
    key: str
    label: str
    field: str
    family_id: str
    values: tuple[float, ...]

    def value_for(self, sample: SampleRecord) -> float | None:
        source = getattr(sample, self.field) or {}
        value = source.get(self.family_id)
        return None if value is None else float(value)


@dataclass(frozen=True)
class HeatmapCell:
    x: float
    y: float
    value: float
    count: int
    case_ids: tuple[str, ...]
    representative_sample_id: str | None = None
    representative_line: int | None = None


@dataclass(frozen=True)
class HeatmapData:
    x_dimension: ScanDimension
    y_dimension: ScanDimension
    cells: tuple[HeatmapCell, ...]


class SNRStatisticsService:
    """纯数据聚合；不依赖 Qt。"""

    METRICS = (
        "snr_db",
        "snr",
        "signal",
        "direct_noise",
        "xtalk_noise",
        "total_noise",
    )
    AGGREGATIONS = ("worst", "best", "mean")
    HIGHER_IS_BETTER = {"snr_db", "snr", "signal"}

    @staticmethod
    def scan_dimensions(
        catalog: SampleCatalog,
        sample_ids: set[str] | None = None,
    ) -> tuple[ScanDimension, ...]:
        samples = tuple(
            sample
            for sample in catalog.available
            if sample_ids is None or sample.sample_id in sample_ids
        )
        dimensions: list[ScanDimension] = []
        fields = (
            ("resistance_ohm", "R", "Ω"),
            ("cio_pf", "Cio", "pF"),
        )
        families = sorted(
            {
                family_id
                for sample in samples
                for field, _name, _unit in fields
                for family_id in (getattr(sample, field) or {})
            }
        )
        for field, name, unit in fields:
            for family_id in families:
                values = tuple(
                    sorted(
                        {
                            float(value)
                            for sample in samples
                            for value in [(getattr(sample, field) or {}).get(family_id)]
                            if value is not None
                        }
                    )
                )
                if len(values) > 1:
                    dimensions.append(
                        ScanDimension(
                            key=f"{field}:{family_id}",
                            label=f"{family_id} {name} ({unit})",
                            field=field,
                            family_id=family_id,
                            values=values,
                        )
                    )
        return tuple(dimensions)

    @staticmethod
    def metric_value(result, metric: str) -> float:
        if metric not in SNRStatisticsService.METRICS:
            raise ValueError(f"未知热力图指标：{metric}")
        if metric == "snr_db":
            return 20.0 * math.log10(result.snr) if result.snr > 0 else -math.inf
        return float(getattr(result, metric))

    @staticmethod
    def _aggregate(results: tuple, metric: str, aggregation: str):
        if aggregation not in SNRStatisticsService.AGGREGATIONS:
            raise ValueError(f"未知热力图聚合方式：{aggregation}")
        values = np.asarray(
            [SNRStatisticsService.metric_value(result, metric) for result in results],
            dtype=float,
        )
        if aggregation == "mean":
            return float(np.mean(values)), None
        higher_is_better = metric in SNRStatisticsService.HIGHER_IS_BETTER
        choose_max = (aggregation == "best") == higher_is_better
        index = int(np.argmax(values) if choose_max else np.argmin(values))
        return float(values[index]), results[index]

    @staticmethod
    def heatmap(
        catalog: SampleCatalog,
        results: Iterable,
        *,
        x_dimension: ScanDimension,
        y_dimension: ScanDimension,
        metric: str,
        aggregation: str = "worst",
        target_family: str | None = None,
        fixed_values: dict[str, float] | None = None,
    ) -> HeatmapData:
        if x_dimension.key == y_dimension.key:
            raise ValueError("热力图 X/Y 维度不能相同")
        samples = {sample.sample_id: sample for sample in catalog.available}
        fixed_values = fixed_values or {}
        dimensions_by_key = {
            dimension.key: dimension
            for dimension in SNRStatisticsService.scan_dimensions(catalog)
        }
        grouped: dict[tuple[float, float], list] = {}
        for result in results:
            sample = samples.get(result.sample_id)
            if sample is None:
                continue
            if target_family is not None and sample.target_family != target_family:
                continue
            if any(
                key not in dimensions_by_key
                or dimensions_by_key[key].value_for(sample) != expected
                for key, expected in fixed_values.items()
            ):
                continue
            x_value = x_dimension.value_for(sample)
            y_value = y_dimension.value_for(sample)
            if x_value is None or y_value is None:
                continue
            grouped.setdefault((x_value, y_value), []).append(result)

        cells: list[HeatmapCell] = []
        for (x_value, y_value), raw_results in sorted(grouped.items()):
            cell_results = tuple(raw_results)
            value, representative = SNRStatisticsService._aggregate(
                cell_results, metric, aggregation
            )
            cells.append(
                HeatmapCell(
                    x=x_value,
                    y=y_value,
                    value=value,
                    count=len(cell_results),
                    case_ids=tuple(
                        sorted({result.case_id or "" for result in cell_results})
                    ),
                    representative_sample_id=(
                        representative.sample_id if representative is not None else None
                    ),
                    representative_line=(
                        representative.line if representative is not None else None
                    ),
                )
            )
        return HeatmapData(x_dimension, y_dimension, tuple(cells))
