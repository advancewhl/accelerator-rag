# Day 7 Retrieval Baseline

## Experiment Setup

- Corpus chunks: 12
- Evaluation cases: 20
- Top-K: 3
- Dense retriever: BGE-small-zh-v1.5 + Qdrant cosine search
- Sparse retriever: BM25 baseline

# Case Results

## q001 [技术缩写]

**Question:** PV 是什么？

**Ground truth:** `epics-pv`

### Dense Top-K

- 1. `epics-pv` score=0.5650 — EPICS 中的过程变量 PV
- 2. `epics-cli` score=0.5080 — caget 与 caput
- 3. `epics-ca` score=0.4997 — Channel Access 通信

### BM25 Top-K

- 1. `epics-pv` score=2.2239 — EPICS 中的过程变量 PV
- 2. `epics-ca` score=1.8421 — Channel Access 通信
- 3. `epics-ioc` score=1.4338 — IOC 的主要职责

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q002 [中文同义表达]

**Question:** 什么叫过程变量？

**Ground truth:** `epics-pv`

### Dense Top-K

- 1. `epics-pv` score=0.6815 — EPICS 中的过程变量 PV
- 2. `rf-cavity` score=0.4473 — 射频腔的作用
- 3. `bpm-position` score=0.4077 — 束流位置监测器 BPM

### BM25 Top-K

- 1. `epics-pv` score=5.4530 — EPICS 中的过程变量 PV
- 2. `rf-cavity` score=1.8491 — 射频腔的作用

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q003 [语义改写]

**Question:** EPICS 中设备测量值、状态和设定值通常用什么表示？

**Ground truth:** `epics-pv`

### Dense Top-K

- 1. `epics-pv` score=0.6326 — EPICS 中的过程变量 PV
- 2. `epics-cli` score=0.5072 — caget 与 caput
- 3. `bpm-position` score=0.4855 — 束流位置监测器 BPM

### BM25 Top-K

- 1. `epics-pv` score=12.7682 — EPICS 中的过程变量 PV
- 2. `epics-opi` score=4.3168 — OPI 操作员界面
- 3. `epics-ca` score=2.8954 — Channel Access 通信

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q004 [英文精确术语]

**Question:** Process Variable

**Ground truth:** `epics-pv`

### Dense Top-K

- 1. `epics-pv` score=0.5336 — EPICS 中的过程变量 PV
- 2. `epics-cli` score=0.4667 — caget 与 caput
- 3. `epics-ioc` score=0.4250 — IOC 的主要职责

### BM25 Top-K

- 1. `epics-pv` score=4.3332 — EPICS 中的过程变量 PV

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q005 [定义问题]

**Question:** IOC 是什么，它主要负责什么？

**Ground truth:** `epics-ioc`

### Dense Top-K

- 1. `epics-ioc` score=0.7375 — IOC 的主要职责
- 2. `epics-cli` score=0.5127 — caget 与 caput
- 3. `epics-ca` score=0.5008 — Channel Access 通信

### BM25 Top-K

- 1. `epics-ca` score=4.2011 — Channel Access 通信
- 2. `epics-ioc` score=2.7663 — IOC 的主要职责
- 3. `epics-opi` score=1.8933 — OPI 操作员界面

**Evaluation:** Dense 第 1 名；BM25 第 2 名；本题排名结果：Dense

## q006 [长语义改写]

**Question:** 哪个组件负责运行 EPICS 数据库记录，并把记录字段作为 PV 提供给客户端？

**Ground truth:** `epics-ioc`

### Dense Top-K

- 1. `epics-ioc` score=0.6548 — IOC 的主要职责
- 2. `epics-pv` score=0.6276 — EPICS 中的过程变量 PV
- 3. `epics-ca` score=0.6172 — Channel Access 通信

### BM25 Top-K

- 1. `epics-ioc` score=17.9288 — IOC 的主要职责
- 2. `epics-ca` score=5.0676 — Channel Access 通信
- 3. `epics-opi` score=3.5428 — OPI 操作员界面

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q007 [技术缩写]

**Question:** OPI 是什么？

**Ground truth:** `epics-opi`

### Dense Top-K

- 1. `epics-opi` score=0.6280 — OPI 操作员界面
- 2. `epics-cli` score=0.4757 — caget 与 caput
- 3. `epics-ca` score=0.4710 — Channel Access 通信

### BM25 Top-K

