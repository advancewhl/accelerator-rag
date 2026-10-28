# Stage 3：Standalone RAG 问答闭环

STANDALONE RAG: PARTIAL

真实 GPU 闭环和 API 已运行，检索保持 20/21，引用均可定位，11 条负例均拒答。人工检查发现多子问题漏答，部分回答仍标为 `answered`，因此本阶段不判定 PASS。当前实现采用证据片段选择、必要时忠实翻译和代码解析引用；尚不能保证完整覆盖每个子问题。

## 实际结果

| 项目 | 结果 |
| --- | --- |
| 真实 API 请求 | 32/32 返回 HTTP 200 |
| GPU Retrieval Hit@5 | 20/21，唯一 miss 仍为 shine-ioc-startup |
| 21 条可回答问题的返回状态 | answered 19；partial 2；insufficient 0；error 0 |
| 11 条负例 | insufficient 11；partial 0；错误 answered 0；error 0 |
| 引用 | 有效 33；非法 0；不可解析 0 |
| 引用到真实 chunk | 33/33 |
| 引用到真实 PDF 物理页 | 33/33，核对来源文件哈希和页码范围 |
| 平均 dense 检索 | 1.461 s |
| 平均 rerank | 0.149 s |
| 平均生成 | 0.366 s |
| 平均总耗时 | 1.976 s |

耗时来自真实运行返回值。dense 检索包含向量查询与候选合并，rerank 单独计时；总耗时不含首次模型加载和 SSH 转发。模型状态计数不能解释为答案正确率。

## 人工检查与未通过项

- `shine-main-linac`：回答给出了最终 8 GeV，但漏答工作模式；canonical parent 物理页 60 已包含超导连续波证据。answered 状态偏乐观，不能将检索命中当作完整回答。
- `epics-cli`：返回 camonitor、caput 相关原文，但漏答读取工具 caget，answered 状态偏乐观。
- `shine-compressors`：返回 BC1 能量选择结论与 BC2 的考虑因素，但没有完整解释两级位置选择。answered 状态偏乐观。
- `xfel-normal-energy`：按文档分别给出 2007 年技术设计报告与 2010 年诊断论文的参数，保持 partial，未把不同参数口径合并。
- `shine-ioc-startup`：返回摘要中可确认的启动上报信息，保持 partial；没有把面板展示字段误当作启动时上报的完整清单。IOC 中文翻译将原文现在时转为将来时，时态不够准确；证据字段与 partial 状态正确。
- `cryo-interlock`：中文译文保留 PLC、CPLD 及响应时间事实，但保留了 PDF 提取造成的断句，阅读体验有待改进。

## 运行入口

独立代码位于 `src/accelerator_rag/rag/`。Python 入口为 `RagRuntime(config).answer(query)`；HTTP 入口为 `POST /v1/rag/answer`，仅接收 `{"query":"自然语言问题"}`。API 与 Agent API 分开运行。

组内服务器工作区为 `/opt/accelerator-rag-stage3`。正式容器为 `accelerator-rag-stage3`，使用物理 GPU 2，容器内为 `cuda:0`。E5、Qwen3 query embedding 为 FP32；reranker 为 BF16。生成服务为同机 `http://127.0.0.1:8001/v1` 的 `qwen3-vl`。

服务绑定服务器回环地址 `127.0.0.1:8003`。本机会话已建立 `127.0.0.1:18003` 转发，可打开 `http://127.0.0.1:18003/docs`，或调用：

```bash
curl --noproxy '*' http://127.0.0.1:18003/v1/rag/answer \
  -H 'Content-Type: application/json' \
  -d '{"query":"SHINE 快联锁对单节点和节点间的响应时间分别有什么要求？"}'
```

服务器重建本任务容器的命令为 `bash /opt/accelerator-rag-stage3/deploy/rag-stage3-start.sh`。同一索引只允许一个 runtime 持有；先停止本任务 API，再运行独立 CLI，避免 Qdrant 本地锁冲突。

验收完成后已恢复普通生产 API，容器健康，OpenAPI 返回 HTTP 200。最终检查中，Qwen3-VL 使用 GPU 0/1，另一个并行部署的 qwen38-flash-next 使用 GPU 4～7；均保持运行。

## 证据与数据边界

