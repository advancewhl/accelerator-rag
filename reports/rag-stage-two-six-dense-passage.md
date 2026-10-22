# RAG Stage 2.6 Dense Passage Compatibility

本轮只改变 Dense 表示。Corpus、eligibility、BM25、query set、query template、模型和余弦距离保持一致。

## 总体 A/B

| 检索器 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| bm25 | 21 | 0.3810 | 0.6667 | 0.7143 | 0.5198 |
| dense_a | 21 | 0.0952 | 0.1905 | 0.3810 | 0.1802 |
| dense_b | 21 | 0.0952 | 0.2381 | 0.4286 | 0.2040 |

## by_query_language

所有切片均为 diagnostic only。zh-en 支持两种语言；混合来源保守归为 cross_language。

| 切片 / 检索器 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| en / dense_a | 13 | 0.0769 | 0.1538 | 0.4615 | 0.1756 |
| en / dense_b | 13 | 0.0769 | 0.1538 | 0.4615 | 0.1756 |
| zh / dense_a | 8 | 0.1250 | 0.2500 | 0.2500 | 0.1875 |
| zh / dense_b | 8 | 0.1250 | 0.3750 | 0.3750 | 0.2500 |

## by_language_relation

所有切片均为 diagnostic only。zh-en 支持两种语言；混合来源保守归为 cross_language。

| 切片 / 检索器 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| cross_language / dense_a | 3 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| cross_language / dense_b | 3 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| same_language / dense_a | 18 | 0.1111 | 0.2222 | 0.4444 | 0.2102 |
| same_language / dense_b | 18 | 0.1111 | 0.2778 | 0.5000 | 0.2380 |

## by_category

所有切片均为 diagnostic only。zh-en 支持两种语言；混合来源保守归为 cross_language。

| 切片 / 检索器 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| accelerator_design / dense_a | 4 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| accelerator_design / dense_b | 4 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| beam_diagnostics / dense_a | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| beam_diagnostics / dense_b | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| beam_transport / dense_a | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| beam_transport / dense_b | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| control_architecture / dense_a | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2000 |
| control_architecture / dense_b | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2000 |
| cryogenics / dense_a | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| cryogenics / dense_b | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| epics / dense_a | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| epics / dense_b | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| interlock / dense_a | 3 | 0.3333 | 0.6667 | 0.6667 | 0.5000 |
| interlock / dense_b | 3 | 0.3333 | 1.0000 | 1.0000 | 0.6667 |
| ioc / dense_a | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| ioc / dense_b | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| photon_diagnostics / dense_a | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333 |
| photon_diagnostics / dense_b | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333 |
| pv / dense_a | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| pv / dense_b | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| timing / dense_a | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| timing / dense_b | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |

## by_expected_document

所有切片均为 diagnostic only。zh-en 支持两种语言；混合来源保守归为 cross_language。

| 切片 / 检索器 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| epics-application-developers-guide-r3-16-2 / dense_a | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| epics-application-developers-guide-r3-16-2 / dense_b | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| epics-documentation-latest-2026-08-18 / dense_a | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| epics-documentation-latest-2026-08-18 / dense_b | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| european-xfel-full-technical-design-report-2007 / dense_a | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| european-xfel-full-technical-design-report-2007 / dense_b | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| european-xfel-standard-e-beam-diagnostics-linac2010 / dense_a | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| european-xfel-standard-e-beam-diagnostics-linac2010 / dense_b | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| european-xfel-undulator-commissioning-spectrometer-cdr-2011 / dense_a | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333 |
| european-xfel-undulator-commissioning-spectrometer-cdr-2011 / dense_b | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333 |
| european-xfel-x-ray-optics-beam-transport-tdr-2012 / dense_a | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| european-xfel-x-ray-optics-beam-transport-tdr-2012 / dense_b | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shine-accelerator-control-system-design-presentation / dense_a | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| shine-accelerator-control-system-design-presentation / dense_b | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| shine-accelerator-fast-interlock-2024 / dense_a | 2 | 0.0000 | 0.5000 | 0.5000 | 0.2500 |
| shine-accelerator-fast-interlock-2024 / dense_b | 2 | 0.0000 | 1.0000 | 1.0000 | 0.5000 |
| shine-accelerator-preliminary-design-report-2017 / dense_a | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shine-accelerator-preliminary-design-report-2017 / dense_b | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shine-control-system-status-icalepcs2019 / dense_a | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2000 |
| shine-control-system-status-icalepcs2019 / dense_b | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2000 |
| shine-cryogenic-control-system-2021 / dense_a | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| shine-cryogenic-control-system-2021 / dense_b | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| shine-epics-ioc-pv-information-management-pcapac2022 / dense_a | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shine-epics-ioc-pv-information-management-pcapac2022 / dense_b | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shine-white-rabbit-beam-synchronous-timing-ipac2022 / dense_a | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| shine-white-rabbit-beam-synchronous-timing-ipac2022 / dense_b | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |

## 全部 answerable query 回归表

| Query | A rank | A Hit@5 | B rank | B Hit@5 | status |
|---|---:|---|---:|---|---|
| epics-pp | None | False | None | False | unchanged |
| epics-reconnect | 4 | True | 4 | True | unchanged |
| epics-cli | None | False | None | False | unchanged |
| xfel-rf | None | False | None | False | unchanged |
| xfel-normal-energy | None | False | None | False | unchanged |
| undulator-tuning | 3 | True | 3 | True | unchanged |
| xfel-mirror-angle | None | False | None | False | unchanged |
| xfel-soft-mono | None | False | None | False | unchanged |
| xfel-bpm-types | 1 | True | 1 | True | unchanged |
| shine-ioc-management | None | False | None | False | unchanged |
| shine-ioc-startup | None | False | None | False | unchanged |
| interlock-latency | None | False | 2 | True | improved |
| interlock-platform | 2 | True | 2 | True | unchanged |
| shine-control-layers | 5 | True | 5 | True | unchanged |
| cryo-integration | 4 | True | 4 | True | unchanged |
| cryo-interlock | None | False | None | False | unchanged |
| timing-wrtd | 4 | True | 4 | True | unchanged |
| timing-jitter | None | False | None | False | unchanged |
| control-slow-interlock | 1 | True | 1 | True | unchanged |
| shine-compressors | None | False | None | False | unchanged |
| shine-main-linac | None | False | None | False | unchanged |

## 变化与诊断 case

以下展示全部变化，并补足至少 5 个诊断 case；未变化的问题不伪称改善。

### interlock-latency（improved）

- A rank 1，score 0.736094，`shine-accelerator-fast-interlock-2024`，物理页 7，`shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量
- A rank 2，score 0.726798，`shine-accelerator-fast-interlock-2024`，物理页 8，`shine-accelerator-fast-interlock-2024:edd3cf33739f6a91d0e07b8563181b17dba2b9beafabe69c85ae292a1a0eb052`。
  核 技 术 2024, 47: 120203  单节点平均响应时间为328.81 ns，节点间经800 m 电缆连接的系统平均响应时间为5.33 µs，均优于快 联锁系统的设计指标。系统运行模式的设置和传输 功能正常，各站点在不同模式下相应联锁逻辑切换 等功能也已通过测试并投入正常运行。SHINE加速 器快联锁系统功能完善，运行稳定正常，满足系统的 设计要求。  作者贡献声明 于春蕾负责联锁系统的整体设计、 需求对接、运行模式设计和实现、快联锁系统的设计 与开发，并负责数据的收集和整理、文章的起草和最 终版本的修订；陈广花负责研究的提出及设计，样机 的搭建和测试；丁建国负责系统设计的指导和监督
- A rank 3，score 0.687768，`shine-accelerator-control-system-design-presentation`，物理页 21，`shine-accelerator-control-system-design-presentation:4e92201c2cf375a954b2860baf67a725b258f56b1a36a01b061e46d2775928dc`。
  联锁系统  \uf06e 快联锁 + 慢联锁；主站 + 从站，分层设计  \uf0b2快联锁关键信号响应时间：  站内≤10us，站间≤100us  \uf0b2慢联锁关键信号响应时间：  站内≤20ms，站间≤100ms
- B rank 1，score 0.740364，`shine-accelerator-fast-interlock-2024`，物理页 7，`shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量
- B rank 2，score 0.730097，`shine-accelerator-fast-interlock-2024`，物理页 2，`shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b`。
  核 技 术 2024, 47: 120203  and the system have been put into online operation for SHINE injector. The response time test results meet the  SHINE operation requirements, and remote control of the system has been implemented based on the EPICS.  Key words Fast interlock, FPGA, Data transmission, FL-net, 
