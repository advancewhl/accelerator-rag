# RAG Stage 2 全知识库检索基线

生成日期：2026-10-19。4547 个 Chunk 共用一个 BM25 和一个 Qdrant 集合。
BM25 与 Dense 分开评测，分数不相加、不比较，也没有阈值或 reranker。

## 指标

| 检索器 | Recall@1 | Recall@3 | Recall@5 | MRR（深度 5） | 可回答 | 无答案 |
|---|---:|---:|---:|---:|---:|---:|
| bm25 | 0.4286 | 0.7619 | 0.8095 | 0.6071 | 21 | 3 |
| dense | 0.1429 | 0.4286 | 0.5714 | 0.2976 | 21 | 3 |

Recall@K 表示可回答问题中，Top-K 至少含一条已标注可接受文档与物理页证据的问题比例。多个可接受来源按任一命中判定。MRR 在深度 5 截断，未命中记为 0。
页级 ground truth 是检索前固定的种子判断，不穷尽 corpus 中所有合理答案。未命中表示未命中已标注页，仍需人工检查其他页的相关性。

## 无答案行为与分数

### bm25

无答案行为：`{'queries_returning_results': 2, 'queries_returning_empty': 1, 'correct_hits': 0, 'threshold': None}`。
可回答 Top-1 分数：`{'count': 21, 'min': 20.15356862980385, 'max': 66.65831002514996, 'mean': 38.45632380900639, 'p10': 21.81313372737136, 'p25': 24.411183940366094, 'median': 38.1138157489369, 'p75': 50.323513615378154, 'p90': 60.24651387492714, 'p95': 62.474643540295375}`。
无答案 Top-1 分数：`{'count': 2, 'min': 12.06619575488726, 'max': 13.359896571956714, 'mean': 12.713046163421987, 'p10': 12.195565836594206, 'p25': 12.389620959154623, 'median': 12.713046163421987, 'p75': 13.036471367689352, 'p90': 13.230526490249769, 'p95': 13.295211531103241}`。

### dense

无答案行为：`{'queries_returning_results': 3, 'queries_returning_empty': 0, 'correct_hits': 0, 'threshold': None}`。
可回答 Top-1 分数：`{'count': 21, 'min': 0.5029936055153001, 'max': 0.7782650980675581, 'mean': 0.6646625931700756, 'p10': 0.5708380912579243, 'p25': 0.6365569617778466, 'median': 0.666657418598924, 'p75': 0.7076117817397227, 'p90': 0.7360936741426042, 'p95': 0.7688694317055917}`。
无答案 Top-1 分数：`{'count': 3, 'min': 0.41021033208544283, 'max': 0.5327771035730879, 'mean': 0.4694254110388763, 'p10': 0.4212260251599739, 'p25': 0.4377495647717705, 'median': 0.46528879745809826, 'p75': 0.4990329505155931, 'p90': 0.51927944235009, 'p95': 0.5260282729615889}`。

## 实际 case

### bm25 best cases

**epics-pp**：When does an EPICS PP input link process its target record?

预期：`[{'document_id': 'epics-application-developers-guide-r3-16-2', 'pages': [88]}]`；首个命中排名：`1`。

- Top 1，score 31.946063，`epics-application-developers-guide-r3-16-2`，物理页 88～88，Chunk `epics-application-developers-guide-r3-16-2:4e943f6ecf46b38b7ee6430c4af3d6ca5f8395f55de38b4ae99b8c2934d796fd`。
  For input and output links, two additional attributes can be speciﬁed by the application developer: process passive, and maximize severity.  5.3.1 Process Passive  The Process Passive attribute takes the value NPP (Non-Process Passive) or PP (Process Passive). It determines if the linked record should be processed before getting a value from an input link or
- Top 2，score 31.464646，`epics-documentation-latest-2026-08-18`，物理页 152～152，Chunk `epics-documentation-latest-2026-08-18:aa25953509a675f8af13c6cac5035435c1c9c552a95500aec8602ff2dd82f781`。
  Links are defined in file dbLink.h.  ò Note  This chapter discusses mainly database links.  1.11.3 Link Operations  The basic operations which can be performed on a link (excluding hardware links) are as follows.  • dbGetLink(): The value of the field referenced by the input link retrieved.  • dbPutLink(): The value of the field referenced by the output link
- Top 3，score 28.675399，`epics-application-developers-guide-r3-16-2`，物理页 91～91，Chunk `epics-application-developers-guide-r3-16-2:e82abd54ea7a3e6070f76af19edc553cef8a35471d1b6f6abe865ef9aee99910`。
  • dbPutField: This routine sets the target ﬁeld value and then, if the ﬁeld was marked pp(TRUE) it calls dbScanPassive. Each ﬁeld of each record type has an attribute pp declared as either TRUE or FALSE in the record deﬁnition ﬁle. The attribute is a global property which is set by the record type. This use of pp only affects calls to the dbPutField routine.

**epics-reconnect**：What happens to Channel Access client connections when an IOC server crashes and restarts?

预期：`[{'document_id': 'epics-application-developers-guide-r3-16-2', 'pages': [31]}]`；首个命中排名：`1`。

- Top 1，score 46.147549，`epics-application-developers-guide-r3-16-2`，物理页 31～31，Chunk `epics-application-developers-guide-r3-16-2:95cb188c903769a161efd7e58aa0d41b1769de1d3eb1b6338df57dcede30a7e6`。
  Once the process variables have been located, the Channel Access client issues connection requests for each IOC containing process variables the client uses. The connection request server, in the IOC, accepts the request and establishes a connection to the client. Each connection is managed by two separate tasks: ca_get and ca_put. The ca_get and ca_put requ
- Top 2，score 45.879853，`epics-documentation-latest-2026-08-18`，物理页 63～63，Chunk `epics-documentation-latest-2026-08-18:6961ffb7721d5bea047a429812ebf87e24dab760d272d580be108571c315d1fd`。
  Once the process variables have been located, the Channel Access client issues connection requests for each IOC containing process variables the client uses. The connection request server, in the IOC, accepts the request and establishes a connection to the client. Each connection is managed by two separate tasks: ca_get and ca_put. The ca_add_event requests 
- Top 3，score 28.211420，`epics-application-developers-guide-r3-16-2`，物理页 31～31，Chunk `epics-application-developers-guide-r3-16-2:4fdd529ed0da19160859ff1e0a7824efccb13203f1329560c764995cccc8adc4`。
  It should be noted that Channel Access does not provide access to database records as records. This is a deliberate design decision. This allows new record types to be added without impacting any software that accesses the database via Channel Access, and it allows a Channel Access client to communicate with multiple IOCs having differing sets of record type

**undulator-tuning**：How does a K-monochromator select radiation for tuning undulator segments?

预期：`[{'document_id': 'european-xfel-undulator-commissioning-spectrometer-cdr-2011', 'pages': [3]}]`；首个命中排名：`1`。

- Top 1，score 26.359496，`european-xfel-undulator-commissioning-spectrometer-cdr-2011`，物理页 3～3，Chunk `european-xfel-undulator-commissioning-spectrometer-cdr-2011:c208c6408e233a2e7befd62dc28bd5c48599330924d27e193ba6237b84f3e030`。
  The commissioning spectrometer, also known as K-monochromator, is mainly used with spontaneous radiation and selects a narrow bandwidth of the x-ray photon beam in order to tune the undulator segments. This process is called photon beam-based alignment and will minimize the difference in the undulator parameters K between undulator segments and optimize the 
