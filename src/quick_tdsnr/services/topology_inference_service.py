"""S/Y/Z 多判据拓扑共识和 Port_family 建议映射。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
import math

import numpy as np
import skrf as rf
from sipi_sparam_core.topology import TopologyReport, detect_topology

from quick_tdsnr.domain.project_models import (
    FamilyMappingProposal,
    MetricEvaluation,
    TopologyAnalysis,
)


class AnalysisCancelled(RuntimeError):
    pass


class TopologyInferenceService:
    METRICS = ("S", "Y", "Z")

    @staticmethod
    def _signature(report: TopologyReport) -> tuple[tuple[int, ...], ...]:
        return tuple(sorted(tuple(sorted(channel.ports)) for channel in report.channels))

    @staticmethod
    def _report_score(report: TopologyReport) -> tuple[float, tuple[str, ...]]:
        reasons: list[str] = []
        covered = report.n_ports - len(report.isolated_ports)
        coverage = covered / report.n_ports if report.n_ports else 0.0
        sizes = [len(set(channel.ports)) for channel in report.channels]
        uniform = bool(sizes) and len(set(sizes)) == 1
        family_count = sizes[0] if uniform else 0
        plausible_family_count = 2 <= family_count <= 8
        multiple_lines = len(report.channels) >= 2

        score = coverage * 40.0
        if uniform:
            score += 20.0
        else:
            reasons.append("联通簇大小不一致")
        if plausible_family_count:
            score += 20.0
        else:
            reasons.append(f"推断 family 数量不合理：{family_count or '不确定'}")
        if multiple_lines:
            score += 10.0
        else:
            reasons.append("只识别到一条联通簇，无法形成并行线矩形映射")
        if not report.isolated_ports:
            score += 10.0
        else:
            reasons.append(f"存在孤立端口：{report.isolated_ports}")
        return score, tuple(reasons)

    @staticmethod
    def _proposal(report: TopologyReport, confidence: str) -> FamilyMappingProposal | None:
        if not report.channels:
            return None
        rows = tuple(sorted(tuple(sorted(set(channel.ports))) for channel in report.channels))
        sizes = {len(row) for row in rows}
        covered = {port for row in rows for port in row}
        expected = set(range(1, report.n_ports + 1))
        if len(sizes) != 1 or not sizes or covered != expected:
            return None
        family_count = next(iter(sizes))
        if not 2 <= family_count <= 8 or len(rows) < 2:
            return None
        return FamilyMappingProposal(
            rows=rows,
            family_count=family_count,
            line_count=len(rows),
            confidence=confidence,
            source_family_index=None,
        )

    def analyse(
        self,
        networks: dict[str, rf.Network],
        *,
        low_freq_ghz: float = 0.1,
        min_cliff_db: float | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> TopologyAnalysis:
        if not networks:
            raise ValueError("没有可分析的网络")
        if not math.isfinite(low_freq_ghz) or low_freq_ghz < 0:
            raise ValueError("拓扑识别频点必须大于等于 0")
        if min_cliff_db is not None and (
            not math.isfinite(min_cliff_db) or min_cliff_db <= 0
        ):
            raise ValueError("断崖阈值必须大于 0")
        nports = {network.nports for network in networks.values()}
        if len(nports) != 1:
            raise ValueError(f"输入网络端口数不一致：{sorted(nports)}")

        reports: dict[str, tuple[TopologyReport, ...]] = {}
        evaluations: dict[str, MetricEvaluation] = {}
        report_lists: dict[str, list[TopologyReport]] = {metric: [] for metric in self.METRICS}
        for metric in self.METRICS:
            for network in networks.values():
                if should_cancel is not None and should_cancel():
                    raise AnalysisCancelled("拓扑识别已取消")
                report_lists[metric].append(
                    detect_topology(
                        network,
                        low_freq_ghz=low_freq_ghz,
                        metric=metric,
                        min_cliff_db=min_cliff_db,
                    )
                )
            metric_reports = tuple(report_lists[metric])
            reports[metric] = metric_reports
            signatures = [self._signature(report) for report in metric_reports]
            file_consistent = len(set(signatures)) == 1
            scores_and_reasons = [self._report_score(report) for report in metric_reports]
            score = min(item[0] for item in scores_and_reasons)
            reasons = [reason for _, group in scores_and_reasons for reason in group]
            if not file_consistent:
                score -= 30.0
                reasons.append("不同输入文件的拓扑结果不一致")
            evaluations[metric] = MetricEvaluation(
                metric=metric,
                score=max(0.0, score),
                plausible=file_consistent and score >= 80.0,
                file_consistent=file_consistent,
                signature=signatures[0] if file_consistent else (),
                reasons=tuple(dict.fromkeys(reasons)),
            )

        plausible = [item for item in evaluations.values() if item.plausible]
        signature_counts = Counter(item.signature for item in plausible)
        preference = {"S": 2, "Z": 1, "Y": 0}
        ranked = sorted(
            plausible,
            key=lambda item: (
                signature_counts[item.signature], item.score, preference[item.metric]
            ),
            reverse=True,
        )
        recommended = ranked[0].metric if ranked else None
        agreement_count = (
            signature_counts[evaluations[recommended].signature] if recommended else 0
        )
        if recommended is None:
            confidence = "低"
        elif agreement_count >= 2 and evaluations[recommended].score >= 90:
            confidence = "高"
        else:
            confidence = "中"

        proposals = {
            metric: self._proposal(reports[metric][0], confidence)
            if evaluations[metric].file_consistent
            else None
            for metric in self.METRICS
        }
        warnings: list[str] = []
        if recommended is None:
            warnings.append("S/Y/Z 均未形成可信的矩形 Port_family 建议。")
        else:
            recommended_signature = evaluations[recommended].signature
            for metric in self.METRICS:
                evaluation = evaluations[metric]
                if evaluation.signature != recommended_signature:
                    warnings.append(
                        f"{metric} 判据与推荐的 {recommended} 判据拓扑不一致。"
                    )
            if proposals[recommended] and proposals[recommended].requires_source_confirmation:
                warnings.append("互易 S 参数不能确定真实 driver，请人工确认 family1/source。")

        first_network = next(iter(networks.values()))
        target_hz = low_freq_ghz * 1e9
        index = int(np.abs(first_network.f - target_hz).argmin())
        snapshots = {
            "S": np.abs(first_network.s[index]),
            "Y": np.abs(first_network.y[index]),
            "Z": np.abs(first_network.z[index]),
        }
        return TopologyAnalysis(
            reports=reports,
            evaluations=evaluations,
            proposals=proposals,
            recommended_metric=recommended,
            confidence=confidence,
            warnings=tuple(warnings),
            actual_frequency_ghz=float(first_network.f[index] / 1e9),
            matrix_snapshots=snapshots,
        )