- B rank 3，score 0.718147，`shine-accelerator-fast-interlock-2024`，物理页 8，`shine-accelerator-fast-interlock-2024:edd3cf33739f6a91d0e07b8563181b17dba2b9beafabe69c85ae292a1a0eb052`。
  核 技 术 2024, 47: 120203  单节点平均响应时间为328.81 ns，节点间经800 m 电缆连接的系统平均响应时间为5.33 µs，均优于快 联锁系统的设计指标。系统运行模式的设置和传输 功能正常，各站点在不同模式下相应联锁逻辑切换 等功能也已通过测试并投入正常运行。SHINE加速 器快联锁系统功能完善，运行稳定正常，满足系统的 设计要求。  作者贡献声明 于春蕾负责联锁系统的整体设计、 需求对接、运行模式设计和实现、快联锁系统的设计 与开发，并负责数据的收集和整理、文章的起草和最 终版本的修订；陈广花负责研究的提出及设计，样机 的搭建和测试；丁建国负责系统设计的指导和监督

命中 passage：

- parent `shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`，passage ordinal 1，score 0.740364。
  响应时间平均值为5.33 µs，满足节 点间响应时间100 µs的设计要求。  图9 单节点响应时间测试的示波器截图 Fig.9 Snapshot of oscilloscope results for single node  response time test  图10 节点间响应时间测试的示波器截图  (a) 1 m电缆连接，(b) 800 m电缆连接 Fig.10 Snapshot of oscilloscope results for multi-nodes response time test (a) 1 m cable connection, (b) 800 m cable  connection  6 结语  通过自行开发代码，完成了基于FPGA 的快联 锁逻辑功能开发、快联锁和慢联锁之间数据通讯开 发、EPICS 远程控制系统的开
- parent `shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b`，passage ordinal 1，score 0.730097。
  系统单节点响应时间 应小于10 µs，节点间的响应时间应小于100 µs。传  统基于可编程逻辑控制器（Programmable Logic Controller，PLC）的联锁系统响应时间仅在毫秒量  级  ［7］，因此，快联锁系统需要采用基于现场可编程门  阵列（Field Programmable Gate Array，FPGA）的技术  路线  ［8］。为区别于快联锁系统，基于传统PLC IO模  块的联锁系统称为慢联锁系统。其次，SHINE 装置  的总长度达到3 100 m，联锁系统的站点数量、信号  数量和种类以及地理分布范围都随之扩大，联锁站  点预计达到100个。如何实现大规模系统架构下特  殊信号的传输和共享，也是联锁系统设计中需要解  决和考虑的问题。基于以上需求，SHINE 需搭建一  套基于FPGA+PLC的联锁系统，并且对
- parent `shine-accelerator-fast-interlock-2024:edd3cf33739f6a91d0e07b8563181b17dba2b9beafabe69c85ae292a1a0eb052`，passage ordinal 0，score 0.718147。
  核 技 术 2024, 47: 120203  单节点平均响应时间为328.81 ns，节点间经800 m 电缆连接的系统平均响应时间为5.33 µs，均优于快 联锁系统的设计指标。系统运行模式的设置和传输 功能正常，各站点在不同模式下相应联锁逻辑切换 等功能也已通过测试并投入正常运行。SHINE加速 器快联锁系统功能完善，运行稳定正常，满足系统的 设计要求。  作者贡献声明 于春蕾负责联锁系统的整体设计、 需求对接、运行模式设计和实现、快联锁系统的设计 与开发，并负责数据的收集和整理、文章的起草和最 终版本的修订；陈广花负责研究的提出及设计，样机 的搭建和测试；丁建国负责系统设计的指导和监督、 系统机柜集成的硬件设计；李明负责系统的工艺流 程和实施工作，慢联锁系统的软件开发和调试；肖庆 雯负责基于EPICS 远程控制系统的开发和调试；阎 映炳负责文

### interlock-platform（unchanged）

- A rank 1，score 0.733792，`shine-accelerator-fast-interlock-2024`，物理页 2，`shine-accelerator-fast-interlock-2024:568004790ecec62325207c734c8249811e0ba0c6f1da6fac206316dcbe9e20a5`。
  SHINE 联锁系统采用“成熟的硬件板卡+完全 自主开发联锁功能软件”的系统方案，确定了基于横 河FPIO（Field Programmable High-speed IO）模块的 快联锁开发方案。FPIO 模块是在横河FA-M3/e-RT3的基础上安装和使用的高功能I/O模块，具备µs 级的IO 响应时间，其结构图如图2 所示。模块内置 FPGA，允许用户在模块中开发和编译FPGA 功能， 开放用户自主开发用户逻辑回路。模块共有24 个 LED 灯，可指定任意信号显示；每个模块支持24 路 输入和24路的输出（5~24 V）。  SHINE直线段的机柜需要直接安装在加速器隧 道内，机柜规格只
- A rank 2，score 0.717186，`shine-accelerator-fast-interlock-2024`，物理页 3，`shine-accelerator-fast-interlock-2024:3989f77d1ed901e922429b49a72751dc4b71b50fb0267e5c7a8fe005090a5120`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  系统的工艺和供电问题，并且缩减了快联锁系统所 需的安装空间，和慢联锁系统在硬件结构和外观上 可结合为一个“整体”。FPIO 模块内置的FPGA 使 用的是Xilinx 公司的Spartan6 XC6SLX25 系列芯 片，其开发和设计流程遵循FPGA开发的通用流程。 模块带有编程口，通过转接线缆和JTAG 编程线缆 可连接计算机，实现与Xilinx 的工具包ISE Design  Suite 的连接。BSP（Board Support Program）板级支 持软件提供了部分可调用的接口模块和功能。在此 基础上，使用硬件描述性语言可以实现联锁
- A rank 3，score 0.675657，`shine-accelerator-fast-interlock-2024`，物理页 3，`shine-accelerator-fast-interlock-2024:a5b7baa31dd6b7e2bccef2a847deb913b96aac8381844a10f7aa0d1ea5b4ac6a`。
  在快联锁FPGA 逻辑程序开发过程中，需要配 置和定义系统自主的userlogic.h 头文件，将需要与 CPU之间进行数据交互的寄存器在此文件中进行地 址和变量的声明，在此基础上通过读写接口模块的 开发和调用，在CPU端即可通过梯形图读写头文件 中相应地址的寄存器数值。  图3 快联锁与慢联锁系统总体结构图 Fig.3 General architecture of fast interlock system and slow interlock system  SHINE的远程控制系统使用加速器主流的分布 式控制软件EPICS（Experimental Physics and Indust
- B rank 1，score 0.733792，`shine-accelerator-fast-interlock-2024`，物理页 2，`shine-accelerator-fast-interlock-2024:568004790ecec62325207c734c8249811e0ba0c6f1da6fac206316dcbe9e20a5`。
  SHINE 联锁系统采用“成熟的硬件板卡+完全 自主开发联锁功能软件”的系统方案，确定了基于横 河FPIO（Field Programmable High-speed IO）模块的 快联锁开发方案。FPIO 模块是在横河FA-M3/e-RT3的基础上安装和使用的高功能I/O模块，具备µs 级的IO 响应时间，其结构图如图2 所示。模块内置 FPGA，允许用户在模块中开发和编译FPGA 功能， 开放用户自主开发用户逻辑回路。模块共有24 个 LED 灯，可指定任意信号显示；每个模块支持24 路 输入和24路的输出（5~24 V）。  SHINE直线段的机柜需要直接安装在加速器隧 道内，机柜规格只
