# Quick_TDSNR 开发计划

<!-- updated: 2026-08-31 -->

配套测试标准见 [Quick_TDSNR 测试与验收方案](TEST_ACCEPTANCE_PLAN.md)。

## 1. 项目定位

Quick_TDSNR 是面向并行总线/多 Rank S 参数的独立桌面分析工具，负责完成以下闭环：

```text
导入一批原始多端口 S 参数
    → 文件预检与拓扑识别
    → Port_family 建议映射及人工确认
    → R//C 参数扫描与目标 Rank 子网络生成
    → VTF 时域脉冲响应
    → Cursor、Noise 与 SNR 统计
    → CSV / JSON / Touchstone / 波形图 / 汇总报告
```

产品名称统一为 **Quick_TDSNR**。安装或开发环境完成命令注册后，在 PowerShell 中执行：

```powershell
qts
```

即可启动桌面界面。命令行契约规划为：

```text
qts                     启动 Quick_TDSNR GUI
qts --version           显示版本
qts run <project-file>  无人值守执行已保存的项目配置（后续阶段开放）
```

`qts` 应通过 `pyproject.toml` 的 console script 注册，不依赖用户手工维护 PowerShell alias；安装包需把启动器加入 PATH。源码开发环境通过 editable install 获得同一命令。

## 2. 范围与关键术语

### 2.1 工具范围

Quick_TDSNR 包含：

- Touchstone 文件加载、元数据恢复和批量一致性预检；
- p2p / multi-drop 拓扑识别和多文件拓扑共识；
- Port_family 建议映射、人工修正和完整性校验；
- 各 family 的 R 候选值、固定 Cio、目标 Rank 笛卡尔积规划；
- traveling-wave 重归一化与非目标端口 R//C 匹配终接；
- VTF、时域脉冲响应、cursor、Noise 和线性 SNR；
- 长任务进度、取消、失败隔离、运行清单和结果追溯；
- 表格、图表、Touchstone、CSV、JSON 等输出；
- GUI 与批处理命令入口。

Quick_TDSNR 不承担 QS 的通用 S 参数查看、频域切片、差分转换、纹波拟合、级联等功能。

### 2.2 “单目标 Rank 子网络”不是逐线 S2P

重归一化后保留的是 `family1 + 当前目标 family` 的全部端口。例如每个 family 有 8 个端口，输出仍是 S16P。这样某个 RX 才能同时看到直通 TX 和其他攻击 TX。

如果把每条线裁成独立 S2P，其他攻击线会消失，无法计算串扰 Noise。因此文档和 UI 统一使用：

- 原始多 Rank 网络；
- 单目标 Rank 子网络；
- 目标线（victim）与攻击线（aggressor）。

## 3. 开发与测试协作方式

采用“测试左移 + 阶段门 + 最终独立验收”的组合方式：

1. 每个 Phase 开始前先冻结输入、输出、异常和验收标准；
2. 核心公式优先写单元测试或黄金样例，再实现代码；
3. 实现过程中持续跑当前 Phase 测试和 QS 回归测试；
4. Phase 结束时必须通过阶段验收，未通过不进入下阶段；
5. 发布前由未参与该功能实现的人或独立测试轮次执行端到端验收。

测试不是开发完成后的独立补充，也不应完全由测试替代设计。算法开发与测试设计同步进行，最终验收保持相对独立。详细标准见 [Quick_TDSNR 测试与验收方案](TEST_ACCEPTANCE_PLAN.md)。

## 4. 总体技术架构

### 4.1 最终项目关系

建议形成三个边界清晰的发行物：

```text
sipi-sparam-core                 无 UI 公共算法包
├── Quick_Sparam 依赖它
└── Quick_TDSNR 依赖它

Quick_Sparam                     通用 S 参数查看与分析工具
Quick_TDSNR                      批量重归一化、时域与 SNR 工具
```

公共包禁止依赖 Qt 和 matplotlib，只允许 numpy、scipy、scikit-rf 等数值依赖。QS 迁移期间保留兼容 re-export，避免一次性修改全部调用方。

### 4.2 公共核心模块

```text
sipi_sparam_core/
├── models.py                    公共不可变数据模型
├── impedance.py                 R//C 阻抗、零阻抗检查
├── renormalization.py           case 规划、重归一化、目标子网络
├── topology.py                  p2p / multi-drop 拓扑识别
├── ports.py                     端口解析、line_port_pairs
├── transfer.py                  traveling-wave VTF
├── time_response.py             插值、irFFT、脉冲、卷积、cursor 原语
└── touchstone_io.py             S_DEF、端口名和逐频点 Zref 契约
```