- Top 2，score 20.010637，`european-xfel-full-technical-design-report-2007`，物理页 5～5，Chunk `european-xfel-full-technical-design-report-2007:8ccaa5ccab95a3a107337339f4366548c407a86e05cbf48d79dc29cf01909fc0`。
  ..............................................................189 5.4.1 Choice of undulator parameters ..................................................189 5.4.2 Basic tolerance requirements ......................................................193 5.4.3 Undulator segments ....................................................................194 5.4.4 Interse
- Top 3，score 19.946757，`european-xfel-full-technical-design-report-2007`，物理页 225～225，Chunk `european-xfel-full-technical-design-report-2007:7d15845a6708ac1d93d4433bc1eb5b8e2a7c6b1b370bfcaed523252822a821c0`。
  5.5.3 Phase tuning  Changing the undulator gap will result in a change of the phase relation between two adjacent segments. In order to compensate for the wavelength dependent phasing condition, a phase shifter is installed in the intersection module (Section 5.4.4). It consists of a three-magnet chicane which is powered by a gap-dependent current, and delay

### bm25 failure cases

**xfel-rf**：What RF frequency and nominal design energy are used by the European XFEL main linac?

预期：`[{'document_id': 'european-xfel-full-technical-design-report-2007', 'pages': [65]}]`；首个命中排名：`None`。

- Top 1，score 26.897949，`european-xfel-full-technical-design-report-2007`，物理页 57～57，Chunk `european-xfel-full-technical-design-report-2007:185d4b3f8fa3f1a6e8dfeefec951f19740941d19c5ce65a7b26e63a1b1ed51a0`。
  The basic functions of the main components are schematically described in the following: In the injector, electron bunches are extracted from a solid cathode by a laser beam, focused and accelerated by an electron radio frequency (RF) gun and directed towards the linac with an exit energy of 120 MeV. In the linac, consisting of a 1.6 km long sequence of supe
- Top 2，score 25.671638，`european-xfel-full-technical-design-report-2007`，物理页 99～99，Chunk `european-xfel-full-technical-design-report-2007:819cd9c53ccc93e996dd10665b10cd5bf2c8036144844449e289fec137d30405`。
  At 20 GeV, the linac for the XFEL operates at a gradient of 23.6 MV/m with a repetition rate of 10 Hz. Since the particle beam current is 5 mA, up to 122 kW are required per cavity. The maximum beam pulse duration is 600 µs and the cavity filling time 780 µs.  Thirty-two cavities (four times eight cavities per cryogenic module) will be connected to one klyst
- Top 3，score 25.172392，`european-xfel-full-technical-design-report-2007`，物理页 72～72，Chunk `european-xfel-full-technical-design-report-2007:1cc4da6f3c71834720bd429eb0c05a7d8f9665cc431f98ea59533ce2a0e09da2`。
  4.2 Linac  4.2.1 Cavities  4.2.1.1 Introduction  The XFEL accelerating cavity is a nine-cell standing wave structure of about 1 m length whose fundamental TM mode has a frequency of 1,300 MHz. It is identical to the so-called TESLA cavity [4-1], made from solid Niobium, and is bath-cooled by superfluid Helium at 2 K. Each cavity is equipped with: a Helium ta

**xfel-normal-energy**：欧洲 XFEL 常规运行时电子束能量是多少，与最高设计能量有何区别？

预期：`[{'document_id': 'european-xfel-full-technical-design-report-2007', 'pages': [21, 57]}]`；首个命中排名：`None`。

- Top 1，score 24.411184，`shine-accelerator-preliminary-design-report-2017`，物理页 279～279，Chunk `shine-accelerator-preliminary-design-report-2017:ec52d742272b6f76b352f882d9f8ae6603be767e251a845adc4c50cee43672da`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  275  6. 加速器公共子系统  6.1 束流诊断  6.1.1 概述  电子束流诊断系统作为自由电子激光装置调束、运行时的主要工具，应具备  如下基本功能：（1）在装置调束期间，实现对电子束流各项参数的实时测量，测  量结果通过控制网发布提供给调束、运行人员，各类诊断设备的测量动态范围需  要满足初始调束的需求；（2）在装置进行验收时，对电子束流关键参数进行精确  测量，作为主要验收手段；（3）在装置投入运行之后，实现对电子束流主要运行  参数的实时在线监测，为运行人员监测及优化运行状态提供手段，要求系统具有  高可靠性、重复性及稳定性；（4）为装置中的束流反馈控制环路提供束流数据。  本装置中所需的各类电子束流诊断技术，大多已经在上海光源、上海深紫外
- Top 2，score 23.615906，`shine-accelerator-control-system-design-presentation`，物理页 10～10，Chunk `shine-accelerator-control-system-design-presentation:2509d214dbcf2c7954dba968bf9cae8b3c33ece03fc3d2639f9f12a1098489e6`。
  \uf06eCSS是否是最合适的用户界面？  \uf06e全局网络环境下，一个IOC对应多少台设备最合理？  \uf06e虚拟化可以整合硬件资源，提高控制系统可靠性和稳定性；  IOC虚拟化占比多少最合适？  \uf06e控制系统存储容量多少最合理？  \uf06e是否需要异地容灾备份？  \uf06e控制系统是否需要持续集成 (Continue Integrate)？
- Top 3，score 22.506373，`shine-accelerator-preliminary-design-report-2017`，物理页 174～174，Chunk `shine-accelerator-preliminary-design-report-2017:58c8589d587df4fd3645220e5c5d2c806359a1ab2cdafa1c886f5f714682a5f1`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  170  4.1.1.3 HB-SASE  HB-SASE 主要用于改善SASE 纵向相干性，提高光谱亮度。HB-SASE 特点  是采用锁模型波荡器，即在波荡器段间加入小的滑移段来大幅度增加FEL 相干  长度，改善FEL 的纵向相干性，提高FEL 的光谱亮度，其方案如图3.3.4.1-9 所  示。相比于种子型FEL，HB-SASE 的优点在于不需要种子激光和额外的光学器  件，因而从原理上讲HB-SASE 可运行于任意FEL 光子能量和重复频率。  图3.3.4.1-9 HB-SASE 波荡器示意图  在HB-SASE 的设计中首先要考虑的问题是单节波荡器的长度和段间滑移段  的强度。一般来讲，为有效抑制SASE 的非相干噪声，单节波荡器长度应略小于

**shine-ioc-startup**：SHINE 中 IOC 启动后会向管理系统提交哪些信息？

预期：`[{'document_id': 'shine-epics-ioc-pv-information-management-pcapac2022', 'pages': [2]}, {'document_id': 'shine-epics-ioc-pv-information-management-pcapac2022', 'pages': [3]}]`；首个命中排名：`None`。

- Top 1，score 22.963092，`shine-accelerator-control-system-design-presentation`，物理页 28～28，Chunk `shine-accelerator-control-system-design-presentation:b0660b85a16b9319003972afc581f5ece2cdca5398313113390916e148417fbb`。
  通道信息管理  \uf06e 完成通道信息管理软件核心模块开发  \uf06e 将控制系统中的IOC信息、Record信息纳入数据库管理  \uf06e 所有IOC的静态信息（地址、端口、...），状态信息（连接、...）  \uf06e 所有Record的名称、类型、域定义情况，以及访问权限、合法性等  软件著作权登记 数据库设计
- Top 2，score 20.814323，`shine-accelerator-control-system-design-presentation`，物理页 30～30，Chunk `shine-accelerator-control-system-design-presentation:8680eaac49a9aab40945aa9353f67e1921ea0ba214fc008fabeffeacfa8f499c`。
  超导腔文件管理系统  \uf06e SHINE项目中，77个模组，每个模组包含8个超导腔（1.3GHz、3.9GHz）  \uf06e 基于Mediawiki构建，可以管理超导腔的加工、生产、测试过程文件  \uf06e 不同用户的编辑权限不同、厂商之间相互屏蔽报告内容、可以上传文件、图片等附件  （详见吕慧慧博士的报告）  客户端Web界面