复用签名索引，没有重新计算文档向量，没有更改 corpus、chunk identity、检索语义或冻结 benchmark。正式路径仍为 E5 Top-10 与 Qwen3 Top-10 合并、Qwen3 reranker、Top-5 canonical parent。

32 条生成首轮输入已逐条重建核对，共 160 个完整 canonical `KnowledgeChunk.text`。额外片段 ID 仅用于请求内原文选择，不改变索引或 canonical chunk。模型不输出真实路径、chunk ID 或物理页；这些字段由代码映射。

模型仅接收真实问题、证据和输出契约。原始 PDF、ground truth、预期答案和评测标签留在本机。引用检查与冻结标签对照在生成返回后进行。无效引用和无法验证的模型输出返回错误，不直接交给用户。时间条件使用通用解析，不包含固定问题 ID 或基准日期特判。

原始审计记录位于本机 `tmp/rag-stage-three-http-results.json`，HTTP 回执位于 `tmp/rag-stage-three-http-client.json`。本报告 JSON 保存全部实际回答、检索诊断、模型调用记录与本地判断；先前试运行不计入本次统计。

必要检查已完成：冻结文件哈希、33 条引用来源与页码、32 条真实 HTTP 请求、引用契约检查、Ruff、`git diff --check`。没有运行完整 pytest，没有提交或推送 Git，没有修改 Agent、Waveform 或原始 PDF。

下一步仅需修复多子问题覆盖与状态判断，再按相同闭环复验。当前不接入 Agent 或 Open WebUI。

## 真实回答

### epics-pp

When does an EPICS PP input link process its target record?

状态：answered。

《EPICS Documentation》（latest (2026-08-18)）：
> If they are set to PP (process passive), then the record is processed before the field is returned. [1]

《EPICS Application Developer's Guide》（R3.16.2 (2018-10-22)）：
> For input and output links, two additional attributes can be speciﬁed by the application developer: process passive, and maximize severity. 5.3.1 Process Passive The Process Passive attribute takes the value NPP (Non-Process Passive) or PP (Process Passive). It determines if the linked record should be processed before getting a value from an input link or after writing a value to an output link. The linked record will be processed only if link’s Process Passive attribute is PP and the target record’s SCAN ﬁeld is Passive. [2]

[1] 《EPICS Documentation》，版本 latest (2026-08-18)，物理页 128～128；`epics-documentation-latest-2026-08-18:ec0ef9a370a051e5a2b80f106a8b2358779cb81d77317c7a046017b774e77ff6`。

[2] 《EPICS Application Developer's Guide》，版本 R3.16.2 (2018-10-22)，物理页 88～88；`epics-application-developers-guide-r3-16-2:95f9f00fa8a6ec6e4e94ed21244521e43ef5d2486f3f56bc3b28a49e4eeaf20e`。

### epics-reconnect

What happens to Channel Access client connections when an IOC server crashes and restarts?

状态：answered。

《EPICS Application Developer's Guide》（R3.16.2 (2018-10-22)）：
> When a server crashes, the client automatically re-establishes communication when the server restarts. [1]

《EPICS Documentation》（latest (2026-08-18)）：
> If a server crashes, the client automatically re-establishes communication when the server restarts. pvAccess [2]

[1] 《EPICS Application Developer's Guide》，版本 R3.16.2 (2018-10-22)，物理页 31～31；`epics-application-developers-guide-r3-16-2:2360d24c575c8539d66b24a381d26d9705e989fcdf4d8459dd361ea51b8a8203`。

[2] 《EPICS Documentation》，版本 latest (2026-08-18)，物理页 63～63；`epics-documentation-latest-2026-08-18:5ed27b152e619d65d23d7dde439604437d01c5a32afc94d6955004054543c138`。

### epics-cli

Which EPICS command-line tools read, write and continuously monitor the temperature:water PV?

状态：answered。

> Now open yet another terminal (nr. 3) and try camonitor as camonitor temperature:water First, have a look at what happens when you change the temperature:water value from terminal nr. 2 using caput. [1]

> Now open yet another terminal (nr. 3) and try camonitor as camonitor temperature:water First, have a look at what happens when you change the temperature:water value from terminal nr. 2 using caput. Then, try to change the value by some tiny amounts, like 15.500001, 15.500002, 15.500003... [1]