- B rank 2，score 0.717695，`shine-accelerator-fast-interlock-2024`，物理页 3，`shine-accelerator-fast-interlock-2024:3989f77d1ed901e922429b49a72751dc4b71b50fb0267e5c7a8fe005090a5120`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  系统的工艺和供电问题，并且缩减了快联锁系统所 需的安装空间，和慢联锁系统在硬件结构和外观上 可结合为一个“整体”。FPIO 模块内置的FPGA 使 用的是Xilinx 公司的Spartan6 XC6SLX25 系列芯 片，其开发和设计流程遵循FPGA开发的通用流程。 模块带有编程口，通过转接线缆和JTAG 编程线缆 可连接计算机，实现与Xilinx 的工具包ISE Design  Suite 的连接。BSP（Board Support Program）板级支 持软件提供了部分可调用的接口模块和功能。在此 基础上，使用硬件描述性语言可以实现联锁
- B rank 3，score 0.675657，`shine-accelerator-fast-interlock-2024`，物理页 3，`shine-accelerator-fast-interlock-2024:a5b7baa31dd6b7e2bccef2a847deb913b96aac8381844a10f7aa0d1ea5b4ac6a`。
  在快联锁FPGA 逻辑程序开发过程中，需要配 置和定义系统自主的userlogic.h 头文件，将需要与 CPU之间进行数据交互的寄存器在此文件中进行地 址和变量的声明，在此基础上通过读写接口模块的 开发和调用，在CPU端即可通过梯形图读写头文件 中相应地址的寄存器数值。  图3 快联锁与慢联锁系统总体结构图 Fig.3 General architecture of fast interlock system and slow interlock system  SHINE的远程控制系统使用加速器主流的分布 式控制软件EPICS（Experimental Physics and Indust

命中 passage：

- parent `shine-accelerator-fast-interlock-2024:568004790ecec62325207c734c8249811e0ba0c6f1da6fac206316dcbe9e20a5`，passage ordinal 0，score 0.733792。
  SHINE 联锁系统采用“成熟的硬件板卡+完全 自主开发联锁功能软件”的系统方案，确定了基于横 河FPIO（Field Programmable High-speed IO）模块的 快联锁开发方案。FPIO 模块是在横河FA-M3/e-RT3的基础上安装和使用的高功能I/O模块，具备µs 级的IO 响应时间，其结构图如图2 所示。模块内置 FPGA，允许用户在模块中开发和编译FPGA 功能， 开放用户自主开发用户逻辑回路。模块共有24 个 LED 灯，可指定任意信号显示；每个模块支持24 路 输入和24路的输出（5~24 V）。  SHINE直线段的机柜需要直接安装在加速器隧 道内，机柜规格只有26U，因此设备安装的空间十分  有限。FPIO模块与常规PLC模块的大小相同，能够 直接安装在PLC的底板上，这样有效解决了快联锁  图1 SHINE装置示
- parent `shine-accelerator-fast-interlock-2024:3989f77d1ed901e922429b49a72751dc4b71b50fb0267e5c7a8fe005090a5120`，passage ordinal 0，score 0.717695。
  于春蕾等： SHINE加速器快联锁系统设计与开发  系统的工艺和供电问题，并且缩减了快联锁系统所 需的安装空间，和慢联锁系统在硬件结构和外观上 可结合为一个“整体”。FPIO 模块内置的FPGA 使 用的是Xilinx 公司的Spartan6 XC6SLX25 系列芯 片，其开发和设计流程遵循FPGA开发的通用流程。 模块带有编程口，通过转接线缆和JTAG 编程线缆 可连接计算机，实现与Xilinx 的工具包ISE Design  Suite 的连接。BSP（Board Support Program）板级支 持软件提供了部分可调用的接口模块和功能。在此 基础上，使用硬件描述性语言可以实现联锁系统自 行定义的控制逻辑开发，SHINE 联锁系统选用 verilog HDL语言进行相关功能开发。表1列出了在 快联锁系统开发过程中用到的软硬件。  表1 快
- parent `shine-accelerator-fast-interlock-2024:a5b7baa31dd6b7e2bccef2a847deb913b96aac8381844a10f7aa0d1ea5b4ac6a`，passage ordinal 0，score 0.675657。
  在快联锁FPGA 逻辑程序开发过程中，需要配 置和定义系统自主的userlogic.h 头文件，将需要与 CPU之间进行数据交互的寄存器在此文件中进行地 址和变量的声明，在此基础上通过读写接口模块的 开发和调用，在CPU端即可通过梯形图读写头文件 中相应地址的寄存器数值。  图3 快联锁与慢联锁系统总体结构图 Fig.3 General architecture of fast interlock system and slow interlock system  SHINE的远程控制系统使用加速器主流的分布 式控制软件EPICS（Experimental Physics and Industrial Control System）进行开发与设计，联锁系  统通过PLC CPU端的网络接口可以连接到控制网， 实现与IOC 服务器的通讯  ［9］。目前

### shine-compressors（unchanged）

- A rank 1，score 0.502994，`shine-accelerator-control-system-design-presentation`，物理页 6，`shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`。
  \uf06e Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE)  e-beam : 8 GeV Photon energy : 0.4 ～25 keV Pulse duration : 1～100 fs Repetition : 1 MHz Total length : 3.1 km Underground ~ 29 m  SHINE
- A rank 2，score 0.497280，`shine-accelerator-preliminary-design-report-2017`，物理页 197，`shine-accelerator-preliminary-design-report-2017:c3dd78611920f09598f129f0e4d5216575f790c1d9508f8e77d478270a26468c`。
  图3.3.4.2-3 束流偏转线总体布局图  经过直线加速器加速后的束流，传输至直线加速器出口前120 米处开始进入  束流分配段，此处开始往后25 米是LTU2 偏转线的Kicker 系统。LTU2 偏转线  的水平偏转部分是由包括DC Lamberson Septum 在内的四块水平偏转磁铁，以及  若干四极磁铁构成的Dog-leg 偏转结构，总体偏转角度为3˚，水平偏移距离为  1.85 米。其中，DC Lamberson Septum 与一块水平偏转磁铁及两者之间的三块四  极磁铁构成所谓对称双弯铁消色散结构，即Double-Bend-Achromat(DBA)。另两  块水平偏转磁铁
- A rank 3，score 0.496506，`shine-accelerator-preliminary-design-report-2017`，物理页 193，`shine-accelerator-preliminary-design-report-2017:8be003019d5fa5b88c879c1c747daba6790459100a7f38b513a906bf76cbacbf`。
  日本理化所的SACLA 装置束流能量为8GeV，束团重复频率为120Hz。早  期采用水平方向±0.53∘的水平方向冲击磁铁（kicker magnet）结合± 2.47∘的水  平偏转直流切割磁铁（DC septum magnet），实现± 3∘的水平偏转，当kicker 系统  关闭时，束流无偏转通往BL3 波荡器线，+3∘时，束流经过包含kicker 和septum  的dog-leg 偏转结构（即偏转-反向偏转），通往BL2 线，−3∘时则用作SPring8  的注入。然而当该装置运行在较高峰值流强（10kA）模式下，由于偏转时束流  受到相干同步辐射（CSR）效应的影响，束流发射度出
- B rank 1，score 0.510908，`shine-accelerator-preliminary-design-report-2017`，物理页 193，`shine-accelerator-preliminary-design-report-2017:8be003019d5fa5b88c879c1c747daba6790459100a7f38b513a906bf76cbacbf`。
  日本理化所的SACLA 装置束流能量为8GeV，束团重复频率为120Hz。早  期采用水平方向±0.53∘的水平方向冲击磁铁（kicker magnet）结合± 2.47∘的水  平偏转直流切割磁铁（DC septum magnet），实现± 3∘的水平偏转，当kicker 系统  关闭时，束流无偏转通往BL3 波荡器线，+3∘时，束流经过包含kicker 和septum  的dog-leg 偏转结构（即偏转-反向偏转），通往BL2 线，−3∘时则用作SPring8  的注入。然而当该装置运行在较高峰值流强（10kA）模式下，由于偏转时束流  受到相干同步辐射（CSR）效应的影响，束流发射度出
- B rank 2，score 0.502994，`shine-accelerator-control-system-design-presentation`，物理页 6，`shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`。
  \uf06e Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE)  e-beam : 8 GeV Photon energy : 0.4 ～25 keV Pulse duration : 1～100 fs Repetition : 1 MHz Total length : 3.1 km Underground ~ 29 m  SHINE
- B rank 3，score 0.497280，`shine-accelerator-preliminary-design-report-2017`，物理页 197，`shine-accelerator-preliminary-design-report-2017:c3dd78611920f09598f129f0e4d5216575f790c1d9508f8e77d478270a26468c`。
  图3.3.4.2-3 束流偏转线总体布局图  经过直线加速器加速后的束流，传输至直线加速器出口前120 米处开始进入  束流分配段，此处开始往后25 米是LTU2 偏转线的Kicker 系统。LTU2 偏转线  的水平偏转部分是由包括DC Lamberson Septum 在内的四块水平偏转磁铁，以及  若干四极磁铁构成的Dog-leg 偏转结构，总体偏转角度为3˚，水平偏移距离为  1.85 米。其中，DC Lamberson Septum 与一块水平偏转磁铁及两者之间的三块四  极磁铁构成所谓对称双弯铁消色散结构，即Double-Bend-Achromat(DBA)。另两  块水平偏转磁铁