- Top 3，score 20.526288，`shine-accelerator-control-system-design-presentation`，物理页 11～11，Chunk `shine-accelerator-control-system-design-presentation:6b8f0ceb515b720630218435f9e584b54b8a3da91de09e50aacc8c21420c968f`。
  \uf06e控制系统的层级 (刘德康 研究员)：  设备控制层、本地处理层、人机交互层、束流物理层、数学模型层  \uf06e哪些工作需要做？哪些工作必须现在做？哪些工作可以推后做？  \uf06e控制是一个全局性的系统，系统架构设计、各类协议和标准的统一  对于系统集成至关重要；  \uf06e协议、标准、规范如何做到有前瞻性？如何有效、“轻负”推进？

### bm25 cross-language cases

**xfel-normal-energy**：欧洲 XFEL 常规运行时电子束能量是多少，与最高设计能量有何区别？

预期：`[{'document_id': 'european-xfel-full-technical-design-report-2007', 'pages': [21, 57]}]`；首个命中排名：`None`。

- Top 1，score 24.411184，`shine-accelerator-preliminary-design-report-2017`，物理页 279～279，Chunk `shine-accelerator-preliminary-design-report-2017:ec52d742272b6f76b352f882d9f8ae6603be767e251a845adc4c50cee43672da`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  275  6. 加速器公共子系统  6.1 束流诊断  6.1.1 概述  电子束流诊断系统作为自由电子激光装置调束、运行时的主要工具，应具备  如下基本功能：（1）在装置调束期间，实现对电子束流各项参数的实时测量，测  量结果通过控制网发布提供给调束、运行人员，各类诊断设备的测量动态范围需  要满足初始调束的需求；（2）在装置进行验收时，对电子束流关键参数进行精确  测量，作为主要验收手段；（3）在装置投入运行之后，实现对电子束流主要运行  参数的实时在线监测，为运行人员监测及优化运行状态提供手段，要求系统具有  高可靠性、重复性及稳定性；（4）为装置中的束流反馈控制环路提供束流数据。  本装置中所需的各类电子束流诊断技术，大多已经在上海光源、上海深紫外
- Top 2，score 23.615906，`shine-accelerator-control-system-design-presentation`，物理页 10～10，Chunk `shine-accelerator-control-system-design-presentation:2509d214dbcf2c7954dba968bf9cae8b3c33ece03fc3d2639f9f12a1098489e6`。
  \uf06eCSS是否是最合适的用户界面？  \uf06e全局网络环境下，一个IOC对应多少台设备最合理？  \uf06e虚拟化可以整合硬件资源，提高控制系统可靠性和稳定性；  IOC虚拟化占比多少最合适？  \uf06e控制系统存储容量多少最合理？  \uf06e是否需要异地容灾备份？  \uf06e控制系统是否需要持续集成 (Continue Integrate)？
- Top 3，score 22.506373，`shine-accelerator-preliminary-design-report-2017`，物理页 174～174，Chunk `shine-accelerator-preliminary-design-report-2017:58c8589d587df4fd3645220e5c5d2c806359a1ab2cdafa1c886f5f714682a5f1`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  170  4.1.1.3 HB-SASE  HB-SASE 主要用于改善SASE 纵向相干性，提高光谱亮度。HB-SASE 特点  是采用锁模型波荡器，即在波荡器段间加入小的滑移段来大幅度增加FEL 相干  长度，改善FEL 的纵向相干性，提高FEL 的光谱亮度，其方案如图3.3.4.1-9 所  示。相比于种子型FEL，HB-SASE 的优点在于不需要种子激光和额外的光学器  件，因而从原理上讲HB-SASE 可运行于任意FEL 光子能量和重复频率。  图3.3.4.1-9 HB-SASE 波荡器示意图  在HB-SASE 的设计中首先要考虑的问题是单节波荡器的长度和段间滑移段  的强度。一般来讲，为有效抑制SASE 的非相干噪声，单节波荡器长度应略小于

**shine-ioc-startup**：SHINE 中 IOC 启动后会向管理系统提交哪些信息？

预期：`[{'document_id': 'shine-epics-ioc-pv-information-management-pcapac2022', 'pages': [2]}, {'document_id': 'shine-epics-ioc-pv-information-management-pcapac2022', 'pages': [3]}]`；首个命中排名：`None`。

- Top 1，score 22.963092，`shine-accelerator-control-system-design-presentation`，物理页 28～28，Chunk `shine-accelerator-control-system-design-presentation:b0660b85a16b9319003972afc581f5ece2cdca5398313113390916e148417fbb`。
  通道信息管理  \uf06e 完成通道信息管理软件核心模块开发  \uf06e 将控制系统中的IOC信息、Record信息纳入数据库管理  \uf06e 所有IOC的静态信息（地址、端口、...），状态信息（连接、...）  \uf06e 所有Record的名称、类型、域定义情况，以及访问权限、合法性等  软件著作权登记 数据库设计
- Top 2，score 20.814323，`shine-accelerator-control-system-design-presentation`，物理页 30～30，Chunk `shine-accelerator-control-system-design-presentation:8680eaac49a9aab40945aa9353f67e1921ea0ba214fc008fabeffeacfa8f499c`。
  超导腔文件管理系统  \uf06e SHINE项目中，77个模组，每个模组包含8个超导腔（1.3GHz、3.9GHz）  \uf06e 基于Mediawiki构建，可以管理超导腔的加工、生产、测试过程文件  \uf06e 不同用户的编辑权限不同、厂商之间相互屏蔽报告内容、可以上传文件、图片等附件  （详见吕慧慧博士的报告）  客户端Web界面
- Top 3，score 20.526288，`shine-accelerator-control-system-design-presentation`，物理页 11～11，Chunk `shine-accelerator-control-system-design-presentation:6b8f0ceb515b720630218435f9e584b54b8a3da91de09e50aacc8c21420c968f`。
  \uf06e控制系统的层级 (刘德康 研究员)：  设备控制层、本地处理层、人机交互层、束流物理层、数学模型层  \uf06e哪些工作需要做？哪些工作必须现在做？哪些工作可以推后做？  \uf06e控制是一个全局性的系统，系统架构设计、各类协议和标准的统一  对于系统集成至关重要；  \uf06e协议、标准、规范如何做到有前瞻性？如何有效、“轻负”推进？

**interlock-latency**：SHINE 快联锁对单节点和节点间的响应时间分别有什么要求？

预期：`[{'document_id': 'shine-accelerator-fast-interlock-2024', 'pages': [2]}]`；首个命中排名：`2`。

- Top 1，score 60.246514，`shine-accelerator-fast-interlock-2024`，物理页 7～7，Chunk `shine-accelerator-fast-interlock-2024:ee60572dc682fe0e48200b35c16f73ecfee54cfa2b8d3cfb204cb5337a7e155c`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量计数不低于10 000次，测试结 果显示单节点响应时间平均值为328.81 ns，优于单 节点响应时间10 µs的设计指
- Top 2，score 52.031162，`shine-accelerator-fast-interlock-2024`，物理页 2～2，Chunk `shine-accelerator-fast-interlock-2024:072ee7b7291b1a7f3042ce1fa225efbc1de7ac07bcca5a86061dc5a5b0ccee4e`。
  核 技 术 2024, 47: 120203  and the system have been put into online operation for SHINE injector. The response time test results meet the  SHINE operation requirements, and remote control of the system has been implemented based on the EPICS.  Key words Fast interlock, FPGA, Data transmission, FL-net, Response time  上海硬X 射线自由电子激光装置（Shanghai HIgh repetitioN rate