> You will see that camonitor reacts but the readings do not change. [1]

> If you wanted to see more digits, you could run camonitor -g8 temperature:water [1]

[1] 《EPICS Documentation》，版本 latest (2026-08-18)，物理页 9～9；`epics-documentation-latest-2026-08-18:a7cea79623100df414ec81d17f2bc3815c6ee8056a5d45f5f9853372edfe1cf6`。

### xfel-rf

What RF frequency and nominal design energy are used by the European XFEL main linac?

状态：answered。

> 4 XFEL accelerator 4.1 Overview 4.1.1 Introduction The heart of the accelerator complex is the L-band (1.3 GHz) electron linear accelerator (linac) with a nominal design energy of 20 GeV, operating at an accelerating gradient of 23.6 MV/m. [1]

> 4 XFEL accelerator 4.1 Overview 4.1.1 Introduction The heart of the accelerator complex is the L-band (1.3 GHz) electron linear accelerator (linac) with a nominal design energy of 20 GeV, operating at an accelerating gradient of 23.6 MV/m. It utilises the advanced superconducting radio fequency (RF) technology which has been successfully developed by the international Tera-Electronvolt Superconducting Linear Accelerator (TESLA) Collaboration, leading to the superconducting Linear Collider technical proposal in 2001 , and which is routinely in operation at the TESLA Test Facility (TTF) Linac and FLASH at Deutsches Elektronen Synchrotron Laboratory (DESY). [1]

[1] 《The European X-Ray Free-Electron Laser Technical Design Report》，版本 DESY 2006-097 (2007-07)，物理页 65～65；`european-xfel-full-technical-design-report-2007:a28479a4c17014782d0ce4480528110f45f1eb55e9ec9367c7e80787abb2f78d`。

### xfel-normal-energy

欧洲 XFEL 常规运行时电子束能量是多少，与最高设计能量有何区别？

状态：partial。

《The European X-Ray Free-Electron Laser Technical Design Report》（DESY 2006-097 (2007-07)）：
> 在直线加速器中，由1.6公里长的超导加速模块序列、用于束流偏转和聚焦的磁铁以及诊断设备组成，电子可被加速至最高20 GeV的能量（XFEL设施正常运行时的预期能量为17.5 GeV） [1]

《Standard E-Beam Diagnostics for the European-XFEL》（LINAC2010 TUP095）：
> 表1：E-XFEL设计束流参数 参数 值 单位 最大能量 17.5 GeV 归一化发射度 1-2 mm mrad 束电荷 0.1-1 nC 最小束间距 222 ns 最大宏脉冲长度 600 μs 宏脉冲内束团数 1 - 2700 束团模式 任意 射频重复频率 10 Hz 根据当前计划，调试工作应于2014年开始。 [2]

证据不足：当前片段来自多个文档，参数口径尚未核对，不能据此给出统一比较结论。

[1] 《The European X-Ray Free-Electron Laser Technical Design Report》，版本 DESY 2006-097 (2007-07)，物理页 57～57；`european-xfel-full-technical-design-report-2007:66fe8f7d369d58380b218e11f28e1a1c7b82b7b4dc63112857884404967fed2a`。

[2] 《Standard E-Beam Diagnostics for the European-XFEL》，版本 LINAC2010 TUP095，物理页 1～1；`european-xfel-standard-e-beam-diagnostics-linac2010:57008e67519a847d601128f9574ea963b697b7cc0ce860e8c2c405da1928d101`。

### undulator-tuning

How does a K-monochromator select radiation for tuning undulator segments?

状态：answered。

《The European XFEL Undulator Commissioning Spectrometer》（Rev B, Ver 2 (2011-06-08)）：
> The commissioning spectrometer, also known as K-monochromator, is mainly used with spontaneous radiation and selects a narrow bandwidth of the x-ray photon beam in order to tune the undulator segments. [1]

《The European XFEL Undulator Commissioning Spectrometer》（Rev B, Ver 2 (2011-06-08)）：
> The commissioning spectrometer, also known as K-monochromator, is mainly used with spontaneous radiation and selects a narrow bandwidth of the x-ray photon beam in order to tune the undulator segments. This process is called photon beam-based alignment and will minimize the difference in the undulator parameters K between undulator segments and optimize the phase between segments. [1]