命中 passage：

- parent `shine-accelerator-preliminary-design-report-2017:8be003019d5fa5b88c879c1c747daba6790459100a7f38b513a906bf76cbacbf`，passage ordinal 0，score 0.510908。
  日本理化所的SACLA 装置束流能量为8GeV，束团重复频率为120Hz。早  期采用水平方向±0.53∘的水平方向冲击磁铁（kicker magnet）结合± 2.47∘的水  平偏转直流切割磁铁（DC septum magnet），实现± 3∘的水平偏转，当kicker 系统  关闭时，束流无偏转通往BL3 波荡器线，+3∘时，束流经过包含kicker 和septum  的dog-leg 偏转结构（即偏转-反向偏转），通往BL2 线，−3∘时则用作SPring8  的注入。然而当该装置运行在较高峰值流强（10kA）模式下，由于偏转时束流  受到相干同步辐射（CSR）效应的影响，束流发射度出现了大幅度增长，无法被  BL2 线使用。目前该装置已经更改了设计方案，采用垂直方向偏转kicker 结合水  平方向偏转直流Lamberson 型切割磁铁（D
- parent `shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`，passage ordinal 0，score 0.502994。
  \uf06e Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE)  e-beam : 8 GeV Photon energy : 0.4 ～25 keV Pulse duration : 1～100 fs Repetition : 1 MHz Total length : 3.1 km Underground ~ 29 m  SHINE
- parent `shine-accelerator-preliminary-design-report-2017:c3dd78611920f09598f129f0e4d5216575f790c1d9508f8e77d478270a26468c`，passage ordinal 0，score 0.497280。
  图3.3.4.2-3 束流偏转线总体布局图  经过直线加速器加速后的束流，传输至直线加速器出口前120 米处开始进入  束流分配段，此处开始往后25 米是LTU2 偏转线的Kicker 系统。LTU2 偏转线  的水平偏转部分是由包括DC Lamberson Septum 在内的四块水平偏转磁铁，以及  若干四极磁铁构成的Dog-leg 偏转结构，总体偏转角度为3˚，水平偏移距离为  1.85 米。其中，DC Lamberson Septum 与一块水平偏转磁铁及两者之间的三块四  极磁铁构成所谓对称双弯铁消色散结构，即Double-Bend-Achromat(DBA)。另两  块水平偏转磁铁则同样与三块四极磁铁构成一个相同但反向的DBA 结构。为  抑制CSR 效应引起的发射度增长，采用光学平衡法，DBA 两块偏转磁铁之间的  相移为π，两DBA 

### shine-main-linac（unchanged）

- A rank 1，score 0.664654，`shine-accelerator-control-system-design-presentation`，物理页 8，`shine-accelerator-control-system-design-presentation:6ef921c2c3cc45659c9744acd2df45838e9cbf0bce28f92d2d2dd8fcf1d5cf26`。
  控制系统设计、实施过程中的一些问题  （关于加速器控制工程的一些思考）
- A rank 2，score 0.663262，`shine-accelerator-control-system-design-presentation`，物理页 6，`shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`。
  \uf06e Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE)  e-beam : 8 GeV Photon energy : 0.4 ～25 keV Pulse duration : 1～100 fs Repetition : 1 MHz Total length : 3.1 km Underground ~ 29 m  SHINE
- A rank 3，score 0.654379，`shine-accelerator-control-system-design-presentation`，物理页 14，`shine-accelerator-control-system-design-presentation:f7ab778c51869e4f0c3013020278027e9f046b4b61540c73a840b9990c7895b0`。
  \uf06e一流的装置，需要一流的、数量可观的控制队伍；  \uf06e人员缺口大、招聘难度大、培养周期长，结构不合理；  \uf06e如何充分发挥现有的人员力量？  \uf06e项目之间如何优化配比？  \uf06e如何建立有效的国内、国际合作？
- B rank 1，score 0.664654，`shine-accelerator-control-system-design-presentation`，物理页 8，`shine-accelerator-control-system-design-presentation:6ef921c2c3cc45659c9744acd2df45838e9cbf0bce28f92d2d2dd8fcf1d5cf26`。
  控制系统设计、实施过程中的一些问题  （关于加速器控制工程的一些思考）
- B rank 2，score 0.663262，`shine-accelerator-control-system-design-presentation`，物理页 6，`shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`。
  \uf06e Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE)  e-beam : 8 GeV Photon energy : 0.4 ～25 keV Pulse duration : 1～100 fs Repetition : 1 MHz Total length : 3.1 km Underground ~ 29 m  SHINE
- B rank 3，score 0.662877，`shine-accelerator-fast-interlock-2024`，物理页 5，`shine-accelerator-fast-interlock-2024:fb77460ddb53b1eaa6ea406ddceba2e11119bad8231d16f4a443c62a063769c8`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  损报警等信号，功率源的低电平系统状态和控制信 号、真空快规报警信号等，SHINE快联锁系统主要信 号的数量统计如表2所示。快联锁的逻辑处理与加 速器的运行模式相关，当装置处于运行状态时，任意  一路快联锁信号报警，快联锁系统将执行停束操作， 包括关闭快激光光闸和停止激光系统的定时触发， 如图5所示。  表2 快联锁系统信号统计表 Table 2 Statistical table of fast interlock signals  对接系统 Systems  注入器段信号数量 Numbers of signals from injector

命中 passage：

- parent `shine-accelerator-control-system-design-presentation:6ef921c2c3cc45659c9744acd2df45838e9cbf0bce28f92d2d2dd8fcf1d5cf26`，passage ordinal 0，score 0.664654。
  控制系统设计、实施过程中的一些问题  （关于加速器控制工程的一些思考）
- parent `shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`，passage ordinal 0，score 0.663262。
  \uf06e Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE)  e-beam : 8 GeV Photon energy : 0.4 ～25 keV Pulse duration : 1～100 fs Repetition : 1 MHz Total length : 3.1 km Underground ~ 29 m  SHINE
- parent `shine-accelerator-fast-interlock-2024:fb77460ddb53b1eaa6ea406ddceba2e11119bad8231d16f4a443c62a063769c8`，passage ordinal 1，score 0.662877。
  的模式下自动匹配不同的逻 辑，由主站综合控制，分发给系统的各个站点  ［12］。 根据SHINE加速器结构和调试需求，模式选择 中对加速器进行了分段设计，注入器部分按照电子 枪和完整注入器段设置两个分段模式，直线部分按 照废束桶的位置进行分段，共设BC1（bunch compressor 1）、BC2、break、分支线、直线加速器末端 5 个分段，其中注入器段的运行模式设定和说明 见表3。  系统设有老练和运行两种状态选择，老练模式 一般用于加速器调试和功率源等设备的老练阶段， 由于各系统设备状态不稳定，所有报警信号不锁存， 可实现报警信号的自动复位功能。SHINE装置在不 同重复频率下参与联锁的设备不完全相同，按照设  备对频率的保护要求，频率模式又可划分成高重复 频率、中重复频率和低重复频率三种状态。此外， SHINE 三条波荡器线的运行和调试

### control-slow-interlock（unchanged）

- A rank 1，score 0.778265，`shine-accelerator-control-system-design-presentation`，物理页 21，`shine-accelerator-control-system-design-presentation:4e92201c2cf375a954b2860baf67a725b258f56b1a36a01b061e46d2775928dc`。
  联锁系统  \uf06e 快联锁 + 慢联锁；主站 + 从站，分层设计  \uf0b2快联锁关键信号响应时间：  站内≤10us，站间≤100us  \uf0b2慢联锁关键信号响应时间：  站内≤20ms，站间≤100ms
- A rank 2，score 0.717592，`shine-accelerator-fast-interlock-2024`，物理页 8，`shine-accelerator-fast-interlock-2024:edd3cf33739f6a91d0e07b8563181b17dba2b9beafabe69c85ae292a1a0eb052`。
  核 技 术 2024, 47: 120203  单节点平均响应时间为328.81 ns，节点间经800 m 电缆连接的系统平均响应时间为5.33 µs，均优于快 联锁系统的设计指标。系统运行模式的设置和传输 功能正常，各站点在不同模式下相应联锁逻辑切换 等功能也已通过测试并投入正常运行。SHINE加速 器快联锁系统功能完善，运行稳定正常，满足系统的 设计要求。  作者贡献声明 于春蕾负责联锁系统的整体设计、 需求对接、运行模式设计和实现、快联锁系统的设计 与开发，并负责数据的收集和整理、文章的起草和最 终版本的修订；陈广花负责研究的提出及设计，样机 的搭建和测试；丁建国负责系统设计的指导和监督