从 QS 迁移或共享的主要实现：

| 当前来源 | 进入公共核心的内容 |
|---|---|
| `QS_domain/algorithms/impedance.py` | `parallel_rc_impedance`、零阻抗检查 |
| `QS_services/batch_renormalize_service.py` | case、校验、重归一化、命名、Touchstone 写出 |
| `QS_domain/algorithms/topology_detect.py` | `ChannelInfo`、`TopologyReport`、`detect_topology` |
| `QS_domain/algorithms/vtf.py` | VTF 及频变复数 Zref 校验 |
| `QS_domain/port_parser.py` | 端口解析和自动线对 |
| `QS_domain/algorithms/time_domain.py` | 可复用数值原语，不直接照搬 QS UI 包装入口 |
| `QS_infra/touchstone_patch.py` | PowerSI 端口名和 `QS_S_DEF` 恢复 |

### 4.3 Quick_TDSNR 内部分层

```text
Quick_TDSNR/
├── pyproject.toml
├── src/quick_tdsnr/
│   ├── launcher.py
│   ├── cli.py
│   ├── domain/
│   │   ├── project_models.py
│   │   ├── topology_models.py
│   │   └── snr.py
│   ├── services/
│   │   ├── input_preflight_service.py
│   │   ├── topology_inference_service.py
│   │   ├── family_mapping_service.py
│   │   ├── sweep_planning_service.py
│   │   ├── renormalization_job.py
│   │   ├── time_domain_job.py
│   │   ├── pipeline_service.py
│   │   └── export_service.py
│   ├── infra/
│   │   ├── project_store.py
│   │   ├── result_store.py
│   │   ├── resource_path.py
│   │   └── logging_setup.py
│   └── ui/
│       ├── main_window.py
│       ├── style.py
│       ├── pages/
│       ├── widgets/
│       └── workers.py
├── resources/
└── tests/
```

依赖方向固定为：

```text
ui → services → domain / sipi_sparam_core
              → infra
```

`domain`、`services` 和公共核心不得 import Qt。耗时任务通过 worker 调用服务，不把算法写进按钮回调。

## 5. 拓扑识别与映射设计

### 5.1 页面顺序

原先合并的“输入与端口映射”拆为：

1. 文件导入；
2. 拓扑识别；
3. Port_family 确认。

拓扑识别必须先有输入文件，因此它位于“文件选择之后、人工映射之前”。

### 5.2 拓扑预处理

`TopologyInferenceService` 负责：

- 对输入文件执行 S/Y/Z 低频拓扑分析；
- 并行比较 S/Y/Z 判据，不预设某一种矩阵永远优先；
- 根据簇尺寸一致性、端口名证据、跨文件共识和孤立端口数量评价候选结果；
- 比较多个文件的端口数、联通簇、簇大小和孤立端口；
- 输出多文件共识、差异和高/中/低置信状态；
- 生成 `FamilyMappingProposal`，但不直接替代用户确认。

每个联通簇对应一条物理信号线，簇内端口对应不同 family。建议映射优先使用：

1. 端口名中的 family / DQ 信息；
2. 用户指定的 family1/source 锚点；
3. 稳定的端口编号分组；
4. 拓扑中心和耦合强度只作辅助。

互易 S 参数不能可靠区分真实 driver；算法中的 hub 是拓扑中心，不应自动解释为 family1。

### 5.3 异常处理

以下情况必须进入人工确认，不得静默执行：

- 不同文件拓扑不一致；
- S/Y 判据结果明显冲突；
- S/Y/Z 判据中只有部分结果满足预期 family 矩形结构；
- 联通簇大小不一致；
- p2p 与 multi-drop 混杂且无法组成矩形 family 表；
- 孤立、重复、缺失或无法归属的端口；
- family1/source 身份缺少名称或用户锚点证据。

重归一化前仍要求所有物理端口恰好处理一次。孤立或辅助端口必须明确分配 family，或设置独立终接模型。

## 6. UI 视觉与交互规范

Quick_TDSNR 的视觉风格与 QS 保持一致，但不复制 QS 主窗口的业务耦合。

### 6.1 视觉基线