《The European X-Ray Free-Electron Laser Technical Design Report》（DESY 2006-097 (2007-07)）：
> The concept of the photon-beam-based alignment procedure is based on variable gap undulator segments which allow the sampling of the spontaneous radiation of each segment individually by opening the gap of all other devices. [2]

《The European X-Ray Free-Electron Laser Technical Design Report》（DESY 2006-097 (2007-07)）：
> With simultaneous measurement of photon beam position and angle, this radiation will be analysed with a special diagnostic station in order to: • optimise angle and position of the electron beam trajectory; • adjust the K-parameter of all undulator segments; and • adjust the phase match between adjacent undulator segments. [2]

《X-Ray Optics and Beam Transport》（XFEL.EU TR-2012-006 (2012-12)）：
> The K monochromators are silicon channel-cuts that are used to calibrate the gap (K value) of individual undulator segments. [3]

[1] 《The European XFEL Undulator Commissioning Spectrometer》，版本 Rev B, Ver 2 (2011-06-08)，物理页 3～3；`european-xfel-undulator-commissioning-spectrometer-cdr-2011:3d9cff81b154e116e2b45c608f54d696a9594d653cd3ae8b86626dff067a206a`。

[2] 《The European X-Ray Free-Electron Laser Technical Design Report》，版本 DESY 2006-097 (2007-07)，物理页 221～221；`european-xfel-full-technical-design-report-2007:21ed4609646a52be1aac49855c620d0061346334e908e358df8868583a412055`。

[3] 《X-Ray Optics and Beam Transport》，版本 XFEL.EU TR-2012-006 (2012-12)，物理页 131～131；`european-xfel-x-ray-optics-beam-transport-tdr-2012:2f303ab57beb122e36500026400ff7f426a75dd54788d8e5842c0d4e6715fe67`。

### xfel-mirror-angle

Why was the grazing-incidence angle range of the SASE3 offset mirrors reduced?

状态：answered。

> The main reason is the smaller wavefront distortion coming from shape errors of the mirrors. [1]

[1] 《X-Ray Optics and Beam Transport》，版本 XFEL.EU TR-2012-006 (2012-12)，物理页 8～8；`european-xfel-x-ray-optics-beam-transport-tdr-2012:9a66a3cf2e8db6a52918f1de36e836b9584c3f4f4980413b63b29ac4f7a419da`。

### xfel-soft-mono

Why did the soft X-ray monochromator change to a vertical in-line geometry?

状态：answered。

> While the previous design was in the horizontal geometry and more optimized towards higher energy resolution, the new design is now focused more on a faster time response. [1]

> The vertical in-line geometry makes a monochromatic beam now equally available to all three branch beamlines at SASE3. [1]

> Another change is the implementation of an in-line design in the vertical plane. [2]

> In the vertical geometry, the monochromator is independent of the focusing properties and heat load effects of the offset mirrors, which would otherwise influence the resolution. [2]

[1] 《X-Ray Optics and Beam Transport》，版本 XFEL.EU TR-2012-006 (2012-12)，物理页 5～5；`european-xfel-x-ray-optics-beam-transport-tdr-2012:5af849fe4715abccdff144d8b08a568395bc54fbbbc8e64b936b8cc59e8db405`。

[2] 《X-Ray Optics and Beam Transport》，版本 XFEL.EU TR-2012-006 (2012-12)，物理页 43～43；`european-xfel-x-ray-optics-beam-transport-tdr-2012:f80b625a32c4d7d85831163aed5cc834738280ee825053bf80b74d3a892f4b4d`。

### xfel-bpm-types

Which BPM pickup types provide standard and high-precision position measurements at European XFEL?

状态：answered。

《Standard E-Beam Diagnostics for the European-XFEL》（LINAC2010 TUP095）：
> The standard BPMs will be of the button type. [1]

《Standard E-Beam Diagnostics for the European-XFEL》（LINAC2010 TUP095）：
> Precision monitors will be different cavity BPM types. [1]

《Standard E-Beam Diagnostics for the European-XFEL》（LINAC2010 TUP095）：
> High precision cavity BPMs with a 10 mm beam pipe will be integrated in the undulator intersections. [1]