- A rank 3，score 0.710922，`shine-accelerator-fast-interlock-2024`，物理页 7，`shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量
- B rank 1，score 0.778265，`shine-accelerator-control-system-design-presentation`，物理页 21，`shine-accelerator-control-system-design-presentation:4e92201c2cf375a954b2860baf67a725b258f56b1a36a01b061e46d2775928dc`。
  联锁系统  \uf06e 快联锁 + 慢联锁；主站 + 从站，分层设计  \uf0b2快联锁关键信号响应时间：  站内≤10us，站间≤100us  \uf0b2慢联锁关键信号响应时间：  站内≤20ms，站间≤100ms
- B rank 2，score 0.727623，`shine-accelerator-fast-interlock-2024`，物理页 7，`shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量
- B rank 3，score 0.714518，`shine-accelerator-fast-interlock-2024`，物理页 2，`shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b`。
  核 技 术 2024, 47: 120203  and the system have been put into online operation for SHINE injector. The response time test results meet the  SHINE operation requirements, and remote control of the system has been implemented based on the EPICS.  Key words Fast interlock, FPGA, Data transmission, FL-net, 

命中 passage：

- parent `shine-accelerator-control-system-design-presentation:4e92201c2cf375a954b2860baf67a725b258f56b1a36a01b061e46d2775928dc`，passage ordinal 0，score 0.778265。
  联锁系统  \uf06e 快联锁 + 慢联锁；主站 + 从站，分层设计  \uf0b2快联锁关键信号响应时间：  站内≤10us，站间≤100us  \uf0b2慢联锁关键信号响应时间：  站内≤20ms，站间≤100ms
- parent `shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`，passage ordinal 0，score 0.727623。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量计数不低于10 000次，测试结 果显示单节点响应时间平均值为328.81 ns，优于单 节点响应时间10 µs的设计指标，示波器测试结果如 图9所示。  在多
- parent `shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b`，passage ordinal 1，score 0.714518。
  系统单节点响应时间 应小于10 µs，节点间的响应时间应小于100 µs。传  统基于可编程逻辑控制器（Programmable Logic Controller，PLC）的联锁系统响应时间仅在毫秒量  级  ［7］，因此，快联锁系统需要采用基于现场可编程门  阵列（Field Programmable Gate Array，FPGA）的技术  路线  ［8］。为区别于快联锁系统，基于传统PLC IO模  块的联锁系统称为慢联锁系统。其次，SHINE 装置  的总长度达到3 100 m，联锁系统的站点数量、信号  数量和种类以及地理分布范围都随之扩大，联锁站  点预计达到100个。如何实现大规模系统架构下特  殊信号的传输和共享，也是联锁系统设计中需要解  决和考虑的问题。基于以上需求，SHINE 需搭建一  套基于FPGA+PLC的联锁系统，并且对

## Passage 统计与预算

```json
{
  "algorithm": "dense-passages-v1",
  "contract": {
    "algorithm": "dense-passages-v1",
    "config": {
      "max_tokens": null,
      "guard_tokens": 16,
      "overlap_tokens": 32
    },
    "tokenizer": {
      "model": "BAAI/bge-small-zh-v1.5",
      "max_seq_length": 512,
      "tokenizer_sha256": "838bba27a9e5bbcbb7bed0b25535c69d88b63768857dda2ab13d015c4a98591f",
      "do_lower_case": true,
      "template": "document_title + \"\\n\" + passage.text"
    },
    "effective_max_tokens": 512
  },
  "contract_id": "1041a9bee3f5fcffa7dd72f0ae62a59a2e39b9aca6c72450087f4e5e87733595",
  "model_max_seq_length": 512,
  "eligible_parent_chunks": 4532,
  "embedding_passages": 4950,
  "parents_with_1_passage": 4156,
  "parents_split": 376,
  "average_passages_per_parent": 1.0922330097087378,
  "passages_per_parent": {
    "count": 4532,
    "min": 1,
    "max": 4,
    "mean": 1.0922330097087378,
    "p10": 1.0,
    "p25": 1.0,
    "median": 1.0,
    "p75": 1.0,
    "p90": 1.0,
    "p95": 2.0
  },
  "passage_token_length": {
    "count": 4950,
    "min": 8,
    "max": 512,
    "mean": 315.5387878787879,
    "p10": 149.0,
    "p25": 232.0,
    "median": 334.0,
    "p75": 399.0,
    "p90": 463.0,
    "p95": 483.0
  },
  "passages_exceeding_limit": 0,
  "all_passage_inputs_within_model_limit": true,
  "guard_policy": "Already-fitting parent inputs remain unchanged; split windows reserve guard_tokens in the complete title+body+specials template.",
  "by_document": {
    "epics-application-developers-guide-r3-16-2": {
      "parents": 847,
      "passages": 858
    },
    "epics-documentation-latest-2026-08-18": {
      "parents": 1071,
      "passages": 1086
    },
    "european-xfel-full-technical-design-report-2007": {
      "parents": 1730,
      "passages": 1780
    },
    "european-xfel-standard-e-beam-diagnostics-linac2010": {
      "parents": 13,
      "passages": 13
    },
    "european-xfel-undulator-commissioning-spectrometer-cdr-2011": {
      "parents": 41,
      "passages": 41
    },
    "european-xfel-x-ray-optics-beam-transport-tdr-2012": {
      "parents": 235,
      "passages": 246
    },
    "shine-accelerator-control-system-design-presentation": {
      "parents": 33,
      "passages": 33
    },
    "shine-accelerator-fast-interlock-2024": {
      "parents": 18,
      "passages": 27
    },
    "shine-accelerator-preliminary-design-report-2017": {
      "parents": 477,
      "passages": 799
    },
    "shine-control-system-status-icalepcs2019": {
      "parents": 15,
      "passages": 15
    },
    "shine-cryogenic-control-system-2021": {
      "parents": 22,
      "passages": 22
    },
    "shine-epics-ioc-pv-information-management-pcapac2022": {
      "parents": 13,
      "passages": 13
    },
    "shine-white-rabbit-beam-synchronous-timing-ipac2022": {
      "parents": 17,
      "passages": 17
    }
  }
}
```

## 历史截断与证据位置

```json
{
  "position_method": "Real tokenizer max-length offsets -> source prefix -> deterministic normalized evidence matching. Ambiguous normalization at boundary is unclassified, never guessed. This describes evidence position, not embedding understanding or retrieval causality.",
  "answerable_queries": 21,
  "stage25_failure_count": 13,
  "failures_with_truncating_relevant_parent": 3,
  "failures_with_required_group_not_fully_visible": 1,
  "position_counts": {
    "fully_before_limit": 36,
    "crosses_limit": 1
  }
}
```

## 控制变量核验

```json
{
  "query_hash_identical": true,
  "sources_identical": true,
  "canonical_parents_identical_to_stage25_index": true,
  "eligibility_identical": true,
  "bm25_metrics_rankings_scores_identical": true,
  "live_stage25_dense_metrics_rankings_match_history": true,
  "a_vectors": "Preserved Stage 2.5 direct-chunk vectors with actual historical truncation; no new A document embedding. Queries re-run locally.",
  "oversample_factor": 4,
  "distance": "cosine",
  "ground_truth_all_alternatives_validated": true
}
```

## 索引与耗时

```json
{
  "collection": "knowledge_stage26",
  "qdrant_path": "tmp/stage-two-six-qdrant",
  "preparation_seconds": 15.316111594001995,
  "embedding_seconds": 524.8550086799769,
  "qdrant_indexing_seconds": 10.842458590996102,
  "embedded_passage_count": 4950,
  "point_count": 4950,
  "unique_parent_count": 4532,
  "payload_parent_integrity_verified": true
}
```

## 可复现信息

