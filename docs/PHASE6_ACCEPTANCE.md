# Phase 6 验收记录

<!-- date: 2026-08-31 -->

## 1. 结论

**通过。** VTF→幅值/相位插值→irFFT→梯形脉冲→cursor→Noise/SNR 已成为独立、可复用的结构化服务，并提供时域参数页。

## 2. 数值口径

- 新增公共核心 `snr.py`：`find_main_cursor`、`make_cursor_times`、`find_window_peak` 和 `combine_noise`;
- 旧 `time_domain_test` 只做数据模型适配，不再保留 cursor/SNR 算法副本；
- main cursor 支持 `peak` / `half_height_center`;
- 直通 Noise 同一波形窗口线性累加，不同攻击线之间 RSS，总 Noise 与直通 Noise 再 RSS，输出线性 SNR;
- post-cursor 窗口超出时间轴时明确失败，不静默低估；外推和频率覆盖告警显式记录。

## 3. 真实样件串联

对 `parallel line_1d2line.s24p` 先生成一个 16-port traveling-wave 1驱1 输出，再用 1 条 victim + 7 条 aggressor 分析：

- victim VTF：`VTF9,1`
- UI / rise / dt / FFT：100 ps / 20 ps / 10 ps / 256
- main cursor：half-height center；pre/post=1/5；Noise 窗口=0.1 UI
- Signal `0.311854`，直通 Noise `0.041260`，串扰 Noise `0.014405`，总 Noise `0.043703`，SNR `7.135877`
- 6 个直通 cursor 窗口和 7 条攻击线均返回结构化结果，无频率覆盖告警。

## 4. UI 与测试

- 时域与 SNR 页可输入 UI、rise、dt、FFT 点数、main 方法、pre/post 和 Noise 窗口；
- 参数页和服务均拒绝零/负数、NaN/Infinity、不合法 main 方法和重叠窗口；
- Quick_TDSNR：68 passed；
- sipi-sparam-core：108 passed，92% coverage；
- Quick_Sparam：272 passed；
- 旧时域 SNR unittest：13 passed；
- P0/P1/P2：0/0/0；允许进入 Phase 7：**是**。
