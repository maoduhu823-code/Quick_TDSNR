# Phase 7 验收记录

<!-- date: 2026-08-31 -->

## 1. 结论

**通过。** 已把重归一化 manifest 的 1 驱41 输出全部送入 SNR，提供结果工作台、波形预览、筛选/排序和 JSON/CSV 报告。

## 2. 真实样件串联

对 `parallel line_1d2line.s24p` 使用 8 线 × 3 families 映射，执行 1 个 target case：

- 重归一化：1.111 秒，1/1 saved，16-port traveling-wave 输出；
- SNR：0.172 秒，8 条 victim 结果，0 失败；
- 结果可追溯至 input/case/kept ports，使用 `parallel_sparam_snr_v1` 版本标识。

## 3. 报告与工作台

- `PipelineService` 消费结构化 manifest，不解析日志文本；
- 结果表包含 Line、VTF、main 时间、Signal、直通 Noise、串扰 Noise、总 Noise、SNR 和警告；
- 支持关键字筛选和列排，选中行后绘制 direct + 各 aggressor 波形；
- JSON 保存执行版本和失败输出，CSV 保存扁平指标；
- 执行页提供重归一化开始/取消和时域 SNR 开始入口，共享同一进度栏。

## 4. 测试

- Quick_TDSNR：70 passed；
- 其中 PipelineService 与 ResultPage：2 passed；
- sipi-sparam-core：108 passed，92% coverage；
- Quick_Sparam：272 passed；
- 旧时域 SNR unittest：13 passed；
- P0/P1/P2：0/0/0；允许进入 Phase 8：**是**。