```json
{
  "embedding_model": "BAAI/bge-small-zh-v1.5",
  "model_max_seq_length": 512,
  "passage_algorithm": "dense-passages-v1",
  "passage_config": {
    "max_tokens": null,
    "guard_tokens": 16,
    "overlap_tokens": 32
  },
  "tokenizer_contract": {
    "algorithm": "dense-passages-v1",
    "config": {
      "max_tokens": null,
      "guard_tokens": 16,
      "overlap_tokens": 32
    },
    "tokenizer": {
      "model": "BAAI/bge-small-zh-v1.5",
      "max_seq_length": 512,
      "tokenizer_sha256": "838bba27a9e5bbcbb7bed0b25535c69d88b63768857dda2ab13d015c4a98591f",
      "do_lower_case": true,
      "template": "document_title + \"\\n\" + passage.text"
    },
    "effective_max_tokens": 512
  },
  "query_template": "为这个句子生成表示以用于检索相关文章：{query}",
  "query_set_sha256": "19eea7643cc749acb51c1c2953823c3547c5d8da2eb05d947495395a870f56e5",
  "source_sha256": {
    "data/l0_raw/EPICS/EPICS_Application_Developers_Guide_R3.16.2.pdf": "6d4c00b3a4bf97424e353b17e5fca57959ce964adf0452e20c0a80f7e2296b4e",
    "data/l0_raw/EPICS/EPICS_Documentation_latest.pdf": "caa56720766f788b073b15542d19ac4c5717d2b0d2ba8c22189f2a30ef781d54",
    "data/l0_raw/Hard_XFEL_European_XFEL/European_XFEL_Full_Technical_Design_Report.pdf": "0464c700394d496aeb9ebbad1c6fd5ab8074a3e0929a562db35f78504e77f99d",
    "data/l0_raw/Hard_XFEL_European_XFEL/European_XFEL_Undulator_Commissioning_Spectrometer_CDR.pdf": "5b05e0f710954f171628b23ef7417ca86fd8ae638a6f380439c888b06af69d75",
    "data/l0_raw/Hard_XFEL_European_XFEL/European_XFEL_X-Ray_Optics_and_Beam_Transport_TDR.pdf": "2d1d1cc2ff3b080465bbc38d0f4a72f7ee69bebeb915070c3fa7e0edd65e425f",
    "data/l0_raw/Hard_XFEL_European_XFEL/Standard_E-Beam_Diagnostics_for_European_XFEL.pdf": "8b131d0825d6018ec41c041782f3300fc759686ea901d9f84b4fada009bc24aa",
    "data/l0_raw/Hard_XFEL_SHINE/EPICS_IOC_and_PVs_Information_Management_System_for_SHINE_PCaPAC2022.pdf": "e9e4e2b836cc2e483b13c50082652f7e9c9937995105653116eacd518ba6996b",
    "data/l0_raw/Hard_XFEL_SHINE/SHINE_Accelerator_Fast_Interlock_System_Design_and_Development_CN.pdf": "3e500e7ced87d4180d93edd416db0d2d198843dcb6dbcf54ff683479798c3a97",
    "data/l0_raw/Hard_XFEL_SHINE/Status_of_the_SHINE_Control_System_ICALEPCS2019.pdf": "b4a3b83c407fc9287be053bd74c01927ce849f79575fe0da46d0ceebe9e572b8",
    "data/l0_raw/Hard_XFEL_SHINE/The_Cryogenic_Control_System_of_SHINE_2021.pdf": "9f10c9a9965ef592ad87c08d9c87c798b121e06403f6ff21abcbb960d610d4f8",
    "data/l0_raw/Hard_XFEL_SHINE/White_Rabbit_Based_Beam_Synchronous_Timing_Systems_for_SHINE_IPAC2022.pdf": "0bb488a758302a761923de2f096b4bc8ddb98418b6ea0dc4b0a7534729e5be32",
    "data/l0_raw/SHINE加速器控制系统设计与开发.pdf": "c9a8c81d7eed3dbc3a502e651b395e9cb899f38eb38809f874d858fead86876e",
    "data/l0_raw/加速器分册(20171226).pdf": "412cff8c89afc000f1790707dacde9deb3dc2bf3db0bcc09f5894eb807ed9dab"
  },
  "chunking_algorithm": "pdf-chunks-v3",
  "schema_version": 2,
  "judgment_revision": "evidence-contract-v1",
  "historical_report_sha256": "aeb4ed0ee5fb4058a13dca47fcb111195335c7f6cc75daf4bf4a35e6dd18fa2f",
  "git": {
    "head": "971bf45464b4fae5330109d1446470cd01eaadd7",
    "dirty": true,
    "identity_note": "HEAD is a base commit, not the identity of this dirty run; see code hashes."
  },
  "code_sha256": {
    "src/accelerator_rag/__init__.py": "a3f7f6d5937bec359685bd111481c5ae644f3079f53325bd50490b812a9d2177",
    "src/accelerator_rag/api/__init__.py": "5e938cc30de09d9fedab211dde27dc893b5297ddb036b8e8e72062a80b8b8e05",
    "src/accelerator_rag/config.py": "e0c3c51da9cfc44c015180ae3e0204d4413f37600448f05eeecdc05d14ea2662",
    "src/accelerator_rag/corpus/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "src/accelerator_rag/corpus/audit.py": "0c84a823fb754dba39fbaa23c16549358ee64562e51788330d3863ddd5886e69",
    "src/accelerator_rag/corpus/chunking.py": "a5ef35b3b3d40134e30c7cc1a18f14c2cd9cd283fdd9dd2350cd63edb436ae51",
    "src/accelerator_rag/corpus/cleaning.py": "881f6b83389c445dd26898c7bbd49401715da62354bd3bb55282039104d0c46c",
    "src/accelerator_rag/corpus/eligibility.py": "6b3c88b3b3fab4d980e2005fdc321ca633b03e150c9609bb5ec682e2bbce2b09",
    "src/accelerator_rag/corpus/pdf_parser.py": "951e51aedf03db757b505f26e0a0e4226f30b7c524f2f901462b7b5f14c7c1d9",
    "src/accelerator_rag/corpus/registry.py": "7a66024f91ed56dd11f5ae8b75c94094c6e2a4cc343b051aaaa066cf1e8fcbf7",
    "src/accelerator_rag/corpus/taxonomy.py": "ba3f4eb6440cdc9c24d872d76cda7dcaf99f9e4063a4c4d2939e38b47995e54e",
    "src/accelerator_rag/domain/__init__.py": "d68e14e5d3aa45fcbf81dbadc929e6fa195766e79a206d31d333545234aebb61",
    "src/accelerator_rag/domain/knowledge.py": "b76a52b497eea85f9d09fb4182cd348bba232442717233971bd1e7a9dccb8129",
    "src/accelerator_rag/embedding.py": "95c6c82bbbfb7b1ab62d1547424e317b2b2c09c00330841cc8af6051822363c9",
    "src/accelerator_rag/evaluation/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "src/accelerator_rag/evaluation/comparison.py": "2869c7144cc1e5f5b2e382fedbb2c0ef6a6af45dba4dfa9c51d99e0b4c484a55",
    "src/accelerator_rag/evaluation/passage_comparison.py": "41052dbafa13ebc6f64bce6ff703ada677c62e42d07e39f081a5bbd94e97fecf",
    "src/accelerator_rag/evaluation/reporting.py": "ac09d51faae4ee992c4b90fefb5bc6f6fde3f166f2b8ccba77fad192f72508cf",
    "src/accelerator_rag/evaluation/retrieval.py": "25da05e1b8ef49a73ff752f038a1e61eedf102aa53c9c118906a63d935050ecc",
    "src/accelerator_rag/ingestion.py": "1f2879786bb789f645a562652d103e48efe2354719aa605cecfb3b774bcf7910",
    "src/accelerator_rag/logging_config.py": "a5751cbe34f2e5ac26182c32a5f941fc38ea2f52fd23f7ad96c24035a9b25a41",
    "src/accelerator_rag/main.py": "244a4f60448c5e9f8e5625aa630a759b7d09f85dbcbb9abdb2eef74888835d4c",
    "src/accelerator_rag/memory/__init__.py": "e168b1669829f37b7ce4e2ee3fa78e152280f61885030ef0b0707d6d05fdc042",
    "src/accelerator_rag/observability/__init__.py": "882c2b0237c3a7fcee88ee7f33b00e434173dbe8ea9219520258170d24be62f1",
    "src/accelerator_rag/retrieval/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "src/accelerator_rag/retrieval/bm25.py": "db754ba815c5193f8d74d1ccbd370bdc75c3bc32b700727a4022ef47237e1fa6",
    "src/accelerator_rag/retrieval/cli.py": "ffe2e8f5e01100775e29cf33cadaa1f7c15571a1b6e9ce8ab1be619c8454654f",
    "src/accelerator_rag/retrieval/corpus_baseline.py": "588a3fed6a560b5d616ed3ae6a46148a90a1c215f01a817f4bdd46fccd6a6042",
    "src/accelerator_rag/retrieval/dense.py": "81baa00328a61fbc8648c6813d384461e4830b215663875c382bbdf36c6c8b5c",
    "src/accelerator_rag/retrieval/passage_baseline.py": "fc0854917cbabc768bcfef5fa2373b74f292bb250af437af56a7046c3f97adbf",
    "src/accelerator_rag/retrieval/passages.py": "de05b92dff0cb62911b52766687701fe1c10ce79998c37abcd4ea011ed53409b",
    "src/accelerator_rag/storage/__init__.py": "99fcd80d8a2c288a8aa98b894c56149fc5245c163a47c44a8c7c7816a5381966",
    "src/accelerator_rag/storage/qdrant_passages.py": "e996b17f66af3c86800ccf5bfc84a1e6ec030d9bdfaf701cfaf83a7ba542b5df",
    "src/accelerator_rag/storage/qdrant_store.py": "4fc83daf81f6c42ce0d6d625d38e9a7a4ca564d40b2b2c9a0157ad5a2ba03246",
    "src/accelerator_rag/tools/__init__.py": "a81f0652e943a88fcf15cbe4c03a730518302244887cc78b2d27eff9f629cdf4"
  },
  "local_files_only": true
}
```

