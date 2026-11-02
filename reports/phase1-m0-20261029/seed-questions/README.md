# PRAB Phase 1 种子题集（v1，50 道）

本目录记录 `data/evaluation/seed-questions-v1.json` 的方法、字段、分布与核验状态。
**题集是开发种子集（dev seed），不是独立测试集**；同一案例的变体不得进入未来独立测试集。

## 1. 构成与组装

| 文件 | 角色 | 道数 |
| --- | --- | --- |
| `data/evaluation/seed-questions-v1.json` | **规范文件**（元数据 + 50 道） | 50 |
| `data/evaluation/seed-questions-v1-corpus.json` | 语料侧 authored part（task1 + task3） | 21 |
| `data/evaluation/seed-questions-v1-waveform.json` | Waveform 侧 authored part（task2 + task4） | 21 |
| 规范文件内的 8 道完整样例 | 先做的字段/评分样例（每类 2 道） | 8 |

组装：`scripts/build_seed_questions.py`（按 id 去重、按 category 排序、写入 `sources` 哈希）。
校验：`scripts/validate_seed_questions.py data/evaluation/seed-questions-v1.json --expect-total 50`。
**最近一次校验结果：`OK`**（2026-10-29）。

各 part 的 SHA-256 记录在规范文件的 `sources` 字段：

```
seed-questions-v1-corpus.json    a89b9f02…  (组装时)
seed-questions-v1-waveform.json  6fbef728…  (组装时)
```

注意：规范文件在组装后**本身**又被写入（`sources` 哈希对应 part 文件，不是规范文件自身），
所以规范文件的哈希不等于 `sources` 中任何一项——这是预期行为。

## 2. 分类与状态分布（实测）

| 类别 | 道数 | answerable | partial | insufficient | overlaps_36q |
| --- | --- | --- | --- | --- | --- |
| `task1_parameter_condition` 设备参数与适用工况 | 13 | 10 | 1 | 2 | 13 |
| `task2_alignment_prep` Waveform 对齐与分析准备 | 13 | 11 | 1 | 1 | 0 |
| `task3_cross_version_comparison` 跨版本/跨子系统比较 | 12 | 9 | 2 | 1 | 12 |
| `task4_fault_diagnosis` 故障复盘与诊断路径 | 12 | 6 | 2 | 4 | 2 |
| **合计** | **50** | **36** | **6** | **8** | **27** |

- 非 answerable 共 **14 道（28%）**，高于“至少 12 道”的下限。
- 全部 50 道 `language=zh`；每题 `evidence` 平均 3 条（共 150），`must_cover` 平均 4.16 条（共 208）。
- 评分 `hazardous_patterns` 共 116 条，平均 2.3 条/题。

## 3. 负例与构造方式（13 道）

负例不是真实故障，全部在 `negative_construction.{method,detail}` 中标注：

| 构造方式 | 道数 | 含义 |
| --- | --- | --- |
| `hidden_evidence` | 6 | 证据在目标知识库中确实缺失（逐端口接线、部署固件版本、跨版本文档未入库等） |
| `live_data_absent_by_design` | 3 | 实时运行数据，服务按设计不读取 |
| `absent_semantics` | 2 | 系统不存在的概念/字段（如“对齐容差参数”、4 文件集合哈希≠系统字段） |
| `out_of_bounds` | 1 | 越界参数（阈值 0/-1、不存在的 tolerance） |
| `wrong_version` | 1 | 版本归属错误（现场部署无法用任何提交定位） |

另外 2 道 task4 题专门检验**错误前提的纠正**（“国庆后对齐异常=版本回归”、
“国庆前后存在两套对齐逻辑”），正确答案必须包含“该措辞作为版本回归不成立/证据不足”。

## 4. 字段契约（逐题必须有）

