"""Port_family 校验、参数解析和可复现扫描规划。"""

from __future__ import annotations

import hashlib
import json
import math
import re

from sipi_sparam_core.renormalization import iter_batch_cases, validate_family_ports

from quick_tdsnr.domain.project_models import (
    ConfirmedMapping,
    ProjectConfig,
    SweepCase,
    SweepPlan,
)


_SEPARATOR = re.compile(r"[\s,，]+")


def parse_positive_candidates(text: str) -> tuple[float, ...]:
    """解析中英文逗号/空白分隔的有限正数，保留输入顺序。"""
    tokens = [token for token in _SEPARATOR.split(text.strip()) if token]
    if not tokens:
        raise ValueError("R 候选值不能为空")
    try:
        values = tuple(float(token) for token in tokens)
    except ValueError as exc:
        raise ValueError("R 候选值必须是数字") from exc
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("R 候选值必须为有限正数")
    if len(set(values)) != len(values):
        raise ValueError("R 候选值不能重复")
    return values


def parse_cio_pf(text: str) -> float:
    if not text.strip():
        raise ValueError("Cio 不能为空")
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError("Cio 必须是数字") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError("Cio 必须为有限非负数")
    return value


def validate_mapping(mapping: ConfirmedMapping, nports: int) -> None:
    if not mapping.family_ids:
        raise ValueError("Port_family 不能为空")
    if len(set(mapping.family_ids)) != len(mapping.family_ids):
        raise ValueError("Port_family 名称不能重复")
    if mapping.source_family not in mapping.family_ids:
        raise ValueError("必须明确确认 family1/source")
    if not mapping.rows or any(len(row) != len(mapping.family_ids) for row in mapping.rows):
        raise ValueError("Port_family 映射必须是无空单元格的矩形")
    validate_family_ports(
        {key: list(value) for key, value in mapping.family_ports.items()}, nports
    )


class SweepPlanningService:
    def build_plan(self, config: ProjectConfig) -> SweepPlan:
        nports = config.mapping.nports
        validate_mapping(config.mapping, nports)
        family_ids = list(config.mapping.family_ids)
        targets = list(config.target_families)
        if not targets:
            raise ValueError("至少选择一个目标 family")
        if config.mapping.source_family in targets:
            raise ValueError("目标 family 不能是 source family")
        if len(set(targets)) != len(targets):
            raise ValueError("目标 family 不能重复")

        resistance = {
            family_id: list(config.resistance_candidates.get(family_id, ()))
            for family_id in family_ids
        }
        raw_cases = iter_batch_cases(
            family_ids,
            targets,
            resistance,
            config.cio_pf,
        )
        cases: list[SweepCase] = []
        for index, raw in enumerate(raw_cases, start=1):
            payload = {
                "target_family": raw.target_family,
                "resistance_ohm": [
                    [family_id, raw.resistance_ohm[family_id]] for family_id in family_ids
                ],
                "cio_pf": [[family_id, raw.cio_pf[family_id]] for family_id in family_ids],
            }
            encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
            digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:10]
            cases.append(
                SweepCase(
                    case_id=f"C{index:06d}-{digest}",
                    target_family=raw.target_family,
                    resistance_ohm=raw.resistance_ohm,
                    cio_pf=raw.cio_pf,
                )
            )
        return SweepPlan(tuple(cases), input_count=len(config.inputs))