- 1. `epics-opi` score=3.5793 — OPI 操作员界面
- 2. `epics-ca` score=2.2968 — Channel Access 通信
- 3. `epics-pv` score=0.7876 — EPICS 中的过程变量 PV

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q008 [自然语言改写]

**Question:** 运行人员通过什么图形界面查看设备状态、趋势曲线和报警？

**Ground truth:** `epics-opi`

### Dense Top-K

- 1. `epics-opi` score=0.5227 — OPI 操作员界面
- 2. `rag-boundary` score=0.4622 — 加速器 RAG 系统运行边界
- 3. `bpm-orbit` score=0.4318 — 束流轨道与 BPM

### BM25 Top-K

- 1. `epics-opi` score=15.8270 — OPI 操作员界面
- 2. `rag-boundary` score=3.8713 — 加速器 RAG 系统运行边界
- 3. `epics-pv` score=3.4689 — EPICS 中的过程变量 PV

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q009 [英文技术术语]

**Question:** Channel Access 是做什么的？

**Ground truth:** `epics-ca`

### Dense Top-K

- 1. `epics-ca` score=0.7137 — Channel Access 通信
- 2. `epics-ioc` score=0.5010 — IOC 的主要职责
- 3. `epics-cli` score=0.4515 — caget 与 caput

### BM25 Top-K

- 1. `epics-ca` score=6.9796 — Channel Access 通信
- 2. `epics-pv` score=0.8531 — EPICS 中的过程变量 PV
- 3. `epics-ioc` score=0.6311 — IOC 的主要职责

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q010 [精确技术词]

**Question:** camonitor 通过什么协议访问 PV？

**Ground truth:** `epics-ca`

### Dense Top-K

- 1. `epics-ca` score=0.6382 — Channel Access 通信
- 2. `epics-pv` score=0.4917 — EPICS 中的过程变量 PV
- 3. `epics-cli` score=0.4760 — caget 与 caput

### BM25 Top-K

- 1. `epics-ca` score=6.6777 — Channel Access 通信
- 2. `epics-pv` score=2.2993 — EPICS 中的过程变量 PV
- 3. `epics-opi` score=1.7491 — OPI 操作员界面

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q011 [命令行术语]

**Question:** caget 和 caput 分别有什么作用？

**Ground truth:** `epics-cli`

### Dense Top-K

- 1. `epics-cli` score=0.7231 — caget 与 caput
- 2. `epics-ioc` score=0.5049 — IOC 的主要职责
- 3. `epics-ca` score=0.4642 — Channel Access 通信

### BM25 Top-K

- 1. `epics-cli` score=4.1614 — caget 与 caput
- 2. `epics-ca` score=3.7190 — Channel Access 通信
- 3. `rf-cavity` score=2.4220 — 射频腔的作用

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q012 [自然语言改写]

**Question:** 哪个命令用于读取一个 PV 的当前值？

**Ground truth:** `epics-cli`

### Dense Top-K

- 1. `epics-cli` score=0.6155 — caget 与 caput
- 2. `epics-pv` score=0.5434 — EPICS 中的过程变量 PV
- 3. `epics-ioc` score=0.4345 — IOC 的主要职责

### BM25 Top-K

- 1. `epics-cli` score=11.4006 — caget 与 caput
- 2. `epics-pv` score=3.1559 — EPICS 中的过程变量 PV
- 3. `epics-ca` score=1.7523 — Channel Access 通信

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q013 [技术缩写]

**Question:** BPM 是什么？

**Ground truth:** `bpm-position`

### Dense Top-K

- 1. `bpm-position` score=0.5827 — 束流位置监测器 BPM
- 2. `bpm-orbit` score=0.5221 — 束流轨道与 BPM
- 3. `epics-ca` score=0.4778 — Channel Access 通信

### BM25 Top-K

- 1. `bpm-position` score=3.1240 — 束流位置监测器 BPM
- 2. `bpm-orbit` score=2.2752 — 束流轨道与 BPM
- 3. `epics-pv` score=0.7876 — EPICS 中的过程变量 PV

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q014 [自然语言改写]

**Question:** 哪个设备用来测量束流的横向位置？

**Ground truth:** `bpm-position`

### Dense Top-K

- 1. `bpm-position` score=0.6818 — 束流位置监测器 BPM
- 2. `bpm-orbit` score=0.6646 — 束流轨道与 BPM
- 3. `vacuum-pressure` score=0.5054 — 真空系统与压力监测