`id`（唯一）、`category`、`language`、`question`、`source_case`、
`applicable{system_version, conditions}`、`expected_status`（answerable/partial/insufficient）、
`gold_answer`、`must_cover[{id,fact,type,value,unit,comparator,match}]`、
`constraints{numbers, comparators, preconditions, version_constraints}`、
`evidence[{id,locator,excerpt}]`、`scoring{full,partial,zero,hazardous_patterns}`、
`verification{status,method,checked_at,pending}`、`negative_construction`、
`provenance{derivation, overlaps_36q, independent_test_allowed}`。

评分规则（题集元数据 `scoring_contract`）：

- `full` = 1.0：must_cover 全满足 + constraints 全满足 + 未命中 hazardous；
- `partial` = 0.5：核心结论正确但至少 1 项必需条件缺失且被显式标注；
- `zero` = 0.0：核心结论错误或引用不支撑；
- **hazardous 是标记不是分值**：命中 `hazardous_patterns` 的 partial/zero 仍得 0.5/0.0，但计入
  “危险误导率”。报告指标必须同时给 strict 与 hazardous 两个数，不得只报其一。

## 5. 证据定位

- 语料侧用 `data/evaluation/retrieval_baseline.json#<qid>.evidence_groups[i].alternatives[j]`
  或 `reports/rag-framework-20261028/version-scope-recheck/http-results.json#cases[<id>].response.citations[N]`；
  摘录逐字来自冻结基准/请求记录（经人工复核的证据）。
- Waveform 侧用 `src/waveform_storage/...py:<行号>`（Waveform 仓库 HEAD `dc50e08`）、
  `docs/waveform/*.md#<章节>`、`reports/phase1-m0-20261029/waveform-audit/cases.json#cases[case-0N]`。
- 校验器检查 locator **可解析**（文件存在、行号在范围内），不检查语义充分性。

## 6. 核验状态（必须如实读）

- **50/50 `machine_verified`，0 道 `pending_human`**。
- `machine_verified` 的含义**仅限**：schema 完整、id 唯一、locator 可解析、excerpt 非空、
  must_cover.match 能在 evidence.excerpt 或 gold_answer 中找到（作者自检）。
  **它不代表领域专家确认过答案正确。**
- 29 道题的 `verification.pending` 非空，列出了仍需人工确认的具体问题（单位口径、表号、
  负责人确认等）；这些不是“已完成”的标记。
- **本阶段没有任何人工语义复核资源**。进入独立测试集之前必须补人工双人复核。

## 7. 使用边界（硬约束）

1. 本集是**开发种子集**：Phase 2 用它调约束核查器、Phase 3 用它扩 200 题。
2. **27 道标记 `overlaps_36q=true`**（与 36 题开发回归集同源/变体）。它们**不得**进入未来独立测试集；
   Phase 3 的独立测试集必须重新出题并做去重检查。
3. `independent_test_allowed` 在 50 道中全部为 `false` —— 这是刻意的。
4. 不得把本题集的分数当作泛化性能；不得用 `answered` 状态代替正确性。
5. Waveform 类题目（task2/task4）的目标知识库 = M0 语料 + 4 份 Waveform 文档；后者**尚未入库**
   （见 [RAG 入库手册](../../../docs/runbooks/rag-ingestion-verification-rollback.md)），
   因此在 M0 上这些题预期为 `insufficient`，这不是题目缺陷。

## 8. 已知问题与待办

| 项 | 说明 |
| --- | --- |
| S3-VERSION-010 只有 1 个文档来源 | CDR2011 主体不在 M0 语料，故 expected_status=partial；若要求每道 task3 ≥2 文档，需补语料或撤题 |
| S1-PARAM-010 的连字符变体 | 源文用 en dash，答案允许 ASCII 连字符；`match` 已覆盖两种写法 |
| intervals 语义题（S4-FAULT-011） | 依赖 2026-08-28 交接记录；标注为“待核实”类事实，答案须声明证据边界 |
| 统一哈希口径 | 全部题目的 `alignment_algo_hash` 一律为系统值 `e8db12d7…`；`390fd8e9…` 只作“文档侧集合哈希”出现 |
| 人工复核 | 未做；Phase 3 前必须补齐并更新 `verification.status` |
