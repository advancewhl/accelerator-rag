# RAG Stage 2.5 Evidence Retrieval Baseline

Hit@K = fraction of answerable queries with at least one accepted evidence target in Top-K

all 模式还要求覆盖全部证据组。组内 OR；all 模式组间 AND，any 模式组间 OR。MRR@5 使用 first_complete_rank。
证据必须同时匹配文档、物理页和规范化后的 Chunk 文本。无答案问题不进入指标分母。
所有切片均为 diagnostic only，样本数不足以支持泛化结论。zh-en 文档支持中英文；存在跨语言目标时保守归入 cross_language。

## bm25

### overall

| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| overall | 21 | 0.3810 | 0.6667 | 0.7143 | 0.5198 |

### by_query_language

| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| en | 13 | 0.5385 | 0.7692 | 0.7692 | 0.6410 |
| zh | 8 | 0.1250 | 0.5000 | 0.6250 | 0.3229 |

### by_language_relation

| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| cross_language | 3 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| same_language | 18 | 0.4444 | 0.7778 | 0.8333 | 0.6065 |

### by_category

| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| accelerator_design | 4 | 0.2500 | 0.2500 | 0.5000 | 0.3125 |
| beam_diagnostics | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| beam_transport | 2 | 0.5000 | 1.0000 | 1.0000 | 0.7500 |
| control_architecture | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| cryogenics | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000 |
| epics | 2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| interlock | 3 | 0.0000 | 1.0000 | 1.0000 | 0.4444 |
| ioc | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| photon_diagnostics | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| pv | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333 |
| timing | 2 | 0.5000 | 1.0000 | 1.0000 | 0.7500 |

### by_expected_document

| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| epics-application-developers-guide-r3-16-2 | 2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| epics-documentation-latest-2026-08-18 | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333 |
| european-xfel-full-technical-design-report-2007 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| european-xfel-standard-e-beam-diagnostics-linac2010 | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| european-xfel-undulator-commissioning-spectrometer-cdr-2011 | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| european-xfel-x-ray-optics-beam-transport-tdr-2012 | 2 | 0.5000 | 1.0000 | 1.0000 | 0.7500 |
| shine-accelerator-control-system-design-presentation | 1 | 0.0000 | 1.0000 | 1.0000 | 0.5000 |
| shine-accelerator-fast-interlock-2024 | 2 | 0.0000 | 1.0000 | 1.0000 | 0.4167 |
| shine-accelerator-preliminary-design-report-2017 | 2 | 0.5000 | 0.5000 | 1.0000 | 0.6250 |
| shine-control-system-status-icalepcs2019 | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shine-cryogenic-control-system-2021 | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000 |
| shine-epics-ioc-pv-information-management-pcapac2022 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shine-white-rabbit-beam-synchronous-timing-ipac2022 | 2 | 0.5000 | 1.0000 | 1.0000 | 0.7500 |

### Top-1 分数分布

- answerable（21 条）：`{'count': 21, 'min': 20.107346717942878, 'max': 66.59611601469898, 'mean': 38.441512003440735, 'p10': 21.76206120223665, 'p25': 24.629414516484164, 'median': 37.997432979151355, 'p75': 50.36008143295979, 'p90': 60.3129365109046, 'p95': 62.967097399576296}`。
- obvious（3 条）：`{'count': 2, 'min': 12.057979385897658, 'max': 13.350518410051798, 'mean': 12.704248897974729, 'p10': 12.187233288313072, 'p25': 12.381114141936193, 'median': 12.704248897974729, 'p75': 13.027383654013263, 'p90': 13.221264507636384, 'p95': 13.285891458844091}`。
- hard_domain（8 条）：`{'count': 8, 'min': 14.751719316964397, 'max': 36.52440617225013, 'mean': 25.81813476917505, 'p10': 18.393589241529423, 'p25': 23.092861435973102, 'median': 26.40279687053927, 'p75': 28.246757611450477, 'p90': 32.700308608104606, 'p95': 34.612357390177365}`。

### 逐条判断

**epics-pp**：When does an EPICS PP input link process its target record?

first_complete_rank：`1`；groups_satisfied_at_k：`{'1': 2, '3': 2, '5': 2}`。

- Top 1，score 31.871484，`epics-application-developers-guide-r3-16-2`，物理页 88～88，Chunk `epics-application-developers-guide-r3-16-2:95f9f00fa8a6ec6e4e94ed21244521e43ef5d2486f3f56bc3b28a49e4eeaf20e`。
  For input and output links, two additional attributes can be speciﬁed by the application developer: process passive, and maximize severity.  5.3.1 Process Passive  The Process Passive attribute takes the value NPP (Non-Process Passive) or PP (Process Passive). It determines if the linked record shou
- Top 2，score 31.389216，`epics-documentation-latest-2026-08-18`，物理页 152～152，Chunk `epics-documentation-latest-2026-08-18:79faa9ede0173c79b19e56fdb101c77b2a07093c59baf3a2a2a134105b69a7cf`。
  Links are defined in file dbLink.h.  ò Note  This chapter discusses mainly database links.  1.11.3 Link Operations  The basic operations which can be performed on a link (excluding hardware links) are as follows.  • dbGetLink(): The value of the field referenced by the input link retrieved.  • dbPut
- Top 3，score 28.611495，`epics-application-developers-guide-r3-16-2`，物理页 91～91，Chunk `epics-application-developers-guide-r3-16-2:4f6ceb4aea28986ff369b87ba333a2bd7a2a7c6ddda2950c81cc4b4c64b62888`。
  • dbPutField: This routine sets the target ﬁeld value and then, if the ﬁeld was marked pp(TRUE) it calls dbScanPassive. Each ﬁeld of each record type has an attribute pp declared as either TRUE or FALSE in the record deﬁnition ﬁle. The attribute is a global property which is set by the record type. 

**epics-reconnect**：What happens to Channel Access client connections when an IOC server crashes and restarts?

first_complete_rank：`1`；groups_satisfied_at_k：`{'1': 1, '3': 1, '5': 1}`。

- Top 1，score 46.038272，`epics-application-developers-guide-r3-16-2`，物理页 31～31，Chunk `epics-application-developers-guide-r3-16-2:2360d24c575c8539d66b24a381d26d9705e989fcdf4d8459dd361ea51b8a8203`。
  Once the process variables have been located, the Channel Access client issues connection requests for each IOC containing process variables the client uses. The connection request server, in the IOC, accepts the request and establishes a connection to the client. Each connection is managed by two s
- Top 2，score 45.772472，`epics-documentation-latest-2026-08-18`，物理页 63～63，Chunk `epics-documentation-latest-2026-08-18:5ed27b152e619d65d23d7dde439604437d01c5a32afc94d6955004054543c138`。
  Once the process variables have been located, the Channel Access client issues connection requests for each IOC containing process variables the client uses. The connection request server, in the IOC, accepts the request and establishes a connection to the client. Each connection is managed by two s
- Top 3，score 28.133796，`epics-application-developers-guide-r3-16-2`，物理页 31～31，Chunk `epics-application-developers-guide-r3-16-2:9c6ead1f3c88ceed8f0b480873970274eb8208649db54fea0da0b97d973454a4`。
  It should be noted that Channel Access does not provide access to database records as records. This is a deliberate design decision. This allows new record types to be added without impacting any software that accesses the database via Channel Access, and it allows a Channel Access client to communi

**epics-cli**：Which EPICS command-line tools read, write and continuously monitor the temperature:water PV?

first_complete_rank：`3`；groups_satisfied_at_k：`{'1': 0, '3': 3, '5': 3}`。

- Top 1，score 22.294108，`epics-documentation-latest-2026-08-18`，物理页 381～381，Chunk `epics-documentation-latest-2026-08-18:db5e43b21efb1209b9404be577f808718a6252d4de541d8613c50d78ec9050f6`。
  1.37.1 Find Host and TCP port  The cainfo command will tell you which host is serving a particular PV, and which TCP port number on that host is used.  $ cainfo LN-TS{EVR:1A-SFP}Pwr:RX-I LN-TS{EVR:1A-SFP}Pwr:RX-I State: connected Host: 10.0.152.111:5064 Access: read, write  1.37. How to find which I
