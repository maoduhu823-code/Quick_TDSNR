# Phase 11 验收：独立 SNR 统计与二维热力图

日期：2026-09-01  
版本：Quick_TDSNR 0.2.0

## 结论

**通过。** 用户工作流已扩展为七步；第六步保留执行、样本管理、频域和时域，第七步独立提供 SNR 热力图、汇总指标、逐串扰和逐结果。

## 已实现

- 从 sample catalog 自动识别具有多个取值的 family R/Cio；固定参数不列为维度；
- 恰好两个变化维度时自动作为 X/Y，超过两个时显示 X/Y 选择并要求固定其余维度；
- 热力图支持 SNR dB、线性 SNR、Signal、Direct/Xtalk/Total Noise；
- 聚合支持最好、最差、平均，默认最差；SNR/Signal 越大越好，Noise 越小越好；
- 格点直接显示数值并按数值映射底色，tooltip/选择状态保留 case、结果数和代表 Victim；
- 统计范围默认全部，也可显式使用第六步勾选样本；空勾选得到空结果；
- 项目 current_phase 支持第七步，旧 schema 2 阶段值保持兼容；
- 逐结果增加 SNR dB 列。

## 自动化覆盖

- 变化维度识别与固定 R/Cio 排除；
- SNR/Signal 与 Noise 的最好/最差方向；
- 三种聚合的格点数值和代表 Victim；
- 1驱2自动维度与1驱多于2的 X/Y、固定值控件；
- 全部/已勾选范围和空选择语义；
- 七步页面装配、导航和第七步 current_phase 往返。

## 默认工程界面验收

工程：`C:\Users\33202\Desktop\HFSS script\data\qtsnr\_test.qtsnr.json`

- 样本：16；
- SNR结果：128；
- 失败：0；
- 自动维度：X=`family2 R (Ω)`，Y=`family3 R (Ω)`；
- 网格：2×4，共8个有效格点；
- 默认指标/聚合：SNR dB / 最差；
- 最差SNR dB范围：1.09847–5.39227。

## 阶段门结果

- Quick_TDSNR：96 passed；
- Phase 9真实50-case验收：50/50保存成功；
- 真实验收性能：重归一化26.354秒，50条频域8.576秒，50条时域8.420秒；
- Network LRU：3；波形缓存：50；
- 公共算法未修改，因此不触发Quick_Sparam公共算法回归；
- P0/P1/P2/P3：0/0/0/0。

允许关闭 Phase 11。
