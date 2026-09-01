# Phase 8 验收记录

<!-- date: 2026-08-31 -->

## 1. 结论

**通过。** Quick_TDSNR 已建立 Windows PyInstaller 构建脚本、用户指南、资源清单和 `qts` 命令验收。

## 2. 打包与安装

- `Quick_TDSNR.spec` 使用 one-dir + windowed 模式，包含 `resources/quick_tdsnr.ico`;
- `scripts/build_release.ps1` 可重复构建，排除 Torch/TensorFlow 等无关大包，保留 scikit-rf 启动所需的 pandas，并执行冻结程序运行时依赖检查；
- 发布构建成功：`dist/Quick_TDSNR/Quick_TDSNR.exe`，EXE 25,561,137 bytes；
- 冻结后启动 3 秒仍保持运行，`_internal/resources/quick_tdsnr.ico` 存在；
- `qts --version` 输出 `Quick_TDSNR 0.1.0`，`pip check` 无断裂依赖；
- wheel 构建成功：`quick_tdsnr-0.1.0-py3-none-any.whl` 47,213 bytes；
- 用户指南：`docs/USER_GUIDE.md` 。

## 3. 性能与回归

- 普通模式主窗口启动平均 0.154 秒（三次测量）；
- 真实样件 12-case 重归一化 6.638 秒，1-case 重归一化 + 8 条 victim SNR 约 1.283 秒；
- Quick_TDSNR：70 passed；
- sipi-sparam-core：108 passed，92% coverage；
- Quick_Sparam：272 passed；
- 旧时域 SNR unittest：13 passed；
- 三项回归均保持单一公共算法实现，QS 相关入口保留兼容 shim。

## 4. 发布限制

- 当前版本需 Windows + Python 3.12 开发环境构建；运行用户使用 PyInstaller 目录即可；
- 系统安装程序和数字签名留待发布域流程接入；
- 复数频变 Zref 和输入指纹限制仍按 `docs/USER_GUIDE.md` 执行。

## 5. 阶段门

- P0/P1/P2：0/0/0
- Quick_TDSNR 、公共核心、QS 和旧时域回归：全部通过
- 是否达成 Quick_TDSNR v1 开发阶段门：**是（功能版）**