- Top 3，score 51.825567，`shine-accelerator-preliminary-design-report-2017`，物理页 398～398，Chunk `shine-accelerator-preliminary-design-report-2017:97bb36fda132e48a990c56ebf0bc0fe3186d34055e0b5d7f09f504e19ff90b44`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  394  包括网络传输和服务器处理时间。负载能力是在正常的响应时间范围内，系统能  够支持的最多的客户端的数量，可以通过发起大量的CA 连接进行测试。  6.2.3.2 硬件检测平台  硬件检测平台针对主定时和快联锁系统中自主研制的模块，主要检测时间相  关的参数，包括主定时系统的时钟晃动检测、快联锁系统的站内或站间的响应时  间检测，它是确保这整控制系统达到设计指标的关键。硬件模块常规的测试，例  如检测有无开短路问题，是否符合电磁兼容要求等，通过借用或租用平台的方式  来完成。  硬件检测平台由射频信号源、任意波形发生器、稳压电源、数字示波器、信  号源分析仪、逻辑分析仪等仪器设备组成。其中，数字示波器用来在时域测量主  定时系统的时钟晃动或快联锁系统

### bm25 no-answer cases

**no-answer-finance**：What was NVIDIA quarterly revenue in fiscal 2026 Q4?

预期：`[]`；首个命中排名：`None`。

- Top 1，score 12.066196，`epics-documentation-latest-2026-08-18`，物理页 1～1，Chunk `epics-documentation-latest-2026-08-18:6cf3c145c9aa4286c42ddce4ddbe38932010ae4f84020a27837810ed19dafdfb`。
  EPICS Documentation  EPICS  Aug 18, 2026
- Top 2，score 11.718082，`epics-documentation-latest-2026-08-18`，物理页 19～19，Chunk `epics-documentation-latest-2026-08-18:749e843635e01b9e9112a5f1e67068081ca7e0108b1bf3a8e333df537ab6a45c`。
  (continued from previous page) ############################################################################ ## EPICS R7.0.10 ## Rev. 2026-06-25T10:56+0200 ## Rev. Date build date/time: ############################################################################ iocRun: All initialization complete epics>  Create a demo/test IOC  We will create a test ioc from
- Top 3，score 9.303333，`epics-application-developers-guide-r3-16-2`，物理页 11～11，Chunk `epics-application-developers-guide-r3-16-2:c54bb59207457fca1dc22335f53cd7ed5a5990a50cf9633b938fa94052ddf53c`。
  1.2. ACKNOWLEDGMENTS 11  1.2 Acknowledgments  The basic model of what an IOC should do and how to do it was developed by Bob Dalesio at LANL/GTA. The principle ideas for Channel Access were developed by Jeff Hill at LANL/GTA. Bob and Jeff also were the principle implementers of the original IOC software. This software (called GTACS) was developed over a peri

**no-answer-recipe**：如何制作四川麻婆豆腐？请给出食材和烹饪步骤。

预期：`[]`；首个命中排名：`None`。

- Top 1，score 13.359897，`shine-accelerator-control-system-design-presentation`，物理页 11～11，Chunk `shine-accelerator-control-system-design-presentation:6b8f0ceb515b720630218435f9e584b54b8a3da91de09e50aacc8c21420c968f`。
  \uf06e控制系统的层级 (刘德康 研究员)：  设备控制层、本地处理层、人机交互层、束流物理层、数学模型层  \uf06e哪些工作需要做？哪些工作必须现在做？哪些工作可以推后做？  \uf06e控制是一个全局性的系统，系统架构设计、各类协议和标准的统一  对于系统集成至关重要；  \uf06e协议、标准、规范如何做到有前瞻性？如何有效、“轻负”推进？
- Top 2，score 11.640601，`shine-accelerator-control-system-design-presentation`，物理页 14～14，Chunk `shine-accelerator-control-system-design-presentation:b153c74d979cbc7475f03a4f0bdb604ec26f714a958bc754529a4c5671b1cce1`。
  \uf06e一流的装置，需要一流的、数量可观的控制队伍；  \uf06e人员缺口大、招聘难度大、培养周期长，结构不合理；  \uf06e如何充分发挥现有的人员力量？  \uf06e项目之间如何优化配比？  \uf06e如何建立有效的国内、国际合作？
- Top 3，score 11.625080，`shine-accelerator-preliminary-design-report-2017`，物理页 160～160，Chunk `shine-accelerator-preliminary-design-report-2017:33ede243c6502b63eb5765a12e35cb1825be41825cad9ed945c2acc7cedc36d6`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  156  FPGA程序和EPICS db文件。  预估的单套联锁信号如表3.3.3.5-2。  表3.3.3.5-2 预估的单套联锁信号  ai ar aw di dr dw  环流器打火 1  环流器打火测试 1  环流器水流量计 1  环流器温差 1  水负载打火 1  水负载打火测试 1  水负载入水温度 1  水负载出水温度 1  水负载流量 1  水路压力 1  超导腔入射功率 1  超导腔反射功率 1  发射机输出功率 1  发射机反射功率 1  预研阶段，将完成一套联锁系统的研发。  时间进度规划如下（视开始研制时间顺延）：  2017年8月底前完成系统结构设计；  2017年12月底完成第一版硬件制作；  2018年6月底前完成第一版联调；

**no-answer-token**：zxqv9999unlistedcalibrationartifact

预期：`[]`；首个命中排名：`None`。


### dense best cases

**epics-cli**：Which EPICS command-line tools read, write and continuously monitor the temperature:water PV?

预期：`[{'document_id': 'epics-documentation-latest-2026-08-18', 'pages': [9]}]`；首个命中排名：`1`。

- Top 1，score 0.707612，`epics-documentation-latest-2026-08-18`，物理页 9～9，Chunk `epics-documentation-latest-2026-08-18:cc49ec8dfb9665754cb55d8d5fcc7ff32cde90f718f39fde3f7213ede6f93442`。
  Ok, that is not very impressive, but at least you know that EPICS is installed correctly. So now let us try something more complex, which will hopefully suggest how EPICS works.  In whatever directory you like, prepare a file test.db that reads like  record(ai, "temperature:water") {  field(DESC, "Water temperature in the fish tank") }  This file defines a r
- Top 2，score 0.698929，`epics-documentation-latest-2026-08-18`，物理页 10～10，Chunk `epics-documentation-latest-2026-08-18:7bc27d6092afcaba3ca6978766b217455889611afb605d24d575e99e25ec9872`。
  record(ai, "temperature:water") {  field(DESC, "Water temperature in Lab 10") field(MDEL, ".01") }  MDEL stands for Monitor Deadband. If you now run  softIoc -d test.db  with the new test.db file, you will see that camonitor reacts only to changes that are larger than 0.01.  This was just a simple example. Please refer to a recent Record Reference Manual for
- Top 3，score 0.682759，`epics-documentation-latest-2026-08-18`，物理页 39～39，Chunk `epics-documentation-latest-2026-08-18:424a5eef1c0778d857c9415f92a527a1417b4334c49dab3ed7e10fea54f613be`。
  Change the line that says  VALID_BUILDS = Ioc  To  VALID_BUILDS = Host Ioc  This is needed in order to get caRepeater compiled, according to this source.  Recompile EPICS base  Now, we recompile EPICS base:  make clean uninstall make  Hopefully, we have everything in place to start developing our IOC’s.

**xfel-bpm-types**：Which BPM pickup types provide standard and high-precision position measurements at European XFEL?

