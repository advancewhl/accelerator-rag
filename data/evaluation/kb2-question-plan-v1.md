# kb-2.0.0 首版验收题集规划摘要（v1）

题集版本：`kb2-question-plan-v1`，`status: draft`，生成日期 2026-11-02。权威字段与完整答案边界见同名 JSON；本文件只作人可读摘要，不能替代 JSON。

## 计数

| 分组 | 题数 | 开发 | 封存 | verified | derived | needs_check |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `new_facts_operations` | 20 | 14 | 6 | 18 | 2 | 0 |
| `version_comparison` | 15 | 10 | 5 | 12 | 3 | 0 |
| `format_evidence` | 15 | 10 | 5 | 2 | 0 | 13 |
| `conflict_boundary` | 10 | 6 | 4 | 7 | 3 | 0 |
| **合计** | **60** | **40** | **20** | **39** | **8** | **13** |

说明：`reports/incoming-2026-11-02/tmp/doc-txt/` 现有 15 份可读正文；批次清单中的 16 个 `.doc` 路径包含 1 个 Office 临时锁文件。其余 DOCX/PPTX/XLSX/扫描 PDF 的题目标为 `derived_from_analysis` 或 `needs_source_check`。

## 逐题一览

- **KB2-FACT-001** | `new_facts_operations` | dev | 按 2023-09《硬X射线自由电子激光装置项目 定时系统控制界面操作说明》，给 Laser、LLRF 和束测系统设置延时值时，输入值的单位是什么？输入后怎样生效？ | `verified`
- **KB2-FACT-002** | `new_facts_operations` | dev | 定时界面上的单触发模式应怎样操作？请按顺序说明使能、触发和退出的步骤，以及状态在哪里显示。 | `verified`
- **KB2-FACT-003** | `new_facts_operations` | dev | 定时控制总界面的设备状态灯中，绿色、红色、白色分别表示什么？交换机第一状态灯为灰色有什么特殊含义？ | `verified`
- **KB2-FACT-004** | `new_facts_operations` | dev | 恒温机柜控制界面控制几台 LLRF 恒温机柜？怎样开停机柜、怎样设置温度报警阈值？超过阈值时界面如何提示？ | `verified`
- **KB2-FACT-005** | `new_facts_operations` | dev | 激光控制系统手册中，注入器激光设备分布在哪些层？B3 层和 B5 层当前上线参与调试的设备分别有哪些、各多少台？ | `verified`
- **KB2-FACT-006** | `new_facts_operations` | dev | 激光控制页面的光闸控制区中，InterLock、Enable、Status、Switch 四列分别表示什么？联锁解除和联锁状态用什么颜色表示？ | `verified`
- **KB2-FACT-007** | `new_facts_operations` | dev | 激光控制系统共提供几台能量计的控制？其中哪几台上线使用？界面中 Energy 与 Power 两列各显示什么？ | `verified`
- **KB2-FACT-008** | `new_facts_operations` | dev | 激光控制系统的 CCD 控制区共提供几台 CCD？哪几台上线？Trigger Mode 有哪些选项？重新连接、开始采集和停止采集分别用什么控件？ | `verified`
- **KB2-FACT-009** | `new_facts_operations` | dev | 注入器真空设备分布在哪些层？真空计、泵电源和门阀分别通过什么方式与控制系统通信？ | `verified`
- **KB2-FACT-010** | `new_facts_operations` | dev | GUN 段真空控制页面包含多少台 CCG、PRG、离子泵、门阀和温度显示？ | `verified`
- **KB2-FACT-011** | `new_facts_operations` | dev | 沈科仪（SKY）离子泵电源的压力保护值、压力回差值和保护电流分别怎样设置？输入格式和回差比例有什么限制？ | `verified`
- **KB2-FACT-012** | `new_facts_operations` | dev | 当前系统有哪几种 Agilent 离子泵电源、各多少台、编号是什么？ | `verified`
- **KB2-FACT-013** | `new_facts_operations` | dev | Inficon 094 真空计最多可以带几个真空规？有几路保护继电器输出？修改保护阈值时 SP Low 与 SP High 的关系是什么？设定后为什么要保存参数？ | `verified`
- **KB2-FACT-014** | `new_facts_operations` | dev | SHINE PDU 界面操作手册中，每台 PDU 有几个通道？主界面和 details 页面分别能查看哪些电气量？能否重启 PDU？ | `verified`
- **KB2-FACT-015** | `new_facts_operations` | sealed | 在 archiver appliance web 查询软件中，Check Status 显示“Being archived”表示什么？输入“*”会看到什么？details 页面可以对 PV 做哪些操作？ | `verified`
- **KB2-FACT-016** | `new_facts_operations` | sealed | 2023-10《数据存档系统查询软件设计报告》中，Quick chart 显示波形数据时，横坐标的上下两个位置分别表示什么？黄色点表示什么？ | `verified`
- **KB2-FACT-017** | `new_facts_operations` | sealed | 第三版（202411）《SHINE注入段段真空控制界面操作手册》中，分子泵机组共有几套？InjCM 段和 BI 段分别采用什么组合？ | `verified`
- **KB2-FACT-018** | `new_facts_operations` | sealed | 2023-10 数据存储系统设计报告中，EPICS Archiver Appliance 服务用什么命令启动和停止？查询运行状态用什么命令？web 查询入口是什么地址？ | `verified`
- **KB2-FACT-019** | `new_facts_operations` | sealed | V6 优化设计报告的总体目标是什么？装置由哪些主要部分组成？请给出能量、波荡器线、光束线和首批实验站数量。 | `derived_from_analysis`
- **KB2-FACT-020** | `new_facts_operations` | sealed | V6 中 SHINE 主加速器采用什么工作模式？注入器出口能量约多少？三个加速段分别有多少个 1.3 GHz 模组？ | `derived_from_analysis`
- **KB2-VER-001** | `version_comparison` | dev | 对照 2023-09 归档版《定时系统控制界面操作说明》与 2023-12-06 第二版《SHINE定时界面操作手册》：第二版在信号控制和全局频率设置中新增了哪个束测信号？两版的频率分组有何不同？ | `verified`
- **KB2-VER-002** | `version_comparison` | dev | 对照第一版《SHINE定时界面操作手册》与 2023-09 归档版《定时系统控制界面操作说明》：控制机器时钟输出使能时，哪一版要求先点 Enable/Disable 再点 APPLY？两版步骤能否互换？ | `verified`
- **KB2-VER-003** | `version_comparison` | dev | 对照第一版与 2023-12-06 第二版定时界面手册：全局频率设置的分组方式有什么变化？第一版的“其余系统频率设置”与第二版的 LLRF、同步频率设置如何对应？ | `verified`
- **KB2-VER-004** | `version_comparison` | dev | 对照第一版《SHINE恒温机柜界面操作手册》与 2023-09 归档版《恒温机柜控制界面操作说明》：两版都控制几台机柜？开停机柜、设置温度阈值和报警灯语义是否一致？能否据此认定它们是同一修订？ | `verified`
- **KB2-VER-005** | `version_comparison` | dev | 对照 2024-10 归档版《SHINE注入段真空控制操作手册》与 第三版（202411）《SHINE注入段段真空控制界面操作手册》：GUN 段页面统计是否变化？能否据此认定第三版取代归档版？ | `verified`
- **KB2-VER-006** | `version_comparison` | dev | 对照 2023-09 第一版《SHINE数据存档系统archiverDesktop操作手册》与 2024-11《SHINE存档数据查询软件操作手册》：主窗口区域数从几变几？新增了哪些区域？ | `verified`
- **KB2-VER-007** | `version_comparison` | dev | 对照 2023-09 第一版与 2024-11 版 archiverDesktop 手册：图形右键菜单的可用性说明有什么变化？2024-11 版给出的导出路径是什么？ | `verified`
- **KB2-VER-008** | `version_comparison` | sealed | 对照 2023-09 第一版与 2024-11 版 archiverDesktop 手册：2024-11 版新增了哪两种历史数据导出方式？各自的时间限制是什么？第一版是否已有这些导出说明？ | `verified`
- **KB2-VER-009** | `version_comparison` | sealed | 对照 2023-09 第一版与 2024-11 版 archiverDesktop 手册：2024-11 版新增的 Live 和关联图功能分别是什么？第一版是否已有这两项？ | `verified`
- **KB2-VER-010** | `version_comparison` | dev | 对照第一版《SHINE数据存档系统web查询软件操作手册》与 2023-12-06 第二版《archiver appliance数据存档系统web查询软件操作手册》：第二版新增了哪些概述和多 PV 说明？第一版是否已有这… | `verified`
- **KB2-VER-011** | `version_comparison` | dev | 对照 2023-10《数据存档系统查询软件设计报告》与 2023-12-06 第二版 web 查询操作手册：两者是什么关系？设计报告能否当作第二版操作手册的发布说明？ | `verified`
- **KB2-VER-012** | `version_comparison` | sealed | 对照 2018-11《常规功率源控制初步设计报告》与 V6《优化设计报告-加速器分册（返回通读版本）》：两处对 SHINE 直线加速器能量的表述分别是多少？哪一个是现行依据？ | `derived_from_analysis`
- **KB2-VER-013** | `version_comparison` | sealed | 对照《快联锁样机设计报告》的设计指标与同批样机测试/ANALYSIS 摘要：单节点/整系统响应时间的设计要求是多少？FPGA 快保护和 PLC 的实测/实现量级分别是多少？能否把 11.8 µs 当作满足“小于 10 µ… | `derived_from_analysis`
- **KB2-VER-014** | `version_comparison` | dev | 对照 2018-07《定时样机设计报告》的设计指标与旧题 P50-009 中 Prototype II 的实测口径：设计时钟精度/抖动是多少？实测抖动有哪三个口径、分别是什么？两组数能否直接互换？ | `derived_from_analysis`
- **KB2-VER-015** | `version_comparison` | sealed | web 查询软件与 archiverDesktop 是同一软件的两个版本吗？两者在架构和主要功能上分别是什么关系？ | `verified`
- **KB2-FMT-001** | `format_evidence` | dev | 2023-10《数据存储系统设计报告》的服务器配置清单中，服务器型号、CPU、内存和物理磁盘分别是什么？请逐项给出数量、型号/规格和容量。 | `verified`
- **KB2-FMT-002** | `format_evidence` | dev | 2023-10《数据存储系统设计报告》的目录结构表中，/arch 根目录下的 sts、mts、lts 分别指向哪里？请按表格结构给出对应关系。 | `verified`
- **KB2-FMT-003** | `format_evidence` | dev | 在《端子对应表最终版3.8现场改造.xlsx》的“主控柜 (调整)”工作表中，信号源 FEEDCAP1、前线号 F1001（压力传感器，量程 0–5 bar）这一行对应的航插号、航插接口、端子排、端子编号、后线号、模块接… | `needs_source_check`
- **KB2-FMT-004** | `format_evidence` | dev | 在端子对应表中，前线号、航插号、端子排、端子编号、后线号、模块接口、连接信号、模块型号、槽号分别表示什么？为什么不能按相邻行推断接线关系？ | `needs_source_check`
- **KB2-FMT-005** | `format_evidence` | dev | 在《快联锁样机工艺设计评审报告.pptx》（2019-12-20）中，给出单节点和整系统响应时间指标的是哪一页幻灯片？请报告幻灯片序号、页面标题和指标原文，并说明它是设计指标还是实测结果。 | `needs_source_check`
- **KB2-FMT-006** | `format_evidence` | dev | 在《定时样机评审报告.pptx》（2018-07-12）中，设计指标页给出的时钟精度和抖动指标分别是多少？请给出幻灯片序号、指标原文、单位与统计口径。 | `needs_source_check`
- **KB2-FMT-007** | `format_evidence` | dev | 在《恒温机柜控制样机验收评审报告.pptx》中，验收测试项和结论分别是什么？请给出幻灯片序号、测试项、实测值/判定和结论原文。 | `needs_source_check`
- **KB2-FMT-008** | `format_evidence` | sealed | 《机柜命名规则.pptx》规定的机柜命名格式是什么？请给出字段顺序、分隔符和至少两个示例，并说明备注中是否另有适用条件。 | `needs_source_check`
- **KB2-FMT-009** | `format_evidence` | sealed | 《快联锁样机测试报告.pdf》（17 页扫描件）中，单节点和整系统的实测响应时间分别是多少？请给出页码、测量条件、单位和原文表格/图注位置。 | `needs_source_check`
- **KB2-FMT-010** | `format_evidence` | sealed | 《设备命名规则》（SHINE-OP-TL-018-R0-20190903，14 页扫描件）中，控制信号命名的字段构成和分隔规则是什么？请给出页码与至少一个示例。 | `needs_source_check`
- **KB2-FMT-011** | `format_evidence` | dev | 《SHINE 项目技术代号规则》（SHINE-OP-TL-004-2022，12 页扫描件）中，加速器总体、直线加速器分总体等系统代号的层级和写法是什么？请给出页码与示例。 | `needs_source_check`
- **KB2-FMT-012** | `format_evidence` | dev | 《24. 控制需求工作联系单.pdf》（47 页扫描件）中，任选一条控制需求，给出提出系统、需求内容、接口方式和页码；请说明该表是需求记录还是已实现接口。 | `needs_source_check`
- **KB2-FMT-013** | `format_evidence` | sealed | 从 V6《优化设计报告-加速器分册》中选取一个定义加速器能量/加速梯度的公式，给出可编辑 LaTeX 源码、符号定义、单位和所在章节/表格位置。 | `needs_source_check`
- **KB2-FMT-014** | `format_evidence` | sealed | 在《联锁系统初步设计报告.docx》（2019-10，14 个表格）中，找出慢联锁和快联锁的关键信号响应时间指标表，分别给出站内/站间（或单节点/节点间）的数值、比较符、单位和表名/表号。 | `needs_source_check`
- **KB2-FMT-015** | `format_evidence` | dev | 在《硬X射线自由电子激光装置网络安全设计报告.docx》（2026-11-05，76 个表格）中，任选一张访问控制/网络分区表，给出表名、表头、一行具体规则和所在章节；该表能否直接证明现场已按此配置？ | `needs_source_check`
- **KB2-BND-001** | `conflict_boundary` | dev | 《硬X射线自由电子激光装置网络安全设计报告》封面写 2026 年 11 月 5 日，晚于本计划编制日期 2026-11-02，且审核/审定/会签栏为空。能否把该报告当作 kb-2.0.0 的现行批准依据？ | `derived_from_analysis`
- **KB2-BND-002** | `conflict_boundary` | dev | V6 优化设计报告文件名含“返回通读版本”。能否据此把 V6 当作 kb-2.0.0 的正式现行版？回答应说明还需确认哪些信息。 | `derived_from_analysis`
- **KB2-BND-003** | `conflict_boundary` | dev | 2018-11《常规功率源控制初步设计报告》写 SHINE 是 8 GeV 超导直线加速器，V6 写 7.2 GeV。面对“SHINE 是多少 GeV”的问题，正确回答应怎样处理这个冲突？ | `derived_from_analysis`
- **KB2-BND-004** | `conflict_boundary` | dev | 2023-10《数据存储系统设计报告》一方面写“将服务器磁盘配置为 RAID5”，另一方面配置清单写“2 x 480GB raid 1”。能否回答“所有磁盘都是 RAID5”？ | `verified`
- **KB2-BND-005** | `conflict_boundary` | dev | 2024-10《SHINE注入段真空控制操作手册》封面有编制人缪海峰和日期，但审核、审定、会签栏为空。能否把它称为“已批准/现行”的操作手册？ | `verified`
- **KB2-BND-006** | `conflict_boundary` | dev | 2023-09《硬X射线自由电子激光装置项目 定时系统控制界面操作说明》封面编制、审核、审定、会签栏均为空，只有“2023年9月”。能否据此认定它是已批准的现行操作依据？ | `verified`
- **KB2-BND-007** | `conflict_boundary` | sealed | 仅凭《恒温机柜控制界面操作说明》或《定时系统控制界面操作说明》，能否回答“今天 8 台 LLRF 恒温机柜的实际温度是多少”或“当前定时系统频率是多少”？ | `verified`
- **KB2-BND-008** | `conflict_boundary` | sealed | 《SHINE激光界面操作手册》写“目前上线参与调试的设备有……”。能否用它回答“今天 B3/B5 激光设备实际在线哪些”？ | `verified`
- **KB2-BND-009** | `conflict_boundary` | sealed | 仅凭《SHINE电源分配器PDU界面操作手册》，能否回答“现场共有多少台 PDU、分别是什么型号”？ | `verified`
- **KB2-BND-010** | `conflict_boundary` | sealed | 2024-11 archiverDesktop 手册写“Export Raw Data……最多导出 2 周的数据”。能否据此回答“存档系统只保留 2 周历史数据”？ | `verified`

