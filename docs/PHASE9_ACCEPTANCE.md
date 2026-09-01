# Phase 9 验收：样本工作台与持久化缓存

日期：2026-08-31  
版本：Quick_TDSNR 0.2.0

## 结论

**通过。** 批量重归一化后的结果已进入可恢复样本工作台，频域、时域和统计三页均已接通；真实24端口文件的50-case验收通过。

## 实现结果

- 每次运行建立唯一 `qtsnr_runs/<timestamp_run-id>` 工作区；
- `sample_catalog.json` 记录sample_id、输入、case、target、R/Cio、kept ports、输出路径和SHA；
- 样本列表支持筛选、勾选、文件名/完整路径、移出列表、恢复隐藏、打开历史运行和打开目录；
- 样本列表默认采用case/target/R/Cio/端口数的简洁行，避免长Touchstone文件名挤占界面；
- 执行页默认显示“样本工作台”，文件/case状态和错误独立放入“运行明细”；
- 拓扑矩阵按QS约定只显示严格下三角；映射、扫描、时域确认统一由底部上下文“确认并下一步”执行；
- 频域支持任意Tx/Rx、S/VTF及dB、幅值、相位、实部、虚部；
- 时域支持完整设置并按输出SHA、算法版本、Tx/Rx和设置哈希缓存NPZ；
- 统计支持Signal、Direct/Xtalk/Total Noise、SNR、SNR dB分位数和逐aggressor Noise；
- Network LRU默认上限为3；仅内存运行现可继续进入SNR；
- 清理派生缓存经过工作区边界与catalog一致性校验，不删除Touchstone和输入。

## 自动化测试

- Quick_TDSNR：78 passed；
- 新增覆盖：50样本目录、run隔离、LRU上限、频域曲线、时域缓存命中、统计分位数、列表筛选/勾选、in-memory Pipeline；
- 架构约束继续通过：domain/services无Qt，未强制matplotlib后端。

## 真实样本50-case

输入：`parallel line_1d2line.s24p`  
SHA-256：`ffd5899b0f5ce4f0a8d87cc107023a15715fc9d701a981fbeae96b5f9d7daa11`

- 生成与保存：50/50；
- 重归一化：28.352秒；
- 50条频域曲线：9.312秒；
- 50条256点时域波形：9.466秒；
- Network LRU最终常驻：3；
- 波形缓存文件：50；
- 验收输出位于系统临时目录并在脚本结束后自动清理。

## 缺陷等级

- P0：0
- P1：0
- P2：0
- P3：0

## 发布构建

- PyInstaller 0.2.0 onedir构建成功；
- `dist/Quick_TDSNR/Quick_TDSNR.exe`：25,601,441 bytes；
- 冻结应用启动5秒保持运行，启动检查通过。

允许进入后续发布构建与用户体验微调。

## 2026-09-01 布局复验

- 生成样本列表与分析页签默认按约 1:1 分配纵向空间，仍可拖动分隔条调整；
- 频域和时域均改为“左侧设置卡 + 右侧波形图”，参数不再挤在横向工具栏；
- 统计区改为“汇总指标 / 逐串扰 / 逐结果”三级子页签，避免三张表纵向堆叠；
- 新增布局自动化测试，默认测试窗口实测上下区域为 333:333；
- Quick_TDSNR：83 passed；Quick_Sparam：272 passed；
- 发布版重新构建并通过5秒启动检查，`Quick_TDSNR.exe` 为 25,619,453 bytes。