预期：`[{'document_id': 'european-xfel-standard-e-beam-diagnostics-linac2010', 'pages': [1]}]`；首个命中排名：`1`。

- Top 1，score 0.641950，`european-xfel-standard-e-beam-diagnostics-linac2010`，物理页 1～1，Chunk `european-xfel-standard-e-beam-diagnostics-linac2010:5d1326d80464912ad0c6bc8c4cd79e7152e734a6427ba19d7aa684e6e5d42cde`。
  BEAM POSITION MONITOR SYSTEM The E-XFEL BPM system will be provided by a collaboration of PSI, CEA and DESY [5]. As listed in Table 2, there will be standard BPMs with moderate and precision BPMs with high resolution. The standard BPMs will be of the button type. Precision monitors will be different cavity BPM types. About one third of the BPMs in the accele
- Top 2，score 0.623851，`european-xfel-standard-e-beam-diagnostics-linac2010`，物理页 1～1，Chunk `european-xfel-standard-e-beam-diagnostics-linac2010:4f2b23ad60abab3707fa6efd0e1f12b3f46afb572c5de2a5d12d26fa32e56920`。
  Button BPMs will be the standard BPMs in E-XFEL. In the superconducting part they are rigidly connected to the quadrupoles (see Fig. 1) at the end of each accelerator module string [6].  Figure 1: Button BPM for the cryo-modules, already assembled to the superconducting quadrupole package of the PXFEL3 prototype accelerator module.  The development of this B
- Top 3，score 0.619061，`european-xfel-standard-e-beam-diagnostics-linac2010`，物理页 2～2，Chunk `european-xfel-standard-e-beam-diagnostics-linac2010:09b86ebee01c92e93f267b7c84cefb3e29b5eaa1dcdfe41130aa8125834952e0`。
  Two types of cavity BPMs based on the development of T. Shintake for SCSS will be used [8]. Both types with a beam pipe diameter of 10 mm and 40.5 mm, respectively, as shown in Fig. 2, consist of a reference and dipole resonator. The cross talk between the two resonators was measured to be very low (-43 dB). The two types have very similar RF parameters, whi

**control-slow-interlock**：SHINE 控制系统设计中慢联锁的站内和站间响应时间指标是什么？

预期：`[{'document_id': 'shine-accelerator-control-system-design-presentation', 'pages': [21]}]`；首个命中排名：`1`。

- Top 1，score 0.778265，`shine-accelerator-control-system-design-presentation`，物理页 21～21，Chunk `shine-accelerator-control-system-design-presentation:25ed01ed469d6dea8a224590fbade9da0e70ca5cbebe2acac44d09ce2d74e577`。
  联锁系统  \uf06e 快联锁 + 慢联锁；主站 + 从站，分层设计  \uf0b2快联锁关键信号响应时间：  站内≤10us，站间≤100us  \uf0b2慢联锁关键信号响应时间：  站内≤20ms，站间≤100ms
- Top 2，score 0.717592，`shine-accelerator-fast-interlock-2024`，物理页 8～8，Chunk `shine-accelerator-fast-interlock-2024:5555f0f1baab72d4c0a95b900177ed146ddcf661b864c6b7fdb3861009f5537b`。
  核 技 术 2024, 47: 120203  单节点平均响应时间为328.81 ns，节点间经800 m 电缆连接的系统平均响应时间为5.33 µs，均优于快 联锁系统的设计指标。系统运行模式的设置和传输 功能正常，各站点在不同模式下相应联锁逻辑切换 等功能也已通过测试并投入正常运行。SHINE加速 器快联锁系统功能完善，运行稳定正常，满足系统的 设计要求。  作者贡献声明 于春蕾负责联锁系统的整体设计、 需求对接、运行模式设计和实现、快联锁系统的设计 与开发，并负责数据的收集和整理、文章的起草和最 终版本的修订；陈广花负责研究的提出及设计，样机 的搭建和测试；丁建国负责系统设计的指导和监督、 系统机柜集成的硬件设计；李明负责系统的工艺流 程和实施工作，慢联锁系统的软件开发和调试；肖庆 雯负责基于EPICS 
- Top 3，score 0.710922，`shine-accelerator-fast-interlock-2024`，物理页 7～7，Chunk `shine-accelerator-fast-interlock-2024:ee60572dc682fe0e48200b35c16f73ecfee54cfa2b8d3cfb204cb5337a7e155c`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量计数不低于10 000次，测试结 果显示单节点响应时间平均值为328.81 ns，优于单 节点响应时间10 µs的设计指

### dense failure cases

**epics-pp**：When does an EPICS PP input link process its target record?

预期：`[{'document_id': 'epics-application-developers-guide-r3-16-2', 'pages': [88]}]`；首个命中排名：`None`。

- Top 1，score 0.674150，`epics-application-developers-guide-r3-16-2`，物理页 179～179，Chunk `epics-application-developers-guide-r3-16-2:2cd3a3cb6421e80179c68e28a829b0a8d4b9ba7394c2c4e3cbc068405fac4cb1`。
  The most important record support routine is process. This routine determines what record processing means. Before the record speciﬁc “process” routine is called, the following has already been done:  • Decision to process a record.  • Check that record is not active, i.e. pact must be FALSE.  • Check that the record is not disabled.  The process routine, to
- Top 2，score 0.657891，`epics-documentation-latest-2026-08-18`，物理页 131～131，Chunk `epics-documentation-latest-2026-08-18:6b4e32ccd68059a99d2a32ef441b3fb79c2e4f08bd97cfffb244a29c5aa58aa2`。
  The PHAS field is used to order the processing of records that are scanned at the same time, i.e., records that are scanned periodically at the same interval and priority, or that are scanned on the same event. In this manner records dependent upon other records can be assured of using current data.
- Top 3，score 0.655905，`epics-documentation-latest-2026-08-18`，物理页 155～155，Chunk `epics-documentation-latest-2026-08-18:ee980f4df3fdad8e5da75193b83824a00ea51b19d8e14d162760b450247357ea`。
  • dbPutLink: This routine sets the target field. Then, if the link includes the process passive flag PP it calls dbScanPassive to process the target record. dbPutLink is only called from record processing routines. If dbPutLink finds the record already active because of a dbPutField directed to this record then it arranges for the record to be processed agai

**xfel-rf**：What RF frequency and nominal design energy are used by the European XFEL main linac?

预期：`[{'document_id': 'european-xfel-full-technical-design-report-2007', 'pages': [65]}]`；首个命中排名：`None`。

- Top 1，score 0.636557，`european-xfel-full-technical-design-report-2007`，物理页 35～35，Chunk `european-xfel-full-technical-design-report-2007:f0afaccc44d2c73685ce6fdadc662805de98f9e82d4a8694a481ed001c1194c4`。
  The XFEL based on superconducting accelerator technology will make possible not only a jump in peak brilliance by ten orders of magnitude, but also an increase by five orders of magnitude in average brilliance. The LCLS and European XFEL projects are scheduled to start operation in 2009 and 2013, respectively.
- Top 2，score 0.634058，`european-xfel-full-technical-design-report-2007`，物理页 311～311，Chunk `european-xfel-full-technical-design-report-2007:354525cce7a6dea6a75ea10b7a3875d0d62160944c33bccc526a4c6775850c96`。
  The only constraint is that the system assumes that the surface is flat. It is clear that, depending on the nature of the experiment, some methods of moving targets into position and monitoring their position relative to the focal plane of the XFEL and/or the optical laser systems will need to be developed.
