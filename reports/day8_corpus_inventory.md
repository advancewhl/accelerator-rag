# Day 8：加速器语料范围、分类与登记

## 今日目标

Day 8 不做 PDF 正文解析、切块、Embedding 或 Qdrant 入库。今天建立的是
corpus 的控制面：先知道有哪些文档、每份文档属于什么范围、是否仍缺文件，
再进入 Day 9 的解析工作。

学习计划给出的验收条件是：每份文档都有主题、类型、语言、版本和状态。
本项目额外记录稳定的 `doc_id`、显示标题和相对路径，保证后续 chunk 可以追溯
到唯一源文档。

## 首批语料边界

- 原始文件：13 份 PDF，合计约 69.7 MiB。
- 内容范围：EPICS、SHINE 控制系统、IOC/PV、联锁、定时、低温控制、
  European XFEL 总体设计、束流输运及电子/光子诊断。
- 暂无 HLA 专题文档。分类体系保留 `high_level_application/hla`，但不为了
  “分类齐全”虚构或重复登记资料。
- `data/raw` 只保存源文件；登记信息位于 `data/documents/registry.json`。
- 原始大文件被 `.gitignore` 排除，registry、验证器和报告进入 Git。

## 分类规则

每份文档选择一个主类别和一个主主题。文档可以涉及多个概念，但 Day 8 先用
主主题避免重复统计；多标签、设备、系统和访问级别等扩展字段留到 Day 13。

类别：

- `control_system`：EPICS、IOC/PV、控制架构、联锁、定时和低温控制。
- `beam_diagnostics`：电子束与光子诊断设备和方法。
- `accelerator_physics`：装置总体设计、束流输运、晶格和光源物理。
- `high_level_application`：HLA；当前首批语料中数量为 0。

状态：

- `active`：当前维护或持续更新的资料。
- `reference`：历史版本、设计报告或会议论文，仍具有学习和检索价值。
- `draft`：尚未定稿。
- `deprecated`：明确废弃，后续默认不检索。
- `unknown`：无法判断状态。

`reference` 与 `deprecated` 必须区分：旧文档不等于无效文档。

## 文档登记表

| # | 文档 | 主分类 | 语言 | 版本 | 状态 |
|---:|---|---|---|---|---|
| 1 | EPICS Application Developer's Guide | control_system/epics | en | R3.16.2 (2018-10-22) | active |
| 2 | EPICS Documentation | control_system/epics | en | latest (2026-08-18) | active |
| 3 | European XFEL Full Technical Design Report | accelerator_physics/accelerator_design | en | DESY 2006-097 (2007-07) | reference |
| 4 | European XFEL Undulator Commissioning Spectrometer | beam_diagnostics/photon_diagnostics | en | Rev B, Ver 2 (2011-06-08) | reference |
| 5 | X-Ray Optics and Beam Transport | accelerator_physics/beam_transport | en | XFEL.EU TR-2012-006 (2012-12) | reference |
| 6 | Standard E-Beam Diagnostics for the European-XFEL | beam_diagnostics/electron_beam_diagnostics | en | LINAC2010 TUP095 | reference |
| 7 | EPICS IOC and PVs Information Management System for SHINE | control_system/ioc | en | PCaPAC2022 FRO21 | reference |
| 8 | SHINE 加速器快联锁系统设计与开发 | control_system/interlock | zh | 核技术 47(12):120203 (2024-12) | reference |
| 9 | Status of the SHINE Control System | control_system/control_architecture | en | ICALEPCS2019 WEPHA167 | reference |
| 10 | The Cryogenic Control System of SHINE | control_system/cryogenics | en | EPJ Techniques and Instrumentation (2021) | reference |
| 11 | White Rabbit Based Beam-Synchronous Timing Systems for SHINE | control_system/timing | en | IPAC2022 THIYGD1 | reference |
| 12 | SHINE 加速器控制系统设计与开发 | control_system/control_architecture | zh | unknown | reference |
| 13 | 硬 X 射线自由电子激光装置初步设计报告（加速器分册） | accelerator_physics/accelerator_design | zh | 初步设计报告 (2017-12-26) | reference |

## 自动验证

执行：

```bash
python scripts/day8_corpus_inventory.py
```

验证器检查：

1. registry 根节点、字段和枚举值是否合法；
2. `doc_id` 与 `source_path` 是否重复；
3. category/topic 组合是否属于 taxonomy；
4. 路径是否安全、是否位于 `data/raw`、扩展名是否匹配；
5. registry 中的文件是否都存在；
6. `data/raw` 是否存在未登记文件。

本次 inventory：

- registry 文档数：13；
- raw 文件数：13；
- 文件一致性：通过；
- 类别：control_system 8、accelerator_physics 3、beam_diagnostics 2；
- 语言：英文 10、中文 3；
- 状态：active 2、reference 11；
- 格式：PDF 13。

## 今日验收

- [x] 13 份真实 PDF 统一位于 `data/raw`。
- [x] 每份文档都有稳定 ID、标题、路径、主题、类型、语言、版本和状态。
- [x] `registry.json` 可自动加载并验证。
- [x] registry 与文件系统一一对应，无缺失、无漏登记。
- [x] inventory 能输出分类统计，并在不一致时返回失败。
- [x] 未对 PDF 做正文解析、切块或向量入库。

## 你应该能回答的三个问题

1. 为什么 `source_path` 只存项目相对路径，而不存电脑上的绝对路径？
2. 为什么“历史参考资料”不能直接标为 `deprecated`？
3. 新增第 14 份 PDF 时，如果忘记写 registry，验证器会在哪一步失败？

Day 9 将以这份 registry 为输入，逐份提取正文、页码、标题和段落，并检查
扫描版、双栏、表格、公式和乱码风险。
