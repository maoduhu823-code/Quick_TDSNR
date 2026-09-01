# Quick_TDSNR 协作约束

- `src/quick_tdsnr/domain/`、`src/quick_tdsnr/services/` 以及公共核心禁止 import Qt。
- 禁止在模块级调用 `matplotlib.use(...)`。
- UI 字符串使用简体中文，视觉风格与 Quick_Sparam 保持一致。
- 算法和服务不得写入 Qt 按钮回调；耗时任务必须通过 worker 调用服务层。
- 端口号跨层统一使用 1-based。
- 修改公共算法后必须同时运行 Quick_TDSNR 测试和 Quick_Sparam 回归测试。
- 每个 Phase 必须通过 `docs/TEST_ACCEPTANCE_PLAN.md` 对应阶段门后才能关闭。