- Top 3，score 0.630203，`european-xfel-full-technical-design-report-2007`，物理页 376～376，Chunk `european-xfel-full-technical-design-report-2007:93c83a1054af4ffaa75b1d195267055f0a618e27f02411c3feda4dee3d742050`。
  during and after the dynamics; b) the monitoring of the electronic structure changes (by XANES) induced by the laser excitation and; c) the use of atomic ions as probe species, which are usually optically silent, but offer the great advantage of being free from internal modes, so only intermolecular changes are observed.

**xfel-normal-energy**：欧洲 XFEL 常规运行时电子束能量是多少，与最高设计能量有何区别？

预期：`[{'document_id': 'european-xfel-full-technical-design-report-2007', 'pages': [21, 57]}]`；首个命中排名：`None`。

- Top 1，score 0.625739，`shine-accelerator-preliminary-design-report-2017`，物理页 188～188，Chunk `shine-accelerator-preliminary-design-report-2017:c101948c7012bdcd8360b46bef36dd52a4f11e53bf6739b94e2129c206d2ba2c`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  184  图3.3.4.1-35 FEL 辐射性能随着波荡器LATTICE 结构的变化。(a)12.4keV；(b)25keV。  4.1.5.2 电子束团参数灵敏性分析  FEL 输出性能完全取决于电子束团品质，图3.3.4.1-36 扫描了FEL-I 中  12.4keV 辐射的饱和功率以及增益长度随着电子束团参数的变化情况。可以看出，  电子束发射度和峰值流强在一定程度上可以相互补偿，这也为直线加速器的性能  指标带来一定的灵活性。  图3.3.4.1-36 FEL-I 辐射12.4keV 性能随着电子束团参数的变化  除此之外，电子束团能从目前1.5kA 提升到3.0kA，抑或从100pC 增加到  200pC，将会对SCLF 输出性能提升有很大的
- Top 2，score 0.608906，`shine-accelerator-preliminary-design-report-2017`，物理页 193～193，Chunk `shine-accelerator-preliminary-design-report-2017:2f1cd17fb49e51e90606cd5118bc0f3b168e1a8e554156c25b61c1e2f95e21b9`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  189  日本理化所的SACLA 装置束流能量为8GeV，束团重复频率为120Hz。早  期采用水平方向±0.53∘的水平方向冲击磁铁（kicker magnet）结合± 2.47∘的水  平偏转直流切割磁铁（DC septum magnet），实现± 3∘的水平偏转，当kicker 系统  关闭时，束流无偏转通往BL3 波荡器线，+3∘时，束流经过包含kicker 和septum  的dog-leg 偏转结构（即偏转-反向偏转），通往BL2 线，−3∘时则用作SPring8  的注入。然而当该装置运行在较高峰值流强（10kA）模式下，由于偏转时束流  受到相干同步辐射（CSR）效应的影响，束流发射度出现了大幅度增长，无法被  BL2 线使用。目前该装置已
- Top 3，score 0.605246，`shine-accelerator-preliminary-design-report-2017`，物理页 61～61，Chunk `shine-accelerator-preliminary-design-report-2017:db6d56c00b0567fd5c1028d1e63addf596b28d001164d5dc9aa9fc4b98cf49f4`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  57  一个加速段L1 的下游，电子束的能量为270MeV。电子束经过磁压缩以后流强  由12A 压缩至85A，压缩倍数约为7。第二个磁压缩器位于主加速器第二个加速  段L2 的下游，电子束的能量为2.1GeV。纵向参数优化采用一维束流动力学模拟  软件Litrack 完成。电子束的纵向相空间和流强分布演化过程如图3.3.3.1-2 所示。  图3.3.3.1-2 电子束的纵向相空间和流强分布  (a) 注入器出口；(b) BC1 出口；(c) BC2 出口；(d) L3 出口  两级磁压缩位置的选择基于束流稳定性的优化及束团集体效应对束流亮度  和品质的影响。第一级磁压缩BC1 通常距离注入器比较近，电子束能量比较低，  束团也比较长，需要尽早压缩束团长

### dense cross-language cases

**xfel-normal-energy**：欧洲 XFEL 常规运行时电子束能量是多少，与最高设计能量有何区别？

预期：`[{'document_id': 'european-xfel-full-technical-design-report-2007', 'pages': [21, 57]}]`；首个命中排名：`None`。

- Top 1，score 0.625739，`shine-accelerator-preliminary-design-report-2017`，物理页 188～188，Chunk `shine-accelerator-preliminary-design-report-2017:c101948c7012bdcd8360b46bef36dd52a4f11e53bf6739b94e2129c206d2ba2c`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  184  图3.3.4.1-35 FEL 辐射性能随着波荡器LATTICE 结构的变化。(a)12.4keV；(b)25keV。  4.1.5.2 电子束团参数灵敏性分析  FEL 输出性能完全取决于电子束团品质，图3.3.4.1-36 扫描了FEL-I 中  12.4keV 辐射的饱和功率以及增益长度随着电子束团参数的变化情况。可以看出，  电子束发射度和峰值流强在一定程度上可以相互补偿，这也为直线加速器的性能  指标带来一定的灵活性。  图3.3.4.1-36 FEL-I 辐射12.4keV 性能随着电子束团参数的变化  除此之外，电子束团能从目前1.5kA 提升到3.0kA，抑或从100pC 增加到  200pC，将会对SCLF 输出性能提升有很大的
- Top 2，score 0.608906，`shine-accelerator-preliminary-design-report-2017`，物理页 193～193，Chunk `shine-accelerator-preliminary-design-report-2017:2f1cd17fb49e51e90606cd5118bc0f3b168e1a8e554156c25b61c1e2f95e21b9`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  189  日本理化所的SACLA 装置束流能量为8GeV，束团重复频率为120Hz。早  期采用水平方向±0.53∘的水平方向冲击磁铁（kicker magnet）结合± 2.47∘的水  平偏转直流切割磁铁（DC septum magnet），实现± 3∘的水平偏转，当kicker 系统  关闭时，束流无偏转通往BL3 波荡器线，+3∘时，束流经过包含kicker 和septum  的dog-leg 偏转结构（即偏转-反向偏转），通往BL2 线，−3∘时则用作SPring8  的注入。然而当该装置运行在较高峰值流强（10kA）模式下，由于偏转时束流  受到相干同步辐射（CSR）效应的影响，束流发射度出现了大幅度增长，无法被  BL2 线使用。目前该装置已
- Top 3，score 0.605246，`shine-accelerator-preliminary-design-report-2017`，物理页 61～61，Chunk `shine-accelerator-preliminary-design-report-2017:db6d56c00b0567fd5c1028d1e63addf596b28d001164d5dc9aa9fc4b98cf49f4`。
  硬X 射线自由电子激光装置初步设计报告——加速器分册  57  一个加速段L1 的下游，电子束的能量为270MeV。电子束经过磁压缩以后流强  由12A 压缩至85A，压缩倍数约为7。第二个磁压缩器位于主加速器第二个加速  段L2 的下游，电子束的能量为2.1GeV。纵向参数优化采用一维束流动力学模拟  软件Litrack 完成。电子束的纵向相空间和流强分布演化过程如图3.3.3.1-2 所示。  图3.3.3.1-2 电子束的纵向相空间和流强分布  (a) 注入器出口；(b) BC1 出口；(c) BC2 出口；(d) L3 出口  两级磁压缩位置的选择基于束流稳定性的优化及束团集体效应对束流亮度  和品质的影响。第一级磁压缩BC1 通常距离注入器比较近，电子束能量比较低，  束团也比较长，需要尽早压缩束团长

**shine-ioc-startup**：SHINE 中 IOC 启动后会向管理系统提交哪些信息？

