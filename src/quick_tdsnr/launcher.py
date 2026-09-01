"""PowerShell 命令 ``qts`` 的稳定入口。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from collections.abc import Sequence

from quick_tdsnr import __version__


DEFAULT_TEST_PROJECT = Path(
    r"C:\Users\33202\Desktop\HFSS script\data\qtsnr\_test.qtsnr.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qts",
        description="Quick_TDSNR — 批量重归一化、时域响应与 SNR 分析",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Quick_TDSNR {__version__}",
    )
    parser.add_argument(
        "-test",
        action="store_true",
        dest="test_mode",
        help="打开默认测试工程",
    )
    parser.add_argument(
        "--runtime-check",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """解析命令并启动 GUI；返回进程退出码。"""
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    os.environ.setdefault("SKRF_PLOT_ENV", "none")
    if args.runtime_check:
        from quick_tdsnr.ui.main_window import QuickTDSNRMainWindow  # noqa: F401

        return 0
    from quick_tdsnr.ui.application import run_gui

    project_path = DEFAULT_TEST_PROJECT if args.test_mode else None
    return run_gui(project_path=project_path)


if __name__ == "__main__":
    raise SystemExit(main())