## 需要业务审核人裁决的题目

以下题目的答案边界、证据位置或版本状态在冻结前必须由业务审核人确认：

- 全部格式证据题：`FMT-001`～`FMT-015`。
- 二手推导题：`FACT-019`、`FACT-020`、`VER-012`、`VER-013`、`VER-014`、`BND-001`、`BND-002`、`BND-003`。
- 版本身份/产品关系：`VER-001`～`VER-005`、`VER-012`～`VER-015`。
- 批准状态/资料边界：`BND-001`～`BND-006`。

## 业务审核重点（最需要确认的 10 个问题）

1. `KB2-BND-001`：网络安全设计报告封面日期 2026-11-05、审核/审定/会签为空：能否作为 kb-2.0.0 现行依据？
2. `KB2-BND-002`：V6 文件名含“返回通读版本”：能否作为正式现行版？替代范围与生效时间是什么？
3. `KB2-BND-003`：2018 初步设计 8 GeV 与 V6 7.2 GeV 冲突：当前应如何回答“SHINE 是多少 GeV”？
4. `KB2-VER-013`：快联锁设计要求 <10 µs / <100 µs 与 FPGA 约 11.8 µs、PLC 约 33 ms 的实测/实现口径如何区分？
5. `KB2-VER-014`：定时样机设计 1 ns / <30 ps 与 Prototype II 实测 <20/<10/<35 ps 的口径如何区分？
6. `KB2-FMT-014`：联锁初步设计报告 14 个表格中的慢/快联锁指标表：表名、站内/站间或单节点/节点间的具体表值是什么？
7. `KB2-FMT-003`：端子对应表 F1001 行的航插号、端子排、端子编号、后线号、模块接口、槽号等单元格值是否与 inventory head 一致？
8. `KB2-FMT-013`：V6 公式的 LaTeX 源码、符号、单位和章节位置：哪些公式可作为验收金标准？
9. `KB2-FMT-009`：快联锁样机测试报告 17 页扫描件的实测响应时间、测量条件与页码：OCR 后哪些数值可人工确认？
10. `KB2-BND-005`：2024-10 真空操作手册封面审核/审定/会签为空：应标为待核实还是可按归档版使用？

## 使用限制

- 本摘要不包含完整 `required_facts`、`forbidden_inferences`、`task_condition` 和 `expected_answer_boundary`；评分必须读 JSON。
- 当前为规划态，60 题均未冻结；代表样本解析后须按设计文档第 5 节冻结，不能直接用本表计算通过率。
- 封存 20 题不得用于提示词/检索策略调参；一旦使用即退回开发集并补充新封存题。