《Standard E-Beam Diagnostics for the European-XFEL》（LINAC2010 TUP095）：
> Further high precision (cavity) monitors with a 40.5 mm beam pipe diameter will be used for critical sections in the machine, like the vicinity of the bunch compressor chicanes, the collimation and distribution section, as well as after the undulators. [1]

《Standard E-Beam Diagnostics for the European-XFEL》（LINAC2010 TUP095）：
> Further high precision (cavity) monitors with a 40.5 mm beam pipe diameter will be used for critical sections in the machine, like the vicinity of the bunch compressor chicanes, the collimation and distribution section, as well as after the undulators. They will also be used for the Intra Bunchtrain Feedback System currently developed by PSI. [1]

《The European X-Ray Free-Electron Laser Technical Design Report》（DESY 2006-097 (2007-07)）：
> 4.6.2.2 Beam position About 500 BPMs are required along the whole machine. [2]

《The European X-Ray Free-Electron Laser Technical Design Report》（DESY 2006-097 (2007-07)）：
> Due to different machine environments (space and beam pipe) different types of BPMs have to be used, and: • 117 cold BPMs are foreseen in the accelerator modules, either of pick-up type or re-entrant cavity type ; • striplines and button BPMs similar to the ones used in TTF2 will be used in the warm beamlines; • in the undulator, the resolution of these standard types is not sufficient. [2]

《The European X-Ray Free-Electron Laser Technical Design Report》（DESY 2006-097 (2007-07)）：
> Therefore, cavity BPMs with a resolution about 1 µm are planned for the intersections between the undulator segments; • special attention has to be put on the BPMs in the dispersive parts of the bunch compressors, since they have to deliver precise information about energy and energy fluctuations in the bunch compressors. [2]

[1] 《Standard E-Beam Diagnostics for the European-XFEL》，版本 LINAC2010 TUP095，物理页 1～1；`european-xfel-standard-e-beam-diagnostics-linac2010:ca586d4bb17b2f3b046c3ff7df9f0a5f4e983cd3f7185207b5c9e30543aef05e`。

[2] 《The European X-Ray Free-Electron Laser Technical Design Report》，版本 DESY 2006-097 (2007-07)，物理页 138～138；`european-xfel-full-technical-design-report-2007:9492afd5274a1b0f9a18af446abe843a69dd0afeaceac5afed35717607353403`。

### shine-ioc-management

How are IOC and PV information managed in SHINE?

状态：answered。

> In this case, we develop the application to obtain all the PVs from EPICS system and store them in the MySQL database. [1]

> In order to search through data easily, we also develop the web application to represent the information of the database. [1]

> MySQL database is utilized to store all the information, of which the running data from the control system is fetched via PSI CA interfaces and the running states of servers are obtained via SSH protocol. [2]

> The web service allows web pages to render for the information in MySQL database. [2]

> One application backed by MySQL is designed, running periodi-cally to interact with EPICS system where to take data from run-time databases via Channel Access and pvAccess. [3]

> We embed scripting codes into the IOC startup script to realize that as soon as the IOC starts up, the information of the server’s address, the IOC installation path, and all the records maintained by the IOC will be automatically pushed to the application and then stored in the database. [3]

> With this necessary information, we could access all the active IOCs and PVs. [3]

> Another web application is designed to render servers, IOCs and PVs data in MySQL on the web to give us an overall running status of the control system. [3]

[1] 《EPICS IOC and PVs Information Management System for SHINE》，版本 PCaPAC2022 FRO21，物理页 1～1；`shine-epics-ioc-pv-information-management-pcapac2022:ee367f0a36287d1f95b22845d0f2103fb4b0cd22ef4421024730762fe0ed6d60`。

[2] 《EPICS IOC and PVs Information Management System for SHINE》，版本 PCaPAC2022 FRO21，物理页 3～3；`shine-epics-ioc-pv-information-management-pcapac2022:1932c96141925c86a65dfa6e099ba4ccedb9d73bc4a8de6a17d5d405d2544981`。

[3] 《EPICS IOC and PVs Information Management System for SHINE》，版本 PCaPAC2022 FRO21，物理页 1～1；`shine-epics-ioc-pv-information-management-pcapac2022:6b532252b1d9b5d12ff2e3846095924490c1864b4f7f864b57d511bf95da5bd2`。

### shine-ioc-startup