- 简体中文 UI；
- Windows 使用 SimHei，Linux 使用 WenQuanYi Zen Hei；
- matplotlib 设置 `axes.unicode_minus=False`、`mathtext.fontset='stix'`；
- 浅灰系统风格、QGroupBox 分组、适度圆角；
- 主按钮沿用 QS 的浅灰垂直渐变、14 px 字号、5 px 圆角；
- 普通操作按钮高度约 32 px，主要动作约 38～56 px；
- 表单标签右对齐，输入列宽统一，减少界面跳动；
- 可调整区域使用 QSplitter，handle 采用 QS 的浅灰与 hover 提示；
- 文件、配置、结果和日志使用明确分组，不堆叠连续弹窗；
- 长任务必须显示阶段、当前文件、case、目标线、总进度和取消入口。

样式集中在 `ui/style.py`，以命名令牌管理按钮、列表、表格、状态颜色和间距。不得在每个页面复制 stylesheet。

### 6.2 主窗口布局

建议保持 QS 的三栏心智模型：

```text
左栏：Phase 导航和项目动作
中栏：当前 Phase 的配置、拓扑、映射或结果
右栏：任务摘要、告警、进度和日志
```

顶部显示项目名、当前输入数量和配置状态；底部提供“上一步 / 下一步 / 保存项目 / 执行”。窗口默认约 1600×800，并在 100%、125%、150% 缩放下验证。

### 6.3 开发 Phase 与七个用户页面的关系

最终用户工作流保持 7 个页面：

1. 文件导入；
2. 拓扑识别；
3. Port_family 确认；
4. 参数扫描；
5. 时域与 SNR；
6. 执行与波形；
7. SNR 统计。

## 7. 数据与运行契约

### 7.1 项目配置

项目文件需保存：

- 输入文件及指纹；
- 拓扑参数、报告摘要和用户确认状态；
- family 映射、source family、目标 families；
- R 候选值、Cio、时域、cursor、输出配置；
- 算法版本和应用版本。

配置采用带 `schema_version` 的 JSON，读取时校验并保留升级入口。

### 7.2 运行清单

每次运行生成唯一 `run_id`。每条结果至少包含：

```text
run_id / source_file / source_fingerprint / case_id / target_family
R/C 参数 / victim_line / tx_port / rx_port / algorithm_version
时域参数 / cursor 参数 / signal / direct_noise / xtalk_noise
total_noise / snr_linear / status / error
```

`parallel_sparam_snr_v1` 在规则未正式升级前保持不变。修改 Noise 组合、cursor 规则或时域定义时必须增加算法版本。

### 7.3 中间 Touchstone

同一进程内优先直接传递 `rf.Network`，避免“写盘再读取”。Touchstone 中间文件设为可选审计产物；写出时必须保存逐频点 Zref、`QS_S_DEF traveling` 和 R//C 模型元数据。

## 8. 八阶段实施计划

每个 Phase 的详细测试用例和量化标准见测试验收方案。这里的“完成门”全部满足后，Phase 才可关闭。

### Phase 1：工程骨架、基线与视觉规范

工作内容：

- 建立 Quick_TDSNR 独立工程、`src` 布局、依赖和版本管理；
- 注册 `qts`、`qts --version`，建立 GUI 空壳；
- 建立 domain/services/infra/ui 依赖约束；
- 建立统一日志、异常边界和资源路径；
- 从 QS 提取视觉令牌，完成三栏主窗口和 Phase 导航原型；
- 固化现有 QS、拓扑、重归一化、VTF、时域/SNR 测试基线；
- 选定合成样例和真实回归样例，记录首轮性能基线。

完成门：`qts` 可从新 PowerShell 启动；测试框架、CI/本地一键测试入口和 UI 风格基线可用；未迁移任何算法行为。

### Phase 2：公共核心抽取与 QS 兼容

工作内容：

- 建立 `sipi-sparam-core`；
- 迁移 impedance、renormalization、VTF、topology、ports、Touchstone 契约；
- 合并 QS 和 `time_domain_test` 重复的插值、脉冲、卷积、cursor 原语；
- 为 QS 保留兼容 re-export，逐步改用公共包；
- 清理公共层中的 Qt、matplotlib 和 QS 主窗口依赖；
- 修正架构/接口文档中拓扑识别已支持 multi-drop 的过期描述。

完成门：公共核心测试通过；QS 全量 pytest 无回归；公共包可单独安装、导入和运行。

### Phase 3：文件预检、拓扑识别与建议映射

