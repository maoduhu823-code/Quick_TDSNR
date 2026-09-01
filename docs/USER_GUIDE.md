# Quick_TDSNR 用户指南

## 启动

在 PowerShell 中运行 `qts`；查看版本运行 `qts --version`。

## 七步流程

1. **文件导入**：添加原始 `.sNp`，检查端口数、频点、频率范围和端口名。
2. **拓扑识别**：在探测频点比较 S/Y/Z；判据冲突会保留告警。
3. **Port_family 确认**：编辑或拖放交换端口，明确选择 source family。
4. **参数扫描**：输入各 family 的 R 候选和 Cio，选择 target family，查看 case 数。
5. **时域与 SNR**：设置 UI、rise、dt、FFT 点数、main cursor、pre/post 和 Noise 窗口。
6. **执行与波形**：执行重归一化；每次运行自动建立独立工作区，并把成功结果加入生成样本列表。样本工作台提供“频域”“时域”两个页面。
7. **SNR 统计**：运行或刷新 SNR，查看二维参数热力图、汇总指标、逐 victim/aggressor Noise 和逐结果曲线。

映射、扫描和时域设置页使用窗口底部唯一的“确认并下一步”按钮，不需要在页面内重复确认。拓扑参数矩阵只显示下三角，与QS一致。

## 工程保存与恢复

- 工程文件扩展名为 `.qtsnr.json`，可在任意Phase保存，不要求先完成参数扫描；
- 第一次保存后，确认并进入下一Phase时会自动更新同一个检查点；
- `Ctrl+S`：保存当前工程；`Ctrl+Shift+S`：项目另存为；`Ctrl+O`：打开工程；
- 快照保存输入路径和SHA、拓扑显示结果、未完成的映射单元格、原始R/Cio文本、当前Phase、时域设置、输出目录及最近run目录引用；
- 输入文件内容变化或缺失时仍会恢复界面设置，但强制回到文件预检，不会沿用旧分析结果；
- 打开含历史run的工程后会恢复样本列表和Touchstone引用，并可继续频域/时域查看或重新运行SNR；
- 旧版schema 1工程可直接打开，下一次保存时升级为schema 2。

工程文件不保存窗口位置、Network对象或完整波形数组；这些大数据继续由run工作区和派生缓存管理。

## 样本工作台

- 样本列表默认显示简洁case摘要，也可切换文件名/完整路径；支持搜索、勾选全部、取消勾选、移出列表和恢复隐藏；移出列表不会删除磁盘文件；
- **频域**：直接键入 1-based Tx/Rx，可查看 S 或 VTF 的 dB、线性幅值、相位、实部和虚部，并叠加多个样本；
- **时域**：设置 UI、rise、dt、FFT点数、main/pre/post cursor 和 Noise 窗口，对勾选样本生成任意 Tx/Rx 的时域波形；
- 可从 `sample_catalog.json` 恢复历史运行；Network 按需加载，最多常驻最近 3 个样本。

## SNR 统计与热力图

- 统计范围明确选择“全部样本”或“第六步已勾选样本”；空勾选表示空结果，不再隐含表示全部；
- 汇总表显示 Signal、Direct/Xtalk/Total Noise、线性 SNR、SNR dB 的均值、标准差、极值和 P5/P50/P95；
- 热力图格点指标支持 SNR dB、线性 SNR、Signal、Direct/Xtalk/Total Noise；
- 聚合支持“最好”“最差”“平均”，默认“最差”。SNR/Signal 越大越好，Noise 越小越好；
- 只有两个变化扫描参数时自动作为 X/Y；超过两个时选择 X/Y，并为其余维度指定固定值；
- 每个格点显示数值，底色按数值大小映射；悬停或选择可查看 case、结果数量和对应 Victim。

## 运行工作区

默认路径为输入文件旁的 `qtsnr_runs/<时间_run-id>/`，包含 `sparams`、`derived/waveforms`、`derived/statistics` 和 `exports`。输入目录不可写时默认使用本机应用数据目录。Touchstone和manifest不会随“清理派生缓存”删除。

## 追溯与限制

- Touchstone 文件名包含输入指纹、target、R/C 轴；manifest 记录输入、case、kept ports 和输出哈希；
- SNR JSON 使用 `parallel_sparam_snr_v1`；复数频变 Zref 始终标记 traveling-wave；
- 拓扑 hub 不等于真实 driver，互易 S 参数的 source 必须人工确认；
- Nyquist 超出原始频率范围会给出外推告警，cursor 窗口超出时间范围会失败；
- 工程快照当前使用 schema 2；输入文件内容变化后必须重新预检。旧 schema 1 配置仍可读取并在下次保存时升级。
- 时域波形使用输出SHA、算法版本、Tx/Rx和设置哈希命名为压缩NPZ；样本内容变化后旧缓存不会复用。