- Top 2，score 20.597085，`epics-documentation-latest-2026-08-18`，物理页 9～9，Chunk `epics-documentation-latest-2026-08-18:e54c3b94095ce47b2fe7086603836e77e824e58080ed40eb7c8a11e8b9340e99`。
  Ok, that is not very impressive, but at least you know that EPICS is installed correctly. So now let us try something more complex, which will hopefully suggest how EPICS works.  In whatever directory you like, prepare a file test.db that reads like  record(ai, "temperature:water") {  field(DESC, "W
- Top 3，score 17.983374，`epics-documentation-latest-2026-08-18`，物理页 9～9，Chunk `epics-documentation-latest-2026-08-18:a7cea79623100df414ec81d17f2bc3815c6ee8056a5d45f5f9853372edfe1cf6`。
  your prompt> caget temperature:water temperature:water 0 your prompt> caget temperature:water.DESC temperature:water.DESC Water temperature in the fish tank your prompt> caput temperature:water 21 Old : temperature:water 0 New : temperature:water 21 your prompt> caput temperature:water 24 Old : temp

**xfel-rf**：What RF frequency and nominal design energy are used by the European XFEL main linac?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 1, '5': 1}`。

- Top 1，score 26.801183，`european-xfel-full-technical-design-report-2007`，物理页 57～57，Chunk `european-xfel-full-technical-design-report-2007:66fe8f7d369d58380b218e11f28e1a1c7b82b7b4dc63112857884404967fed2a`。
  The basic functions of the main components are schematically described in the following: In the injector, electron bunches are extracted from a solid cathode by a laser beam, focused and accelerated by an electron radio frequency (RF) gun and directed towards the linac with an exit energy of 120 MeV
- Top 2，score 25.589336，`european-xfel-full-technical-design-report-2007`，物理页 99～99，Chunk `european-xfel-full-technical-design-report-2007:92692bbfebec7421bba5bcd1d5f3504006cc664c70de9a8aa34e23c37181574b`。
  At 20 GeV, the linac for the XFEL operates at a gradient of 23.6 MV/m with a repetition rate of 10 Hz. Since the particle beam current is 5 mA, up to 122 kW are required per cavity. The maximum beam pulse duration is 600 µs and the cavity filling time 780 µs.  Thirty-two cavities (four times eight c
- Top 3，score 25.081529，`european-xfel-full-technical-design-report-2007`，物理页 72～72，Chunk `european-xfel-full-technical-design-report-2007:2fbc0ca82267a011a7652fa7589cef064c5045391094d6bbf2b18789963f7de4`。
  4.2 Linac  4.2.1 Cavities  4.2.1.1 Introduction  The XFEL accelerating cavity is a nine-cell standing wave structure of about 1 m length whose fundamental TM mode has a frequency of 1,300 MHz. It is identical to the so-called TESLA cavity [4-1], made from solid Niobium, and is bath-cooled by superfl

**xfel-normal-energy**：欧洲 XFEL 常规运行时电子束能量是多少，与最高设计能量有何区别？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 24.629415，`shine-accelerator-preliminary-design-report-2017`，物理页 279～279，Chunk `shine-accelerator-preliminary-design-report-2017:2112b858d457f30a8b8aca50fea69b417899100dd17733b915998c19ec8bf985`。
  6. 加速器公共子系统  6.1 束流诊断  6.1.1 概述  电子束流诊断系统作为自由电子激光装置调束、运行时的主要工具，应具备  如下基本功能：（1）在装置调束期间，实现对电子束流各项参数的实时测量，测  量结果通过控制网发布提供给调束、运行人员，各类诊断设备的测量动态范围需  要满足初始调束的需求；（2）在装置进行验收时，对电子束流关键参数进行精确  测量，作为主要验收手段；（3）在装置投入运行之后，实现对电子束流主要运行  参数的实时在线监测，为运行人员监测及优化运行状态提供手段，要求系统具有  高可靠性、重复性及稳定性；（4）为装置中的束流反馈控制环路提供束流数据。  本装置中所需
- Top 2，score 23.620534，`shine-accelerator-control-system-design-presentation`，物理页 10～10，Chunk `shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9`。
  \uf06eCSS是否是最合适的用户界面？  \uf06e全局网络环境下，一个IOC对应多少台设备最合理？  \uf06e虚拟化可以整合硬件资源，提高控制系统可靠性和稳定性；  IOC虚拟化占比多少最合适？  \uf06e控制系统存储容量多少最合理？  \uf06e是否需要异地容灾备份？  \uf06e控制系统是否需要持续集成 (Continue Integrate)？
- Top 3，score 23.063082，`shine-accelerator-preliminary-design-report-2017`，物理页 368～368，Chunk `shine-accelerator-preliminary-design-report-2017:ca4c1108b2cf911a829817a5fc02f9c51c55dbde64d1104d50debd51ed8643a1`。
  的时钟脉冲信号和硬件时标信号。机器联锁也称机器保护，在系统与设备之间建  立联锁保护逻辑，故障发生时对加速器重要设备进行保护。在上述基础之上，提  供各种附加的扩展能力，例如基于Web 的远程访问能力，各类分析程序接口等，  以满足不同的需求。  系统结构如图3.3.6.2-1 所示。  图3.3.6.2-1 控制系统结构示意图  6.2.1.3 设计指标  参照美国LCLS-II 和欧洲European XFEL 的相关设计，SCLF 控制系统主要  设计指标如下：  （1）最大存储容量达到1P；  （2）控制网络带宽达到10Gb/s；  （3）常规图像采集系统帧率达到10fps；  （4）

**undulator-tuning**：How does a K-monochromator select radiation for tuning undulator segments?

first_complete_rank：`1`；groups_satisfied_at_k：`{'1': 1, '3': 1, '5': 1}`。

- Top 1，score 26.300764，`european-xfel-undulator-commissioning-spectrometer-cdr-2011`，物理页 3～3，Chunk `european-xfel-undulator-commissioning-spectrometer-cdr-2011:3d9cff81b154e116e2b45c608f54d696a9594d653cd3ae8b86626dff067a206a`。
  The commissioning spectrometer, also known as K-monochromator, is mainly used with spontaneous radiation and selects a narrow bandwidth of the x-ray photon beam in order to tune the undulator segments. This process is called photon beam-based alignment and will minimize the difference in the undulat
- Top 2，score 19.973533，`european-xfel-full-technical-design-report-2007`，物理页 5～5，Chunk `european-xfel-full-technical-design-report-2007:7e00f5caf5678d12a8071f1c6b0b3c15c0126e48b2e79fa6f86a1dada9ea0e6b`。
  ..............................................................189 5.4.1 Choice of undulator parameters ..................................................189 5.4.2 Basic tolerance requirements ......................................................193 5.4.3 Undulator segments .........................
- Top 3，score 19.890630，`european-xfel-full-technical-design-report-2007`，物理页 225～225，Chunk `european-xfel-full-technical-design-report-2007:1990d84c77a9bed1ef9a68972f0d3bac82c56a3be6fcf90bd18e4fc7eba71891`。
  5.5.3 Phase tuning  Changing the undulator gap will result in a change of the phase relation between two adjacent segments. In order to compensate for the wavelength dependent phasing condition, a phase shifter is installed in the intersection module (Section 5.4.4). It consists of a three-magnet ch

**xfel-mirror-angle**：Why was the grazing-incidence angle range of the SASE3 offset mirrors reduced?

first_complete_rank：`1`；groups_satisfied_at_k：`{'1': 1, '3': 1, '5': 1}`。

- Top 1，score 37.997433，`european-xfel-x-ray-optics-beam-transport-tdr-2012`，物理页 8～8，Chunk `european-xfel-x-ray-optics-beam-transport-tdr-2012:9a66a3cf2e8db6a52918f1de36e836b9584c3f4f4980413b63b29ac4f7a419da`。
  December 2012 XFEL.EU TR-2012-006 8 of 164 TDR: X-Ray Optics and Beam Transport  4 As discussed in the introduction, the concept of the soft X-ray  monochromator was modified and will be presented later in a dedicated  section.  5 The range of grazing-incidence angles at the SASE3 offset mirrors was
- Top 2，score 23.577034，`european-xfel-x-ray-optics-beam-transport-tdr-2012`，物理页 38～38，Chunk `european-xfel-x-ray-optics-beam-transport-tdr-2012:8b92c5c111da0777116588bb4ea66400784f2413aa8ff91d919be4daab568ef9`。
  0.6 mrad (400 mm distance) is smaller than the operation range of the mirrors  (2.5 mrad for SASE1 and SASE2, and 14 mrad for SASE3), the  interferometer heads have to be turned accordingly. For the distribution  mirrors, the angular range in pitch is sufficient; however, in order to steer the  beam
- Top 3，score 23.435906，`european-xfel-x-ray-optics-beam-transport-tdr-2012`，物理页 31～31，Chunk `european-xfel-x-ray-optics-beam-transport-tdr-2012:3d56abe02b789e655f853f5632ac536179dca1929309838a8ea57432efdb8dc0`。
  required to guide the beam to all experiments of the SASE1, SASE2, and  SASE3 beamlines. The first mirror of each beamline is exposed to high-energy spontaneous radiation and will absorb up to 10 W (100 W for SASE3)  of integrated beam power (see CDR2011). The static deformation can reach  up to 200

**xfel-soft-mono**：Why did the soft X-ray monochromator change to a vertical in-line geometry?

first_complete_rank：`2`；groups_satisfied_at_k：`{'1': 0, '3': 1, '5': 1}`。

- Top 1，score 33.839959，`european-xfel-x-ray-optics-beam-transport-tdr-2012`，物理页 43～43，Chunk `european-xfel-x-ray-optics-beam-transport-tdr-2012:f80b625a32c4d7d85831163aed5cc834738280ee825053bf80b74d3a892f4b4d`。
  XFEL.EU TR-2012-006 December 2012 TDR: X-Ray Optics and Beam Transport 43 of 164  4 Soft X-ray monochromator  Compared to CDR2011, the design of the soft X-ray monochromator was  fundamentally revised and optimized. The time broadening was improved, so  that now an almost Fourier-limited time respon
- Top 2，score 31.987230，`european-xfel-x-ray-optics-beam-transport-tdr-2012`，物理页 5～5，Chunk `european-xfel-x-ray-optics-beam-transport-tdr-2012:5af849fe4715abccdff144d8b08a568395bc54fbbbc8e64b936b8cc59e8db405`。
  and heat load, will cause noticeable beam distortions. A prototype  development for these mirrors is discussed as well as the design of the mirror  chambers, which face high requirements in terms of vibration stability and  motion capabilities at the best possible UHV conditions.  An important conce
- Top 3，score 16.359564，`european-xfel-full-technical-design-report-2007`，物理页 268～268，Chunk `european-xfel-full-technical-design-report-2007:18bfc359acbe10175c3e9d61e72eec77530f2f00f51b3b0e6c5805cbd5388aac`。
  Name/ Device Distance Task Line [m]  A1, B1 Mirror 250 Assembly of two mirrors to be placed alternatively in the FEL beam. They reflect the beam in horizontal geometry into the Lines A and B. Different mirrors will be used for this task: A1. plane mirror reflects towards the second mirror. B1. cylin

**xfel-bpm-types**：Which BPM pickup types provide standard and high-precision position measurements at European XFEL?

first_complete_rank：`1`；groups_satisfied_at_k：`{'1': 1, '3': 1, '5': 1}`。

- Top 1，score 20.107347，`european-xfel-standard-e-beam-diagnostics-linac2010`，物理页 1～1，Chunk `european-xfel-standard-e-beam-diagnostics-linac2010:ca586d4bb17b2f3b046c3ff7df9f0a5f4e983cd3f7185207b5c9e30543aef05e`。
  BEAM POSITION MONITOR SYSTEM The E-XFEL BPM system will be provided by a collaboration of PSI, CEA and DESY [5]. As listed in Table 2, there will be standard BPMs with moderate and precision BPMs with high resolution. The standard BPMs will be of the button type. Precision monitors will be different
- Top 2，score 19.482451，`european-xfel-standard-e-beam-diagnostics-linac2010`，物理页 2～2，Chunk `european-xfel-standard-e-beam-diagnostics-linac2010:92dae4dd6a54b38fbeda66d748394da4e0e8164519b8124c19f208d3b6fb6914`。
  Two types of cavity BPMs based on the development of T. Shintake for SCSS will be used [8]. Both types with a beam pipe diameter of 10 mm and 40.5 mm, respectively, as shown in Fig. 2, consist of a reference and dipole resonator. The cross talk between the two resonators was measured to be very low 
- Top 3，score 19.184368，`shine-accelerator-preliminary-design-report-2017`，物理页 320～320，Chunk `shine-accelerator-preliminary-design-report-2017:2b69b0f4a9d678a6a9e14d57405390d4d8351a3220b9cb34cdf2e9bcabb666b1`。
  [27] G. Waldschmidt and R. Lill, et al. Electromagnetic Design of the RF cavity  beam position monitor for the LCLS. Proceedings of PAC07, Albuquerque, New  Mexico, USA  [28] S. Smith, S. Hoobler, et al. LCLS cavity beam position monitors.  Proceedings of DIPAC09, Basel, Switzerland  [29] Stephen Sm

**shine-ioc-management**：How are IOC and PV information managed in SHINE?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 1}`。

- Top 1，score 21.762061，`shine-epics-ioc-pv-information-management-pcapac2022`，物理页 2～2，Chunk `shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355`。
  Figure 5: PV Service Architecture. To be specific, the operation process of PV Service is divided into three stages: register, scanning and updating. First of all, necessary scripts (Figure 6) are embedded into the startup shell (st.cmd) in order to obtain the information of the IOC, such as the ins
- Top 2，score 20.907509，`shine-epics-ioc-pv-information-management-pcapac2022`，物理页 1～1，Chunk `shine-epics-ioc-pv-information-management-pcapac2022:25174c02d5ade025d5667e0fab4688ff826624edd46edc94b4204537de76c235`。
  The database saves the properties as Name/Value pairs. Details are illustrated in Figure 3. More specifically, it is needed to store the information of server, IOC, record and PV. For the server, the database is not only to store static attributes, like environment variables related to EPICS, but al
- Top 3，score 18.834135，`epics-documentation-latest-2026-08-18`，物理页 449～449，Chunk `epics-documentation-latest-2026-08-18:9613124816a8df6b38a639ce490da04452a906eee438d97f2620b28ac098370e`。
  • References: for users to consult, when looking for specific information  Each of those type of page must be put in that order in the various topics. For example:  • Process database  – Making an IOC with linked PVs (tutorial)  – How to find which IOC provides a PV (guide)  1.45. Documentation cont

**shine-ioc-startup**：SHINE 中 IOC 启动后会向管理系统提交哪些信息？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 22.940454，`shine-accelerator-control-system-design-presentation`，物理页 28～28，Chunk `shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996`。
  通道信息管理  \uf06e 完成通道信息管理软件核心模块开发  \uf06e 将控制系统中的IOC信息、Record信息纳入数据库管理  \uf06e 所有IOC的静态信息（地址、端口、...），状态信息（连接、...）  \uf06e 所有Record的名称、类型、域定义情况，以及访问权限、合法性等  软件著作权登记 数据库设计
- Top 2，score 20.794676，`shine-accelerator-control-system-design-presentation`，物理页 30～30，Chunk `shine-accelerator-control-system-design-presentation:ddf93febe49d79d60f5f9600a4b9f6f75c1d608371009d15441a4804ac416dfb`。
  超导腔文件管理系统  \uf06e SHINE项目中，77个模组，每个模组包含8个超导腔（1.3GHz、3.9GHz）  \uf06e 基于Mediawiki构建，可以管理超导腔的加工、生产、测试过程文件  \uf06e 不同用户的编辑权限不同、厂商之间相互屏蔽报告内容、可以上传文件、图片等附件  （详见吕慧慧博士的报告）  客户端Web界面
- Top 3，score 20.510750，`shine-accelerator-control-system-design-presentation`，物理页 11～11，Chunk `shine-accelerator-control-system-design-presentation:fa8c0077ece6768d8abd8b26f38ba9ec4b42dda3962adec3f580e4a0d1e7150c`。
  \uf06e控制系统的层级 (刘德康 研究员)：  设备控制层、本地处理层、人机交互层、束流物理层、数学模型层  \uf06e哪些工作需要做？哪些工作必须现在做？哪些工作可以推后做？  \uf06e控制是一个全局性的系统，系统架构设计、各类协议和标准的统一  对于系统集成至关重要；  \uf06e协议、标准、规范如何做到有前瞻性？如何有效、“轻负”推进？

**interlock-latency**：SHINE 快联锁对单节点和节点间的响应时间分别有什么要求？

first_complete_rank：`3`；groups_satisfied_at_k：`{'1': 0, '3': 1, '5': 1}`。

- Top 1，score 60.312937，`shine-accelerator-fast-interlock-2024`，物理页 7～7，Chunk `shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量
- Top 2，score 52.342143，`shine-accelerator-preliminary-design-report-2017`，物理页 398～398，Chunk `shine-accelerator-preliminary-design-report-2017:20a7722ba35caef9a1789bc46d8e7baf45d3c1b905d01ec573314449bdd0f163`。
  包括网络传输和服务器处理时间。负载能力是在正常的响应时间范围内，系统能  够支持的最多的客户端的数量，可以通过发起大量的CA 连接进行测试。  6.2.3.2 硬件检测平台  硬件检测平台针对主定时和快联锁系统中自主研制的模块，主要检测时间相  关的参数，包括主定时系统的时钟晃动检测、快联锁系统的站内或站间的响应时  间检测，它是确保这整控制系统达到设计指标的关键。硬件模块常规的测试，例  如检测有无开短路问题，是否符合电磁兼容要求等，通过借用或租用平台的方式  来完成。  硬件检测平台由射频信号源、任意波形发生器、稳压电源、数字示波器、信  号源分析仪、逻辑分析仪等仪器设备组成。其中，数字示
- Top 3，score 52.063881，`shine-accelerator-fast-interlock-2024`，物理页 2～2，Chunk `shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b`。
  核 技 术 2024, 47: 120203  and the system have been put into online operation for SHINE injector. The response time test results meet the  SHINE operation requirements, and remote control of the system has been implemented based on the EPICS.  Key words Fast interlock, FPGA, Data transmission, FL-net, 

**interlock-platform**：横河 FPIO 快联锁模块使用哪种 FPGA 芯片和开发语言？

first_complete_rank：`2`；groups_satisfied_at_k：`{'1': 0, '3': 2, '5': 2}`。

- Top 1，score 66.596116，`shine-accelerator-fast-interlock-2024`，物理页 2～2，Chunk `shine-accelerator-fast-interlock-2024:568004790ecec62325207c734c8249811e0ba0c6f1da6fac206316dcbe9e20a5`。
  SHINE 联锁系统采用“成熟的硬件板卡+完全 自主开发联锁功能软件”的系统方案，确定了基于横 河FPIO（Field Programmable High-speed IO）模块的 快联锁开发方案。FPIO 模块是在横河FA-M3/e-RT3的基础上安装和使用的高功能I/O模块，具备µs 级的IO 响应时间，其结构图如图2 所示。模块内置 FPGA，允许用户在模块中开发和编译FPGA 功能， 开放用户自主开发用户逻辑回路。模块共有24 个 LED 灯，可指定任意信号显示；每个模块支持24 路 输入和24路的输出（5~24 V）。  SHINE直线段的机柜需要直接安装在加速器隧 道内，机柜规格只
- Top 2，score 64.625741，`shine-accelerator-fast-interlock-2024`，物理页 3～3，Chunk `shine-accelerator-fast-interlock-2024:3989f77d1ed901e922429b49a72751dc4b71b50fb0267e5c7a8fe005090a5120`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  系统的工艺和供电问题，并且缩减了快联锁系统所 需的安装空间，和慢联锁系统在硬件结构和外观上 可结合为一个“整体”。FPIO 模块内置的FPGA 使 用的是Xilinx 公司的Spartan6 XC6SLX25 系列芯 片，其开发和设计流程遵循FPGA开发的通用流程。 模块带有编程口，通过转接线缆和JTAG 编程线缆 可连接计算机，实现与Xilinx 的工具包ISE Design  Suite 的连接。BSP（Board Support Program）板级支 持软件提供了部分可调用的接口模块和功能。在此 基础上，使用硬件描述性语言可以实现联锁
- Top 3，score 41.631829，`shine-accelerator-fast-interlock-2024`，物理页 3～3，Chunk `shine-accelerator-fast-interlock-2024:a5b7baa31dd6b7e2bccef2a847deb913b96aac8381844a10f7aa0d1ea5b4ac6a`。
  在快联锁FPGA 逻辑程序开发过程中，需要配 置和定义系统自主的userlogic.h 头文件，将需要与 CPU之间进行数据交互的寄存器在此文件中进行地 址和变量的声明，在此基础上通过读写接口模块的 开发和调用，在CPU端即可通过梯形图读写头文件 中相应地址的寄存器数值。  图3 快联锁与慢联锁系统总体结构图 Fig.3 General architecture of fast interlock system and slow interlock system  SHINE的远程控制系统使用加速器主流的分布 式控制软件EPICS（Experimental Physics and Indust

**shine-control-layers**：How are the functional layers of the SHINE control system separated?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 2, '3': 2, '5': 2}`。

- Top 1，score 20.370277，`shine-control-system-status-icalepcs2019`，物理页 1～1，Chunk `shine-control-system-status-icalepcs2019:f79189e6eca2f8c7b31f8b61b01a7cec9e5f60c1573d880ba71c7b9bd1fb5269`。
  According to the experience of SSRF and SXFEL, the control system of SHINE will be mainly based on EPICS (Experimental Physics and Industrial Control System) to reach the balance between the high performance and costs of maintenance. EPICS is a set of open source software tools, libraries and applic
- Top 2，score 20.352904，`shine-cryogenic-control-system-2021`，物理页 3～3，Chunk `shine-cryogenic-control-system-2021:b140b52b1b1c29d82fc85c090e3ede87819a3dd9b44182ce3f54e415e439a5d9`。
  As shown in Fig. 2, the control system will adopt the standard three layers control architecture to ensure scalability and avoid performance limitations. EPICS will give a set of toolkits with well-defined interfaces at both the servers and clients to enable integration and development. SIEMENS fibe
- Top 3，score 19.521536，`shine-cryogenic-control-system-2021`，物理页 4～4，Chunk `shine-cryogenic-control-system-2021:37b6c4b918b1328d3f72df5be03d2077cacd53269eb89fa8f0ace4cdf555c418`。
  In the core of the control system, powerful Linux servers host the operational files and run other application software based on JAVA or script languages.  With this structure, remote consoles running Graphical User Interfaces (GUI) will allow machine operators to control and optimize the beams and 

**cryo-integration**：How do PLCs and soft IOCs divide control and PV acquisition in the SHINE cryogenic system?

first_complete_rank：`1`；groups_satisfied_at_k：`{'1': 1, '3': 1, '5': 1}`。

- Top 1，score 39.731166，`shine-cryogenic-control-system-2021`，物理页 3～3，Chunk `shine-cryogenic-control-system-2021:b140b52b1b1c29d82fc85c090e3ede87819a3dd9b44182ce3f54e415e439a5d9`。
  As shown in Fig. 2, the control system will adopt the standard three layers control architecture to ensure scalability and avoid performance limitations. EPICS will give a set of toolkits with well-defined interfaces at both the servers and clients to enable integration and development. SIEMENS fibe
- Top 2，score 33.181141，`shine-cryogenic-control-system-2021`，物理页 2～2，Chunk `shine-cryogenic-control-system-2021:55733903164b8ee4afabc462a61675562f353392a107ea7197073d19f170219a`。
  The control system is aimed to implement all devices control and integerates them all. For each sub cryogenic system, refrigerator cold box will be purchased from the vendor-ALAT Company, which performs the cryogenic plant control through Siemens PLCs, mainly model is S7–1500, Profinet and WinCC sof
- Top 3，score 32.408096，`shine-cryogenic-control-system-2021`，物理页 5～5，Chunk `shine-cryogenic-control-system-2021:1413f9f76757ede06ed88e441e08125e6d428db6df0661e6694ddf83dddacf01`。
  refrigerator PLC and other sub PLCs. Master to refrigerator is read only with a shared memory table to avoid impact to it; Master to sub is read/write through register address with PLC configuration technology.  \u0001 interface 2 between PLCs and IOCs. S7nodave EPICS device support driver resident 

**cryo-interlock**：SHINE 低温测试装置如何通过主联锁 PLC 和 CPLD 实现低温设备保护？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 41.811293，`shine-accelerator-preliminary-design-report-2017`，物理页 396～396，Chunk `shine-accelerator-preliminary-design-report-2017:91cbfc99a77fa73a1cb353fef9000885aa7bba013eacf53cc8deb7f53daa9430`。
  设计，用于模块之间信号传输及机械安装。  （2）监控模块：商业CPU 板或自主设计，用于对其它模块监控及通过EPICS  程序实现上层人机交互。  （3）联锁主模块：2 路千兆光纤输入/输出用于主/从站互联，FPGA 实现联  锁逻辑并且通过背板总线驱动输入/输出模块。  （4）输入模块：8 路通道，包含TTL,继电器，光纤接口，用于外部需联锁  设备的信号调理和多路输入。  （5）输出模块：8 路通道，包含TTL,继电器，光纤接口，用于外部需联锁  设备的信号调理和多路输出。  一般联锁系统由联锁信号输入、联锁逻辑和联锁信号输出组成。如果联锁系  统需要切换不同的联锁模式，就必须修改联锁逻辑
- Top 2，score 40.179120，`shine-accelerator-preliminary-design-report-2017`，物理页 395～395，Chunk `shine-accelerator-preliminary-design-report-2017:f6a519bbd3b1d582b2aea8d735c8feb12a3046ce17d623401210022c6e192d7a`。
  表3.3.6.2-2 SCLF 快联锁主要性能参数表  组件内容 响应/传输时间  单站 1us~10us  2km 单模光纤 20us 以内单向传输  主/从站 50us 以内  6.2.2.9.3 设计方案  通常加速器机器联锁系统由PLC 等联锁控制器、各种信号调理模块及对应  的连接电缆、光纤等组成。本装置机器联锁系统和一般加速器联锁系统相比，具  有规模大，设备分布区域广、束流能量高，系统响应时间严格等特点。因此基于  传统PLC 和电缆连接的机器联锁系统已无法满足需要，新系统宜采用菊花链和  星型网络混合的拓扑结构，主从站全光纤网络连接方式，单节点响应时间需控制  在微秒量级，整个
- Top 3，score 36.214239，`shine-accelerator-fast-interlock-2024`，物理页 3～3，Chunk `shine-accelerator-fast-interlock-2024:a5b7baa31dd6b7e2bccef2a847deb913b96aac8381844a10f7aa0d1ea5b4ac6a`。
  在快联锁FPGA 逻辑程序开发过程中，需要配 置和定义系统自主的userlogic.h 头文件，将需要与 CPU之间进行数据交互的寄存器在此文件中进行地 址和变量的声明，在此基础上通过读写接口模块的 开发和调用，在CPU端即可通过梯形图读写头文件 中相应地址的寄存器数值。  图3 快联锁与慢联锁系统总体结构图 Fig.3 General architecture of fast interlock system and slow interlock system  SHINE的远程控制系统使用加速器主流的分布 式控制软件EPICS（Experimental Physics and Indust

**timing-wrtd**：Why is standard White Rabbit Trigger Distribution insufficient for the SHINE beam-synchronous trigger rate?

first_complete_rank：`1`；groups_satisfied_at_k：`{'1': 1, '3': 1, '5': 1}`。

- Top 1，score 50.360081，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 2～2，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:5aa688cbe36ec0b60520b1a45ec473e83ca2459c86144db73ed08a2ef17eab53`。
  Figure 1: SHINE timing system architecture.  White Rabbit Trigger Distribution  White Rabbit Trigger Distribution (WRTD) is a generic framework for distributing triggers (events) between Nodes over a White Rabbit network [2]. WRTD nodes re-ceive input events and distribute them to other nodes over W
- Top 2，score 50.279896，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 1～1，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:4130d7f7a5a0075429ebf878b5cad8e5ea4bc1f88e55073b291a4246ffc3c3af`。
  Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE) is under construction. SHINE requires precise distribution and synchronization of the 1.003086 MHz timing signals over a long distance of about 3.1 km. Two prototype systems were developed, both containing three functions: beam-sy
- Top 3，score 47.500840，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 1～1，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:044f7bc2b3e46bebdd43195cac2d05a60087e6df478e1a3f889082ae9933217e`。
  SHINE project requires precise distribution and synchronization of the 1.003086 MHz (1300 MHz/1296) timing signals over a long distance of about 3.1 km. The beam-synchronous trigger signal distribution is the basic and pri-ority function.  The standard White Rabbit network operates at 125/62.5 MHz c

**timing-jitter**：What beam-synchronous and random-event trigger jitter was measured for SHINE timing Prototype II?

first_complete_rank：`2`；groups_satisfied_at_k：`{'1': 0, '3': 1, '5': 1}`。

- Top 1，score 50.432320，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 4～4，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:df1ac099cc83fb10f4001f877ceeb64c78cb684c8e02c27cbfd259f8bec6b246`。
  For the beam-synchronous trigger signal distribution, the jitter between the output of slave node and the external reference signal is less than 10ps (RMS). The jitter between the outputs from different slave nodes is less than 5ps (RMS). The temperature drift test results are shown in the Fig. 10. 
- Top 2，score 48.382849，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 5～5，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:adb5de8c979b387a905cea6e11dfe193f44004f74377c7349640d3d63e5b2445`。
  (1.003086 MHz×9). The laptop computer is connected to the WR switches and nodes via the standard network switch. The Keysight MSOS604A and Siglent SDS6204 H12 Pro Oscilloscope are used to measure the output of slave node and the external reference signal.  in Proc. ICALEPCS'15, Melbourne, Australia,
- Top 3，score 48.374141，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 1～1，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:4130d7f7a5a0075429ebf878b5cad8e5ea4bc1f88e55073b291a4246ffc3c3af`。
  Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE) is under construction. SHINE requires precise distribution and synchronization of the 1.003086 MHz timing signals over a long distance of about 3.1 km. Two prototype systems were developed, both containing three functions: beam-sy

**control-slow-interlock**：SHINE 控制系统设计中慢联锁的站内和站间响应时间指标是什么？

first_complete_rank：`2`；groups_satisfied_at_k：`{'1': 0, '3': 1, '5': 1}`。

- Top 1，score 62.967097，`shine-accelerator-preliminary-design-report-2017`，物理页 398～398，Chunk `shine-accelerator-preliminary-design-report-2017:20a7722ba35caef9a1789bc46d8e7baf45d3c1b905d01ec573314449bdd0f163`。
  包括网络传输和服务器处理时间。负载能力是在正常的响应时间范围内，系统能  够支持的最多的客户端的数量，可以通过发起大量的CA 连接进行测试。  6.2.3.2 硬件检测平台  硬件检测平台针对主定时和快联锁系统中自主研制的模块，主要检测时间相  关的参数，包括主定时系统的时钟晃动检测、快联锁系统的站内或站间的响应时  间检测，它是确保这整控制系统达到设计指标的关键。硬件模块常规的测试，例  如检测有无开短路问题，是否符合电磁兼容要求等，通过借用或租用平台的方式  来完成。  硬件检测平台由射频信号源、任意波形发生器、稳压电源、数字示波器、信  号源分析仪、逻辑分析仪等仪器设备组成。其中，数字示
- Top 2，score 58.981847，`shine-accelerator-control-system-design-presentation`，物理页 21～21，Chunk `shine-accelerator-control-system-design-presentation:4e92201c2cf375a954b2860baf67a725b258f56b1a36a01b061e46d2775928dc`。
  联锁系统  \uf06e 快联锁 + 慢联锁；主站 + 从站，分层设计  \uf0b2快联锁关键信号响应时间：  站内≤10us，站间≤100us  \uf0b2慢联锁关键信号响应时间：  站内≤20ms，站间≤100ms