SHINE 中 IOC 启动后会向管理系统提交哪些信息？

状态：partial。

> 我们将在IOC启动脚本中嵌入脚本代码，以实现IOC启动后，服务器地址、IOC安装路径以及IOC维护的所有记录信息能够自动推送到应用程序，并存储在数据库中。 [1]

证据不足：当前检索证据不足以确认完整信息。

[1] 《EPICS IOC and PVs Information Management System for SHINE》，版本 PCaPAC2022 FRO21，物理页 1～1；`shine-epics-ioc-pv-information-management-pcapac2022:6b532252b1d9b5d12ff2e3846095924490c1864b4f7f864b57d511bf95da5bd2`。

### interlock-latency

SHINE 快联锁对单节点和节点间的响应时间分别有什么要求？

状态：answered。

《SHINE 加速器快联锁系统设计与开发》（核技术 47(12):120203 (2024-12)）：
> 由于上海硬X射线自由电子激光装置具有高重复频率、高稳定性等特点，联锁系统单节点响应时间应小于10 µs，节点间的响应时间应小于100 µs。 [1]

《SHINE 加速器控制系统设计与开发》（unknown）：
> 联锁系统  快联锁 + 慢联锁；主站 + 从站，分层设计 快联锁关键信号响应时间： 站内\(\leq 10\,\mathrm{\mu s}\)，站间\(\leq 100\,\mathrm{\mu s}\) 慢联锁关键信号响应时间： 站内\(\leq 20\,\mathrm{ms}\)，站间\(\leq 100\,\mathrm{ms}\) [2]

[1] 《SHINE 加速器快联锁系统设计与开发》，版本 核技术 47(12):120203 (2024-12)，物理页 2～2；`shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b`。

[2] 《SHINE 加速器控制系统设计与开发》，版本 unknown，物理页 21～21；`shine-accelerator-control-system-design-presentation:4e92201c2cf375a954b2860baf67a725b258f56b1a36a01b061e46d2775928dc`。

### interlock-platform

横河 FPIO 快联锁模块使用哪种 FPGA 芯片和开发语言？

状态：answered。

> FPIO 模块内置的FPGA 使用的是Xilinx 公司的Spartan6 XC6SLX25 系列芯片，其开发和设计流程遵循FPGA开发的通用流程。 [1]

> 在此基础上，使用硬件描述性语言可以实现联锁系统自行定义的控制逻辑开发，SHINE 联锁系统选用 verilog HDL语言进行相关功能开发。 [1]

[1] 《SHINE 加速器快联锁系统设计与开发》，版本 核技术 47(12):120203 (2024-12)，物理页 3～3；`shine-accelerator-fast-interlock-2024:3989f77d1ed901e922429b49a72751dc4b71b50fb0267e5c7a8fe005090a5120`。

### shine-control-layers

How are the functional layers of the SHINE control system separated?

状态：answered。

> EPICS is a set of open source software tools, libraries and applications developed collaboratively and used worldwide to create distributed soft real-time control systems for scientific instruments such as particle accelerators, telescopes and other large-scale scientific ex-periments. ___________________________________________ † yanyingbing@zjlab.org.cn ARCHITECTURE As shown in Fig. 1, the control system can be divided into four layers to ensure the performance and scalability, which are operator interface layer, middle layer, device control layer and data acquisition layer. [1]

> The middle layer consists of compute, storage and network devices. [2]

> The middle layer consists of compute, storage and network devices. It provides the runtime environment for the whole accelerator control system. [2]

> The middle layer consists of compute, storage and network devices. It provides the runtime environment for the whole accelerator control system. It also undertakes the centralized processing tasks for image and stream data acquisition system. [2]

> The device control layer is responsible for the facility-wide input and output device control, such as magnet power supply control, vacuum gauge control, stepper motor control and so on. [2]

> The machine protection and timing system will be also implemented in this layer. [2]

> The machine protection and timing system will be also implemented in this layer. They are the basis components of the control system. [2]

> The data acquisition layer is designed for the high speed image and stream data acquisition, processing and storage. [2]

> The data acquisition layer is designed for the high speed image and stream data acquisition, processing and storage. It involves the beam and laser diagnostics, microwave related system. [2]

> Some custom software will be used at this layer. [2]

