# Quick_TDSNR

Quick_TDSNR 是独立的批量 S 参数重归一化、时域响应与 SNR 分析工具。

当前已完成 Phase 1–11，可从原始 S 参数完成批量1驱多重归一化、样本工作台、频域/时域波形和 SNR 统计报告。

批量重归一化后，每次运行会在输入文件旁的 `qtsnr_runs` 中建立独立工作区。第六步的生成样本可筛选、勾选、隐藏和恢复，并提供频域/时域查看；第七步独立呈现 SNR 热力图、汇总、逐串扰和逐结果。频域与时域分析采用最多 3 个 Network 的按需缓存。

项目文件采用可向后兼容的阶段快照格式。可以在任意Phase保存；首次保存后，确认并切换Phase会自动更新检查点。`Ctrl+S`保存、`Ctrl+Shift+S`另存为、`Ctrl+O`打开，适合逐Phase开发和调试。

## 发布构建

```powershell
.\scripts\build_release.ps1
```

构建会排除 Torch/TensorFlow 等无关大包、保留 scikit-rf 启动所需的 pandas，
并在结束前自动验证冻结程序的运行时依赖。

## 开发环境

```powershell
.\scripts\setup_dev.ps1
qts --version
qts
qts -test
```

开发脚本会先安装同级目录的 `sipi-sparam-core`，再安装 Quick_TDSNR。 
`qts -test` 会打开当前默认测试工程：
`C:\Users\33202\Desktop\HFSS script\data\qtsnr\_test.qtsnr.json`。

## 测试

```powershell
python -m pytest -q
python scripts/phase9_real_acceptance.py
```

本机真实样例通过仓库根目录的 `dev_samples.local.json` 注册。该文件不提交，发布测试不会依赖个人桌面路径。

## 文档

- `docs/DEVELOPMENT_PLAN.md`
- `docs/TEST_ACCEPTANCE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `docs/USER_GUIDE.md`