- Top 3，score 56.065523，`shine-accelerator-fast-interlock-2024`，物理页 7～7，Chunk `shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量

**shine-compressors**：为什么 SHINE 的两级磁压缩分别布置在 270 MeV 和约 2.1 GeV 位置？

first_complete_rank：`1`；groups_satisfied_at_k：`{'1': 1, '3': 1, '5': 1}`。

- Top 1，score 52.967884，`shine-accelerator-preliminary-design-report-2017`，物理页 61～61，Chunk `shine-accelerator-preliminary-design-report-2017:485d8b33ff6ed2e347fa8cba06c82d98aeec1523072c4601be8da25fc12826a3`。
  一个加速段L1 的下游，电子束的能量为270MeV。电子束经过磁压缩以后流强  由12A 压缩至85A，压缩倍数约为7。第二个磁压缩器位于主加速器第二个加速  段L2 的下游，电子束的能量为2.1GeV。纵向参数优化采用一维束流动力学模拟  软件Litrack 完成。电子束的纵向相空间和流强分布演化过程如图3.3.3.1-2 所示。  图3.3.3.1-2 电子束的纵向相空间和流强分布  (a) 注入器出口；(b) BC1 出口；(c) BC2 出口；(d) L3 出口  两级磁压缩位置的选择基于束流稳定性的优化及束团集体效应对束流亮度  和品质的影响。第一级磁压缩BC1 通常距离注入器比较近
- Top 2，score 51.672567，`shine-accelerator-preliminary-design-report-2017`，物理页 68～68，Chunk `shine-accelerator-preliminary-design-report-2017:ea5677c174492e5a71253d42d2132a1732c220422f051dd58e3c66fdb961c461`。
  图3.3.3.1-9 消能散段布局  电子束通过褶皱结构后的纵向相空间如图3.3.3.1-10 所示。可以看到，通过  优化褶皱结构的参数，电子束的能散得到了很好的补偿。  图3.3.3.1-10 电子束通过褶皱结构前后的纵向相空间（a）及流强分布（b）  电子束通过褶皱结构不但会产生纵向尾场，同时也会产生横向尾场。结构尾  场的强度与电子束通过褶皱结构的位置有关。偏离中心通过褶皱结构的电子束，  不仅会受到横向踢力，而且会受到结构尾场的四极场作用，使电子束的相空间发  生畸变从而导致束团品质下降。因此为了减少褶皱结构横向尾场对电子束的影响，  应尽可能的使电子束通过褶皱结构的中心。  3.1
- Top 3，score 47.064152，`shine-accelerator-preliminary-design-report-2017`，物理页 60～60，Chunk `shine-accelerator-preliminary-design-report-2017:cf8f273a1807979a26bbeb8f961f70b0886235053ba0f7b80ee3989f17712b7b`。
  实现了在硬X 射线波段出光。不同于FLASH 和European XFEL 这种基于宏脉冲  模式的自由电子激光装置，美国的SLAC 国家实验室在LCLS 取得巨大的成功以  后，联合其它实验室开始研制基于超导连续波的X 射线自由电子激光装置  LCLS-II。  基于超导加速结构的自由电子激光装置是结合了各系统最顶尖技术的大型  光子科学装置。硬X 射线自由电子激光装置基于超导连续波工作模式，其主加  速器采用三级加速、两级压缩的结构设计，如图3.4.3.1-1 所示。主加速器位于注  入器之后（注入器出口能量~100MeV），通过一消色散dogleg 段将注入器出口高  亮度电子束注入到主

**shine-main-linac**：SHINE 初步设计中的主加速器采用什么工作模式，最终把电子加速到多少能量？

first_complete_rank：`4`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 1}`。

- Top 1，score 47.140101，`shine-accelerator-preliminary-design-report-2017`，物理页 60～60，Chunk `shine-accelerator-preliminary-design-report-2017:cf8f273a1807979a26bbeb8f961f70b0886235053ba0f7b80ee3989f17712b7b`。
  实现了在硬X 射线波段出光。不同于FLASH 和European XFEL 这种基于宏脉冲  模式的自由电子激光装置，美国的SLAC 国家实验室在LCLS 取得巨大的成功以  后，联合其它实验室开始研制基于超导连续波的X 射线自由电子激光装置  LCLS-II。  基于超导加速结构的自由电子激光装置是结合了各系统最顶尖技术的大型  光子科学装置。硬X 射线自由电子激光装置基于超导连续波工作模式，其主加  速器采用三级加速、两级压缩的结构设计，如图3.4.3.1-1 所示。主加速器位于注  入器之后（注入器出口能量~100MeV），通过一消色散dogleg 段将注入器出口高  亮度电子束注入到主
- Top 2，score 38.491615，`shine-accelerator-preliminary-design-report-2017`，物理页 63～63，Chunk `shine-accelerator-preliminary-design-report-2017:8c9eae11d9baa8eecf40e783c9f2b825d2aa96e87dc4818ee8839a74108b7076`。
  根据加速器中电子性质的不同，可分为高亮度光电子束和杂散电子。光电子  束用于产生自由电子激光，杂散电子与光电子束混合，增大束流调试难度。杂散  电子来自于场致发射形成的暗电流或者其他电离效应。与光电子相比，杂散电子  在束流能量、束团到达时间、横向位置与光电子或有不同。杂散电子的存在，一  方面影响光电子束流的参数调节、测量；另一方面，杂散电子沿束流线的不可控  传输增大辐射安全设计难度，降低波荡器等剂量敏感设备的使用寿命。超导加速  器运行在连续波状态，杂散电子平均功率相比脉冲式加速器呈几何量级增加，其  潜在风险必须在设计阶段足够重视。  综合以上考虑，将直线加速器按照功能段划分。激光加热
- Top 3，score 38.410834，`shine-accelerator-preliminary-design-report-2017`，物理页 7～7，Chunk `shine-accelerator-preliminary-design-report-2017:105cf63b52dede129e539bc6e7721385cf834f319fd5272c704f1bc6e8aaf508`。
  2. 注入器  2.1 注入器物理  2.1.1 概述  根据自由电子激光的理论，要获得高平均功率的激光辐射，必须有相应的高  平均功率的电子束流。另一方面，不论工作在低增益还是高增益模式，只有电子  束流的横向几何发射度小于等于激光辐射的波长时，才能获得相干的激光辐射，  这就是对电子束流的低横向发射度的要求。电子束流在加速和传输的过程中受到  非线性、非保守力的作用，其归一化横向发射度会产生增长，所以在产生电子束  流时，要求有更低的归一化横向发射度。此外，根据自由电子激光理论，自由电  子激光的增益与电子束流强I 成正比例关系，I 越大，不仅使得自由电子激光越  快达到饱和，激光辐射的能

**no-answer-finance**：What was NVIDIA quarterly revenue in fiscal 2026 Q4?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 12.057979，`epics-documentation-latest-2026-08-18`，物理页 1～1，Chunk `epics-documentation-latest-2026-08-18:52bd89183ad468642dc79ac19cc30ee5ceed85db30f2143d5df4c0da14001e37`。
  EPICS Documentation  EPICS  Aug 18, 2026
- Top 2，score 11.682932，`epics-documentation-latest-2026-08-18`，物理页 19～19，Chunk `epics-documentation-latest-2026-08-18:39bc60ed670a709038a415ff4bfb7f4aa4ed95ad8e18d7c50fd5c53efffc0536`。
  (continued from previous page) ############################################################################ ## EPICS R7.0.10 ## Rev. 2026-06-25T10:56+0200 ## Rev. Date build date/time: ############################################################################ iocRun: All initialization complete ep
- Top 3，score 9.276372，`epics-application-developers-guide-r3-16-2`，物理页 11～11，Chunk `epics-application-developers-guide-r3-16-2:8770cf2a2aa6a717ea712e7c94f0b7a6812cdf8a167403fc40aa47a7f70f11fb`。
  1.2. ACKNOWLEDGMENTS 11  1.2 Acknowledgments  The basic model of what an IOC should do and how to do it was developed by Bob Dalesio at LANL/GTA. The principle ideas for Channel Access were developed by Jeff Hill at LANL/GTA. Bob and Jeff also were the principle implementers of the original IOC soft

**no-answer-recipe**：如何制作四川麻婆豆腐？请给出食材和烹饪步骤。

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 13.350518，`shine-accelerator-control-system-design-presentation`，物理页 11～11，Chunk `shine-accelerator-control-system-design-presentation:fa8c0077ece6768d8abd8b26f38ba9ec4b42dda3962adec3f580e4a0d1e7150c`。
  \uf06e控制系统的层级 (刘德康 研究员)：  设备控制层、本地处理层、人机交互层、束流物理层、数学模型层  \uf06e哪些工作需要做？哪些工作必须现在做？哪些工作可以推后做？  \uf06e控制是一个全局性的系统，系统架构设计、各类协议和标准的统一  对于系统集成至关重要；  \uf06e协议、标准、规范如何做到有前瞻性？如何有效、“轻负”推进？
- Top 2，score 11.921036，`shine-accelerator-preliminary-design-report-2017`，物理页 160～160，Chunk `shine-accelerator-preliminary-design-report-2017:e62ee44bf02195608e08281ae11e6f71cc29faec13d172e8262fa8a9ffd76aba`。
  FPGA程序和EPICS db文件。  预估的单套联锁信号如表3.3.3.5-2。  表3.3.3.5-2 预估的单套联锁信号  ai ar aw di dr dw  环流器打火 1  环流器打火测试 1  环流器水流量计 1  环流器温差 1  水负载打火 1  水负载打火测试 1  水负载入水温度 1  水负载出水温度 1  水负载流量 1  水路压力 1  超导腔入射功率 1  超导腔反射功率 1  发射机输出功率 1  发射机反射功率 1  预研阶段，将完成一套联锁系统的研发。  时间进度规划如下（视开始研制时间顺延）：  2017年8月底前完成系统结构设计；  2017年12月底完成
- Top 3，score 11.762415，`shine-accelerator-preliminary-design-report-2017`，物理页 472～472，Chunk `shine-accelerator-preliminary-design-report-2017:9040872425a04f82059f31c21c76c0bf5ad120a38363546b5ff39a587a8343e9`。
  （11）2021.6-2022.3：完成所有电源的验收和调试，按照测试内容逐一进行  测试和验收，并对验收情况请专家评审，验收合格方可进行安装。  （12）2022.4-12：完成电源的安装，完成电源电缆的铺设，完成电源控制器  的安装，完成电源联锁电缆的铺设；  （13）2023.1-8：完成电源机柜配电检查，完成电源电缆对应检查，完成电  源联锁信号对应检查，完成电源初步上电检查，完成负载和电源所有保护功能是  否正常工作，完成电源带真实负载的调试，完成电源控制参数的烧写，完成电源  大电流输出烤机，完成在现场的验收带实际负载的调试和性能指标验收测试。  （14）2023.8-12：完成电

**no-answer-token**：zxqv9999unlistedcalibrationartifact

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。


**no-answer-hard-live-pv**：SHINE 在 2026-10-19 10:00 UTC 的 temperature:water PV 实时读数是多少？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 24.139018，`shine-accelerator-control-system-design-presentation`，物理页 10～10，Chunk `shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9`。
  \uf06eCSS是否是最合适的用户界面？  \uf06e全局网络环境下，一个IOC对应多少台设备最合理？  \uf06e虚拟化可以整合硬件资源，提高控制系统可靠性和稳定性；  IOC虚拟化占比多少最合适？  \uf06e控制系统存储容量多少最合理？  \uf06e是否需要异地容灾备份？  \uf06e控制系统是否需要持续集成 (Continue Integrate)？
- Top 2，score 19.071758，`epics-documentation-latest-2026-08-18`，物理页 323～323，Chunk `epics-documentation-latest-2026-08-18:b720469cc610dbf13fc31de67afcd4152670239a12685fad5624518dd3a7f61a`。
  Interpretation: The point in time being identified by a time_t, is given by Jan 1, 1970 00:00:00 UTC plus some nanoseconds given by its secondsPastEpoch times 109 plus its nanoseconds.  time_t[]  A time_t[] describes an array of points in time. The field is an array of structures each describing a t
- Top 3，score 19.023174，`shine-accelerator-preliminary-design-report-2017`，物理页 72～72，Chunk `shine-accelerator-preliminary-design-report-2017:0bd28aa63caba761c136097683ba2d0ad02e8710842ecef9ce949a2bc49be991`。
  3.1.7.3 反馈系统  SCLF 反馈系统主要包括横向反馈系统和纵向反馈系统，该系统可以保证束  流在短时间和长期运行中各项参数的稳定性，其中包括：电荷量、横向轨道、能  量、束长、到达时间等。  在反馈系统中，根据反馈的速度，通常将反馈系统分为慢反馈和快反馈，其  定义如表3.3.3.1-7 所示。同时，根据反馈参数类型，也可以分为横向反馈和纵向  反馈。  表3.3.3.1-7 反馈系统控制速度  慢反馈  以较低频率运行的反馈回路，通常小于10Hz，可以通过上层应用软件与  EPICS 控制系统进行通信及控制。  快反馈  以较高频率运行的反馈回路，通常大于10KHz，通常运行在FP

**no-answer-hard-live-ioc-count**：How many SHINE IOCs are online at 10:00 UTC on 19 October 2026?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 19.954391，`shine-epics-ioc-pv-information-management-pcapac2022`，物理页 1～1，Chunk `shine-epics-ioc-pv-information-management-pcapac2022:ee367f0a36287d1f95b22845d0f2103fb4b0cd22ef4421024730762fe0ed6d60`。
  The control system involves heterogeneous equipment and interfaces with a number of different subsystems. Several IOCs will be deployed in one server, in which hundreds of PVs perform real-world I/O and local control tasks. But we suffer from a lack of high level tools to centrally manage all the IO
- Top 2，score 19.071758，`epics-documentation-latest-2026-08-18`，物理页 323～323，Chunk `epics-documentation-latest-2026-08-18:b720469cc610dbf13fc31de67afcd4152670239a12685fad5624518dd3a7f61a`。
  Interpretation: The point in time being identified by a time_t, is given by Jan 1, 1970 00:00:00 UTC plus some nanoseconds given by its secondsPastEpoch times 109 plus its nanoseconds.  time_t[]  A time_t[] describes an array of points in time. The field is an array of structures each describing a t
- Top 3，score 17.909016，`epics-documentation-latest-2026-08-18`，物理页 323～323，Chunk `epics-documentation-latest-2026-08-18:49604cdb3e90c405a1af391ceb81c91af681d785b1ffda26db5e72ad8b2ce63c`。
  (continued from previous page) int index string[] choices  where:  index  The index of the current value of the enumeration in the array choices below.  choices  An array of strings specifying the set of labels for the valid values of the enumeration.  enum_t[]  An enum_t[] describes an array of enu

**no-answer-hard-live-interlock**：SHINE 快联锁在 2026-10-19 10:00 UTC 的在线许可状态是什么？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 36.524406，`shine-accelerator-fast-interlock-2024`，物理页 5～5，Chunk `shine-accelerator-fast-interlock-2024:fb77460ddb53b1eaa6ea406ddceba2e11119bad8231d16f4a443c62a063769c8`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  损报警等信号，功率源的低电平系统状态和控制信 号、真空快规报警信号等，SHINE快联锁系统主要信 号的数量统计如表2所示。快联锁的逻辑处理与加 速器的运行模式相关，当装置处于运行状态时，任意  一路快联锁信号报警，快联锁系统将执行停束操作， 包括关闭快激光光闸和停止激光系统的定时触发， 如图5所示。  表2 快联锁系统信号统计表 Table 2 Statistical table of fast interlock signals  对接系统 Systems  注入器段信号数量 Numbers of signals from injector
- Top 2，score 35.159840，`shine-accelerator-fast-interlock-2024`，物理页 2～2，Chunk `shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b`。
  核 技 术 2024, 47: 120203  and the system have been put into online operation for SHINE injector. The response time test results meet the  SHINE operation requirements, and remote control of the system has been implemented based on the EPICS.  Key words Fast interlock, FPGA, Data transmission, FL-net, 
- Top 3，score 35.028045，`shine-accelerator-fast-interlock-2024`，物理页 3～3，Chunk `shine-accelerator-fast-interlock-2024:3989f77d1ed901e922429b49a72751dc4b71b50fb0267e5c7a8fe005090a5120`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  系统的工艺和供电问题，并且缩减了快联锁系统所 需的安装空间，和慢联锁系统在硬件结构和外观上 可结合为一个“整体”。FPIO 模块内置的FPGA 使 用的是Xilinx 公司的Spartan6 XC6SLX25 系列芯 片，其开发和设计流程遵循FPGA开发的通用流程。 模块带有编程口，通过转接线缆和JTAG 编程线缆 可连接计算机，实现与Xilinx 的工具包ISE Design  Suite 的连接。BSP（Board Support Program）板级支 持软件提供了部分可调用的接口模块和功能。在此 基础上，使用硬件描述性语言可以实现联锁

**no-answer-hard-live-cryo**：What is the measured SHINE helium refrigerator outlet pressure at 10:00 UTC on 19 October 2026?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 25.993388，`european-xfel-full-technical-design-report-2007`，物理页 565～565，Chunk `european-xfel-full-technical-design-report-2007:419943d50a24e8ea07effea825394e71406b3bf1c22c3048eb15621f971e1af7`。
  Figure 7.2.5 shows a simplified flow scheme of the XFEL refrigerator. The refrigerator processes are almost identical to the TMR and have been reported in detail already [7-1, 7-8]. Helium is compressed at ambient temperature by a two-stage screw compressor group (LP 1,2,3 and HP 1 in Figure 7.2.5) 
- Top 2，score 25.713389，`european-xfel-full-technical-design-report-2007`，物理页 573～573，Chunk `european-xfel-full-technical-design-report-2007:cbfb5fb8512614cb0eac13e83a32bc6843dc5b7c2b7dc0bd1c36c0155a739867`。
  The cryogenic system of the test facility will be supplied with cold Helium from the HERA refrigerator. For the continuous operation of the test hall, cooling capacities of about 10 kW at 40/80 K, 1.0 kW at 4.5 K and 0.6 kW at 2.0 K are needed. In order to reduce the strain on the Helium distributio
- Top 3，score 23.973092，`european-xfel-full-technical-design-report-2007`，物理页 567～567，Chunk `european-xfel-full-technical-design-report-2007:4e2f3aabeb18256c1cb6607ec8607fa9446acacb0455342ead5c945f23589d15`。
  Mass flow Outlet Return  2K load 2450 W 117 g/s 1.1 bar 0.0275 bar 2.2 K 3.5 K 5-8K shield 4000 W 142 g/s 5.5 bar 5.4 bar 5.16 K 8.2 K 40-80K shield 30000 W 142 g/s 18 bar 17 bar 40 K 80 K  Compressors LP 3 117 g/s floating 0.5 – 0.9 bar 295 K LP 1+2 1045 g/s floating 1.2 bar 295 K HP 1 1162 g/s 20 

**no-answer-hard-deployed-firmware**：What exact firmware build SHA was installed on the SHINE White Rabbit master on 19 October 2026?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 31.061410，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 2～2，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:37158e7d14cc1e4b55d682d016455f887dc1dfad5fbf5c9b1ac895d6c23840fe`。
  The repetition frequency of SHINE is 1.0030864 MHz. If we build a customized White Rabbit network with non-standard PTP core, we can use the frequency division of 1300 MHz as the reference signal instead of GPS/Cesium clock. This was originally just an idea, verified by the prototype (I, II) develop
- Top 2，score 30.091780，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 3～3，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:7ababcf6645fcfd666d8cae6b1ed932df158d0bded09069b3cbb46ab0ab81dd5`。
  The system architecture is shown in Fig. 4. Based on the standard White Rabbit network, the master node converted the 9.027778 MHz (1.003086 MHz× 9) RF signal to the frequency and phase information. Then the data is trans-mitted to all slave nodes. The slave nodes use the received date to recover th