工作内容：

- 实现批量文件元数据预检和一致性分组；
- 实现 `TopologyInferenceService` 和多文件拓扑共识；
- 实现 S/Y/Z 判据切换、断崖阈值、高/中/低置信状态；
- 实现 `FamilyMappingProposal`；
- 建立文件导入页、拓扑确认页、热力图和差异提示；
- 后台执行拓扑分析，保持 UI 可交互。

完成门：典型 p2p、multi-drop、混合和孤立端口样例识别正确；拓扑不确定时不会自动提交错误 family 映射。

### Phase 4：Port_family 确认与参数扫描规划

工作内容：

- 实现可拖拽/编辑的 family 映射矩阵；
- 由拓扑建议预填行列，支持 family1/source 锚点；
- 实现重复、缺失、孤立和跨文件不一致校验；
- 实现 R 候选、Cio、目标 family 配置和 case 实时计数；
- 定义 `ProjectConfig`、`SweepPlan`、schema version；
- 实现项目保存、加载和配置升级入口。

完成门：合法配置可稳定往返保存；非法映射不能进入执行阶段；case 规划完全可复现。

### Phase 5：批量重归一化执行引擎

工作内容：

- 把 QS 主窗口中的批量循环迁为无 UI `RenormalizationJob`；
- 每个输入网络只预计算一次 Z 矩阵；
- 支持目标 Rank 子网络的内存传递和可选 Touchstone 写出；
- 实现唯一命名、manifest、失败隔离、进度和取消；
- 控制 BLAS 线程与批处理并发，防止超额订阅；
- UI 显示文件/case 级进度和失败明细。

完成门：物理终接、traveling-wave 和文件往返精度通过；取消后已有产物仍完整可追溯。

### Phase 6：VTF 时域与 SNR 引擎

工作内容：

- 正式迁移 `time_domain_test` 中的 VTF→插值→irFFT→脉冲卷积；
- 实现 main/pre/post cursor、窗口峰值和边界检查；
- 实现直通 Noise、逐攻击线 Noise、RSS 和线性 SNR；
- 支持 victim/aggressor 选择和端口方向；
- 为相同 case/时域配置缓存可复用传输路径；
- 输出结构化结果和 `parallel_sparam_snr_v1` 版本标识。

完成门：解析解、合成波形和现有原型结果一致；任何外推、时间范围不足或波定义错误都显式告警/失败。

### Phase 7：结果工作台、报告与完整工作流

工作内容：

- 串联六个用户页面和完整 `PipelineService`；
- 实现结果表筛选、排序、case/R/family/victim 联动；
- 实现目标线详细波形、逐攻击线 Noise、2×2 指标图；
- 实现 CSV、JSON、Touchstone、图片和运行 manifest 导出；
- 实现运行恢复、失败项定位和日志保存；
- 完成所有页面的 QS 风格统一、键盘导航和高 DPI 调整。

完成门：真实样例端到端结果数量、数值和关联关系正确；用户可从错误结果追溯到输入、case 和参数。

### Phase 8：打包、性能、发布与迁移收尾

工作内容：

- 建立 Windows PyInstaller/安装包和资源清单；
- 确保安装后新 PowerShell 可直接执行 `qts`；
- 完成干净环境安装、卸载、升级和项目兼容测试；
- 进行长批次性能、内存、取消和异常恢复测试；
- 编写用户指南、示例项目、算法版本说明和已知限制；
- 确认 QS 中相关入口的保留、跳转或下线策略；
- 完成独立发布验收和版本签署。

完成门：安装包、`qts`、资源、中文图表和端到端分析在目标 Windows 环境稳定运行；无阻断级缺陷。

### Phase 9（v0.2扩展）：样本工作台与持久化缓存

工作内容：