[1] 《Status of the SHINE Control System》，版本 ICALEPCS2019 WEPHA167，物理页 1～1；`shine-control-system-status-icalepcs2019:f79189e6eca2f8c7b31f8b61b01a7cec9e5f60c1573d880ba71c7b9bd1fb5269`。

[2] 《Status of the SHINE Control System》，版本 ICALEPCS2019 WEPHA167，物理页 1～1；`shine-control-system-status-icalepcs2019:a3b55aa246c55e377da937ebe851a460b3f0b1f44f4185d57e007f3fe52d5da5`。

### cryo-integration

How do PLCs and soft IOCs divide control and PV acquisition in the SHINE cryogenic system?

状态：answered。

> At the middle layer, PLC will implement most of control logic and PID cycle. [1]

> Soft IOCs running EPICS runtime database accomplish signal collection from PLC, and convert them to Process Variables (PV) under the rule of EPICS Channel Access (CA) protocol. [1]

[1] 《The Cryogenic Control System of SHINE》，版本 EPJ Techniques and Instrumentation (2021)，物理页 3～3；`shine-cryogenic-control-system-2021:b140b52b1b1c29d82fc85c090e3ede87819a3dd9b44182ce3f54e415e439a5d9`。

### cryo-interlock

SHINE 低温测试装置如何通过主联锁 PLC 和 CPLD 实现低温设备保护？

状态：answered。

> 主联锁PLC将执行更复杂的安全逻辑，并通过电缆与冰箱联锁系统交换联锁信号。 [1]

> 为确保严格的时间限制和便于连接，开发了一种专用的复杂可编程逻辑器件（CPLD）模块，该模块带有一个光纤端口、十六个电接口和LATTICE芯片。 [1]

> 使用一对该模块，电和光信号可以在微秒级别双向转换。 [1]

> 测试结果表明，从低温恒温器控制PLC输出到主联锁PLC的响应时间。 [1]

> 约为几十毫秒。 [1]

> 每个低温恒温器控制站有三对DI/DO信号连接到主联锁PLC。 [2]

[1] 《The Cryogenic Control System of SHINE》，版本 EPJ Techniques and Instrumentation (2021)，物理页 6～6；`shine-cryogenic-control-system-2021:ddacec98352d4a3364b0ed059ee45daccd318912026ba96e0e2849bf8bc6de8d`。

[2] 《The Cryogenic Control System of SHINE》，版本 EPJ Techniques and Instrumentation (2021)，物理页 6～6；`shine-cryogenic-control-system-2021:781973867d477bf9605cce02938626938e15c39bc349dc8d5fbcebe71f54e5ad`。

### timing-wrtd

Why is standard White Rabbit Trigger Distribution insufficient for the SHINE beam-synchronous trigger rate?

状态：answered。

> The beam-synchronous trigger signal could theoretically be distributed via WRTD, but the max repetition frequency of SHINE is too high. [1]

> The 10 Gigabit White Rabbit switches are required, but there is no commercial product yet. [1]

[1] 《White Rabbit Based Beam-Synchronous Timing Systems for SHINE》，版本 IPAC2022 THIYGD1，物理页 2～2；`shine-white-rabbit-beam-synchronous-timing-ipac2022:5aa688cbe36ec0b60520b1a45ec473e83ca2459c86144db73ed08a2ef17eab53`。

### timing-jitter

What beam-synchronous and random-event trigger jitter was measured for SHINE timing Prototype II?

状态：answered。

> For the beam-synchronous trigger signal distribution, the jitter between the output of slave node and the external reference signal is less than 20ps (RMS). [1]

> The jitter between the outputs from different slave nodes is less than 10ps (RMS). [1]

> For the random-event trigger signal distribution, the jitter between the output of slave node and the external reference signal is less than 35ps (RMS). [1]

[1] 《White Rabbit Based Beam-Synchronous Timing Systems for SHINE》，版本 IPAC2022 THIYGD1，物理页 5～5；`shine-white-rabbit-beam-synchronous-timing-ipac2022:adb5de8c979b387a905cea6e11dfe193f44004f74377c7349640d3d63e5b2445`。

### control-slow-interlock

SHINE 控制系统设计中慢联锁的站内和站间响应时间指标是什么？

状态：answered。

