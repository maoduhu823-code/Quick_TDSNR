"""Touchstone 文件加载、补丁和批量一致性预检。"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import Path

import numpy as np
import skrf as rf
from sipi_sparam_core.touchstone_io import apply_port_name_patch, apply_qs_s_def_patch

from quick_tdsnr.domain.project_models import InputFileInfo, PreflightBatch


_TOUCHSTONE_SUFFIX = re.compile(r"\.s\d+p$", re.IGNORECASE)


class InputPreflightService:
    def __init__(self) -> None:
        self._networks: dict[Path, rf.Network] = {}

    @staticmethod
    def _key(path: str | Path) -> Path:
        return Path(path).expanduser().resolve()

    def inspect_file(self, path: str | Path) -> InputFileInfo:
        resolved = self._key(path)
        if not resolved.is_file():
            raise ValueError(f"文件不存在：{resolved}")
        if _TOUCHSTONE_SUFFIX.search(resolved.name) is None:
            raise ValueError(f"不是受支持的 Touchstone 文件：{resolved.name}")

        network = rf.Network(str(resolved))
        apply_qs_s_def_patch(network, str(resolved))
        apply_port_name_patch(network, str(resolved))
        stat = resolved.stat()
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        z0 = np.asarray(network.z0, dtype=complex)
        names = tuple(str(item) for item in (network.port_names or ()))
        info = InputFileInfo(
            path=resolved,
            name=resolved.name,
            size_bytes=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            sha256=digest,
            nports=network.nports,
            nfreq=len(network.f),
            f_start_ghz=float(network.f[0] / 1e9),
            f_stop_ghz=float(network.f[-1] / 1e9),
            s_def=str(getattr(network, "s_def", "power")),
            has_complex_z0=bool(np.any(np.abs(z0.imag) > 1e-15)),
            port_names=names,
        )
        self._networks[resolved] = network
        return info

    def inspect_files(
        self,
        paths: list[str | Path],
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> PreflightBatch:
        if not paths:
            raise ValueError("至少选择一个 Touchstone 文件")
        infos: list[InputFileInfo] = []
        errors: dict[str, str] = {}
        warnings: list[str] = []
        seen: set[Path] = set()
        for raw_path in paths:
            if should_cancel is not None and should_cancel():
                raise RuntimeError("文件预检已取消")
            resolved = self._key(raw_path)
            if resolved in seen:
                warnings.append(f"已忽略重复文件：{resolved.name}")
                continue
            seen.add(resolved)
            try:
                infos.append(self.inspect_file(resolved))
            except Exception as exc:
                errors[str(resolved)] = str(exc)

        nports = {item.nports for item in infos}
        if len(nports) > 1:
            warnings.append(f"输入文件端口数不一致：{sorted(nports)}")
        if any(not item.port_names for item in infos):
            warnings.append("部分文件缺少端口名，映射建议置信度会降低。")
        return PreflightBatch(tuple(infos), errors, tuple(warnings))

    def get_network(self, path: str | Path) -> rf.Network:
        key = self._key(path)
        network = self._networks.get(key)
        if network is None:
            self.inspect_file(key)
            network = self._networks[key]
        return network

    def network_map(self, batch: PreflightBatch) -> dict[str, rf.Network]:
        return {str(item.path): self.get_network(item.path) for item in batch.files}