- Top 3，score 28.289509，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 2～2，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:1affb5a5629b4abe751ccc678e0e87e509461e9b0e2f8405ca429337f5f93563`。
  The random-event trigger signal distribution is an exten-sion function of SHINE timing system. It is used to distribute various event signals, such as beam loss, machine snap-shot, etc. They are input from the master node. This function is implemented in our prototypes by WRTD similar technology.  R

**no-answer-hard-current-ioc-ip**：SHINE IOC 在 2026-10-19 10:00 UTC 使用的实时 server IP 完整清单是什么？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 27.308540，`shine-accelerator-control-system-design-presentation`，物理页 13～13，Chunk `shine-accelerator-control-system-design-presentation:503fd8a06ea51d0d8ce7bbba135bbd47216f2e2b77d0a1bf77a14a31f82c3fde`。
  \uf06e软件开发管理、通道权限管理、网络管理与监测、. . .  \uf06e管到什么程度合适？“收益”与“代价”之间如何权衡？  \uf06e从工程管理的角度来说，完善控制系统开发环境和管理规则是非  常有必要的。在制定规则的时候，系统的安全性与使用的便捷性  之间往往有冲突，希望能掌握好这两者之间的平衡。  ( 刘功发 教授 )
- Top 2，score 27.121788，`shine-accelerator-preliminary-design-report-2017`，物理页 387～387，Chunk `shine-accelerator-preliminary-design-report-2017:d1615c0ba7dd7e6e2c2c69b2400e44031b50b3c1a645a5ea738c82964825aed1`。
  6.2.2.7.2 设计方案  与EPICS 体系结构相对应，控制软件包括IOC 软件和OPI 软件，下面分别  进行介绍，并对通道访问安全策略和报警系统进行专门讨论。  （1）IOC 软件  IOC 是控制系统的核心，通过各种通讯总线与设备控制器连接，或直接进行  I/O 操作，实现对加速器各类设备的操作控制与数据采集。IOC 运行EPICS 基础  内核（iocCore），执行I/O 过程控制，包含三个基本的组成部分：  ①运行数据库，实现对I/O 通道实时的过程控制与逻辑控制；  ②通道访问协议，实现客户端与运行数据库之间的数据通讯；  ③输入/输出支持模块，即设备支持模块与设备驱动程序
- Top 3，score 24.113748，`epics-documentation-latest-2026-08-18`，物理页 56～56，Chunk `epics-documentation-latest-2026-08-18:4c625ac8af7112fec269cb941027581b6fcce7eb2e4b87a7d0ce17d03b91d9ae`。
  Motorola PPCBUG boot parameters  Motorola single-board computers which employ PPCBUG should have their ‘NIOT’ parameters set up like:  Controller LUN =00 Device LUN =00 Node Control Memory Address =FFE10000 Client IP Address =‘Dotted-decimal’ IP address of IOC Server IP Address =‘Dotted-decimal’ IP 

**no-answer-hard-live-bpm-calibration**：What measured BPM calibration constant was approved at SHINE on 19 October 2026?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 14.751719，`european-xfel-full-technical-design-report-2007`，物理页 321～321，Chunk `european-xfel-full-technical-design-report-2007:45ac6a3cec41c31c09db6ae4cc4891e901ea0efc592e77ebf0f1aab4b8b6335b`。
  Such bands are known to occur in soft fcc metals and are attributed to recrystallisation following slippage along [111] planes during deformation [6-118].  In the above example, special care was taken to grow unstrained crystals. However, it can be shown, under very general conditions [6-119], that 
- Top 2，score 14.425179，`european-xfel-standard-e-beam-diagnostics-linac2010`，物理页 2～2，Chunk `european-xfel-standard-e-beam-diagnostics-linac2010:92dae4dd6a54b38fbeda66d748394da4e0e8164519b8124c19f208d3b6fb6914`。
  Two types of cavity BPMs based on the development of T. Shintake for SCSS will be used [8]. Both types with a beam pipe diameter of 10 mm and 40.5 mm, respectively, as shown in Fig. 2, consist of a reference and dipole resonator. The cross talk between the two resonators was measured to be very low 
- Top 3，score 13.661087，`european-xfel-full-technical-design-report-2007`，物理页 241～241，Chunk `european-xfel-full-technical-design-report-2007:3b1d16377b00cd0b773a32a89850458807d644e554e734a4b3778ea384076711`。
  In order to get as wide a European basis as possible, consultation of the scientific community was organised by holding four XFEL workshops at different locations in Europe:  • Diffraction, Crystallography and Imaging at the European XFEL, October 28/29, 2005, DESY, Hamburg, Germany.  • European XFE

**no-answer-hard-live-beam-energy**：SHINE 在 2026-10-19 10:00 UTC 实际测量的电子束能量是多少？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 26.812206，`shine-accelerator-preliminary-design-report-2017`，物理页 9～9，Chunk `shine-accelerator-preliminary-design-report-2017:505cd601a47c581201017313af36bf050e4e6890b0f8097f45acef33a8c9eaf9`。
  2.1.2.2 注入器工作参数的初步优化  在注入器中，影响电子束团参数的主要是两类部件，一类是加速元件，如电  子枪、聚束器、加速单元等，主要对电子束团进行加速、提供能量，或是对电子  束团进行纵向的聚束，同时也可以提供发横向射度补偿所需的聚焦；另一类是聚  焦元件，如螺线管线圈，主要对电子束团的横向发射度进行补偿，同时也对横向  尺寸进行约束。这两类元件构成了注入器的主体，其工作参数分别决定了纵向的  束团长度和横向的发射度等电子束团的参数，但是实际上在这一类注入器中，电  子束团聚焦、聚束的束流动力学过程是非常复杂的，通常纵向和横向的参数会相  互影响，而且这些元件的布局也会对最后的束流
- Top 2，score 26.642260，`shine-accelerator-preliminary-design-report-2017`，物理页 182～182，Chunk `shine-accelerator-preliminary-design-report-2017:e7e3259abdead258909d76b5401487b0750c07472debfbe006f0f92cfe7a71cd`。
  图3.3.4.1-23 超导波荡器真空室阻抗壁引入的电子束团能量损失，波荡器总长为200m  (a)20pC 电荷量；(b)100pC 电荷量；(c)200pC 电荷量  从理论上，包括在已有X 射线自由电子激光的实际运行中，可以通过改变  波荡器磁场强度，即采用波荡器的连续渐变来补偿尾场造成的能量单调损失。对  于超导波荡器，可以通过线圈电流来独立地调整每段波荡器的峰值磁场，这意味  着只要保证在每段波荡器内的电子束团能量损失（相对值）远小于FEL 的pierce  参数即可。假设超导波荡器的分段长度为4m，最高光子能量25keV 情况对应  pierce 参数最小为1.5×10-4，计算阻
- Top 3，score 26.452711，`shine-accelerator-preliminary-design-report-2017`，物理页 18～18，Chunk `shine-accelerator-preliminary-design-report-2017:ac38840bf9ce702ab1c42b83f5010fd31a4d400d077d443b6e331554669ea03a`。
  图3.3.2.1-12 束测段1#  电子束流进入聚束器后，受到能量调制，经过一段漂移后，在单腔加速单元  的入口处，电子束团在纵向上得到较好的压缩。单腔加速单元对电子束团进行加  速，以补偿电子束流峰值电流增大导致的横向发射度和束团长度的增长，同时对  聚束器产生的能散有一定补偿作用。第二束流测量段位于单腔加速单元和8 腔加  速单元之间，对该处的电子的束流截面（YAG）、位置（BPM）、能量/能散（分  析磁铁）、发射度（扫描束+固定狭缝）、束团长度（TDS）等束流参数进行测量，  如图3.3.2.1-13 所示。可以对聚束过程进行评估，作为聚束器工作参数调整的依  据。  图3.3.2.

## dense

### overall

| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| overall | 21 | 0.0952 | 0.1905 | 0.3810 | 0.1802 |

### by_query_language

| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| en | 13 | 0.0769 | 0.1538 | 0.4615 | 0.1756 |
| zh | 8 | 0.1250 | 0.2500 | 0.2500 | 0.1875 |

### by_language_relation

| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| cross_language | 3 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| same_language | 18 | 0.1111 | 0.2222 | 0.4444 | 0.2102 |

### by_category

| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| accelerator_design | 4 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| beam_diagnostics | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| beam_transport | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| control_architecture | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2000 |
| cryogenics | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| epics | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| interlock | 3 | 0.3333 | 0.6667 | 0.6667 | 0.5000 |
| ioc | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| photon_diagnostics | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333 |
| pv | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| timing | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |

### by_expected_document

| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| epics-application-developers-guide-r3-16-2 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| epics-documentation-latest-2026-08-18 | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| european-xfel-full-technical-design-report-2007 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| european-xfel-standard-e-beam-diagnostics-linac2010 | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| european-xfel-undulator-commissioning-spectrometer-cdr-2011 | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333 |
| european-xfel-x-ray-optics-beam-transport-tdr-2012 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shine-accelerator-control-system-design-presentation | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| shine-accelerator-fast-interlock-2024 | 2 | 0.0000 | 0.5000 | 0.5000 | 0.2500 |
| shine-accelerator-preliminary-design-report-2017 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shine-control-system-status-icalepcs2019 | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2000 |
| shine-cryogenic-control-system-2021 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |
| shine-epics-ioc-pv-information-management-pcapac2022 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| shine-white-rabbit-beam-synchronous-timing-ipac2022 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250 |

### Top-1 分数分布

- answerable（21 条）：`{'count': 21, 'min': 0.5029935869262879, 'max': 0.7782650906334003, 'mean': 0.6659139335332538, 'p10': 0.5953099007130604, 'p25': 0.6365569239916968, 'median': 0.6646541412392741, 'p75': 0.7076117500420326, 'p90': 0.7360936690974041, 'p95': 0.7688694079807534}`。
- obvious（3 条）：`{'count': 3, 'min': 0.41021031445670614, 'max': 0.5327770869100423, 'mean': 0.46942539494138086, 'p10': 0.4212260082568437, 'p25': 0.43774954895705004, 'median': 0.46528878345739394, 'p75': 0.49903293518371816, 'p90': 0.5192794262195126, 'p95': 0.5260282565647775}`。
- hard_domain（8 条）：`{'count': 8, 'min': 0.5559336035525682, 'max': 0.6793489781197168, 'mean': 0.6066928466829425, 'p10': 0.5568227989679553, 'p25': 0.5798337858028224, 'median': 0.6073741301560778, 'p75': 0.6259211566093996, 'p90': 0.6493925842096742, 'p95': 0.6643707811646955}`。

### 逐条判断

**epics-pp**：When does an EPICS PP input link process its target record?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.674150，`epics-application-developers-guide-r3-16-2`，物理页 179～179，Chunk `epics-application-developers-guide-r3-16-2:bd53b7fec0013cee38105b17a24b14cdcfb99d13d7ecef48609c332808661cc2`。
  The most important record support routine is process. This routine determines what record processing means. Before the record speciﬁc “process” routine is called, the following has already been done:  • Decision to process a record.  • Check that record is not active, i.e. pact must be FALSE.  • Che
- Top 2，score 0.657891，`epics-documentation-latest-2026-08-18`，物理页 131～131，Chunk `epics-documentation-latest-2026-08-18:739a7deaade7e5daeddfc56509d5a4caebbfe1430968b172b32e5935123a54e5`。
  The PHAS field is used to order the processing of records that are scanned at the same time, i.e., records that are scanned periodically at the same interval and priority, or that are scanned on the same event. In this manner records dependent upon other records can be assured of using current data.
- Top 3，score 0.655905，`epics-documentation-latest-2026-08-18`，物理页 155～155，Chunk `epics-documentation-latest-2026-08-18:3aa50ee0e33154a53feac250cb55f721d4d8081429fb0a01bf2fde8aad0dc098`。
  • dbPutLink: This routine sets the target field. Then, if the link includes the process passive flag PP it calls dbScanPassive to process the target record. dbPutLink is only called from record processing routines. If dbPutLink finds the record already active because of a dbPutField directed to this

**epics-reconnect**：What happens to Channel Access client connections when an IOC server crashes and restarts?

first_complete_rank：`4`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 1}`。

- Top 1，score 0.661581，`epics-documentation-latest-2026-08-18`，物理页 63～63，Chunk `epics-documentation-latest-2026-08-18:5ed27b152e619d65d23d7dde439604437d01c5a32afc94d6955004054543c138`。
  Once the process variables have been located, the Channel Access client issues connection requests for each IOC containing process variables the client uses. The connection request server, in the IOC, accepts the request and establishes a connection to the client. Each connection is managed by two s
- Top 2，score 0.655792，`epics-documentation-latest-2026-08-18`，物理页 272～272，Chunk `epics-documentation-latest-2026-08-18:4af60b2f84cfbea8a521efc33116a4b51630b46b8fabc29ad8c180705f746f52`。
  When connection is terminated all related resources MUST be freed. On the server side all channels including their requests MUST be destroyed (this includes all serverChannelIDs). On the client side all channels and their requests MUST be put to disconnected state and searching for channels initiate
- Top 3，score 0.651413，`epics-documentation-latest-2026-08-18`，物理页 372～372，Chunk `epics-documentation-latest-2026-08-18:9674d00e270d8ce8a78a66dec2f392946f4ec99acc832e69bdc3703568947a6c`。
  • The total number of connected clients is high. Each active socket requires dedicated mbufs for protocol control blocks, and for any data that might be pending in the operating system for transmission to Channel Access or to the network at a given instant. If you increase the vxWorks limit on the m

**epics-cli**：Which EPICS command-line tools read, write and continuously monitor the temperature:water PV?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.707612，`epics-documentation-latest-2026-08-18`，物理页 9～9，Chunk `epics-documentation-latest-2026-08-18:e54c3b94095ce47b2fe7086603836e77e824e58080ed40eb7c8a11e8b9340e99`。
  Ok, that is not very impressive, but at least you know that EPICS is installed correctly. So now let us try something more complex, which will hopefully suggest how EPICS works.  In whatever directory you like, prepare a file test.db that reads like  record(ai, "temperature:water") {  field(DESC, "W
- Top 2，score 0.698929，`epics-documentation-latest-2026-08-18`，物理页 10～10，Chunk `epics-documentation-latest-2026-08-18:c0da265bb4f2c732342b7343aa193602e5cd7cdab9710ef51c012ad87273b3be`。
  record(ai, "temperature:water") {  field(DESC, "Water temperature in Lab 10") field(MDEL, ".01") }  MDEL stands for Monitor Deadband. If you now run  softIoc -d test.db  with the new test.db file, you will see that camonitor reacts only to changes that are larger than 0.01.  This was just a simple e
- Top 3，score 0.682759，`epics-documentation-latest-2026-08-18`，物理页 39～39，Chunk `epics-documentation-latest-2026-08-18:300c553cd4aca7b87ee5057495092deadc6128f3a29dc6f1525580f56b22a689`。
  Change the line that says  VALID_BUILDS = Ioc  To  VALID_BUILDS = Host Ioc  This is needed in order to get caRepeater compiled, according to this source.  Recompile EPICS base  Now, we recompile EPICS base:  make clean uninstall make  Hopefully, we have everything in place to start developing our IO

**xfel-rf**：What RF frequency and nominal design energy are used by the European XFEL main linac?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.636557，`european-xfel-full-technical-design-report-2007`，物理页 35～35，Chunk `european-xfel-full-technical-design-report-2007:7e13f57b72ac322f75090022eb0585cd4b8431657cde96be98988995f7fec0f7`。
  The XFEL based on superconducting accelerator technology will make possible not only a jump in peak brilliance by ten orders of magnitude, but also an increase by five orders of magnitude in average brilliance. The LCLS and European XFEL projects are scheduled to start operation in 2009 and 2013, re
- Top 2，score 0.634058，`european-xfel-full-technical-design-report-2007`，物理页 311～311，Chunk `european-xfel-full-technical-design-report-2007:bb1d668369f1b1f466b854f6e42b1977575f704be26dd60e936cebb40a9197a4`。
  The only constraint is that the system assumes that the surface is flat. It is clear that, depending on the nature of the experiment, some methods of moving targets into position and monitoring their position relative to the focal plane of the XFEL and/or the optical laser systems will need to be de
- Top 3，score 0.630203，`european-xfel-full-technical-design-report-2007`，物理页 376～376，Chunk `european-xfel-full-technical-design-report-2007:a88dfd6995e1c22c618cb80aba4c3000a56ce212f4909c0fd533835576412d72`。
  during and after the dynamics; b) the monitoring of the electronic structure changes (by XANES) induced by the laser excitation and; c) the use of atomic ions as probe species, which are usually optically silent, but offer the great advantage of being free from internal modes, so only intermolecular

**xfel-normal-energy**：欧洲 XFEL 常规运行时电子束能量是多少，与最高设计能量有何区别？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.632905，`shine-accelerator-preliminary-design-report-2017`，物理页 188～188，Chunk `shine-accelerator-preliminary-design-report-2017:015b678ae3eeb30da6f3b8e67ff8a8c678589c9b3cdda22a13400caa5f6b67e9`。
  图3.3.4.1-35 FEL 辐射性能随着波荡器LATTICE 结构的变化。(a)12.4keV；(b)25keV。  4.1.5.2 电子束团参数灵敏性分析  FEL 输出性能完全取决于电子束团品质，图3.3.4.1-36 扫描了FEL-I 中  12.4keV 辐射的饱和功率以及增益长度随着电子束团参数的变化情况。可以看出，  电子束发射度和峰值流强在一定程度上可以相互补偿，这也为直线加速器的性能  指标带来一定的灵活性。  图3.3.4.1-36 FEL-I 辐射12.4keV 性能随着电子束团参数的变化  除此之外，电子束团能从目前1.5kA 提升到3.0kA，抑或从100pC 增加
- Top 2，score 0.622538，`shine-accelerator-preliminary-design-report-2017`，物理页 193～193，Chunk `shine-accelerator-preliminary-design-report-2017:8be003019d5fa5b88c879c1c747daba6790459100a7f38b513a906bf76cbacbf`。
  日本理化所的SACLA 装置束流能量为8GeV，束团重复频率为120Hz。早  期采用水平方向±0.53∘的水平方向冲击磁铁（kicker magnet）结合± 2.47∘的水  平偏转直流切割磁铁（DC septum magnet），实现± 3∘的水平偏转，当kicker 系统  关闭时，束流无偏转通往BL3 波荡器线，+3∘时，束流经过包含kicker 和septum  的dog-leg 偏转结构（即偏转-反向偏转），通往BL2 线，−3∘时则用作SPring8  的注入。然而当该装置运行在较高峰值流强（10kA）模式下，由于偏转时束流  受到相干同步辐射（CSR）效应的影响，束流发射度出
- Top 3，score 0.613303，`shine-accelerator-preliminary-design-report-2017`，物理页 322～322，Chunk `shine-accelerator-preliminary-design-report-2017:835d88bff1075ce44fb81c9d77fc57a3e79f88ea59067e025a3f6d45dbc5944d`。
  长度测量。其次，FEL 装置对束团长度测量的分辨率的最高要求在10fs 左右，  常规的频域测量方法，比如BPM 电极双频法难以达到如此高的长度分辨率。最  后，对于高重频的FEL 装置，基于束流反馈的需求，对束团长度测量要求有无  阻快速测量的能力，最快测量数据率为1MHz。  对于精确的束团长度测量，目前国际上可行的方案为横模偏转腔及零相位法。  二者的测量原理相似，可以达到的绝对测量精度在束团100fs 长时为10fs 左右。  同时，该方法可以测量束团的纵向切片参数，为FEL 装置必不可少的纵向测量  设备。当时，该方法为破坏性测量，同时需要额外的功率源及偏转腔或加速装置。  对于有反

**undulator-tuning**：How does a K-monochromator select radiation for tuning undulator segments?

first_complete_rank：`3`；groups_satisfied_at_k：`{'1': 0, '3': 1, '5': 1}`。

- Top 1，score 0.625665，`european-xfel-full-technical-design-report-2007`，物理页 230～230，Chunk `european-xfel-full-technical-design-report-2007:b9fdae8a32d61ccca8d7f370bd1c454e8ac3a39bbfcc63aa6258ccb027e1ac8d`。
  When an electron beam traverses an undulator, it emits radiation at the resonance wavelength λ=λu(1+Krms  2)/(2γ2). The laser-driven sinusoidal energy chirp produces a correlated frequency chirp of the resonant radiation δω/ω=2δγ/γ. After the undulator, the radiation is passed through a crystal mono
- Top 2，score 0.623576，`european-xfel-full-technical-design-report-2007`，物理页 360～360，Chunk `european-xfel-full-technical-design-report-2007:c72adb5b2ec1e30b3a6b3e9c6cf2f1bdcd46c169728e08e9d29238ad4d8e2693`。
  monochromator. For soft x-rays, the grating monochromator will have to be used to achieve the requested resolution. In selection of the optical elements of the monochromators great care has to be taken not to disturb the transverse coherence properties of the XFEL radiation.  X-ray optics requiremen
- Top 3，score 0.621529，`european-xfel-undulator-commissioning-spectrometer-cdr-2011`，物理页 3～3，Chunk `european-xfel-undulator-commissioning-spectrometer-cdr-2011:3d9cff81b154e116e2b45c608f54d696a9594d653cd3ae8b86626dff067a206a`。
  The commissioning spectrometer, also known as K-monochromator, is mainly used with spontaneous radiation and selects a narrow bandwidth of the x-ray photon beam in order to tune the undulator segments. This process is called photon beam-based alignment and will minimize the difference in the undulat

**xfel-mirror-angle**：Why was the grazing-incidence angle range of the SASE3 offset mirrors reduced?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.570500，`european-xfel-full-technical-design-report-2007`，物理页 642～642，Chunk `european-xfel-full-technical-design-report-2007:eba77248894c0bb8facf8d297c51ecc06631ea38682ccad8a18d9509d7171f25`。
  In summary, construction has been scheduled to meet the milestone of first beam through the linac 6.5 years after construction start. At this point in time, the first branch of beamlines with the SASE 1 undulator will also have been installed. As described in Chapter 8, beam commissioning will then 
- Top 2，score 0.565103，`european-xfel-full-technical-design-report-2007`，物理页 199～199，Chunk `european-xfel-full-technical-design-report-2007:5434e31a035fe625e93da573be9fa16d0521675a13fb8c565a8cd0982bd3d0a8`。
  SASE 3 uses the spent electron beam coming from SASE 1. Due to the SASE FEL process in SASE 1, the energy spread of the electron beam increases and is about 8 MeV at the entrance of SASE 3. The XFEL radiation parameters in Table 5.2.2 have been calculated for these parameters, and the saturation len
