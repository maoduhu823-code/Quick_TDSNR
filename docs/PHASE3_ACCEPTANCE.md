# Phase 3 验收记录

<!-- date: 2026-08-31 -->

## 1. 结论

**通过。** 已完成批量 Touchstone 预检、S/Y/Z 多判据拓扑比较、结构化 Port_family 建议、后台执行与可取消 UI，并用指定的 24 端口真实样件通过验收。

## 2. 真实样件结果

- 样件：`parallel line_1d2line.s24p`
- SHA-256：`ffd5899b0f5ce4f0a8d87cc107023a15715fc9d701a981fbeae96b5f9d7daa11`
- 预检：24 端口、500 频点、0–50 GHz、24 个端口名
- 拓扑频点：0.1002 GHz（离 0.1 GHz 最近的实际频点）
- S 判据：100 分，8 个联通簇，可信
- Z 判据：100 分，与 S 形成同一拓扑签名
- Y 判据：70 分，形成一个 24 端口大簇，不自动采信
- 推荐：S，高置信，8 线 × 3 families
- 映射：`(1,9,17)` 至 `(8,16,24)`，24 端口覆盖率 100%，无重复
- source/family1：明确标记为待人工确认，未将拓扑 hub 当作真实 driver

## 3. UI 与取消

- 文件导入页可显示结构化预检表；
- 拓扑页可切换 S/Y/Z，映射和热力图同步更新；
- 热力图端口坐标为 1-based，真实 24 端口矩阵可读；
- 高/中/低置信文字、颜色和 tooltip 一致；
- 预检和拓扑运行于 QThread；自动测试中 GUI timer 在 worker 运行时持续响应；
- 取消在下一文件/数值判据调度点被接收，不再调度后续文件。

视觉基线：`docs/ui_baseline/phase3_real_s24p_windows.png`。

## 4. 自动化与回归

| 项目 | 结果 |
|---|---:|
| Quick_TDSNR | 23 passed |
| Quick_TDSNR 预检服务覆盖率 | 94% |
| Quick_TDSNR 拓扑服务覆盖率 | 90% |
| sipi-sparam-core | 103 passed |
| Quick_Sparam | 272 passed |
| 既有时域 SNR unittest | 13 passed |

## 5. 缺陷与阶段门

- P0：0
- P1：0
- P2：0
- 是否允许进入 Phase 4：**是**