> 联锁系统  快联锁 + 慢联锁；主站 + 从站，分层设计 快联锁关键信号响应时间： 站内\(\leq 10\,\mathrm{\mu s}\)，站间\(\leq 100\,\mathrm{\mu s}\) 慢联锁关键信号响应时间： 站内\(\leq 20\,\mathrm{ms}\)，站间\(\leq 100\,\mathrm{ms}\) [1]

[1] 《SHINE 加速器控制系统设计与开发》，版本 unknown，物理页 21～21；`shine-accelerator-control-system-design-presentation:4e92201c2cf375a954b2860baf67a725b258f56b1a36a01b061e46d2775928dc`。

### shine-compressors

为什么 SHINE 的两级磁压缩分别布置在 270 MeV 和约 2.1 GeV 位置？

状态：answered。

> 因此综合考虑各种效应以后，将BC1 处的束流能量选在270MeV。 [1]

> BC2 位置的选择主要考虑到相干同步辐射效应（CSR）对电子束发射度的破坏，束流能量、能散和到达时间的稳定性的优化。 [1]

[1] 《硬 X 射线自由电子激光装置初步设计报告（加速器分册）》，版本 初步设计报告 (2017-12-26)，物理页 61～61；`shine-accelerator-preliminary-design-report-2017:485d8b33ff6ed2e347fa8cba06c82d98aeec1523072c4601be8da25fc12826a3`。

### shine-main-linac

SHINE 初步设计中的主加速器采用什么工作模式，最终把电子加速到多少能量？

状态：answered。

> L1 中的三次谐波腔（3.9GHz）则用来线性化电子束的能量啁啾，使电子束可以压缩到更高的流强。 [1]

> 主加速器第三个加速段L3 由54 个模组组成，将电子束的能量由2.1GeV 加速至最终的8GeV。 [1]

[1] 《硬 X 射线自由电子激光装置初步设计报告（加速器分册）》，版本 初步设计报告 (2017-12-26)，物理页 60～60；`shine-accelerator-preliminary-design-report-2017:cf8f273a1807979a26bbeb8f961f70b0886235053ba0f7b80ee3989f17712b7b`。

### no-answer-finance

What was NVIDIA quarterly revenue in fiscal 2026 Q4?

状态：insufficient。

The retrieved evidence is insufficient to confirm the requested information.

### no-answer-recipe

如何制作四川麻婆豆腐？请给出食材和烹饪步骤。

状态：insufficient。

当前检索证据不足，无法确认所问事实。

### no-answer-token

zxqv9999unlistedcalibrationartifact

状态：insufficient。

The retrieved evidence is insufficient to confirm the requested information.

### no-answer-hard-live-pv

SHINE 在 2026-10-19 10:00 UTC 的 temperature:water PV 实时读数是多少？

状态：insufficient。

当前检索证据不足，无法确认所问事实。

### no-answer-hard-live-ioc-count

How many SHINE IOCs are online at 10:00 UTC on 19 October 2026?

状态：insufficient。

The retrieved evidence is insufficient to confirm the requested information.

### no-answer-hard-live-interlock

SHINE 快联锁在 2026-10-19 10:00 UTC 的在线许可状态是什么？

状态：insufficient。

当前检索证据不足，无法确认所问事实。

### no-answer-hard-live-cryo

What is the measured SHINE helium refrigerator outlet pressure at 10:00 UTC on 19 October 2026?

状态：insufficient。

The retrieved evidence is insufficient to confirm the requested information.

### no-answer-hard-deployed-firmware

What exact firmware build SHA was installed on the SHINE White Rabbit master on 19 October 2026?

状态：insufficient。

The retrieved evidence is insufficient to confirm the requested information.

### no-answer-hard-current-ioc-ip

SHINE IOC 在 2026-10-19 10:00 UTC 使用的实时 server IP 完整清单是什么？

状态：insufficient。

当前检索证据不足，无法确认所问事实。

### no-answer-hard-live-bpm-calibration

What measured BPM calibration constant was approved at SHINE on 19 October 2026?

状态：insufficient。

The retrieved evidence is insufficient to confirm the requested information.

### no-answer-hard-live-beam-energy

SHINE 在 2026-10-19 10:00 UTC 实际测量的电子束能量是多少？

状态：insufficient。

当前检索证据不足，无法确认所问事实。