## 负例分数对照

| 检索器 | 类型 | 问题数 | 分布 |
|---|---|---:|---|
| dense_a | answerable | 21 | {'count': 21, 'min': 0.5029935869262879, 'max': 0.7782650906334003, 'mean': 0.6659139335332538, 'p10': 0.5953099007130604, 'p25': 0.6365569239916968, 'median': 0.6646541412392741, 'p75': 0.7076117500420326, 'p90': 0.7360936690974041, 'p95': 0.7688694079807534} |
| dense_a | obvious | 3 | {'count': 3, 'min': 0.41021031445670614, 'max': 0.5327770869100423, 'mean': 0.46942539494138086, 'p10': 0.4212260082568437, 'p25': 0.43774954895705, 'median': 0.4652887834573939, 'p75': 0.4990329351837181, 'p90': 0.5192794262195126, 'p95': 0.5260282565647775} |
| dense_a | hard_domain | 8 | {'count': 8, 'min': 0.5559336035525682, 'max': 0.6793489781197168, 'mean': 0.6066928466829425, 'p10': 0.5568227989679553, 'p25': 0.5798337858028224, 'median': 0.6073741301560778, 'p75': 0.6259211566093996, 'p90': 0.6493925842096742, 'p95': 0.6643707811646955} |
| dense_b | answerable | 21 | {'count': 21, 'min': 0.5109084859681636, 'max': 0.7782650980675581, 'mean': 0.6672307085897112, 'p10': 0.5953099080321731, 'p25': 0.6419499300259386, 'median': 0.6646541713602537, 'p75': 0.7076117817397227, 'p90': 0.7403641599843809, 'p95': 0.7688694527129611} |
| dense_b | obvious | 3 | {'count': 3, 'min': 0.41021033208544283, 'max': 0.5545627783959093, 'mean': 0.4766873026464835, 'p10': 0.4212260251599739, 'p25': 0.4377495647717705, 'median': 0.46528879745809826, 'p75': 0.5099257879270038, 'p90': 0.536707982208347, 'p95': 0.5456353803021282} |
| dense_b | hard_domain | 8 | {'count': 8, 'min': 0.5559336235850287, 'max': 0.6791222746209563, 'mean': 0.6077610276920961, 'p10': 0.5629632358352725, 'p25': 0.5820268073160915, 'median': 0.6073741480387829, 'p75': 0.6259211751398128, 'p90': 0.6493245868041355, 'p95': 0.6642234307125459} |

没有实现 score threshold。分数相似不等于问题可回答。零截断证明输入适配，不保证模型理解证据。公式损坏、目录及页眉残留仍属于已知限制。

## 人工 case 复核与结论

实际只有 1 条排名改善，0 条回退。以下补充 7 条改善或未变问题的诊断，不把未变问题伪称为变化。

### interlock-latency

A 未命中冻结目标，B 首次完整命中为 rank 2，来自快联锁论文物理页 2 的 passage ordinal 1，score 0.730097。该 parent 为 758 tokens，但目标证据在 A 中完整位于上限之前。改善与表示粒度变化相关，不能解释为恢复原本不可见的证据。A Top-3 的设计幻灯片物理页 21 含近似的快联锁响应指标，属于未标注来源；种子 miss 不等于所有返回结果都无价值，GT 本轮保持冻结。

### shine-compressors

A/B 均未完整命中。目标 parent 为 540 tokens，所需 BC1/BC2 理由摘录跨越 A 的可见边界。B 已完整覆盖父文本，但仍优先检出束流分配/偏转主题（物理页 193、197），没有检出目标页 61。消除截断没有自动解决该语义选择问题。

### shine-main-linac

A/B 均未完整命中。目标 parent 为 829 tokens，但连续波模式和 8 GeV 摘录已完整位于 A 上限之前。B 仍优先返回控制设计幻灯片物理页 8、6，未检出冻结目标初设报告页 5，不能把失败归因于目标证据被截掉。

### epics-cli

A/B 均未完整命中。包含 caget、caput、camonitor 三组证据的目标 parent 仅 297 tokens。Top-1 虽然同在物理页 9，却是介绍性内容的另一 Chunk；同页不构成证据命中。目标输入本来就适配，passage 化没有修复完整命令证据的排序。

### shine-ioc-startup

A/B 均未完整命中。两组目标 parent 为 175、364 tokens，均完整可见。返回的中文幻灯片页 28 涉及 IOC 信息管理，包含部分字段，但没有覆盖冻结的启动信息证据组。跨语言目标论文页 2/3 仍未进入完整命中集合。

### xfel-rf

A/B 均未完整命中。目标 parent 为 412、360 tokens，RF 频率和设计能量证据均完整可见。Top-3 仍为 XFEL TDR 页 35、311、376，没有检出冻结目标页 65/72。该失败没有 relevant-parent 截断关联。

### cryo-interlock

A/B 均未完整命中。主 PLC/CPLD 三组证据位于 363、233 tokens 的父 Chunk，均完整可见。B 仍优先返回初设报告的一般低温控制内容，未覆盖目标低温论文页 6 的完整保护链。

## 标题与正文 token 预算

拆分窗口的完整输入预留 16 tokens。标题/模板/special tokens 实测为 7～27 tokens，初始正文预算为 469～489 tokens。最终窗口仍逐条重新分词并断言。已适配的父输入保持原样。

| 文档 | 标题模板与特殊 token | 初始 split body budget |
|---|---:|---:|
| epics-application-developers-guide-r3-16-2 | 11 | 485 |
| epics-documentation-latest-2026-08-18 | 7 | 489 |
| european-xfel-full-technical-design-report-2007 | 21 | 475 |
| european-xfel-undulator-commissioning-spectrometer-cdr-2011 | 22 | 474 |
| european-xfel-x-ray-optics-beam-transport-tdr-2012 | 14 | 482 |
| european-xfel-standard-e-beam-diagnostics-linac2010 | 20 | 476 |
| shine-epics-ioc-pv-information-management-pcapac2022 | 15 | 481 |
| shine-accelerator-fast-interlock-2024 | 17 | 479 |
| shine-control-system-status-icalepcs2019 | 10 | 486 |
| shine-cryogenic-control-system-2021 | 12 | 484 |
| shine-white-rabbit-beam-synchronous-timing-ipac2022 | 21 | 475 |
| shine-accelerator-control-system-design-presentation | 16 | 480 |
| shine-accelerator-preliminary-design-report-2017 | 27 | 469 |

## 截断与负例解释

Stage 2.5 has 13 failures. Three have a relevant parent exceeding 512 tokens; only shine-compressors has required evidence crossing the boundary. No accepted target is fully after the boundary. 36/37 target-parent matches are fully before it. Only interlock-latency improves, whose target was already visible. Association and the A/B result do not identify truncation as the dominant source of failure on this small frozen set.

Hard-domain mean increases by 0.001068, with one material increase (live-beam-energy +0.008772), one decrease (live-interlock -0.000227), and six numerically stable scores. Obvious finance negative increases by 0.021786. False similarity worsens locally, without broad separation improvement. No threshold or false-positive rate is introduced.

