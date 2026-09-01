# Phase 1 验收记录

<!-- date: 2026-08-31 -->

## 1. 结论

**通过。** Quick_TDSNR Phase 1 的工程骨架、`qts` 命令、分层约束、QS 风格三栏 UI、测试框架和真实样例基线均已建立，可以进入 Phase 2。

## 2. 版本与环境

- Quick_TDSNR：0.1.0
- Python：3.12.1
- numpy：2.2.4
- scikit-rf：1.6.2
- qtpy：2.4.2
- PyQt6：6.9.0
- matplotlib：3.10.1
- pytest：9.0.3
- 平台：Windows，PowerShell

## 3. 自动测试

| 项目 | 结果 |
|---|---:|
| Quick_TDSNR Phase 1 测试 | 10 passed |
| Quick_TDSNR 总行覆盖率 | 89% |
| Quick_Sparam 全量 pytest | 271 passed |
| 既有时域 SNR 原型测试 | 13 passed |

分层扫描确认：

- domain/services 无 Qt import；
- 源码无模块级 `matplotlib.use(...)`；
- `qts --version` 可从 PowerShell 运行；
- GUI 六步页面、三栏 splitter、日志和导航冒烟通过。

## 4. PowerShell 与启动基线

| 项目 | 基线 |
|---|---:|
| `qts --version` 5 次平均 | 0.13 s |
| QApplication + 主窗口显示/关闭 3 次平均 | 0.53 s |

`qts --version` 输出：`Quick_TDSNR 0.1.0`。

## 5. 真实 S24P 基线

- 文件：`parallel line_1d2line.s24p`
- SHA-256：`ffd5899b0f5ce4f0a8d87cc107023a15715fc9d701a981fbeae96b5f9d7daa11`
- 大小：12,494,576 bytes
- 端口：24
- 频点：500
- 频率：0–50 GHz
- `s_def`：power
- Z0：实数
- 端口名：24 个，呈 3 组 × 8 线结构
- scikit-rf 首次加载基线：0.379 s

桌面绝对路径只保存在被 `.gitignore` 排除的 `dev_samples.local.json`，不进入发布测试。

## 6. 拓扑基线与设计修正

同一文件在 0.1 GHz 的结果：

| 判据 | 时间 | 结果 |
|---|---:|---|
| Y | 0.151 s | 错误合并成 1 个 24 端口大簇 |
| S | 0.200 s | 8 个三端口 multi-drop 簇 |
| Z | 0.172 s | 8 个三端口 multi-drop 簇 |

S/Z 均得到以下 family 结构：

```text
(1, 9, 17), (2, 10, 18), ... , (8, 16, 24)
```

但 S 与 Z 选择的拓扑 hub 不同，再次证明 hub 不能直接解释为真实 driver。

据此修正 Phase 3 设计：并行比较 S/Y/Z，根据簇尺寸一致性、端口名、跨文件共识和孤立端口数选择建议；任何判据分歧都保留给用户确认，不固定 Y 为默认真值。

## 7. UI 视觉验收

已在 Windows Qt 平台生成并人工检查：

- `ui_baseline/phase1_windows_scale_1_0.png`
- `ui_baseline/phase1_windows_scale_1_25.png`
- `ui_baseline/phase1_windows_scale_1_5.png`

检查结论：

- 使用 Microsoft YaHei，中文无方框；
- 三栏布局、QGroupBox、浅灰渐变按钮、列表和 splitter 与 QS 风格一致；
- 100%、125%、150% 三种缩放下无关键控件截断；
- “文件导入→拓扑识别→Port_family→参数→时域/SNR→结果”顺序明确。

## 8. 缺陷与遗留

- P0：0
- P1：0
- P2：0
- P3：0

Phase 1 页面目前仅为骨架，按钮禁用和业务占位属于计划内状态，将在后续 Phase 逐项启用。

## 9. 阶段签署

- 是否允许进入 Phase 2：**是**
- 下一阶段：公共核心抽取与 QS 兼容