预期：`[{'document_id': 'shine-epics-ioc-pv-information-management-pcapac2022', 'pages': [2]}, {'document_id': 'shine-epics-ioc-pv-information-management-pcapac2022', 'pages': [3]}]`；首个命中排名：`None`。

- Top 1，score 0.666657，`shine-accelerator-control-system-design-presentation`，物理页 28～28，Chunk `shine-accelerator-control-system-design-presentation:b0660b85a16b9319003972afc581f5ece2cdca5398313113390916e148417fbb`。
  通道信息管理  \uf06e 完成通道信息管理软件核心模块开发  \uf06e 将控制系统中的IOC信息、Record信息纳入数据库管理  \uf06e 所有IOC的静态信息（地址、端口、...），状态信息（连接、...）  \uf06e 所有Record的名称、类型、域定义情况，以及访问权限、合法性等  软件著作权登记 数据库设计
- Top 2，score 0.621306，`shine-accelerator-control-system-design-presentation`，物理页 10～10，Chunk `shine-accelerator-control-system-design-presentation:2509d214dbcf2c7954dba968bf9cae8b3c33ece03fc3d2639f9f12a1098489e6`。
  \uf06eCSS是否是最合适的用户界面？  \uf06e全局网络环境下，一个IOC对应多少台设备最合理？  \uf06e虚拟化可以整合硬件资源，提高控制系统可靠性和稳定性；  IOC虚拟化占比多少最合适？  \uf06e控制系统存储容量多少最合理？  \uf06e是否需要异地容灾备份？  \uf06e控制系统是否需要持续集成 (Continue Integrate)？
- Top 3，score 0.583227，`shine-accelerator-control-system-design-presentation`，物理页 26～26，Chunk `shine-accelerator-control-system-design-presentation:8b7cf853df55bb7dad3b6f407e4c06639206fc5863e2cc1e91efd8ca0ba7eab7`。
  运行与开发环境  \uf06e 为整个控制系统提供运行环境  \uf06e 由服务器集群、存储设备、网络设备等组成  \uf06e 采用虚拟服务器和实体服务器相结合的方式  \uf06e 提供各类基础服务，如账号管理、文件管理、时间同步等  \uf071\uf020软件开发管理  \uf073\uf020开发过程记录与控制  \uf073\uf020开发流程优化与简化  \uf071\uf020通道信息管理  \uf073\uf020通道信息采集与存储  \uf073\uf020通道状态监控与管理  \uf071\uf020通道权限管理  \uf073\uf020通道访问权限管理  \uf073\uf020通道访问记录存储与显示  \uf071\uf020网络管理与监测  \uf073\uf020网络地址分配与

**interlock-latency**：SHINE 快联锁对单节点和节点间的响应时间分别有什么要求？

预期：`[{'document_id': 'shine-accelerator-fast-interlock-2024', 'pages': [2]}]`；首个命中排名：`None`。

- Top 1，score 0.736094，`shine-accelerator-fast-interlock-2024`，物理页 7～7，Chunk `shine-accelerator-fast-interlock-2024:ee60572dc682fe0e48200b35c16f73ecfee54cfa2b8d3cfb204cb5337a7e155c`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量计数不低于10 000次，测试结 果显示单节点响应时间平均值为328.81 ns，优于单 节点响应时间10 µs的设计指
- Top 2，score 0.726798，`shine-accelerator-fast-interlock-2024`，物理页 8～8，Chunk `shine-accelerator-fast-interlock-2024:5555f0f1baab72d4c0a95b900177ed146ddcf661b864c6b7fdb3861009f5537b`。
  核 技 术 2024, 47: 120203  单节点平均响应时间为328.81 ns，节点间经800 m 电缆连接的系统平均响应时间为5.33 µs，均优于快 联锁系统的设计指标。系统运行模式的设置和传输 功能正常，各站点在不同模式下相应联锁逻辑切换 等功能也已通过测试并投入正常运行。SHINE加速 器快联锁系统功能完善，运行稳定正常，满足系统的 设计要求。  作者贡献声明 于春蕾负责联锁系统的整体设计、 需求对接、运行模式设计和实现、快联锁系统的设计 与开发，并负责数据的收集和整理、文章的起草和最 终版本的修订；陈广花负责研究的提出及设计，样机 的搭建和测试；丁建国负责系统设计的指导和监督、 系统机柜集成的硬件设计；李明负责系统的工艺流 程和实施工作，慢联锁系统的软件开发和调试；肖庆 雯负责基于EPICS 
- Top 3，score 0.687768，`shine-accelerator-control-system-design-presentation`，物理页 21～21，Chunk `shine-accelerator-control-system-design-presentation:25ed01ed469d6dea8a224590fbade9da0e70ca5cbebe2acac44d09ce2d74e577`。
  联锁系统  \uf06e 快联锁 + 慢联锁；主站 + 从站，分层设计  \uf0b2快联锁关键信号响应时间：  站内≤10us，站间≤100us  \uf0b2慢联锁关键信号响应时间：  站内≤20ms，站间≤100ms

### dense no-answer cases

**no-answer-finance**：What was NVIDIA quarterly revenue in fiscal 2026 Q4?

预期：`[]`；首个命中排名：`None`。

- Top 1，score 0.532777，`european-xfel-full-technical-design-report-2007`，物理页 60～60，Chunk `european-xfel-full-technical-design-report-2007:e51493930294c1959436fd1eecddb3b75cbffd03acfd1859867b78ce03913864`。
  the electrons up to 120 MeV; and a series of focusing and diagnostic equipment to ensure the necessary beam quality (low emittance, low energy spread, etc.) which is extremely important for the whole XFEL operation. The total length of the injector is about 66 m, after which the electrons are delivered into the linear accelerator.  3.3 Linear accelerator
- Top 2，score 0.525171，`european-xfel-full-technical-design-report-2007`，物理页 601～601，Chunk `european-xfel-full-technical-design-report-2007:46acf453eb82dec830ffabcf4465fd6bf58e8bc4f6371fec02fd8555644084fe`。
  [7-9] S. Claudet, Recent Progress in Power Refrigeration Below 2 K for superconducting Accelerators, Invited paper at Particle Accelerator Conference, Knoxville,USA, 2005.  [7-10] H. Quack, A. Kutschbach, Über die Möglichkeit des Umbaus der HERA-Kälteanlage für TESLA, internal report DESY/TU Dresden, in German, Dresden/Hamburg, 2002.
- Top 3，score 0.524322，`european-xfel-full-technical-design-report-2007`，物理页 183～183，Chunk `european-xfel-full-technical-design-report-2007:f60b6274eec4304ae446f5e9ea1da121236e9f092cdc215b78d1622a18ba3e92`。
  [4-50] V. Katalev, S. Choroba, RF Power Distributing Waveguide System for TESLA, Proceedings of the Russian Particle Accelerator Conference, Rupac 2002, Obninsk, Russia, October 1-4, (2002,) 79.  [4-51] V. Katalev, S. Choroba, Tuning of External Q and Phase for the Cavities of a Superconducting Linear Accelerator, Proc. XXII International Linear Accelerator 

**no-answer-recipe**：如何制作四川麻婆豆腐？请给出食材和烹饪步骤。

预期：`[]`；首个命中排名：`None`。

