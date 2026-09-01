from __future__ import annotations

import time

from qtpy.QtCore import QTimer

from quick_tdsnr.ui.application import create_application
from quick_tdsnr.ui.workers import TopologyAnalysisWorker


def _wait_until(app, predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert predicate()


def test_worker_keeps_gui_event_loop_alive_and_reports_cancellation(monkeypatch):
    app = create_application(["qts-test"])
    timer_ticks = []
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: timer_ticks.append(time.monotonic()))
    timer.start()

    class SlowPreflight:
        def inspect_files(self, _paths, *, should_cancel):
            for _ in range(100):
                if should_cancel():
                    raise RuntimeError("文件预检已取消")
                time.sleep(0.005)
            raise AssertionError("取消请求未被 worker 接收")

    monkeypatch.setattr(
        "quick_tdsnr.ui.workers.InputPreflightService", SlowPreflight
    )
    worker = TopologyAnalysisWorker(
        {"paths": ["demo.s2p"], "low_freq_ghz": 0.1, "min_cliff_db": None}
    )
    cancelled = []
    worker.cancelled.connect(cancelled.append)
    worker.start()
    QTimer.singleShot(50, worker.requestInterruption)
    _wait_until(app, lambda: bool(cancelled))
    worker.wait(1000)
    app.processEvents()
    timer.stop()
    assert cancelled == ["拓扑识别已取消"]
    assert len(timer_ticks) >= 2