- Top 3，score 0.564576，`european-xfel-full-technical-design-report-2007`，物理页 246～246，Chunk `european-xfel-full-technical-design-report-2007:949d471755ee7b5458f31cd88f2da671db5a450b64255e8dc8a63a17071f7135`。
  Since the mirrors are always in the beam (except when perfect crystals are used instead, see Section 6.2.2.2), they must preserve the wave front of the incident radiation to allow proper focusing and to maintain the coherence properties of the FEL sources. Estimates of the mirror requirements are ge

**xfel-soft-mono**：Why did the soft X-ray monochromator change to a vertical in-line geometry?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.692286，`european-xfel-full-technical-design-report-2007`，物理页 310～310，Chunk `european-xfel-full-technical-design-report-2007:d215d63075d516b431e0756e368559f09bc8ce3310a809e9d9e08e1ec8c0f05b`。
  Higher harmonic content may be reduced to reasonable values using mirror cut-offs. Selection, however, requires spectral dispersion using gratings, i.e., for the soft x-ray regime, or very thin crystals in transmission geometry. Whereas the soft x-ray case has been investigated already, a separation
- Top 2，score 0.687040，`european-xfel-full-technical-design-report-2007`，物理页 272～272，Chunk `european-xfel-full-technical-design-report-2007:47619ca356555199a42b6b1e29ac239808597b192e8a9dde1c6ed6c1c672a5ce`。
  This is why it is necessary to develop techniques to measure the distortions of x-ray wave fronts in-situ. A precise knowledge of the wave fronts could then be a basis for learning about the properties of the source itself, to test and improve the optical components, and may even serve to compensate
- Top 3，score 0.681839，`european-xfel-full-technical-design-report-2007`，物理页 260～260，Chunk `european-xfel-full-technical-design-report-2007:95c3c437e4995d5070f36fe90b8fb4fe1ad851e41c5fefdabb41532e5eb16d01`。
  It can be seen that in the range from 0.1-0.4 nm, an attenuation of 104 is always feasible by adjusting the pressure. The same holds for the soft x-ray regime (0.4-6 nm), where an absorption length of 30 m is sufficient, see Figure 6.2.10(b.). To reduce the consumption of Xenon gas, a recirculation 

**xfel-bpm-types**：Which BPM pickup types provide standard and high-precision position measurements at European XFEL?

first_complete_rank：`1`；groups_satisfied_at_k：`{'1': 1, '3': 1, '5': 1}`。

- Top 1，score 0.641950，`european-xfel-standard-e-beam-diagnostics-linac2010`，物理页 1～1，Chunk `european-xfel-standard-e-beam-diagnostics-linac2010:ca586d4bb17b2f3b046c3ff7df9f0a5f4e983cd3f7185207b5c9e30543aef05e`。
  BEAM POSITION MONITOR SYSTEM The E-XFEL BPM system will be provided by a collaboration of PSI, CEA and DESY [5]. As listed in Table 2, there will be standard BPMs with moderate and precision BPMs with high resolution. The standard BPMs will be of the button type. Precision monitors will be different
- Top 2，score 0.623851，`european-xfel-standard-e-beam-diagnostics-linac2010`，物理页 1～1，Chunk `european-xfel-standard-e-beam-diagnostics-linac2010:0df8b81289a610d0fbcf7f8b40a9e248e311ecd3cbe8fd1449010957547d8edb`。
  Button BPMs will be the standard BPMs in E-XFEL. In the superconducting part they are rigidly connected to the quadrupoles (see Fig. 1) at the end of each accelerator module string [6].  Figure 1: Button BPM for the cryo-modules, already assembled to the superconducting quadrupole package of the PXF
- Top 3，score 0.619061，`european-xfel-standard-e-beam-diagnostics-linac2010`，物理页 2～2，Chunk `european-xfel-standard-e-beam-diagnostics-linac2010:92dae4dd6a54b38fbeda66d748394da4e0e8164519b8124c19f208d3b6fb6914`。
  Two types of cavity BPMs based on the development of T. Shintake for SCSS will be used [8]. Both types with a beam pipe diameter of 10 mm and 40.5 mm, respectively, as shown in Fig. 2, consist of a reference and dipole resonator. The cross talk between the two resonators was measured to be very low 

**shine-ioc-management**：How are IOC and PV information managed in SHINE?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.656236，`shine-epics-ioc-pv-information-management-pcapac2022`，物理页 2～2，Chunk `shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355`。
  Figure 5: PV Service Architecture. To be specific, the operation process of PV Service is divided into three stages: register, scanning and updating. First of all, necessary scripts (Figure 6) are embedded into the startup shell (st.cmd) in order to obtain the information of the IOC, such as the ins
- Top 2，score 0.643854，`shine-epics-ioc-pv-information-management-pcapac2022`，物理页 3～3，Chunk `shine-epics-ioc-pv-information-management-pcapac2022:1932c96141925c86a65dfa6e099ba4ccedb9d73bc4a8de6a17d5d405d2544981`。
  The IOC panel as shown in Figure 8 will display not only the running information of the IOC, but also all the records included in the IOC. The information of the IOC includes the installation path, the startup time, epics ca server port, epics ca repeater port, running status, the number of con-nect
- Top 3，score 0.641802，`shine-epics-ioc-pv-information-management-pcapac2022`，物理页 1～1，Chunk `shine-epics-ioc-pv-information-management-pcapac2022:ee367f0a36287d1f95b22845d0f2103fb4b0cd22ef4421024730762fe0ed6d60`。
  The control system involves heterogeneous equipment and interfaces with a number of different subsystems. Several IOCs will be deployed in one server, in which hundreds of PVs perform real-world I/O and local control tasks. But we suffer from a lack of high level tools to centrally manage all the IO

**shine-ioc-startup**：SHINE 中 IOC 启动后会向管理系统提交哪些信息？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.666657，`shine-accelerator-control-system-design-presentation`，物理页 28～28，Chunk `shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996`。
  通道信息管理  \uf06e 完成通道信息管理软件核心模块开发  \uf06e 将控制系统中的IOC信息、Record信息纳入数据库管理  \uf06e 所有IOC的静态信息（地址、端口、...），状态信息（连接、...）  \uf06e 所有Record的名称、类型、域定义情况，以及访问权限、合法性等  软件著作权登记 数据库设计
- Top 2，score 0.621306，`shine-accelerator-control-system-design-presentation`，物理页 10～10，Chunk `shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9`。
  \uf06eCSS是否是最合适的用户界面？  \uf06e全局网络环境下，一个IOC对应多少台设备最合理？  \uf06e虚拟化可以整合硬件资源，提高控制系统可靠性和稳定性；  IOC虚拟化占比多少最合适？  \uf06e控制系统存储容量多少最合理？  \uf06e是否需要异地容灾备份？  \uf06e控制系统是否需要持续集成 (Continue Integrate)？
- Top 3，score 0.583227，`shine-accelerator-control-system-design-presentation`，物理页 26～26，Chunk `shine-accelerator-control-system-design-presentation:e1c35529e291cca970425ed8236272f89c4baf39b52b11de0bb8516839d73add`。
  运行与开发环境  \uf06e 为整个控制系统提供运行环境  \uf06e 由服务器集群、存储设备、网络设备等组成  \uf06e 采用虚拟服务器和实体服务器相结合的方式  \uf06e 提供各类基础服务，如账号管理、文件管理、时间同步等  \uf071\uf020软件开发管理  \uf073\uf020开发过程记录与控制  \uf073\uf020开发流程优化与简化  \uf071\uf020通道信息管理  \uf073\uf020通道信息采集与存储  \uf073\uf020通道状态监控与管理  \uf071\uf020通道权限管理  \uf073\uf020通道访问权限管理  \uf07

**interlock-latency**：SHINE 快联锁对单节点和节点间的响应时间分别有什么要求？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.736094，`shine-accelerator-fast-interlock-2024`，物理页 7～7，Chunk `shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量
- Top 2，score 0.726798，`shine-accelerator-fast-interlock-2024`，物理页 8～8，Chunk `shine-accelerator-fast-interlock-2024:edd3cf33739f6a91d0e07b8563181b17dba2b9beafabe69c85ae292a1a0eb052`。
  核 技 术 2024, 47: 120203  单节点平均响应时间为328.81 ns，节点间经800 m 电缆连接的系统平均响应时间为5.33 µs，均优于快 联锁系统的设计指标。系统运行模式的设置和传输 功能正常，各站点在不同模式下相应联锁逻辑切换 等功能也已通过测试并投入正常运行。SHINE加速 器快联锁系统功能完善，运行稳定正常，满足系统的 设计要求。  作者贡献声明 于春蕾负责联锁系统的整体设计、 需求对接、运行模式设计和实现、快联锁系统的设计 与开发，并负责数据的收集和整理、文章的起草和最 终版本的修订；陈广花负责研究的提出及设计，样机 的搭建和测试；丁建国负责系统设计的指导和监督
- Top 3，score 0.687768，`shine-accelerator-control-system-design-presentation`，物理页 21～21，Chunk `shine-accelerator-control-system-design-presentation:4e92201c2cf375a954b2860baf67a725b258f56b1a36a01b061e46d2775928dc`。
  联锁系统  \uf06e 快联锁 + 慢联锁；主站 + 从站，分层设计  \uf0b2快联锁关键信号响应时间：  站内≤10us，站间≤100us  \uf0b2慢联锁关键信号响应时间：  站内≤20ms，站间≤100ms

**interlock-platform**：横河 FPIO 快联锁模块使用哪种 FPGA 芯片和开发语言？

first_complete_rank：`2`；groups_satisfied_at_k：`{'1': 0, '3': 2, '5': 2}`。

- Top 1，score 0.733792，`shine-accelerator-fast-interlock-2024`，物理页 2～2，Chunk `shine-accelerator-fast-interlock-2024:568004790ecec62325207c734c8249811e0ba0c6f1da6fac206316dcbe9e20a5`。
  SHINE 联锁系统采用“成熟的硬件板卡+完全 自主开发联锁功能软件”的系统方案，确定了基于横 河FPIO（Field Programmable High-speed IO）模块的 快联锁开发方案。FPIO 模块是在横河FA-M3/e-RT3的基础上安装和使用的高功能I/O模块，具备µs 级的IO 响应时间，其结构图如图2 所示。模块内置 FPGA，允许用户在模块中开发和编译FPGA 功能， 开放用户自主开发用户逻辑回路。模块共有24 个 LED 灯，可指定任意信号显示；每个模块支持24 路 输入和24路的输出（5~24 V）。  SHINE直线段的机柜需要直接安装在加速器隧 道内，机柜规格只
- Top 2，score 0.717186，`shine-accelerator-fast-interlock-2024`，物理页 3～3，Chunk `shine-accelerator-fast-interlock-2024:3989f77d1ed901e922429b49a72751dc4b71b50fb0267e5c7a8fe005090a5120`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  系统的工艺和供电问题，并且缩减了快联锁系统所 需的安装空间，和慢联锁系统在硬件结构和外观上 可结合为一个“整体”。FPIO 模块内置的FPGA 使 用的是Xilinx 公司的Spartan6 XC6SLX25 系列芯 片，其开发和设计流程遵循FPGA开发的通用流程。 模块带有编程口，通过转接线缆和JTAG 编程线缆 可连接计算机，实现与Xilinx 的工具包ISE Design  Suite 的连接。BSP（Board Support Program）板级支 持软件提供了部分可调用的接口模块和功能。在此 基础上，使用硬件描述性语言可以实现联锁
- Top 3，score 0.675657，`shine-accelerator-fast-interlock-2024`，物理页 3～3，Chunk `shine-accelerator-fast-interlock-2024:a5b7baa31dd6b7e2bccef2a847deb913b96aac8381844a10f7aa0d1ea5b4ac6a`。
  在快联锁FPGA 逻辑程序开发过程中，需要配 置和定义系统自主的userlogic.h 头文件，将需要与 CPU之间进行数据交互的寄存器在此文件中进行地 址和变量的声明，在此基础上通过读写接口模块的 开发和调用，在CPU端即可通过梯形图读写头文件 中相应地址的寄存器数值。  图3 快联锁与慢联锁系统总体结构图 Fig.3 General architecture of fast interlock system and slow interlock system  SHINE的远程控制系统使用加速器主流的分布 式控制软件EPICS（Experimental Physics and Indust

**shine-control-layers**：How are the functional layers of the SHINE control system separated?

first_complete_rank：`5`；groups_satisfied_at_k：`{'1': 0, '3': 2, '5': 5}`。

- Top 1，score 0.653739，`european-xfel-full-technical-design-report-2007`，物理页 209～209，Chunk `european-xfel-full-technical-design-report-2007:5e738036d53984cc1ef444f5253831b66bc85c66ff7bf00dfcc9caf901ed7549`。
  • the whole undulator system must be in a very well controlled temperature environment. The impact of this requirement on the tunnel layout and air conditioning system will be discussed in Section 7.2.3;  • the geometric tolerances have a strong impact on the mechanical design and requirements on th
- Top 2，score 0.653032，`shine-control-system-status-icalepcs2019`，物理页 1～1，Chunk `shine-control-system-status-icalepcs2019:f79189e6eca2f8c7b31f8b61b01a7cec9e5f60c1573d880ba71c7b9bd1fb5269`。
  According to the experience of SSRF and SXFEL, the control system of SHINE will be mainly based on EPICS (Experimental Physics and Industrial Control System) to reach the balance between the high performance and costs of maintenance. EPICS is a set of open source software tools, libraries and applic
- Top 3，score 0.650358，`european-xfel-full-technical-design-report-2007`，物理页 110～110，Chunk `european-xfel-full-technical-design-report-2007:29a037c3dcebd6100462bc1c4b21f2ee8670f79193c9d81229ff6df5e49da139`。
  The goal for the FEL control system is the fully automated operation of the large number of sub-systems. One of the most complex sub-systems is the RF control system. The automation will be implemented in the framework of a Finite State Machine (FSM) which is a well established industrial standard. 

**cryo-integration**：How do PLCs and soft IOCs divide control and PV acquisition in the SHINE cryogenic system?

first_complete_rank：`4`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 1}`。

- Top 1，score 0.768869，`shine-cryogenic-control-system-2021`，物理页 2～2，Chunk `shine-cryogenic-control-system-2021:55733903164b8ee4afabc462a61675562f353392a107ea7197073d19f170219a`。
  The control system is aimed to implement all devices control and integerates them all. For each sub cryogenic system, refrigerator cold box will be purchased from the vendor-ALAT Company, which performs the cryogenic plant control through Siemens PLCs, mainly model is S7–1500, Profinet and WinCC sof
- Top 2，score 0.753573，`shine-cryogenic-control-system-2021`，物理页 3～3，Chunk `shine-cryogenic-control-system-2021:dc9209656bee7d707ce4a9aa99decbe6d273e92adaa818e32eb92fd25774fe02`。
  designed scalable, the whole system will be easy to expand based on technical verifica-tion after TFCS station construction.  Control system overview The cryogenic control system for SHINE is designed to clarifying subsystems including helium compressors, refrigerators, auxiliary subsystems, distrib
- Top 3，score 0.742021，`shine-cryogenic-control-system-2021`，物理页 5～5，Chunk `shine-cryogenic-control-system-2021:a37dd15743657d159ae85b687f49f0dd0bbba8c8b8c22db16e6bf195f9fdb2ba`。
  Device control The SIEMENS Distribution Control System (DCS) offers the software TIA Portal to be used in all PLC stations. These include configuration software, control software, advanced process control software, GUI software for remote computer and local touch panel. Almost all actuators, sensors

**cryo-interlock**：SHINE 低温测试装置如何通过主联锁 PLC 和 CPLD 实现低温设备保护？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.595310，`shine-accelerator-preliminary-design-report-2017`，物理页 277～277，Chunk `shine-accelerator-preliminary-design-report-2017:338c3be071bf2a8399235ffed40dad15708f2233eb7307fba06d901fda6a4bfe`。
  温系统的运行参数，对系统的运行状态进行监测，并为系统诊断提供数据。监测  功能包括：腔体、冷屏、支撑、低温管道等的温度；压缩机、室温泵机组、储气  罐、超导腔低温槽、杜瓦、低温传输管道等的压力；进出传输管道、压缩机、热  交换器、低温槽等的液/气流量；低温槽、杜瓦和液氮罐中的液位；压缩机、室  温泵机组、制冷机的工作状态；高频腔加载前后的工作状态等等。  低温控制系统的核心控制器件选择西门子PLC300 及扩展模块，结构如图  3.3.5.3-7 所示。包含过程量：温度、压力、液位及流量等；被控元件：加热器、  调节阀、电磁开关阀等；控制模式：顺序控制模式、PID 控制模式。上位机：工  控电
- Top 2，score 0.581085，`shine-accelerator-preliminary-design-report-2017`，物理页 274～274，Chunk `shine-accelerator-preliminary-design-report-2017:e0ca574b494f83092f3ce6afede8491d2e46262ccb0c0be04e1409c5064b788c`。
  ③粗纯化：若原料气氦气纯度较低，可将被回收的氦气采用纯化器进行常  温初步提纯后储存，以便进行集中纯化。  ④全自动控制，实现远程监控、无人值守等。  图3.3.5.3-5 氦气回收与纯化装置流程图  （3）液氮系统  液氮系统主要为氦制冷机系统的冷箱提供预冷冷源，为各种低温阀箱、超导  设备恒温器及氦低温多通道管线等的80K 冷屏提供冷源。主要设备包括：液氮  储罐、液氮相分离器和液氮低温传输管线等。  （4）低温测控系统  低温监测和控制系统是保证低温系统安全运行的关键，在低温系统的各个部  位，安装各种传感器，建立完整的控制系统，对超导腔以及低温系统的运行状态，  如温度、压力、流量、液
- Top 3，score 0.564384，`shine-accelerator-preliminary-design-report-2017`，物理页 275～275，Chunk `shine-accelerator-preliminary-design-report-2017:21b232f02dc5f3a7fa5d135d3d3eecff84a3029c7dd7ccf6328ceed6cb0f7389`。
  和常温系统等。不同的温度对测量系统的要求也不同，随着温度降低，选用的传  感器要求也会更高。  图3.3.5.3-6 低温测控系统划分示意图  5.3.3.1 主要测量元件选型  为了实施对低温系统的控制，需要及时掌握整个低温系统的工作状况，即需  要测量各部分的温度、压力、流量和液位等参数，根据这些参数及时调整各个阀  门的开闭状态，从而实现对整个低温系统的自动化控制。  （1）温度测量  根据温度等级、精度要求等的不同，温度传感器可有三种选择：  铂电阻温度计:测量温度范围77K-325K，抗磁场特性一般，带2 点标定曲线，  低于70K 标定曲线会整体浮动，因此低于70K 测量不够精确，

**timing-wrtd**：Why is standard White Rabbit Trigger Distribution insufficient for the SHINE beam-synchronous trigger rate?

first_complete_rank：`4`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 1}`。

- Top 1，score 0.717403，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 1～1，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:044f7bc2b3e46bebdd43195cac2d05a60087e6df478e1a3f889082ae9933217e`。
  SHINE project requires precise distribution and synchronization of the 1.003086 MHz (1300 MHz/1296) timing signals over a long distance of about 3.1 km. The beam-synchronous trigger signal distribution is the basic and pri-ority function.  The standard White Rabbit network operates at 125/62.5 MHz c
- Top 2，score 0.688535，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 1～1，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:4130d7f7a5a0075429ebf878b5cad8e5ea4bc1f88e55073b291a4246ffc3c3af`。
  Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE) is under construction. SHINE requires precise distribution and synchronization of the 1.003086 MHz timing signals over a long distance of about 3.1 km. Two prototype systems were developed, both containing three functions: beam-sy
- Top 3，score 0.668856，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 5～5，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:5879a5df7a404004e785919b91dd6ed0b5b9e5aad5b28fc47aef33de08461a2c`。
  CONCLUSION The timing system is currently under construction. Two prototype systems were developed, both containing three functions: beam-synchronous trigger signal distribution, random-event trigger signal distribution and data exchange between multiple nodes. The non-standard clock transmission wa

**timing-jitter**：What beam-synchronous and random-event trigger jitter was measured for SHINE timing Prototype II?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.666973，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 1～1，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:044f7bc2b3e46bebdd43195cac2d05a60087e6df478e1a3f889082ae9933217e`。
  SHINE project requires precise distribution and synchronization of the 1.003086 MHz (1300 MHz/1296) timing signals over a long distance of about 3.1 km. The beam-synchronous trigger signal distribution is the basic and pri-ority function.  The standard White Rabbit network operates at 125/62.5 MHz c
- Top 2，score 0.639967，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 4～4，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:df1ac099cc83fb10f4001f877ceeb64c78cb684c8e02c27cbfd259f8bec6b246`。
  For the beam-synchronous trigger signal distribution, the jitter between the output of slave node and the external reference signal is less than 10ps (RMS). The jitter between the outputs from different slave nodes is less than 5ps (RMS). The temperature drift test results are shown in the Fig. 10. 
