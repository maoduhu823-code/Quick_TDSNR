# Quick_TDSNR Phase 状态

<!-- updated: 2026-08-31 -->

| Phase | 状态 | 阶段门 |
|---|---|---|
| Phase 1 工程骨架、基线与视觉规范 | 已完成 | 通过，见 `PHASE1_ACCEPTANCE.md` |
| Phase 2 公共核心抽取与 QS 兼容 | 已完成 | 通过，见 `PHASE2_ACCEPTANCE.md` |
| Phase 3 文件预检、拓扑识别与建议映射 | 已完成 | 通过，见 `PHASE3_ACCEPTANCE.md` |
| Phase 4 Port_family 确认与参数扫描规划 | 已完成 | 通过，见 `PHASE4_ACCEPTANCE.md` |
| Phase 5 批量重归一化执行引擎 | 已完成 | 通过，见 `PHASE5_ACCEPTANCE.md` |
| Phase 6 VTF 时域与 SNR 引擎 | 已完成 | 通过，见 `PHASE6_ACCEPTANCE.md` |
| Phase 7 结果工作台、报告与完整工作流 | 已完成 | 通过，见 `PHASE7_ACCEPTANCE.md` |
| Phase 8 打包、性能、发布与迁移收尾 | 已完成 | 通过，见 `PHASE8_ACCEPTANCE.md` |
| Phase 9 样本工作台与持久化缓存 | 已完成 | 通过，见 `PHASE9_ACCEPTANCE.md` |
| Phase 10 工程快照与逐Phase调试续接 | 已完成 | 通过，见 `PHASE10_ACCEPTANCE.md` |
| Phase 11 独立 SNR 统计与二维热力图 | 已完成 | 通过，见 `PHASE11_ACCEPTANCE.md` |

## Phase 1 真实样例

- 文件：`parallel line_1d2line.s24p`
- SHA-256：`ffd5899b0f5ce4f0a8d87cc107023a15715fc9d701a981fbeae96b5f9d7daa11`
- 端口：24
- 频点：500
- 频率：0–50 GHz
- 端口名：24 个，呈 3 组 × 8 线结构
- 本机路径只保存在被忽略的 `dev_samples.local.json` 中。