- 每次重归一化建立独立的 `qtsnr_runs/<timestamp_run-id>` 工作区，避免输出和manifest被后续运行覆盖；
- 建立可恢复的 `sample_catalog.json`，用稳定 sample_id 关联输入、case、R/Cio、Touchstone和SNR结果；
- 参考QS文件列表建立生成样本列表，支持搜索、多选、文件名/完整路径、移出列表和恢复隐藏；
- 在列表下建立“频域”“时域”“统计”三页工作台；
- 拓扑参数矩阵沿用QS的严格下三角显示，遮蔽主对角线和上三角；
- 页面内不再重复放置确认按钮；底部主按钮按上下文执行“确认映射/计划/设置并下一步”；
- 执行页以样本工作台为默认内容，文件/case状态和错误移入独立“运行明细”页；
- 频域支持任意1-based Tx/Rx、S/VTF和dB/幅值/相位/实部/虚部；
- 时域支持参数设置、任意Tx/Rx和基于内容/设置哈希的压缩NPZ缓存；
- 统计支持Signal、Direct/Xtalk/Total Noise、SNR/SNR dB的分位数和逐aggressor统计；
- Network采用LRU按需加载，默认最多常驻3个；修复仅内存重归一化结果无法进入SNR的问题；
- 清理功能只删除可重建的 `derived`，不删除输入、Touchstone和manifest。

完成门：真实24端口样本连续生成并管理50个输出；频域与时域批量分析完成后Network缓存不超过3个，50个波形缓存可恢复；程序重启可从catalog恢复；清理派生缓存不影响Touchstone。

### Phase 10（v0.2扩展）：工程快照与逐Phase调试续接

工作内容：

- 项目文件升级为schema 2阶段快照，并兼容读取schema 1；
- 允许在任意Phase保存，不再要求先形成合法扫描计划；
- 保存输入及指纹、拓扑摘要与矩阵、映射原始文本、扫描原始文本、时域设置、输出设置、当前Phase和sample catalog引用；
- 恢复时按依赖完整度回到最近可继续的Phase，输入指纹变化时强制回到预检；
- 首次保存后，在确认并切换Phase、重归一化完成和SNR完成时自动更新检查点；
- 提供Ctrl+S、Ctrl+Shift+S和Ctrl+O，并在窗口标题显示当前工程；
- 从sample catalog和run manifest重建历史运行引用，不在工程JSON中复制大矩阵Network或波形数组。

完成门：部分/非法草稿、完整配置、拓扑显示、时域设置和历史run均可往返；schema 1可迁移；逐Phase自动检查点和输入失效降级通过测试。

### Phase 11（v0.3扩展）：独立 SNR 统计与二维热力图

工作内容：

- 工作流扩展为七步，第六步保留执行、样本管理、频域和时域，第七步独立承载 SNR；
- 从 sample catalog 自动识别具有多个取值的 family R/Cio 扫描维度；
- 两个变化维度自动作为 X/Y，超过两个时允许选择 X/Y并固定其余维度；
- 热力图支持 SNR/SNR dB、Signal、Direct/Xtalk/Total Noise；
- 格点聚合支持最好、最差、平均，默认最差，并按指标方向解释好坏；
- 格点显示数值、按数值映射底色，并保留 case、结果数量和代表 Victim 追溯；
- 统计范围明确区分全部样本和第六步已勾选样本。

完成门：默认工程16个样本得到2×4最差SNR dB热力图和128条逐结果；维度识别、指标方向、三种聚合、空选择语义、七步恢复均有自动化覆盖；Quick_TDSNR与Phase 9真实样例验收通过。

## 9. 主要风险与控制

| 风险 | 控制方式 |
|---|---|
| 拓扑中心被误当成真实 driver | family1 必须由端口名、用户锚点或明确证据确认 |
| QS 与新 App 算法分叉 | 单一公共核心 + QS 兼容 shim + 双方回归测试 |
| 时域 S 与 VTF 口径混用 | 公共传输响应原语 + 两个明确包装入口 + 波定义校验 |
| 批量 case 爆炸 | 实时计数、阈值确认、磁盘预算、取消和失败隔离 |
| 频变复数 Zref 被第三方误读 | 强制 metadata、manifest 和显式警告 |
| UI 长时间无响应 | 所有批量任务进 worker，主线程只更新状态 |
| 结果规则后续变化 | `schema_version` 与 `algorithm_version` 双版本 |
| 打包后 `qts` 或资源失效 | 干净环境安装测试和资源路径契约测试 |

## 10. 交付定义

Quick_TDSNR v1.0 只有同时满足以下条件才算完成：

- 8 个 Phase 完成门全部通过；
- Quick_TDSNR、公共核心和 QS 回归测试全部通过；
- `qts` 在目标 PowerShell 环境可用；
- 七步工作流可以完成真实数据端到端分析；
- 所有结果均可由 run/case/file/port/algorithm version 追溯；
- UI 视觉和基本交互符合 QS 风格验收；
- 发布验收中无 P0/P1 缺陷，P2 缺陷有明确处置记录。