- Top 3，score 0.639614，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 1～1，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:4130d7f7a5a0075429ebf878b5cad8e5ea4bc1f88e55073b291a4246ffc3c3af`。
  Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE) is under construction. SHINE requires precise distribution and synchronization of the 1.003086 MHz timing signals over a long distance of about 3.1 km. Two prototype systems were developed, both containing three functions: beam-sy

**control-slow-interlock**：SHINE 控制系统设计中慢联锁的站内和站间响应时间指标是什么？

first_complete_rank：`1`；groups_satisfied_at_k：`{'1': 1, '3': 1, '5': 1}`。

- Top 1，score 0.778265，`shine-accelerator-control-system-design-presentation`，物理页 21～21，Chunk `shine-accelerator-control-system-design-presentation:4e92201c2cf375a954b2860baf67a725b258f56b1a36a01b061e46d2775928dc`。
  联锁系统  \uf06e 快联锁 + 慢联锁；主站 + 从站，分层设计  \uf0b2快联锁关键信号响应时间：  站内≤10us，站间≤100us  \uf0b2慢联锁关键信号响应时间：  站内≤20ms，站间≤100ms
- Top 2，score 0.717592，`shine-accelerator-fast-interlock-2024`，物理页 8～8，Chunk `shine-accelerator-fast-interlock-2024:edd3cf33739f6a91d0e07b8563181b17dba2b9beafabe69c85ae292a1a0eb052`。
  核 技 术 2024, 47: 120203  单节点平均响应时间为328.81 ns，节点间经800 m 电缆连接的系统平均响应时间为5.33 µs，均优于快 联锁系统的设计指标。系统运行模式的设置和传输 功能正常，各站点在不同模式下相应联锁逻辑切换 等功能也已通过测试并投入正常运行。SHINE加速 器快联锁系统功能完善，运行稳定正常，满足系统的 设计要求。  作者贡献声明 于春蕾负责联锁系统的整体设计、 需求对接、运行模式设计和实现、快联锁系统的设计 与开发，并负责数据的收集和整理、文章的起草和最 终版本的修订；陈广花负责研究的提出及设计，样机 的搭建和测试；丁建国负责系统设计的指导和监督
- Top 3，score 0.710922，`shine-accelerator-fast-interlock-2024`，物理页 7～7，Chunk `shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量

**shine-compressors**：为什么 SHINE 的两级磁压缩分别布置在 270 MeV 和约 2.1 GeV 位置？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.502994，`shine-accelerator-control-system-design-presentation`，物理页 6～6，Chunk `shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`。
  \uf06e Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE)  e-beam : 8 GeV Photon energy : 0.4 ～25 keV Pulse duration : 1～100 fs Repetition : 1 MHz Total length : 3.1 km Underground ~ 29 m  SHINE
- Top 2，score 0.497280，`shine-accelerator-preliminary-design-report-2017`，物理页 197～197，Chunk `shine-accelerator-preliminary-design-report-2017:c3dd78611920f09598f129f0e4d5216575f790c1d9508f8e77d478270a26468c`。
  图3.3.4.2-3 束流偏转线总体布局图  经过直线加速器加速后的束流，传输至直线加速器出口前120 米处开始进入  束流分配段，此处开始往后25 米是LTU2 偏转线的Kicker 系统。LTU2 偏转线  的水平偏转部分是由包括DC Lamberson Septum 在内的四块水平偏转磁铁，以及  若干四极磁铁构成的Dog-leg 偏转结构，总体偏转角度为3˚，水平偏移距离为  1.85 米。其中，DC Lamberson Septum 与一块水平偏转磁铁及两者之间的三块四  极磁铁构成所谓对称双弯铁消色散结构，即Double-Bend-Achromat(DBA)。另两  块水平偏转磁铁
- Top 3，score 0.496506，`shine-accelerator-preliminary-design-report-2017`，物理页 193～193，Chunk `shine-accelerator-preliminary-design-report-2017:8be003019d5fa5b88c879c1c747daba6790459100a7f38b513a906bf76cbacbf`。
  日本理化所的SACLA 装置束流能量为8GeV，束团重复频率为120Hz。早  期采用水平方向±0.53∘的水平方向冲击磁铁（kicker magnet）结合± 2.47∘的水  平偏转直流切割磁铁（DC septum magnet），实现± 3∘的水平偏转，当kicker 系统  关闭时，束流无偏转通往BL3 波荡器线，+3∘时，束流经过包含kicker 和septum  的dog-leg 偏转结构（即偏转-反向偏转），通往BL2 线，−3∘时则用作SPring8  的注入。然而当该装置运行在较高峰值流强（10kA）模式下，由于偏转时束流  受到相干同步辐射（CSR）效应的影响，束流发射度出

**shine-main-linac**：SHINE 初步设计中的主加速器采用什么工作模式，最终把电子加速到多少能量？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.664654，`shine-accelerator-control-system-design-presentation`，物理页 8～8，Chunk `shine-accelerator-control-system-design-presentation:6ef921c2c3cc45659c9744acd2df45838e9cbf0bce28f92d2d2dd8fcf1d5cf26`。
  控制系统设计、实施过程中的一些问题  （关于加速器控制工程的一些思考）
- Top 2，score 0.663262，`shine-accelerator-control-system-design-presentation`，物理页 6～6，Chunk `shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`。
  \uf06e Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE)  e-beam : 8 GeV Photon energy : 0.4 ～25 keV Pulse duration : 1～100 fs Repetition : 1 MHz Total length : 3.1 km Underground ~ 29 m  SHINE
- Top 3，score 0.654379，`shine-accelerator-control-system-design-presentation`，物理页 14～14，Chunk `shine-accelerator-control-system-design-presentation:f7ab778c51869e4f0c3013020278027e9f046b4b61540c73a840b9990c7895b0`。
  \uf06e一流的装置，需要一流的、数量可观的控制队伍；  \uf06e人员缺口大、招聘难度大、培养周期长，结构不合理；  \uf06e如何充分发挥现有的人员力量？  \uf06e项目之间如何优化配比？  \uf06e如何建立有效的国内、国际合作？

**no-answer-finance**：What was NVIDIA quarterly revenue in fiscal 2026 Q4?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.532777，`european-xfel-full-technical-design-report-2007`，物理页 60～60，Chunk `european-xfel-full-technical-design-report-2007:7dd41e10ce5d1d1b50a9789a49518b7f331ec41799c2b2c180a680db66c36ddb`。
  the electrons up to 120 MeV; and a series of focusing and diagnostic equipment to ensure the necessary beam quality (low emittance, low energy spread, etc.) which is extremely important for the whole XFEL operation. The total length of the injector is about 66 m, after which the electrons are delive
- Top 2，score 0.525171，`european-xfel-full-technical-design-report-2007`，物理页 601～601，Chunk `european-xfel-full-technical-design-report-2007:ce49c337856d07ee1aec2cae6d87222b0650f913c5b37777ec1156f34dcf0b64`。
  [7-9] S. Claudet, Recent Progress in Power Refrigeration Below 2 K for superconducting Accelerators, Invited paper at Particle Accelerator Conference, Knoxville,USA, 2005.  [7-10] H. Quack, A. Kutschbach, Über die Möglichkeit des Umbaus der HERA-Kälteanlage für TESLA, internal report DESY/TU Dresden
- Top 3，score 0.524322，`european-xfel-full-technical-design-report-2007`，物理页 183～183，Chunk `european-xfel-full-technical-design-report-2007:40ec82a68043c09e6182347f0deab0b602e45d640e734af13104364b891ecd98`。
  [4-50] V. Katalev, S. Choroba, RF Power Distributing Waveguide System for TESLA, Proceedings of the Russian Particle Accelerator Conference, Rupac 2002, Obninsk, Russia, October 1-4, (2002,) 79.  [4-51] V. Katalev, S. Choroba, Tuning of External Q and Phase for the Cavities of a Superconducting Line