```json
{
  "obvious": {
    "paired_scores": [
      {
        "query_id": "no-answer-finance",
        "stage25_score": 0.5327770869100423,
        "stage26_score": 0.5545627783959093,
        "delta": 0.021785691485866954
      },
      {
        "query_id": "no-answer-recipe",
        "stage25_score": 0.41021031445670614,
        "stage26_score": 0.41021033208544283,
        "delta": 1.7628736692643088e-08
      },
      {
        "query_id": "no-answer-token",
        "stage25_score": 0.4652887834573939,
        "stage26_score": 0.46528879745809826,
        "delta": 1.4000704373628992e-08
      }
    ],
    "increased_beyond_numeric_tolerance": 1,
    "decreased_beyond_numeric_tolerance": 0,
    "stable_within_numeric_tolerance": 2,
    "mean_delta": 0.007261907705102673,
    "numeric_comparison_tolerance": 1e-06
  },
  "hard_domain": {
    "paired_scores": [
      {
        "query_id": "no-answer-hard-live-pv",
        "stage25_score": 0.6022025400288948,
        "stage26_score": 0.6022025646902812,
        "delta": 2.4661386377466954e-08
      },
      {
        "query_id": "no-answer-hard-live-ioc-count",
        "stage25_score": 0.6125457202832607,
        "stage26_score": 0.6125457313872845,
        "delta": 1.1104023811547847e-08
      },
      {
        "query_id": "no-answer-hard-live-interlock",
        "stage25_score": 0.6793489781197168,
        "stage26_score": 0.6791222746209563,
        "delta": -0.00022670349876052764
      },
      {
        "query_id": "no-answer-hard-live-cryo",
        "stage25_score": 0.6223768322535999,
        "stage26_score": 0.6223768504636321,
        "delta": 1.8210032259879938e-08
      },
      {
        "query_id": "no-answer-hard-deployed-firmware",
        "stage25_score": 0.5873770868312942,
        "stage26_score": 0.5873771008215678,
        "delta": 1.3990273606268033e-08
      },
      {
        "query_id": "no-answer-hard-current-ioc-ip",
        "stage25_score": 0.6365541296767988,
        "stage26_score": 0.6365541491683552,
        "delta": 1.9491556368933516e-08
      },
      {
        "query_id": "no-answer-hard-live-bpm-calibration",
        "stage25_score": 0.5559336035525682,
        "stage26_score": 0.5559336235850287,
        "delta": 2.003246057924457e-08
      },
      {
        "query_id": "no-answer-hard-live-beam-energy",
        "stage25_score": 0.5572038827174068,
        "stage26_score": 0.5659759267996627,
        "delta": 0.008772044082255848
      }
    ],
    "increased_beyond_numeric_tolerance": 1,
    "decreased_beyond_numeric_tolerance": 1,
    "stable_within_numeric_tolerance": 6,
    "mean_delta": 0.0010681810091535404,
    "numeric_comparison_tolerance": 1e-06
  }
}
```

## 下一步建议

A. Proceed to a controlled embedding-model comparison after review, retaining this BGE token-safe result as control. Mechanical passage compatibility is established, while English and cross-language failures remain largely unchanged. Defer Hybrid; do not change queries to chase metrics. Existing corpus quality limitations remain, but this experiment does not establish a passage algorithm defect requiring another rewrite.

本轮没有进入模型替换、Hybrid、reranker、LLM 或 Agent。

## 执行验证

```json
{
  "passage_points": 4950,
  "unique_canonical_parents": 4532,
  "duplicate_passages": 0,
  "all_parent_payloads_and_source_ranges_verified": true,
  "all_passage_ids_and_contract_ids_verified": true,
  "all_vector_dimensions_and_norms_verified": true,
  "passage_token_limit_verified": true,
  "protected_files_unchanged": 41,
  "protected_history_qdrant_files_byte_identical": true,
  "all_measurement_source_hashes_match": true,
  "frozen_query_hash_matches_stage25": true,
  "commands": {
    "pytest -q": {
      "exit_code": 0,
      "stdout": "........................................................................ [ 42%]\n........................................................................ [ 85%]\n........................                                                 [100%]\n168 passed in 3.80s\n",
      "stderr": ""
    },
    "ruff check .": {
      "exit_code": 0,
      "stdout": "All checks passed!\n",
      "stderr": ""
    },
    "git diff --check": {
      "exit_code": 0,
      "stdout": "",
      "stderr": ""
    },
    "python scripts/corpus_inventory.py": {
      "exit_code": 0,
      "stdout": "Registered documents\n01. data/l0_raw/EPICS/EPICS_Application_Developers_Guide_R3.16.2.pdf | control_system/epics | en | R3.16.2 (2018-10-22) | active\n02. data/l0_raw/EPICS/EPICS_Documentation_latest.pdf | control_system/epics | en | latest (2026-08-18) | active\n03. data/l0_raw/Hard_XFEL_European_XFEL/European_XFEL_Full_Technical_Design_Report.pdf | accelerator_physics/accelerator_design | en | DESY 2006-097 (2007-07) | reference\n04. data/l0_raw/Hard_XFEL_European_XFEL/European_XFEL_Undulator_Commissioning_Spectrometer_CDR.pdf | beam_diagnostics/photon_diagnostics | en | Rev B, Ver 2 (2011-06-08) | reference\n05. data/l0_raw/Hard_XFEL_European_XFEL/European_XFEL_X-Ray_Optics_and_Beam_Transport_TDR.pdf | accelerator_physics/beam_transport | en | XFEL.EU TR-2012-006 (2012-12) | reference\n06. data/l0_raw/Hard_XFEL_European_XFEL/Standard_E-Beam_Diagnostics_for_European_XFEL.pdf | beam_diagnostics/electron_beam_diagnostics | en | LINAC2010 TUP095 | reference\n07. data/l0_raw/Hard_XFEL_SHINE/EPICS_IOC_and_PVs_Information_Management_System_for_SHINE_PCaPAC2022.pdf | control_system/ioc | en | PCaPAC2022 FRO21 | reference\n08. data/l0_raw/Hard_XFEL_SHINE/SHINE_Accelerator_Fast_Interlock_System_Design_and_Development_CN.pdf | control_system/interlock | zh | 核技术 47(12):120203 (2024-12) | reference\n09. data/l0_raw/Hard_XFEL_SHINE/Status_of_the_SHINE_Control_System_ICALEPCS2019.pdf | control_system/control_architecture | en | ICALEPCS2019 WEPHA167 | reference\n10. data/l0_raw/Hard_XFEL_SHINE/The_Cryogenic_Control_System_of_SHINE_2021.pdf | control_system/cryogenics | en | EPJ Techniques and Instrumentation (2021) | reference\n11. data/l0_raw/Hard_XFEL_SHINE/White_Rabbit_Based_Beam_Synchronous_Timing_Systems_for_SHINE_IPAC2022.pdf | control_system/timing | en | IPAC2022 THIYGD1 | reference\n12. data/l0_raw/SHINE加速器控制系统设计与开发.pdf | control_system/control_architecture | zh | unknown | reference\n13. data/l0_raw/加速器分册(20171226).pdf | accelerator_physics/accelerator_design | zh | 初步设计报告 (2017-12-26) | reference\n\nCorpus inventory\nregistered_documents: 13\nregistered_pdfs: 13\nraw_files: 18\nunsupported_unmanaged_source_files: 5\nregistered_size: 69.7 MiB\ncategories: accelerator_physics=3, beam_diagnostics=2, control_system=8\ntopics: accelerator_design=2, beam_transport=1, control_architecture=2, cryogenics=1, electron_beam_diagnostics=1, epics=2, interlock=1, ioc=1, photon_diagnostics=1, timing=1\ndocument_types: pdf=13\nlanguages: en=10, zh=3\nstatuses: active=2, reference=11\nunsupported_unmanaged_sources (outside PDF validation):\n  - data/l0_raw/control_system/EPICS_7_Overview.pptx\n  - data/l0_raw/control_system/EPICS_Centos8_Packages.docx\n  - data/l0_raw/control_system/EPICS_IOC_Setup.pptx\n  - data/l0_raw/control_system/LNL_Accelerator_Complex_Code_Legend_Rule.docx\n  - data/l0_raw/control_system/areaDetector_training.pptx\nvalidation: OK\n",
      "stderr": ""
    }
  },
  "full_baseline_exit_code": 0
}
```
