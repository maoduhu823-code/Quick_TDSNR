# Phase 5 验收记录

<!-- date: 2026-08-31 -->

## 1. 结论

**通过。** 已实现无 UI 批量重归一化引擎、原子写盘、可取消计数守恒、失败隔离和执行页。

## 2. 真实样件实测

- 输入：`parallel line_1d2line.s24p`，24 端口、500 频点；
- 配置：8 线 × 3 families，`R=(40,50,60)/(45,55)/(50)`，2 个 target family；
- 计划：12 cases，预计 12 个 16-port 输出；
- 实际：6.638 秒，12/12 saved，0 failed，0 cancelled，12/12 进度回调；
- 输出文件为唯一文件名，含输入 SHA 短指纹、target、R/C 轴；
- 首个输出的 kept ports 为 source family + target family 的 16 个端口；
- Touchstone 重读保持 16 端口，manifest 包含每项输入、case、输出哈希和错误。

## 3. 执行与安全性

- 每个输入 Network 只预计一次 Z 矩阵，所有 case 共用该矩阵；
- 服务通过 `threadpoolctl` 限制单次 BLAS 线程，避免超颐订阅；
- 单个 case 写盘失败后后续 case 继续，且不留下半文件；
- 输入文件指纹变化时所有 case 显式标记失败，不误用旧数据；
- 边界取消会把剩余 case 标记为 cancelled，`planned = saved + in_memory + failed + cancelled` 始终守恒；
- 执行页提供进度、取消、失败明细和 manifest 概要。

## 4. 测试与阶段门

- Quick_TDSNR：59 passed
- Phase 5 重归一化任务测试：6 passed
- 公共核心：103 passed
- Quick_Sparam：272 passed
- 旧时域 SNR unittest：13 passed
- P0/P1/P2：0/0/0
- 是否允许进入 Phase 6：**是**