**no-answer-recipe**：如何制作四川麻婆豆腐？请给出食材和烹饪步骤。

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.410210，`epics-documentation-latest-2026-08-18`，物理页 126～126，Chunk `epics-documentation-latest-2026-08-18:ebfe588441802edc6a6c48105c79817767ccb66a9a9275ef84f0c603ad4e5de5`。
  menu(menuScan) {  choice(menuScanPassive,"Passive") choice(menuScanEvent,"Event") choice(menuScanI_O_Intr,"I/O Intr") choice(menuScan10_second,"10 second") choice(menuScan5_second,"5 second") choice(menuScan2_second,"2 second") choice(menuScan1_second,"1 second") choice(menuScan_5_second,".5 second"
- Top 2，score 0.379097，`epics-application-developers-guide-r3-16-2`，物理页 215～215，Chunk `epics-application-developers-guide-r3-16-2:fe4f4569217eadb1fcd1fe8239476fa4a90d18cac9544c595b9744aa901ef0be`。
  These routines should only be used for DCT_MENU and DCT_MENUFORM ﬁelds. Thus they should only be called if dbFindField, dbFirstField, or dbNextField has returned success and the ﬁeld type is DCT_MENU or DCT_MENUFORM.  14.10.1 Get Number of Menu Choices  int dbGetNMenuChoices(DBENTRY *pdbentry);  Thi
- Top 3，score 0.367365，`epics-application-developers-guide-r3-16-2`，物理页 250～250，Chunk `epics-application-developers-guide-r3-16-2:435e9e2fb4cc3ff1a10aa38fb3eefb1396e733c06dac069c39ddba5fcf9b2ca9`。
  17.2.4 PRIO - Scheduling Priority  This ﬁeld can be used by any software component that needs to specify a scheduling priority. The Event and I/O event scan types use this ﬁeld.  17.3 Scan Related Software Components  17.3.1 menuScan.dbd  This ﬁle holds the deﬁnition of the menu used by the ﬁeld SCA

**no-answer-token**：zxqv9999unlistedcalibrationartifact

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.465289，`european-xfel-full-technical-design-report-2007`，物理页 534～534，Chunk `european-xfel-full-technical-design-report-2007:a0381a1d25758ec1a36018e9a1d18000f7e3aab454494b553415bfb0b73cd64d`。
  During the construction phase, the shaft XSE serves as target shaft for the drilling of the tunnel XTL and as emergency exit. During the installation and operation phases, the shaft is used to gain access to the injector tunnel XTIN, the accelerator tunnel XTL and as emergency exit. In addition it i
- Top 2，score 0.447349，`european-xfel-full-technical-design-report-2007`，物理页 448～448，Chunk `european-xfel-full-technical-design-report-2007:c782965d9c0f21def70caf5aba3e1ff74c973eed422c37698e3626cfeccb94fe`。
  Detector signals were computed for a test sample of a CPMV, with labelling of nanoclusters of Gold [6-381]. This may be an early test sample for LCLS and XFEL experiments. The atomic coordinates of the virus capsid (1NY7) were obtained from the EMBL-EBI Macromolecular Structure Database [6-382]. The
- Top 3，score 0.445490，`european-xfel-full-technical-design-report-2007`，物理页 391～391，Chunk `european-xfel-full-technical-design-report-2007:251c63d479e8878839a70e163f77686554aeb54ff96c4e2669d9628280c0fc36`。
  Ultrafast electron diffraction (UED), on the other hand, can probe chemical reactions in the gas phase with 1 ps resolution, but the strong scattering of electrons makes is difficult to use UED in condensed matter, which is an important drawback since most biological and industrial processes take pl

**no-answer-hard-live-pv**：SHINE 在 2026-10-19 10:00 UTC 的 temperature:water PV 实时读数是多少？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.602203，`shine-accelerator-control-system-design-presentation`，物理页 6～6，Chunk `shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`。
  \uf06e Shanghai HIgh repetition rate XFEL aNd Extreme light facility (SHINE)  e-beam : 8 GeV Photon energy : 0.4 ～25 keV Pulse duration : 1～100 fs Repetition : 1 MHz Total length : 3.1 km Underground ~ 29 m  SHINE
- Top 2，score 0.580403，`epics-documentation-latest-2026-08-18`，物理页 9～9，Chunk `epics-documentation-latest-2026-08-18:a7cea79623100df414ec81d17f2bc3815c6ee8056a5d45f5f9853372edfe1cf6`。
  your prompt> caget temperature:water temperature:water 0 your prompt> caget temperature:water.DESC temperature:water.DESC Water temperature in the fish tank your prompt> caput temperature:water 21 Old : temperature:water 0 New : temperature:water 21 your prompt> caput temperature:water 24 Old : temp
- Top 3，score 0.571745，`european-xfel-x-ray-optics-beam-transport-tdr-2012`，物理页 123～123，Chunk `european-xfel-x-ray-optics-beam-transport-tdr-2012:4305ba7626e6fdba1462e7fba0e152d48d3b5e5900306efeb50010f209a60867`。
  XFEL.EU TR-2012-006 December 2012 TDR: X-Ray Optics and Beam Transport 123 of 164  7 Further beamline components  Apertures  To separate the FEL beam from the non-lasing part of the undulator  spectrum, spontaneous radiation apertures (SRAs) were presented  conceptually in CDR2011. In the meantime, 

**no-answer-hard-live-ioc-count**：How many SHINE IOCs are online at 10:00 UTC on 19 October 2026?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.612546，`european-xfel-full-technical-design-report-2007`，物理页 352～352，Chunk `european-xfel-full-technical-design-report-2007:407efd4216fbef5280537e8dadffa608b6fa6d2015d403f035a76b9a6163ce76`。
  A time domain method, such as XPCS, can address such processes as has been shown in recent prototype experiments [6-191, 6-192]. Here, fluctuations about the average intensity can be quantified by means of a two time (t1, t2) intensity correlation function.  [ ] [ ]  1/2 2 2 2 2 1/2 2 1 1 2  2 1 2 1
- Top 2，score 0.610590，`european-xfel-full-technical-design-report-2007`，物理页 53～53，Chunk `european-xfel-full-technical-design-report-2007:b04ed97afdca714495e14059fb03746b8f4e33ca7b0512433b3bcd4692c74ebb`。
  Figure 2.3.9 Example of mean photon pulse energies (averaged over the last eight hours) recorded during three days of a SASE run at 25.6 nm wavelength. On 20-21 May. 10 µJ level of SASE has been delivered to users. On the afternoon of 21 May. SASE intensity has been retuned to the higher level by th
- Top 3，score 0.608568，`european-xfel-full-technical-design-report-2007`，物理页 34～34，Chunk `european-xfel-full-technical-design-report-2007:30a02296f88ef166a986f711739f9cb413ad4ffad22d318a3fde9bd7f8bb8c4f`。
  After many years of development, efforts to produce saturated lasing using a SASE FEL started to come to fruition at the start of this century. In September 2000, a group at Argonne National Laboratory (ANL) demonstrated saturation in a visible (390 nm) SASE FEL [1-14]. In March 2001, the VISA colla

**no-answer-hard-live-interlock**：SHINE 快联锁在 2026-10-19 10:00 UTC 的在线许可状态是什么？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.679349，`shine-accelerator-fast-interlock-2024`，物理页 8～8，Chunk `shine-accelerator-fast-interlock-2024:edd3cf33739f6a91d0e07b8563181b17dba2b9beafabe69c85ae292a1a0eb052`。
  核 技 术 2024, 47: 120203  单节点平均响应时间为328.81 ns，节点间经800 m 电缆连接的系统平均响应时间为5.33 µs，均优于快 联锁系统的设计指标。系统运行模式的设置和传输 功能正常，各站点在不同模式下相应联锁逻辑切换 等功能也已通过测试并投入正常运行。SHINE加速 器快联锁系统功能完善，运行稳定正常，满足系统的 设计要求。  作者贡献声明 于春蕾负责联锁系统的整体设计、 需求对接、运行模式设计和实现、快联锁系统的设计 与开发，并负责数据的收集和整理、文章的起草和最 终版本的修订；陈广花负责研究的提出及设计，样机 的搭建和测试；丁建国负责系统设计的指导和监督
- Top 2，score 0.662601，`shine-accelerator-control-system-design-presentation`，物理页 21～21，Chunk `shine-accelerator-control-system-design-presentation:4e92201c2cf375a954b2860baf67a725b258f56b1a36a01b061e46d2775928dc`。
  联锁系统  \uf06e 快联锁 + 慢联锁；主站 + 从站，分层设计  \uf0b2快联锁关键信号响应时间：  站内≤10us，站间≤100us  \uf0b2慢联锁关键信号响应时间：  站内≤20ms，站间≤100ms
- Top 3，score 0.640989，`shine-accelerator-fast-interlock-2024`，物理页 7～7，Chunk `shine-accelerator-fast-interlock-2024:d2ab5cd0a91201b20562f80d3ce16cbeacef90e16d40a6f457108cf507b3efac`。
  于春蕾等： SHINE加速器快联锁系统设计与开发  图7 SHINE联锁子站现场图 Fig.7 The sub-station site photographs of interlock system  图8 电子枪段的联锁界面截图 Fig.8 Snapshot of the interface of interlock system for  electron gun  5.2 响应时间测试  在单节点快联锁系统响应测试中，随机选择1 路快联锁模块的输入通道作为测试通道，另外一个 测试通道为节点经过联锁逻辑运算后的输出信号， 采用示波器测量输入信号上升沿和输出信号下降沿 之间的相对延时，测量

**no-answer-hard-live-cryo**：What is the measured SHINE helium refrigerator outlet pressure at 10:00 UTC on 19 October 2026?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.622377，`european-xfel-full-technical-design-report-2007`，物理页 35～35，Chunk `european-xfel-full-technical-design-report-2007:ec06d09152a99a845adc547564cbc75f9804d402fda7a793f6c230e43c9e0167`。
  In September 2001, the VUV-FEL at DESY demonstrated lasing to saturation at 98 nm [1-16]. In January 2002, saturation was achieved at 82 nm [1-17], and in November 2005 the lasing at 26 nm, the shortest wavelength at which any FEL works, was demonstrated. Recently, the German government, encouraged 
- Top 2，score 0.620161，`european-xfel-full-technical-design-report-2007`，物理页 34～34，Chunk `european-xfel-full-technical-design-report-2007:30a02296f88ef166a986f711739f9cb413ad4ffad22d318a3fde9bd7f8bb8c4f`。
  After many years of development, efforts to produce saturated lasing using a SASE FEL started to come to fruition at the start of this century. In September 2000, a group at Argonne National Laboratory (ANL) demonstrated saturation in a visible (390 nm) SASE FEL [1-14]. In March 2001, the VISA colla
- Top 3，score 0.603853，`european-xfel-full-technical-design-report-2007`，物理页 301～301，Chunk `european-xfel-full-technical-design-report-2007:821179831c2c08e6ade685b4978423a244996660ebbe2dd65e6ddd2b0abc89ea`。
  I. Warm dense matter experiments  As we saw, in Figure 6.4.9, it will be possible to create samples in the WDM regime, away from the shock Hugoniot. More importantly, they will be uniform well-defined samples. With monitoring of the incident, scattered and transmitted energy, we will obtain a measur

**no-answer-hard-deployed-firmware**：What exact firmware build SHA was installed on the SHINE White Rabbit master on 19 October 2026?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.587377，`european-xfel-full-technical-design-report-2007`，物理页 530～530，Chunk `european-xfel-full-technical-design-report-2007:82ac6013ae84f92112762a9c8cfb330e5a8e44b6a619661b3da09b776f7e2047`。
  The tunnel and shaft buildings will be realised in a depth from 12 m up to 44 m below the surface. The foundation of the buildings will, thus, be situated below the groundwater table and the buildings will lie up to 20 m inside the groundwater.  The tunnels will most probably be constructed using a 
- Top 2，score 0.586719，`european-xfel-full-technical-design-report-2007`，物理页 582～582，Chunk `european-xfel-full-technical-design-report-2007:f129343a5d4e2be94f7de191ddf26f42e092bccf0d4e2670ebd6b08a44320657`。
  This task will be followed by the installation of the basic infrastructure: the smoke exhaust pipe, the fire protection walls, emergency guidance rail, communication services and the support rail for the survey equipment.  Next, the installation of the I-beams to suspend the linac components from th
- Top 3，score 0.579935，`shine-white-rabbit-beam-synchronous-timing-ipac2022`，物理页 1～1，Chunk `shine-white-rabbit-beam-synchronous-timing-ipac2022:ba766f7f8c0d6e793404658c9a19fe163f5bc70682882cea214a82635c32bc9e`。
  SHINE timing system is design to provide precise clock pulses (Trigger) for drive laser, low-level RF, solid state amplifiers, kicker, beam and optical instruments, etc. It will ensure the electron beam is generated and accelerated to the design energy, to produce the free electron laser, while comp

**no-answer-hard-current-ioc-ip**：SHINE IOC 在 2026-10-19 10:00 UTC 使用的实时 server IP 完整清单是什么？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.636554，`epics-documentation-latest-2026-08-18`，物理页 445～445，Chunk `epics-documentation-latest-2026-08-18:cde051b3c617e8ccaadccffc4d663dae0a8ffa198312b12d490d5ab017af0665`。
  Server to Client CA_PROTO_CLEAR_CHANNEL (response) 00 0c 00 00 00 00 00 00 00 00 00 04 00 00 00 01 12 0 0 0 4 1  1.43.18 Glossary of Terms  IOC  Input/Output Controller.  PV  Process variable.  Virtual circuit  Reusable TCP connection between client and server, through which all PVs hosted by the se
- Top 2，score 0.632082，`shine-accelerator-control-system-design-presentation`，物理页 10～10，Chunk `shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9`。
  \uf06eCSS是否是最合适的用户界面？  \uf06e全局网络环境下，一个IOC对应多少台设备最合理？  \uf06e虚拟化可以整合硬件资源，提高控制系统可靠性和稳定性；  IOC虚拟化占比多少最合适？  \uf06e控制系统存储容量多少最合理？  \uf06e是否需要异地容灾备份？  \uf06e控制系统是否需要持续集成 (Continue Integrate)？
- Top 3，score 0.629728，`shine-epics-ioc-pv-information-management-pcapac2022`，物理页 3～3，Chunk `shine-epics-ioc-pv-information-management-pcapac2022:1932c96141925c86a65dfa6e099ba4ccedb9d73bc4a8de6a17d5d405d2544981`。
  The IOC panel as shown in Figure 8 will display not only the running information of the IOC, but also all the records included in the IOC. The information of the IOC includes the installation path, the startup time, epics ca server port, epics ca repeater port, running status, the number of con-nect

**no-answer-hard-live-bpm-calibration**：What measured BPM calibration constant was approved at SHINE on 19 October 2026?

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.555934，`european-xfel-full-technical-design-report-2007`，物理页 34～34，Chunk `european-xfel-full-technical-design-report-2007:30a02296f88ef166a986f711739f9cb413ad4ffad22d318a3fde9bd7f8bb8c4f`。
  After many years of development, efforts to produce saturated lasing using a SASE FEL started to come to fruition at the start of this century. In September 2000, a group at Argonne National Laboratory (ANL) demonstrated saturation in a visible (390 nm) SASE FEL [1-14]. In March 2001, the VISA colla
- Top 2，score 0.540322，`european-xfel-undulator-commissioning-spectrometer-cdr-2011`，物理页 4～4，Chunk `european-xfel-undulator-commissioning-spectrometer-cdr-2011:9447150694203e53043d613d27a310695270f4e4e4269c7937223deb7621f89f`。
  May 6, 2011 page 1/10 Wolfgang Freund / WP74 ! Photon Diagnostics  The European XFEL Undulator Commissioning  Spectrometer  Conceptual Design Review  Document 3: Requirements & Interface Definition  March 29, 2011  Amended version after CDR meeting from Dec. 2010  (Author: W. Freund)  (Review: J. Gr
- Top 3，score 0.528369，`european-xfel-full-technical-design-report-2007`，物理页 48～48，Chunk `european-xfel-full-technical-design-report-2007:74d2002f695c6fc5b3d41604af4cc90369f9fd8e78aafbb350971c9c27e9c225`。
  Based on the experience from commissioning the TTF FEL, Phase 1 and using similar methods and tools (in particular an MCP detector), first lasing could be established at 32 nm already one week after the first passage of the electron beam through the undulator. Single shot spectra were in agreement w

**no-answer-hard-live-beam-energy**：SHINE 在 2026-10-19 10:00 UTC 实际测量的电子束能量是多少？

first_complete_rank：`None`；groups_satisfied_at_k：`{'1': 0, '3': 0, '5': 0}`。

- Top 1，score 0.557204，`shine-accelerator-preliminary-design-report-2017`，物理页 322～322，Chunk `shine-accelerator-preliminary-design-report-2017:835d88bff1075ce44fb81c9d77fc57a3e79f88ea59067e025a3f6d45dbc5944d`。
  长度测量。其次，FEL 装置对束团长度测量的分辨率的最高要求在10fs 左右，  常规的频域测量方法，比如BPM 电极双频法难以达到如此高的长度分辨率。最  后，对于高重频的FEL 装置，基于束流反馈的需求，对束团长度测量要求有无  阻快速测量的能力，最快测量数据率为1MHz。  对于精确的束团长度测量，目前国际上可行的方案为横模偏转腔及零相位法。  二者的测量原理相似，可以达到的绝对测量精度在束团100fs 长时为10fs 左右。  同时，该方法可以测量束团的纵向切片参数，为FEL 装置必不可少的纵向测量  设备。当时，该方法为破坏性测量，同时需要额外的功率源及偏转腔或加速装置。  对于有反
- Top 2，score 0.550720，`shine-accelerator-preliminary-design-report-2017`，物理页 188～188，Chunk `shine-accelerator-preliminary-design-report-2017:015b678ae3eeb30da6f3b8e67ff8a8c678589c9b3cdda22a13400caa5f6b67e9`。
  图3.3.4.1-35 FEL 辐射性能随着波荡器LATTICE 结构的变化。(a)12.4keV；(b)25keV。  4.1.5.2 电子束团参数灵敏性分析  FEL 输出性能完全取决于电子束团品质，图3.3.4.1-36 扫描了FEL-I 中  12.4keV 辐射的饱和功率以及增益长度随着电子束团参数的变化情况。可以看出，  电子束发射度和峰值流强在一定程度上可以相互补偿，这也为直线加速器的性能  指标带来一定的灵活性。  图3.3.4.1-36 FEL-I 辐射12.4keV 性能随着电子束团参数的变化  除此之外，电子束团能从目前1.5kA 提升到3.0kA，抑或从100pC 增加
- Top 3，score 0.549435，`shine-accelerator-preliminary-design-report-2017`，物理页 127～127，Chunk `shine-accelerator-preliminary-design-report-2017:c1f30cffb2aa65c4f9d61c4dcddf68cb686545b31913a8060ef158182016b4bf`。
  图3.3.3.3-28 BPM 输出波形信号 图3.3.3.3-29 BPM 输出频谱信号  图3.3.3.3-30 束团电荷量1nC 时其通过Cold BPM 能量损失  考虑要求测量束团单次通过BPM 时的位置，也就是电子学带宽不小于2/T0，  则带宽不小于2.6MHz，实际的电子学带宽可适当增加，如100MHz。从图  3.3.3.3-29 可知，初步选定的工作频率0.5GHz 处的信号幅度为80μV/MHz@100pC,  而热噪音幅度为0.92μV/MHz@50Ω&300K。由于信号为相干叠加，热噪音为非  相干叠加，对束团电荷量10pC 的情况，该BPM100MHz 带宽内输出信

## 检索资格

```json
{
  "config": {
    "replacement_ratio": 0.2,
    "minimum_replacements": 8
  },
  "total_chunks": 4537,
  "eligible_chunks": 4532,
  "ineligible_chunks": 5,
  "ineligible_by_reason": {
    "number_or_running_code_only": 1,
    "boilerplate_only": 1,
    "mostly_replacement_chars": 3
  },
  "per_document_ineligible": {
    "epics-application-developers-guide-r3-16-2": 1,
    "shine-accelerator-control-system-design-presentation": 1,
    "shine-accelerator-preliminary-design-report-2017": 3
  },
  "examples": [
    {
      "chunk_id": "epics-application-developers-guide-r3-16-2:83952420e3325ba044ceac4be733ac659d90591227e5934991a794f1eb9c9ee1",
      "document_id": "epics-application-developers-guide-r3-16-2",
      "page": 2,
      "text": "2",
      "eligible": false,
      "reasons": [
        "number_or_running_code_only"
      ],
      "effective_characters": 1,
      "effective_tokens": 1,
      "replacement_ratio": 0.0
    },
    {
      "chunk_id": "shine-accelerator-control-system-design-presentation:3bbcf79edceead55ba4ebb0cc291b2f6f3a4243f699a87b882fa5d02566647b4",
      "document_id": "shine-accelerator-control-system-design-presentation",
      "page": 34,
      "text": "谢 谢",
      "eligible": false,
      "reasons": [
        "boilerplate_only"
      ],
      "effective_characters": 2,
      "effective_tokens": 2,
      "replacement_ratio": 0.0
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:2119956386059a9909003e07de59e3a5401a2bb3b6f29432d66c690cd54e776b",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "page": 308,
      "text": "图3.3.6.1-30 束流倾角入射示意图\n\n对整个腔体长度进行积分，得到束流倾角入射时在腔体内激发的信号如下所\n\n示：\n\n��= A\n\n−�\n\n2\n\n� 2 ����� න �−\n\n�+ � �����\n\n2� �����+ � �����\n\n��\n\n�\n\n=\n\n�����\n\n� �−\n\n�\n\n2� −�\n\n2\n\n� 2 � ׬ �−\n\n� �����\n\n2� ��������\n\n��\n\n�����+ ��������\n\n��\n\n����� dz\n\n当条件2   时，即腔体谐振信号周期远小于衰减时间常数时，积分项内当z\n\n从-L/2 到L/2，�\n\n�\n\n−�����\n\n2�项结果均近似为1，因此可简化成：\n\n��≈\n\n�����\n\n� �−\n\n�\n\n2� −�\n\n2\n\n� 2 � ׬ ��������\n\n��\n\n����� dz\n\n= �����\n\n� �−�\n\n2������ 2�2���2� �2 ��� �� 2�����−������ � ��� �� 2�����\n\n由此可知，当束流倾角从腔体中心入射时，激励信号的相位与位置偏移信号\n\n在相位上相差90°，令 p v v  即为倾角为θ时的等效束流偏移量，仿真结果如\n\n图3.3.6.1-31 所示：",
      "eligible": false,
      "reasons": [
        "mostly_replacement_chars"
      ],
      "effective_characters": 195,
      "effective_tokens": 184,
      "replacement_ratio": 0.40389294403892945
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:9f2ae54d8aa5a8d641ea3cc6ca033c924a41bde166fe3c6b20ef8ebbff264dea",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "page": 310,
      "text": "��= A �−������−�\n\n2�������� �\n\n图3.3.6.1-33 束流倾角入射示意图\n\n对整个腔体长度L 进行积分，得到：\n\n��= A\n\n−�\n\n2\n\n� 2 ����� න �−\n\n�+ � �����\n\n2� �����+ � �����\n\n��\n\n�\n\n= �����\n\n� �−�\n\n2������ 2�2���2� �2 ��� �� 2�����−������ � ��� �� 2�����\n\n−�����\n\n�\n\n2����� � ��� �� 2������−� 2������\n\n从公式中可知此种情况下分解成了两部分，第一部分和公式（7）相同，等\n\n效成束流按倾角θ经过腔体中心的结果。第二项对比公式（4），可等效看成在经\n\n过腔体过程中偏离电中心距离为：\n\n�= �����\n\n�\n\n2����� � ��� �� 2�����\n\n当腔体参数以及倾角θ确定时，等效偏移量与m 成正比，第一项、第二项\n\n的影响分别如图3.3.6.1-34、3.3.6.1-35 所示，两项和的影响如图3.3.6.1-36 所示：",
      "eligible": false,
      "reasons": [
        "mostly_replacement_chars"
      ],
      "effective_characters": 190,
      "effective_tokens": 175,
      "replacement_ratio": 0.38917525773195877
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:f82b231d3421be698e7f2b56a0199e8a7bedc5d6db1f664bda04d9d1abb0d3ee",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "page": 312,
      "text": "倾角带来的影响。模型可如图3.3.6.1-37 所示并假设束团呈高斯分布：\n\n图3.3.6.1-37 束团自身倾角入射模型\n\n设束团长度为 z ，束团电荷量为q ，束团自身倾角为，等效结果可视为\n\n将束团分割成一组组带电量为dq 的电子沿z 轴分布，则每组电子的位置偏移量\n\n为�tan �假设束团呈高斯分布，则有：\n\n��= q\n\n2π�� �\n\n−�2\n\n2��2��\n\n结合此前公式，则有：\n\n���= ω\n\n2 � ����\n\n( �\n\n�)0�\n\n−�2��2\n\n�2 �tan (�)\n\n�0\n\n�−�\n\n2�sin ωt ��\n\n= �tan (�)\n\n2��� ��\n\n−�2\n\n2��2�−� 2�sin ωt ��\n\n积分得：\n\n��= �tan (�)\n\n2��� −∞\n\n+∞\n\n��\n\n−�2\n\n2��2�− �−�\n\n� 2� sin ω �−�\n\n� �� න\n\n= �tan (�)\n\n2��� �−�\n\n2�\n\n−��\n\n+��\n\n��\n\n−�2\n\n2��2�−� 2��sin ω �−� � �� න\n\n≈�ωσ�\n\n2����\n\n2��� �−�\n\n2������\n\n由此可知，当束团自身存在倾角时，激励信号的相位与位置偏移信号在相位\n\n上也相差90°，令 p v v  即束团倾角为α时的等效束流偏移量，仿真结果如图\n\n3.3.6.1-38 所示：",
      "eligible": false,
      "reasons": [
        "mostly_replacement_chars"
      ],
      "effective_characters": 273,
      "effective_tokens": 233,
      "replacement_ratio": 0.25164113785557984
    }
  ]
}
```

## Dense 输入审计

```json
{
  "model_max_seq_length": 512,
  "total_chunks": 4532,
  "chunks_exceeding_limit": 376,
  "percentage_exceeding_limit": 8.296557811120918,
  "token_length_distribution": {
    "count": 4532,
    "min": 8,
    "max": 1193,
    "mean": 339.421226831421,
    "p10": 158.0,
    "p25": 243.0,
    "median": 339.0,
    "p75": 401.0,
    "p90": 481.9000000000001,
    "p95": 619.0
  },
  "input_template": "document_title + \"\\n\" + chunk.text",
  "special_tokens_included": true,
  "by_language": {
    "en": {
      "total_chunks": 4004,
      "chunks_exceeding_limit": 76,
      "percentage_exceeding_limit": 1.898101898101898,
      "token_length_distribution": {
        "count": 4004,
        "min": 8,
        "max": 1029,
        "mean": 311.495004995005,
        "p10": 156.0,
        "p25": 234.0,
        "median": 328.0,
        "p75": 386.0,
        "p90": 424.0,
        "p95": 453.0
      }
    },
    "zh": {
      "total_chunks": 528,
      "chunks_exceeding_limit": 300,
      "percentage_exceeding_limit": 56.81818181818182,
      "token_length_distribution": {
        "count": 528,
        "min": 28,
        "max": 1193,
        "mean": 551.1950757575758,
        "p10": 238.70000000000005,
        "p25": 399.5,
        "median": 551.0,
        "p75": 708.5,
        "p90": 849.3,
        "p95": 921.9499999999999
      }
    }
  },
  "by_document": {
    "epics-application-developers-guide-r3-16-2": {
      "total_chunks": 847,
      "chunks_exceeding_limit": 11,
      "percentage_exceeding_limit": 1.2987012987012987,
      "token_length_distribution": {
        "count": 847,
        "min": 14,
        "max": 591,
        "mean": 310.827626918536,
        "p10": 151.60000000000002,
        "p25": 244.0,
        "median": 332.0,
        "p75": 384.5,
        "p90": 419.79999999999995,
        "p95": 449.69999999999993
      }
    },
    "epics-documentation-latest-2026-08-18": {
      "total_chunks": 1071,
      "chunks_exceeding_limit": 15,
      "percentage_exceeding_limit": 1.4005602240896358,
      "token_length_distribution": {
        "count": 1071,
        "min": 8,
        "max": 785,
        "mean": 300.47058823529414,
        "p10": 143.0,
        "p25": 218.0,
        "median": 320.0,
        "p75": 375.0,
        "p90": 411.0,
        "p95": 439.5
      }
    },
    "european-xfel-full-technical-design-report-2007": {
      "total_chunks": 1730,
      "chunks_exceeding_limit": 43,
      "percentage_exceeding_limit": 2.485549132947977,
      "token_length_distribution": {
        "count": 1730,
        "min": 45,
        "max": 1029,
        "mean": 323.428323699422,
        "p10": 178.9,
        "p25": 246.0,
        "median": 333.5,
        "p75": 394.0,
        "p90": 432.0,
        "p95": 460.54999999999995
      }
    },
    "european-xfel-standard-e-beam-diagnostics-linac2010": {
      "total_chunks": 13,
      "chunks_exceeding_limit": 0,
      "percentage_exceeding_limit": 0.0,
      "token_length_distribution": {
        "count": 13,
        "min": 231,
        "max": 433,
        "mean": 349.53846153846155,
        "p10": 246.4,
        "p25": 306.0,
        "median": 366.0,
        "p75": 405.0,
        "p90": 419.2,
        "p95": 426.4
      }
    },
    "european-xfel-undulator-commissioning-spectrometer-cdr-2011": {
      "total_chunks": 41,
      "chunks_exceeding_limit": 0,
      "percentage_exceeding_limit": 0.0,
      "token_length_distribution": {
        "count": 41,
        "min": 49,
        "max": 442,
        "mean": 299.8780487804878,
        "p10": 129.0,
        "p25": 165.0,
        "median": 363.0,
        "p75": 402.0,
        "p90": 416.0,
        "p95": 430.0
      }
    },
    "european-xfel-x-ray-optics-beam-transport-tdr-2012": {
      "total_chunks": 235,
      "chunks_exceeding_limit": 7,
      "percentage_exceeding_limit": 2.978723404255319,
      "token_length_distribution": {
        "count": 235,
        "min": 46,
        "max": 998,
        "mean": 279.91063829787237,
        "p10": 72.0,
        "p25": 134.5,
        "median": 306.0,
        "p75": 397.0,
        "p90": 427.0,
        "p95": 477.6999999999998
      }
    },
    "shine-accelerator-control-system-design-presentation": {
      "total_chunks": 33,
      "chunks_exceeding_limit": 0,
      "percentage_exceeding_limit": 0.0,
      "token_length_distribution": {
        "count": 33,
        "min": 49,
        "max": 304,
        "mean": 146.12121212121212,
        "p10": 72.4,
        "p25": 102.0,
        "median": 142.0,
        "p75": 179.0,
        "p90": 216.4,
        "p95": 255.79999999999995
      }
    },
    "shine-accelerator-fast-interlock-2024": {
      "total_chunks": 18,
      "chunks_exceeding_limit": 9,
      "percentage_exceeding_limit": 50.0,
      "token_length_distribution": {
        "count": 18,
        "min": 146,
        "max": 832,
        "mean": 505.6111111111111,
        "p10": 264.40000000000003,
        "p25": 328.25,
        "median": 480.0,
        "p75": 698.0,
        "p90": 779.0,
        "p95": 828.6
      }
    },
    "shine-accelerator-preliminary-design-report-2017": {
      "total_chunks": 477,
      "chunks_exceeding_limit": 291,
      "percentage_exceeding_limit": 61.0062893081761,
      "token_length_distribution": {
        "count": 477,
        "min": 28,
        "max": 1193,
        "mean": 580.9392033542977,
        "p10": 316.40000000000003,
        "p25": 444.0,
        "median": 569.0,
        "p75": 725.0,
        "p90": 863.2,
        "p95": 926.4
      }
    },
    "shine-control-system-status-icalepcs2019": {
      "total_chunks": 15,
      "chunks_exceeding_limit": 0,
      "percentage_exceeding_limit": 0.0,
      "token_length_distribution": {
        "count": 15,
        "min": 103,
        "max": 391,
        "mean": 294.53333333333336,
        "p10": 225.2,
        "p25": 243.5,
        "median": 298.0,
        "p75": 352.5,
        "p90": 373.59999999999997,
        "p95": 387.5
      }
    },
    "shine-cryogenic-control-system-2021": {
      "total_chunks": 22,
      "chunks_exceeding_limit": 0,
      "percentage_exceeding_limit": 0.0,
      "token_length_distribution": {
        "count": 22,
        "min": 109,
        "max": 389,
        "mean": 281.8181818181818,
        "p10": 187.8,
        "p25": 242.5,
        "median": 288.0,
        "p75": 334.0,
        "p90": 362.9,
        "p95": 365.85
      }
    },
    "shine-epics-ioc-pv-information-management-pcapac2022": {
      "total_chunks": 13,
      "chunks_exceeding_limit": 0,
      "percentage_exceeding_limit": 0.0,
      "token_length_distribution": {
        "count": 13,
        "min": 136,
        "max": 420,
        "mean": 299.84615384615387,
        "p10": 188.0,
        "p25": 253.0,
        "median": 310.0,
        "p75": 364.0,
        "p90": 412.0,
        "p95": 418.8
      }
    },
    "shine-white-rabbit-beam-synchronous-timing-ipac2022": {
      "total_chunks": 17,
      "chunks_exceeding_limit": 0,
      "percentage_exceeding_limit": 0.0,
      "token_length_distribution": {
        "count": 17,
        "min": 170,
        "max": 430,
        "mean": 322.70588235294116,
        "p10": 222.8,
        "p25": 280.0,
        "median": 338.0,
        "p75": 381.0,
        "p90": 406.40000000000003,
        "p95": 426.0
      }
    }
  },
  "worst_examples": [
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:6e251109ac6ee8d2fc408437dcac42659de59087508ca43e997b24a96dcadd8a",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 3,
      "token_count": 1193,
      "would_truncate": true,
      "truncated_token_count": 681,
      "truncation_ratio": 0.5708298407376362
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:a6b79c125757f570efcdbe4e588d21e7b0ffa55897114028d81f23f7ce938668",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 3,
      "token_count": 1188,
      "would_truncate": true,
      "truncated_token_count": 676,
      "truncation_ratio": 0.569023569023569
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:c24c2c3bf0a30c3329ecce491456d896dd00a0e92f4cc398e2013d5ab8594342",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 3,
      "token_count": 1174,
      "would_truncate": true,
      "truncated_token_count": 662,
      "truncation_ratio": 0.5638841567291312
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:2a0d825267f3533a4459cbf30a33c91a6b959b232e6708247bcb9433cfff4dfc",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 417,
      "token_count": 1070,
      "would_truncate": true,
      "truncated_token_count": 558,
      "truncation_ratio": 0.5214953271028038
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:2255eb3ca045e67ed7bbb0f140fadee8c01f16d92a4e0deb47ce59862afb5ea2",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 467,
      "token_count": 1037,
      "would_truncate": true,
      "truncated_token_count": 525,
      "truncation_ratio": 0.506268081002893
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:e258d014ab5ce1c685a1fa35a7388c4d63f68a446843fc0238dae13a3a0301df",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 30,
      "token_count": 1031,
      "would_truncate": true,
      "truncated_token_count": 519,
      "truncation_ratio": 0.5033947623666344
    },
    {
      "chunk_id": "european-xfel-full-technical-design-report-2007:d65e0a6703e3c4f8f68d9bf4d6213e48e0fea703ecdf72ba4a74e89cf9b320a2",
      "document_id": "european-xfel-full-technical-design-report-2007",
      "language": "en",
      "page": 3,
      "token_count": 1029,
      "would_truncate": true,
      "truncated_token_count": 517,
      "truncation_ratio": 0.5024295432458697
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:a74b8be0de8cb157f65a091724afb1776907a54ad0cd67f368acad39125bba5a",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 91,
      "token_count": 1025,
      "would_truncate": true,
      "truncated_token_count": 513,
      "truncation_ratio": 0.5004878048780488
    },
    {
      "chunk_id": "european-xfel-full-technical-design-report-2007:86d1be203091acdd3dbbf7a6904e23874092d6fdbfec0754924cd4af6810235b",
      "document_id": "european-xfel-full-technical-design-report-2007",
      "language": "en",
      "page": 4,
      "token_count": 1023,
      "would_truncate": true,
      "truncated_token_count": 511,
      "truncation_ratio": 0.4995112414467253
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:beb268b0c027406e26fb286a698ec1c4ba449ea3da492489301d65f9f82f747c",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 470,
      "token_count": 1016,
      "would_truncate": true,
      "truncated_token_count": 504,
      "truncation_ratio": 0.49606299212598426
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:bd09538f9d198dd4e1bd698b05af44693827296d411cd3bf3db45253ba70fb6c",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 441,
      "token_count": 1008,
      "would_truncate": true,
      "truncated_token_count": 496,
      "truncation_ratio": 0.49206349206349204
    },
    {
      "chunk_id": "european-xfel-full-technical-design-report-2007:7e00f5caf5678d12a8071f1c6b0b3c15c0126e48b2e79fa6f86a1dada9ea0e6b",
      "document_id": "european-xfel-full-technical-design-report-2007",
      "language": "en",
      "page": 5,
      "token_count": 1002,
      "would_truncate": true,
      "truncated_token_count": 490,
      "truncation_ratio": 0.48902195608782434
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:017a27f5fe60626900697bdd524b1555e93f1a2d6412a670248f43e0e60208d4",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 99,
      "token_count": 1002,
      "would_truncate": true,
      "truncated_token_count": 490,
      "truncation_ratio": 0.48902195608782434
    },
    {
      "chunk_id": "european-xfel-x-ray-optics-beam-transport-tdr-2012:8183ef46e215ce1b6c61de0543f82749e5fe721246cfcb215601d2c6d0900f50",
      "document_id": "european-xfel-x-ray-optics-beam-transport-tdr-2012",
      "language": "en",
      "page": 3,
      "token_count": 998,
      "would_truncate": true,
      "truncated_token_count": 486,
      "truncation_ratio": 0.48697394789579157
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:08c37ed5e923b9d3b2830c669877044871e2957db09ad2573b98d1b0869f2b23",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 392,
      "token_count": 996,
      "would_truncate": true,
      "truncated_token_count": 484,
      "truncation_ratio": 0.4859437751004016
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:7d63c9bac942094d94e39a58f2da12ab0ec73393db50b6c9b984085fe92ed037",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 190,
      "token_count": 989,
      "would_truncate": true,
      "truncated_token_count": 477,
      "truncation_ratio": 0.48230535894843274
    },
    {
      "chunk_id": "european-xfel-full-technical-design-report-2007:7a90ae3b437915fb0b2ba8ba1767676caad03cbd11b33ce4f930a5a0a43e6677",
      "document_id": "european-xfel-full-technical-design-report-2007",
      "language": "en",
      "page": 4,
      "token_count": 987,
      "would_truncate": true,
      "truncated_token_count": 475,
      "truncation_ratio": 0.48125633232016213
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:985bb2d6cc6ef1f9bf79def6d8182378db9665e135edc26661eb1709770024b0",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 404,
      "token_count": 987,
      "would_truncate": true,
      "truncated_token_count": 475,
      "truncation_ratio": 0.48125633232016213
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:f120b471561628212f00dd0ffc4b7ee83a8d5826be55cad6d87899f98d7036ed",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 110,
      "token_count": 976,
      "would_truncate": true,
      "truncated_token_count": 464,
      "truncation_ratio": 0.47540983606557374
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:ba784b2d81bb125cbf690b410c70652706e56235733207353d43abb4f953471f",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "language": "zh",
      "page": 375,
      "token_count": 972,
      "would_truncate": true,
      "truncated_token_count": 460,
      "truncation_ratio": 0.4732510288065844
    }
  ]
}
```

## Stage 2 对照

```json
{
  "comparability_note": "Stage 2 original page-level scores were mislabeled Recall; displayed here as historical Hit. They are not directly comparable to stricter complete-evidence Stage 2.5. Rejudged historical Top-5 below isolates judgment changes from ranking/index changes; no search or GT selection uses historical scores.",
  "stage_two_total_chunks": 4547,
  "stage_two_eligible_chunks": 4547,
  "stage_two_five_total_chunks": 4537,
  "stage_two_five_eligible_chunks": 4532,
  "bm25": {
    "stage_two_historical_page_judgment": {
      "Hit@1": 0.42857142857142855,
      "Hit@3": 0.7619047619047619,
      "Hit@5": 0.8095238095238095,
      "MRR@5": 0.6071428571428571
    },
    "stage_two_cached_top5_new_contract": {
      "count": 21,
      "Hit@1": 0.38095238095238093,
      "Hit@3": 0.6666666666666666,
      "Hit@5": 0.7142857142857143,
      "MRR@5": 0.5277777777777778,
      "interpretation": "diagnostic only",
      "answerable_query_count": 21,
      "no_answer_query_count": 3
    },
    "stage_two_five": {
      "count": 21,
      "Hit@1": 0.38095238095238093,
      "Hit@3": 0.6666666666666666,
      "Hit@5": 0.7142857142857143,
      "MRR@5": 0.5198412698412699,
      "interpretation": "diagnostic only",
      "answerable_query_count": 21,
      "no_answer_query_count": 11
    },
    "historical_to_current": {
      "fail_to_hit": [],
      "hit_to_fail": [
        "shine-ioc-management",
        "shine-control-layers"
      ]
    },
    "contract_change_on_same_rankings": {
      "fail_to_hit": [],
      "hit_to_fail": [
        "shine-ioc-management",
        "shine-control-layers"
      ]
    },
    "ranking_change_under_same_contract": {
      "fail_to_hit": [],
      "hit_to_fail": []
    }
  },
  "dense": {
    "stage_two_historical_page_judgment": {
      "Hit@1": 0.14285714285714285,
      "Hit@3": 0.42857142857142855,
      "Hit@5": 0.5714285714285714,
      "MRR@5": 0.29761904761904756
    },
    "stage_two_cached_top5_new_contract": {
      "count": 21,
      "Hit@1": 0.09523809523809523,
      "Hit@3": 0.19047619047619047,
      "Hit@5": 0.38095238095238093,
      "MRR@5": 0.18015873015873016,
      "interpretation": "diagnostic only",
      "answerable_query_count": 21,
      "no_answer_query_count": 3
    },
    "stage_two_five": {
      "count": 21,
      "Hit@1": 0.09523809523809523,
      "Hit@3": 0.19047619047619047,
      "Hit@5": 0.38095238095238093,
      "MRR@5": 0.18015873015873016,
      "interpretation": "diagnostic only",
      "answerable_query_count": 21,
      "no_answer_query_count": 11
    },
    "historical_to_current": {
      "fail_to_hit": [],
      "hit_to_fail": [
        "epics-cli",
        "shine-ioc-management",
        "cryo-interlock",
        "timing-jitter"
      ]
    },
    "contract_change_on_same_rankings": {
      "fail_to_hit": [],
      "hit_to_fail": [
        "epics-cli",
        "shine-ioc-management",
        "cryo-interlock",
        "timing-jitter"
      ]
    },
    "ranking_change_under_same_contract": {
      "fail_to_hit": [],
      "hit_to_fail": []
    }
  }
}
```

## Ground truth 可检索性

```json
{
  "queries": 32,
  "answerable": 21,
  "all_declared_alternatives_in_raw_and_eligible_chunks": true
}
```

## 索引

```json
{
  "embedding_model": "BAAI/bge-small-zh-v1.5",
  "dimension": 512,
  "query_template": "为这个句子生成表示以用于检索相关文章：{query}",
  "local_files_only": true,
  "collection": "knowledge_stage25",
  "qdrant_path": "tmp/stage-two-five-qdrant",
  "chunk_count": 4532,
  "unique_chunk_count": 4532,
  "point_count": 4532,
  "duplicate_count": 0,
  "embedded_chunk_count": 4532,
  "batch_size": 32
}
```

## 耗时

```json
{
  "parse_clean_chunk": 4.575536142001511,
  "corpus_audit": 0.7366080780011544,
  "bm25_build": 1.3212363209968316,
  "bm25_evaluation": 1.395038663999003,
  "model_load": 3.145781231996807,
  "embedding_seconds": 528.7332412810101,
  "qdrant_indexing_seconds": 10.157769997018477,
  "dense_evaluation": 1.3569360219989903,
  "evaluation_total": 2.751974685997993
}
```

## 限制

没有实现分数阈值。明显负例和领域负例分别记录；领域负例均为静态文档无法支持的指定时刻运行状态。公式损坏继续保留并审计，私用字符未做未验证映射。token 截断统计不等于已经证明截断是 Dense 失败原因。Stage 2 历史页级指标与新证据口径不可直接归因比较；另提供旧 Top-5 在新口径下的复判。

## 人工复核与执行验证

标注从原始 PDF 逐页复核，未按排名反向选择证据。全部 alternative 均通过 raw / eligible Chunk 验证。

| Query | 判断 | 组数 | 修改原因 |
|---|---|---:|---|
| epics-pp | all | 2 | Require both processing-before-input timing and PP/passive-SCAN condition. Reviewed raw physical 88; no ranking-based target selection. |
| epics-reconnect | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| epics-cli | all | 3 | Split read/write/monitor into three required groups; old partial excerpt did not prove all three commands. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| xfel-rf | all | 2 | Two required facts: 1.3 GHz and 20 GeV; raw physical 72 also explicitly states 1,300 MHz as a frequency alternative. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| xfel-normal-energy | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| undulator-tuning | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| xfel-mirror-angle | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| xfel-soft-mono | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| xfel-bpm-types | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| shine-ioc-management | all | 3 | Require CA/pvAccess PV collection/storage, IOC startup metadata registration, and MySQL-backed web display. Raw physical 1 reviewed without ranking-based target selection. |
| shine-ioc-startup | all | 2 | Require startup installation/time/list on physical 2 and address/CA ports/list on physical 3; a single partial list is not complete. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| interlock-latency | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| interlock-platform | all | 2 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| shine-control-layers | all | 5 | Require four-layer names and actual division of responsibilities (operator interfaces, runtime infrastructure, device IO, high-speed data). The old names-only excerpt did not establish complete functional separation. Raw physical 1 reviewed without consulting rankings. |
| cryo-integration | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| cryo-interlock | all | 3 | Require local DI/DO connection, master PLC logic/exchange, and CPLD optical/electric conversion; old CPLD-only excerpt was incomplete. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| timing-wrtd | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| timing-jitter | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| control-slow-interlock | all | 1 | Retain question and source; replace partial-word/context-heavy seed excerpt with complete factual evidence. Manually reviewed raw accepted page; all required facts retained, alternatives not exhaustive. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| shine-compressors | all | 1 | Replace header/location excerpt with explicit BC1 space-charge/wakefield and BC2 CSR/stability rationale; retain full question. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |
| shine-main-linac | all | 1 | Replace introductory facility-goal excerpt with explicit main-linac continuous-wave and final 8 GeV statement on physical 5. Reviewed before Stage 2.5 ranking; eligible-chunk containment is mandatory. |

### 领域负例核查

All 13 raw PDFs searched for the requested date and related domain terms; contextual passages and document chronology manually checked. Static nominal/design values do not answer specified-time live measurements. Verification records remain in query JSON. All hard negatives currently test temporal/live-data gaps, so coverage is narrow.

### 页眉与损坏样本

所查初设报告页眉 raw 出现于 470 页，Stage 2 实际索引含 470 个相关 Chunk，Stage 2.5 剩余 9 个。剩余为页眉与正文合并，未添加文件名或标题特例。

严重 U+FFFD 样本比例为 25.16%、38.92%、40.39%，下一名 8.70%。配置阈值 20% 处于统计间隔。原始损坏保留。

### 历史对照解释

New GT is stricter complete-evidence matching. Historical cached Top-5 rejudgment separately measures this contract effect. Every declared target remains in an eligible chunk: no judged evidence alternative was wholly removed by eligibility. Same-contract rank changes may reflect cleaning/index policy; no ablation isolates their individual contributions.

**bm25 同口径完整命中排名变化**

```json
[
  {
    "query_id": "interlock-latency",
    "stage_two_rejudged_rank": 2,
    "stage_two_five_rank": 3,
    "direction": "regressed"
  }
]
```

**dense 同口径完整命中排名变化**

```json
[]
```

### 限制与 Hybrid 条件

- 376 eligible inputs still exceed 512 tokens; 300/528 Chinese chunks are affected. No claim that tokenizer truncation is the sole cause of Dense failures.
- Directory dot leaders remain eligible and dominate maximum token examples; meaningful Chinese body also exceeds the limit.
- 9 combined header/body chunks still retain the reviewed running header.
- U+FFFD and unexplained PUA remain in the corpus; formulas are not reconstructed.
- 21 answerable judgments are seeded and nonexhaustive; slice counts are diagnostic only. Hard negatives cover a narrow temporal/live-state family.

Reproducible engineering prerequisites are present; do not treat input risks as eliminated. Recommend review and an isolated token-budget experiment before advancing to Hybrid. No Hybrid implementation in this stage.

### 验证

```json
{
  "point_count": 4532,
  "eligible_chunks": 4532,
  "duplicate_count": 0,
  "payload_citations_and_uuid_and_vector_dimension_norm_checked": true,
  "per_document_points": {
    "epics-documentation-latest-2026-08-18": 1071,
    "shine-accelerator-preliminary-design-report-2017": 477,
    "european-xfel-full-technical-design-report-2007": 1730,
    "epics-application-developers-guide-r3-16-2": 847,
    "european-xfel-undulator-commissioning-spectrometer-cdr-2011": 41,
    "shine-cryogenic-control-system-2021": 22,
    "shine-accelerator-fast-interlock-2024": 18,
    "european-xfel-x-ray-optics-beam-transport-tdr-2012": 235,
    "shine-epics-ioc-pv-information-management-pcapac2022": 13,
    "shine-accelerator-control-system-design-presentation": 33,
    "shine-white-rabbit-beam-synchronous-timing-ipac2022": 17,
    "shine-control-system-status-icalepcs2019": 15,
    "european-xfel-standard-e-beam-diagnostics-linac2010": 13
  },
  "historical_point_count": 4547,
  "first_and_final_real_index_count_equal": true,
  "protected_source_and_agent_files": 22,
  "protected_hashes_unchanged": true,
  "code_and_frozen_query_hashes_match_measurement": true,
  "commands": {
    "pytest -q": {
      "exit_code": 0,
      "stdout": "........................................................................ [ 46%]\n........................................................................ [ 93%]\n..........                                                               [100%]\n154 passed in 2.55s\n",
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
  }
}
```

## Stage 2 与 Stage 2.5 对照表

历史页级口径与当前证据口径不同。旧 Top-5 新口径复判行用于区分标注与排名变化。

| 检索器 / 判断口径 | 总 Chunk | 索引 Chunk | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|---:|
| bm25 / Stage 2 历史页级 | 4547 | 4547 | 0.4286 | 0.7619 | 0.8095 | 0.6071 |
| bm25 / Stage 2 旧排名 / 新契约 | 4547 | 4547 | 0.3810 | 0.6667 | 0.7143 | 0.5278 |
| bm25 / Stage 2.5 | 4537 | 4532 | 0.3810 | 0.6667 | 0.7143 | 0.5198 |
| dense / Stage 2 历史页级 | 4547 | 4547 | 0.1429 | 0.4286 | 0.5714 | 0.2976 |
| dense / Stage 2 旧排名 / 新契约 | 4547 | 4547 | 0.0952 | 0.1905 | 0.3810 | 0.1802 |
| dense / Stage 2.5 | 4537 | 4532 | 0.0952 | 0.1905 | 0.3810 | 0.1802 |

## Token 超限文档归属

| 文档 | eligible | 超限 | 超限比例 |
|---|---:|---:|---:|
| epics-application-developers-guide-r3-16-2 | 847 | 11 | 1.30% |
| epics-documentation-latest-2026-08-18 | 1071 | 15 | 1.40% |
| european-xfel-full-technical-design-report-2007 | 1730 | 43 | 2.49% |
| european-xfel-standard-e-beam-diagnostics-linac2010 | 13 | 0 | 0.00% |
| european-xfel-undulator-commissioning-spectrometer-cdr-2011 | 41 | 0 | 0.00% |
| european-xfel-x-ray-optics-beam-transport-tdr-2012 | 235 | 7 | 2.98% |
| shine-accelerator-control-system-design-presentation | 33 | 0 | 0.00% |
| shine-accelerator-fast-interlock-2024 | 18 | 9 | 50.00% |
| shine-accelerator-preliminary-design-report-2017 | 477 | 291 | 61.01% |
| shine-control-system-status-icalepcs2019 | 15 | 0 | 0.00% |
| shine-cryogenic-control-system-2021 | 22 | 0 | 0.00% |
| shine-epics-ioc-pv-information-management-pcapac2022 | 13 | 0 | 0.00% |
| shine-white-rabbit-beam-synchronous-timing-ipac2022 | 17 | 0 | 0.00% |

最严重 3 个样本是 SHINE 初设报告物理页 3 的目录，点线占据大量 token。最大 1193 tokens，截断 681 tokens（57.08%）。物理页 417 的正文也达到 1070 tokens，风险不限于目录。详细 chunk ID 见 embedding_input_audit.worst_examples。