### BM25 Top-K

- 1. `bpm-position` score=7.5230 — 束流位置监测器 BPM
- 2. `bpm-orbit` score=7.0403 — 束流轨道与 BPM
- 3. `vacuum-pressure` score=3.3722 — 真空系统与压力监测

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q015 [关系理解]

**Question:** 多个 BPM 的位置测量结果组合起来可以得到什么？

**Ground truth:** `bpm-orbit`

### Dense Top-K

- 1. `bpm-orbit` score=0.6701 — 束流轨道与 BPM
- 2. `bpm-position` score=0.6323 — 束流位置监测器 BPM
- 3. `mba-emittance` score=0.4770 — MBA 晶格与低发射度

### BM25 Top-K

- 1. `bpm-orbit` score=16.0549 — 束流轨道与 BPM
- 2. `bpm-position` score=7.7484 — 束流位置监测器 BPM
- 3. `vacuum-pressure` score=1.8479 — 真空系统与压力监测

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q016 [解释型问题]

**Question:** MBA 为什么能够帮助降低电子束自然发射度？

**Ground truth:** `mba-emittance`

### Dense Top-K

- 1. `mba-emittance` score=0.6618 — MBA 晶格与低发射度
- 2. `rf-cavity` score=0.5768 — 射频腔的作用
- 3. `bpm-orbit` score=0.4506 — 束流轨道与 BPM

### BM25 Top-K

- 1. `mba-emittance` score=14.7140 — MBA 晶格与低发射度
- 2. `rf-cavity` score=1.8491 — 射频腔的作用

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q017 [技术缩写]

**Question:** 高层应用 HLA 可以完成哪些任务？

**Ground truth:** `hla-role`

### Dense Top-K

- 1. `hla-role` score=0.7249 — 高层应用 HLA
- 2. `epics-cli` score=0.4003 — caget 与 caput
- 3. `epics-ioc` score=0.3988 — IOC 的主要职责

### BM25 Top-K

- 1. `hla-role` score=14.0577 — 高层应用 HLA
- 2. `bpm-orbit` score=0.9565 — 束流轨道与 BPM
- 3. `rf-cavity` score=0.7774 — 射频腔的作用

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q018 [安全边界]

**Question:** 第一版加速器 RAG 为什么不能自动执行 caput？

**Ground truth:** `rag-boundary`

### Dense Top-K

- 1. `rag-boundary` score=0.7575 — 加速器 RAG 系统运行边界
- 2. `epics-cli` score=0.6915 — caget 与 caput
- 3. `epics-ioc` score=0.4672 — IOC 的主要职责

### BM25 Top-K

- 1. `rag-boundary` score=9.9612 — 加速器 RAG 系统运行边界
- 2. `epics-cli` score=8.9988 — caget 与 caput
- 3. `epics-ca` score=1.3707 — Channel Access 通信

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q019 [领域语义]

**Question:** 射频腔的主要作用是什么？

**Ground truth:** `rf-cavity`

### Dense Top-K

- 1. `rf-cavity` score=0.7228 — 射频腔的作用
- 2. `mba-emittance` score=0.4343 — MBA 晶格与低发射度
- 3. `bpm-orbit` score=0.4158 — 束流轨道与 BPM

### BM25 Top-K

- 1. `rf-cavity` score=9.1705 — 射频腔的作用
- 2. `epics-pv` score=0.8531 — EPICS 中的过程变量 PV
- 3. `epics-ioc` score=0.6311 — IOC 的主要职责

**Evaluation:** Dense 第 1 名；BM25 第 1 名；本题排名结果：并列

## q020 [语料覆盖诊断]

**Question:** SR:BPM01:X

**Ground truth:** 不计分，用于语料覆盖诊断。

### Dense Top-K

- 1. `bpm-orbit` score=0.4945 — 束流轨道与 BPM
- 2. `bpm-position` score=0.4919 — 束流位置监测器 BPM
- 3. `epics-ca` score=0.4154 — Channel Access 通信

### BM25 Top-K

- 无结果

**Evaluation:** 该问题没有标注 Ground Truth，不用于检索器排名统计。

# Summary

- Scored cases: 19
- Dense: Top-1 19/19, Top-3 19/19
- BM25: Top-1 18/19, Top-3 19/19
- Per-case ranking: Dense 1, BM25 0, tie 18, both missed 0

Dense 与 BM25 的 score 不在同一尺度，不能直接比较绝对分数。