- Top 1，score 0.410210，`epics-documentation-latest-2026-08-18`，物理页 126～126，Chunk `epics-documentation-latest-2026-08-18:1a8e4b80a4d71313972b98e0734c6c550d5f0ace3b532ffb9984151b72291e65`。
  menu(menuScan) {  choice(menuScanPassive,"Passive") choice(menuScanEvent,"Event") choice(menuScanI_O_Intr,"I/O Intr") choice(menuScan10_second,"10 second") choice(menuScan5_second,"5 second") choice(menuScan2_second,"2 second") choice(menuScan1_second,"1 second") choice(menuScan_5_second,".5 second") choice(menuScan_2_second,".2 second") choice(menuScan_1_se
- Top 2，score 0.379097，`epics-application-developers-guide-r3-16-2`，物理页 215～215，Chunk `epics-application-developers-guide-r3-16-2:8394094cac94e831562c1e58bb2bcf8812fe3405da6d81e34d7c9ed12f7af56d`。
  These routines should only be used for DCT_MENU and DCT_MENUFORM ﬁelds. Thus they should only be called if dbFindField, dbFirstField, or dbNextField has returned success and the ﬁeld type is DCT_MENU or DCT_MENUFORM.  14.10.1 Get Number of Menu Choices  int dbGetNMenuChoices(DBENTRY *pdbentry);  This routine returns the number of menu choices for menu.  14.1
- Top 3，score 0.367365，`epics-application-developers-guide-r3-16-2`，物理页 250～250，Chunk `epics-application-developers-guide-r3-16-2:2d1fe470431b101eb994f8a05ed590b58bd845d53c8b169edc32954836276157`。
  17.2.4 PRIO - Scheduling Priority  This ﬁeld can be used by any software component that needs to specify a scheduling priority. The Event and I/O event scan types use this ﬁeld.  17.3 Scan Related Software Components  17.3.1 menuScan.dbd  This ﬁle holds the deﬁnition of the menu used by the ﬁeld SCAN. The default deﬁnition is:  menu(menuScan) {  choice(menuS

**no-answer-token**：zxqv9999unlistedcalibrationartifact

预期：`[]`；首个命中排名：`None`。

- Top 1，score 0.465289，`european-xfel-full-technical-design-report-2007`，物理页 534～534，Chunk `european-xfel-full-technical-design-report-2007:45d4e488797b514245be8baab6ee75910211ab5b7bbb154ad8f9abcd2544d0b6`。
  During the construction phase, the shaft XSE serves as target shaft for the drilling of the tunnel XTL and as emergency exit. During the installation and operation phases, the shaft is used to gain access to the injector tunnel XTIN, the accelerator tunnel XTL and as emergency exit. In addition it is used as an installation shaft for all supply media for the
- Top 2，score 0.447349，`european-xfel-full-technical-design-report-2007`，物理页 448～448，Chunk `european-xfel-full-technical-design-report-2007:b6677cb2283a7672710861c253ffebcf13342e104ea161895651859068c6307e`。
  Detector signals were computed for a test sample of a CPMV, with labelling of nanoclusters of Gold [6-381]. This may be an early test sample for LCLS and XFEL experiments. The atomic coordinates of the virus capsid (1NY7) were obtained from the EMBL-EBI Macromolecular Structure Database [6-382]. The capsid structure is hollow (since the DNA structure inside 
- Top 3，score 0.445491，`european-xfel-full-technical-design-report-2007`，物理页 391～391，Chunk `european-xfel-full-technical-design-report-2007:7ed488bcae573aa1adbd5048fc2e57aad9611c2b17de60c6e543e1420c62932d`。
  Ultrafast electron diffraction (UED), on the other hand, can probe chemical reactions in the gas phase with 1 ps resolution, but the strong scattering of electrons makes is difficult to use UED in condensed matter, which is an important drawback since most biological and industrial processes take place in a condensed environment.  The European XFEL Facility 

## 索引与耗时

索引：`{'embedding_model': 'BAAI/bge-small-zh-v1.5', 'dimension': 512, 'query_template': '为这个句子生成表示以用于检索相关文章：{query}', 'local_files_only': True, 'collection': 'knowledge_stage2', 'qdrant_path': 'tmp/stage-two-qdrant', 'chunk_count': 4547, 'unique_chunk_count': 4547, 'point_count': 4547, 'duplicate_count': 0, 'embedded_chunk_count': 4547, 'batch_size': 32, 'device': 'cpu'}`。

阶段耗时（秒）：`{'parse_clean_chunk': 4.798870644997805, 'corpus_audit': 0.74551779399917, 'bm25_build': 1.5526524749984674, 'bm25_evaluation': 1.2146897499987972, 'model_load': 3.295414009000524, 'embedding_seconds': 487.30035146299997, 'qdrant_indexing_seconds': 9.521505071024876, 'dense_evaluation': 0.4730243750018417, 'evaluation_total': 1.6877141250006389}`。

模型只从本地加载。每轮索引中每个最终 Chunk 只进入一次 embedding batch。重复执行会重新计算向量，但稳定 ID 与文档级清理避免重复 points。
本报告是 24 条人工可核查问题的探索性基线，覆盖面有限；不代表经过独立测试集验证的泛化指标。全量 case 和 Top-5 原文见同名 JSON。

## 本轮 review 结论

Stage 2 的执行与可复核交付已经完成：13 份 PDF 全部处理，4547 个唯一 Chunk 对应 4547 个持久化 Qdrant point，四份报告已生成。达到本阶段 review 条件，但现有数据质量和检索质量不应被称为生产可用。

BM25 在 21 条可回答问题中 Top-5 命中 17 条，Dense 命中 12 条。按语言分组，BM25 英文为 12/13、中文为 5/8；Dense 英文为 9/13、中文为 3/8。问题不同、样本小且分组不等大，该分组不能证明语言导致性能差异。

三条代表性失败：

- `xfel-normal-energy`：BM25、Dense 首条均进入 SHINE 初步设计报告，未命中已标注的 European XFEL 文档页，存在设施混淆。
- `shine-ioc-startup`：两者 Top-5 都未命中已标注的 IOC 启动采集页。首条为通道信息管理幻灯片第 28 页，主题部分相关，但不等同于已经返回所需启动信息证据。
- `shine-main-linac`：Dense 首条为幻灯片第 34 页的结束语“谢 谢”，score 为 0.670013；Top-5 无已标注答案页。该结果不能回答工作模式和最终能量问题。标题前缀与极短正文的作用尚未做消融，不能把相关观察直接当作因果结论。

无答案三题中，BM25 两题返回邻近结果，一题为空；Dense 三题均返回邻近结果。Dense 可回答 Top-1 分数为 0.502994～0.778265，无答案为 0.410210～0.532777，范围重叠。当前数据不支持凭这三条负例确定生产阈值。

Stage 3 最应优先处理：

1. 已定位的提取损坏与清洗残留，特别是 SHINE 初步设计报告的替换字符、公式区域和重复页眉页码。
2. Dense 的证据区分能力与极短 Chunk 的索引输入，结合跨文档、跨语言失败做有控制的验证。
3. 更完整、独立的页级 relevance 判断与无答案验证，避免将未穷尽 ground truth 或三条负例当作质量保证。

本轮没有按结果修改 ground truth，没有删除失败问题，没有融合分数，也未进入 Stage 3。

## 执行验证

`pytest -q`：118 passed in 2.15s。`ruff check .`：All checks passed!，退出码 0。`git diff --check`：无输出，退出码 0。Corpus inventory：退出码 0，13 个注册 PDF、5 个 unsupported/unmanaged 文件。

重新打开持久化 Qdrant 后，已逐 point 校验全部 Chunk 模型、来源与物理页范围、稳定 UUID 映射和各文档数量。原始 PDF、Agent 文件、冻结查询集和核心检索代码哈希核验通过。报告展示层随后修正了控制字符的转义，测量时的代码哈希与展示层修正后的哈希分别保留。未 commit，未 push。


报告中的异常摘录是解析字符串的证据，控制字符与私用字符以码点转义显示；没有对公式进行转写或语义修复。此展示修正不改变 Chunk、向量或任何评测结果。
