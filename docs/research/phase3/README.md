# 阶段三交付说明：证据包检索与端到端链路

日期：2026-11-08。依据：`docs/research/rag-research-reset-20261107.md` §4.2、§6（P0/P1）、§8、§10 阶段三。契约见 `DESIGN.md`，审核协议见 `review-protocol.md`。

## 1. 交付物

| 交付物 | 位置 | 说明 |
| --- | --- | --- |
| 问题驱动的需要解析与动态预算 | `src/accelerator_rag/evidence_pack/{needs,budget}.py` | 只读问题文本；路由、实体、关系需要、token 预算 |
| 多路召回与关系补全 | `evidence_pack/{index,recall,relations}.py` | BM25、行索引、事实图、修订侧、字面量、表结构、邻接；对端/单位/条件/角色/版本/枚举补全 |
| 证据包选择 | `evidence_pack/pack.py` | 关系覆盖 + 预算内填充；同预算 `parent_top5` 对照；冲突成对保留 |
| 重排器 | `evidence_pack/rerank.py`、`scripts/research/train_pack_reranker.py` | 规则版默认；线性学习版按文档族训练/验证 |
| Archiver 只读适配器 | `evidence_pack/archiver.py`、`scripts/research/ingest_archiver.py` | 消费 MCP 导出；保留窗口/策略/降采样/截断/分段警告 |
| 稠密通道 | `evidence_pack/{dense,dense_local}.py`、`scripts/research/build_dense_vectors.py` | 生产同版权重 E5/Qwen3 向量；CPU float32；passage contract 与生产索引一致 |
| 端到端链路 | `evidence_pack/{pipeline,verify}.py`、`scripts/research/run_evidence_pack.py` | 规则基础版、规则重排版、学习重排版；`--verify` 逐字节重放 |
| 审计 | `scripts/research/audit_evidence_pack.py` | 预算、逐字引用、冲突、枚举、算子重放、生产隔离 |
| 选择消融与构建追溯 | `scripts/research/{ablate_pack_selection,audit_revision_chunks}.py` | passes 0–3、16 原子穷举最优；10 个 `.doc` revision 映射与 40 题重放 |
| 测试 | `tests/evidence_pack/` | 48 项单元与 corpus 测试 |
| 论文素材 | `docs/research/phase3/paper-retrieval-composition.md` | 检索与组合方法章节素材 |
| 审核记录 | `docs/research/phase3/reviews/` | R1—R5 独立审核与复审 |

本地运行数据写入 `reports/phase3/`、`data/evidence-pack/`，含内部原文或逐题证据，不进入 Git。代码、测试、文档不含内部原文。

## 2. 数据边界

- 语料：`tmp/research-rc3/` 只读快照（rc.3）。
- 题目：只使用 `data/evaluation/research-benchmark-300-v1/{dev,val}/questions.json`。阶段三代码、测试与本阶段报告不读取 `sealed-test/`；仓库其他目录（例如其他会话的专家复核输出）不属本阶段范围，已用 `.gitignore` 阻止其入库。
- 检索范围：题目 `family_ids` 对应的文档族；所有对照方法获得相同范围。该范围是题目元数据，不是 gold 证据。
- `verdict_class=deterministic` 才进入回答状态与 gold 指标；`rubric/human` 一律 `not_evaluated`，不作正确性依据。
- 阶段一 37 道 human 题未人工验收，本阶段未将其作为正确性依据。

## 3. 复现命令

```bash
# 测试与静态检查（全量 899 passed；唯一 skipped 为 tests/corpus/test_ocr.py:99，
# 原因是本机未安装 tesseract，不是本阶段失败）
~/miniconda3/envs/accelerator-rag/bin/python -m pytest tests/evidence_pack -q
~/miniconda3/envs/accelerator-rag/bin/python -m ruff check src/accelerator_rag/evidence_pack scripts/research tests/evidence_pack

# 规则基础版（覆盖 + 候选顺序填充）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --reranker none --out reports/phase3/dev.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split val --reranker none --out reports/phase3/val.json

# 可选：确定性 hashing 稠密通道（仅演示通道接口，不是 E5/Qwen3）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --dense hash --out reports/phase3/dev-dense.json

# 真实 E5/Qwen3 向量（生产同版权重，本机 CPU；首次约 12/68 分钟）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/build_dense_vectors.py --model e5
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/build_dense_vectors.py --model qwen3
# lexical-only 与 full（BM25+E5+Qwen3）对照
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --reranker none --dense e5 --out reports/phase3/dev-e5.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --reranker none --dense qwen3 --out reports/phase3/dev-qwen3.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --reranker none --dense both --out reports/phase3/dev-both.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --reranker rule --dense both --out reports/phase3/dev-both-rule.json

# 规则重排版（默认 CLI 行为；W3 规则重排器决定填充顺序）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --reranker rule --out reports/phase3/dev-rule.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split val --reranker rule --out reports/phase3/val-rule.json

# 学习重排版（条件实验）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/train_pack_reranker.py
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --reranker learned --learned data/evidence-pack/reranker.json --out reports/phase3/dev-learned.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split val --reranker learned --learned data/evidence-pack/reranker.json --out reports/phase3/val-learned.json

# 逐字节重放与审计
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --verify reports/phase3/dev-rule.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/audit_evidence_pack.py

# passes 消融与 16 原子穷举最优；.doc revision 映射与受影响题重放
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/ablate_pack_selection.py --mode full --passes 0 1 2 3
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/ablate_pack_selection.py --mode exhaustive --limit 20 --pool-limit 16
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/audit_revision_chunks.py

# Archiver 导出规范化（不联网）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/ingest_archiver.py --export reports/research-reset-20261107/archiver-probes.json
```

## 4. 机制结果

以下为开发用机制状态与 gold 证据覆盖，不是准确率，也不是独立正确性评价。统计按题聚合；报告时须按 `cluster_id`/文档族聚类，不能按 n=300 计算。

### 4.1 状态计数（全部 dev/val 题）

| 划分 | 题数 | deterministic | answered | partial | not_evaluated | rubric | human |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dev | 100 | 68 | 65 | 3 | 32 | 19 | 13 |
| val | 50 | 36 | 36 | 0 | 14 | 8 | 6 |

- `partial` 在 dev 为 3 道 VAC 验收题的**角色差异冲突**（设计/测试/验收取值不同）；val 本版没有检出值冲突，36 道 deterministic 全部 `answered`。`partial` 不是失败计数，而是“未解决条件”的显式状态。
- `not_evaluated` 只表示 rubric/human 未进入规则回答，不表示失败。
- 5 条 gold 补丁应用后，dev/val 的 **verification 状态 0 迁移**（answered/partial/insufficient 组合不变）；dev/val 补丁题的新 `gold.status` 均为 `answered`，其中 S3-VAL-FI-008 仍为 human/`not_evaluated`。检索不读 gold，补丁只改变答案/事实文本与评分口径。

### 4.2 证据包与同预算父块对照（deterministic 题）

| 划分 | 链路 | gold 证据块召回 | 全证据覆盖 | 必要事实支持 | 平均 token / 预算 |
| --- | --- | ---: | ---: | ---: | ---: |
| dev | 证据包（lexical-only，基础） | **0.9571** | 61/68 | **0.9627** | 2224 / 2627 |
| dev | `parent_top5` 基线 | 0.7690 | 42/68 | 0.7823 | 同预算 |
| dev | 证据包 + 规则重排（lexical-only） | **0.9841** | 65/68 | **0.9876** | 2228 / 2627 |
| dev | 证据包 + 学习重排（lexical-only） | 0.9804 | 65/68 | 0.9876 | 2226 / 2627 |
| val | 证据包（lexical-only，基础） | **0.7917** | 23/36 | **0.7696** | 2382 / 2683 |
| val | `parent_top5` 基线 | 0.5718 | 15/36 | 0.5931 | 同预算 |
| val | 证据包 + 规则重排（lexical-only） | **0.8449** | 25/36 | **0.8382** | 2381 / 2683 |
| val | 证据包 + 学习重排（lexical-only） | 0.8171 | 24/36 | 0.7990 | 2383 / 2683 |

- **补丁后的支持口径**：5 条 gold 补丁中，dev/val 的 S1-DEV-006、S1-VAL-002、S2-VAL-IL-05 三道 deterministic 题的 `required_facts` 被写成纯字符串，没有 SPEC 要求的 `support` 列表。上表“必要事实支持”按可用题计算（dev 67/68、val 34/36）；在这 67/34 道题上，补丁前后支持率**逐题完全相同**（dev 基础/规则/学习 0.9627/0.9876/0.9876；val 0.7696/0.8382/0.7990）。若按 `evidence_minimal` 支撑这些字符串事实，则与原值相同（dev 0.9632、val 0.7824）。gold 召回、全证据覆盖、路由、token 与 verification 状态均未变化。
- 同一 token 预算下（lexical-only），证据包把 dev/val 的 gold 证据块召回从 0.77/0.57 提高到 0.96/0.79；规则重排进一步提高。
- 这是机制层面的证据覆盖，不是答案准确率；`parent_top5` 基线使用同一候选集合与预算，但仍按生产“最多 5 个父块”的形状选择。
- deterministic 题平均引用父块 10.9/11.6（规则重排 14.0/14.7），其中标记 `full_text=true` 的完整父块查阅引用平均 5.7/5.8（规则重排同为 5.7/5.8）；证据包可以从小段落和行记录组合，而不必把每个父块全文塞入预算。
- 逐 cluster 的召回与状态分解见报告 `summary.cluster_metrics`；dev 为 10 个文档族/6 个 cluster，val 为 5 个族/4 个 cluster。正式论文须按 cluster/族做聚类 bootstrap。

| 划分 | cluster | 题数 | 证据包召回 | 父块基线召回 | 状态 |
| --- | --- | ---: | ---: | ---: | --- |
| dev | S1-DEV-L3L4 | 33 | 0.9924 | 0.7765 | 33 answered |
| dev | S2-DEV-CONSTTEMP | 8 | 0.9375 | 0.6875 | 8 answered |
| dev | S2-DEV-TIMING | 8 | 0.8958 | 0.7917 | 8 answered |
| dev | S2-DEV-VACUUM | 11 | 0.9545 | 0.8636 | 11 answered |
| dev | S3-DEV-CONSTTEMP | 4 | 0.7917 | 0.5833 | 4 answered |
| dev | S3-DEV-VACUUM | 4 | 1.0000 | 0.7500 | 1 answered / 3 partial |
| val | S1-VAL-L2 | 16 | 0.9375 | 0.7292 | 16 answered |
| val | S2-VAL-ARCHIVE-QUERY | 4 | 0.5833 | 0.5833 | 4 answered |
| val | S2-VAL-INTERLOCK | 7 | 0.7143 | 0.6429 | 7 answered |
| val | S3-VAL-FASTINTERLOCK | 9 | 0.6852 | 0.2315 | 9 answered |

- S2-VAL-ARCHIVE-QUERY 的证据包召回与父块基线持平（0.5833），是当前最弱的一族；版本对齐只覆盖部分段落，未达到 dev 版本族水平。阶段四须针对该族补对齐策略。

### 4.3 冲突、枚举与预算

| 划分 | 检出冲突 | 成对保留 | 枚举必需 | 枚举完整 | 预算越界 |
| --- | ---: | ---: | ---: | ---: | ---: |
| dev | 6 | 6 | 15 | 15 | 0 |
| val | 0 | 0 | 5 | 5 | 0 |

- 冲突按“同对象/属性/条件/角色、不同值”检测；`connectivity` 事实的端口区间是行键，不按值冲突统计，跨表身份由 `exact_join` 的 `AMBIGUOUS_SCOPE` 处理。
- 同一文档、同一表、同一角色的多行差异按“不同行/不同项”处理；同一文档、同一角色的不同段落/图也按不同测试图/量程处理；同段落的抽取变体（字符重合 ≥0.8 或互相包含）不判冲突。以上限制见 §6。全部报告（含 rubric/human 证据包）中 dev 共 30 条冲突/15 题、val 0 条；上表只统计 deterministic 题。
- 预算不足时冲突双方整体不入选并写 `unresolved`，不保留单边。

### 4.4 短路径与调用成本

| 划分 | exact_record | document_explanation | cross_source | 1 轮 | 2 轮 |
| --- | ---: | ---: | ---: | ---: | ---: |
| dev | 16 | 33 | 51 | 100 | 0 |
| val | 9 | 17 | 24 | 49 | 1 |

- 路由只看问题文本；`task_type` 仅用于报告分组，不参与路由或预算。
- 第二轮只在必需关系缺失时触发；dev 本版无需触发，val 触发 1 题。
- 通道调用逐轮记录在报告的 `rounds[].recall.channels`；默认离线回放 `dense.available=false`，未假装调用 E5/Qwen3；可选 `--dense hash` 仅演示通道接口，不是 E5/Qwen3。

### 4.5 学习重排的跨族验证

- 训练：dev 10 个文档族、10,469 个原子（544 正例，另含交换端口/EXT 柜/删条件/角色替换近似负例）；验证：val 5 个文档族、36 道 deterministic 题。
- 验证集逐题 AUC：学习版 0.8459，规则版 0.8497；precision@10：学习版 0.1889，规则版 0.2278。
- 结论：学习版没有在 val 族稳定优于规则版。按方案 §4.2，**保留规则版为默认交付**，学习版只作为条件实验记录，不宣称通用贡献。权重与逐题评估见 `reports/phase3/reranker.json`。

### 4.6 真实稠密通道对照（E5/Qwen3）

- 向量来源：本机使用生产同版权重与 `PassageBuilder` 计算。E5/Qwen3 的 `weights_manifest_sha256`、`model_config_sha256`、`tokenizer_sha256` 与 `data/evaluation/research-benchmark-300-v1/baseline/baseline-freeze.json` 完全一致；passage contract 分别为 `dba19095…`（E5）与 `7ea2c062…`（Qwen3），与生产索引相同。dev/val 的 1,418 个父块生成 E5 1,975 个 passage、Qwen3 1,418 个 passage。设备为 CPU float32，不是生产 CUDA 索引；余弦值可能有设备级差异。
- 通道：`dense` 取父块内最佳 passage 余弦；E5+Qwen3 用 RRF（k=60）融合，再与 BM25 按 RRF 融合。`full` 指 BM25+E5+Qwen3，`lexical-only` 指默认的 BM25/行索引/事实图等离线通道。
- 以下为 deterministic 题对照；所有 dense bundle 均通过 `--verify` 与审计。

| 划分 | 链路 | gold 证据块召回 | 全证据覆盖 | 必要事实支持 | 平均 token / 预算 |
| --- | --- | ---: | ---: | ---: | ---: |
| dev | lexical-only（基础） | 0.9571 | 61/68 | 0.9627 | 2224 / 2627 |
| dev | E5（基础） | 0.9718 | 63/68 | 0.9776 | 2229 / 2627 |
| dev | Qwen3（基础） | 0.9718 | 63/68 | 0.9776 | 2224 / 2627 |
| dev | E5+Qwen3（基础） | 0.9645 | 62/68 | 0.9701 | 2219 / 2627 |
| dev | lexical-only + 规则重排 | 0.9841 | 65/68 | 0.9876 | 2228 / 2627 |
| dev | E5 + 规则重排 | 0.9877 | 66/68 | 0.9876 | 2228 / 2627 |
| dev | Qwen3 + 规则重排 | 0.9877 | 66/68 | 0.9900 | 2230 / 2627 |
| dev | full（E5+Qwen3）+ 规则重排 | 0.9877 | 66/68 | 0.9876 | 2236 / 2627 |
| val | lexical-only（基础） | 0.7917 | 23/36 | 0.7696 | 2382 / 2683 |
| val | E5（基础） | 0.7986 | 23/36 | 0.7794 | 2444 / 2683 |
| val | Qwen3（基础） | 0.7801 | 22/36 | 0.7598 | 2442 / 2683 |
| val | E5+Qwen3（基础） | 0.7894 | 22/36 | 0.7696 | 2439 / 2683 |
| val | lexical-only + 规则重排 | 0.8449 | 25/36 | 0.8382 | 2381 / 2683 |
| val | E5 + 规则重排 | 0.8449 | 25/36 | 0.8382 | 2439 / 2683 |
| val | Qwen3 + 规则重排 | 0.8449 | 25/36 | 0.8382 | 2440 / 2683 |
| val | full（E5+Qwen3）+ 规则重排 | 0.8449 | 25/36 | 0.8382 | 2431 / 2683 |

- 支持列与 §4.2 同口径（dev 67/68、val 34/36 道有 `fact.support` 的题）；gold 补丁未改变任何题的 evidence_minimal，故召回/全证据覆盖与旧值逐题相同。
- 结论：稠密通道在 dev 上把基础版召回从 0.9571 提高到 0.9645—0.9718；val 上只有 E5 基础版提高 0.7 个百分点（0.7917→0.7986），Qwen3 基础版下降 1.2 个百分点，E5+Qwen3 与 lexical-only 基本持平。加规则重排后，dev 由 0.9841 提高到 0.9877，val 四组均为 0.8449，没有增益。
- 因此：**0.9571/0.7917 是 lexical-only 数字，不能称为完整链路**；full（BM25+E5+Qwen3+规则重排）为 dev 0.9877、val 0.8449。当前证据不支持“加入 E5/Qwen3 必然提高 val”的结论，默认报告仍保留 lexical-only，full 仅作对照。

### 4.7 构建追溯：10 个 `.doc` revision 的 chunk 映射

- 复核报告的“41 条 evidence id 缺失”是相对旧 `kb2-batch-full-20261102-r3` 构建的口径。阶段三实际加载 `tmp/research-rc3`（生产 `kb2-prod-20261105-v3` 的 v2 快照）：这 10 个 `.doc` 操作手册 revision 共 **213 个 chunk**；复核 `independent_evidence` 对该 10 个 revision 的 **91 次引用（48 个唯一 id）全部命中**；dev/val gold 中该 10 个 revision 的 **48 条证据 id 也全部命中**。
- 受影响 dev/val 题共 40 道；逐题重放 40/40 与最终包 `report_sha256` 一致，31 answered / 9 not_evaluated（rubric/human），未出现假性 `insufficient`。映射与逐题重放见本地 `reports/phase3/revision-chunk-map.json`。

## 5. Archiver 适配器

- 只读、离线：消费 MCP 导出的 JSON，不建连接、不写归档、不触发采集。
- 规范化字段：PV 原文、UTC 窗口、策略、`bin_seconds`、点数、窗口内/上下文点数、`data_state`、`segments[].warnings`、`downsampled`、`truncated`、`complete`、`source_ids`、单位未知。
- 限制项随证据保留：`downsampled` 不得用于声称连续物理状态；`truncated` 或分段警告不得被 `complete=true` 掩盖；窗口外 context 点不计入窗口统计。
- 主实验不依赖 Archiver；只有显式提供导出且问题含匹配 PV 时才加入，报告中单列 `external_observation` 原子。
- 本次用 `reports/research-reset-20261107/archiver-probes.json`（本地、含真实 PV，不入库）验证了规范化；测试使用匿名 PV。单次探针不构成新系统优于基线的证据。

## 6. 已知限制

- 默认报告仍是 lexical-only；full dense 对照使用本机 CPU 上生产同版权重与 `PassageBuilder` 计算的 E5/Qwen3 向量（指纹与 passage contract 均与生产索引一致），不是生产 CUDA 索引，余弦值可能有设备级差异。`HashingEmbedder` 只是确定性测试替身。环境没有生成模型；本阶段回答是**可复核主张集合与模板化文本**，不是自然语言证明。
- gold 指标是开发诊断，不是独立人工评价；阶段一 human 题未验收，不能作为正确性依据。
- 基准存在 100 条片段复用；本报告按题聚合，未按 n=300 计算置信区间。
- 冲突检测键受阶段二事实粒度限制：`connectivity` 行键不进入值冲突；同文档同表同角色的多行差异、同文档同角色的不同段落/图、同段落的抽取变体均不判冲突；缺少显式条件的参数事实仍可能被合并。预算不足时冲突写入 `resolution=unresolved`，不单边保留。
- 枚举完整性只对已定位的目标表成立，不外推到全库。
- 学习重排为点式线性模型，特征不含语义；未证明跨族泛化。
- 生产 `src/accelerator_rag/rag/` 未改动；本阶段预算不进入生产。实际生产 tokenizer 与离线估计器不同，阶段四须重跑并报告差异。

## 7. 审核

R1—R5 独立审核记录见 `reviews/`。首轮 R1—R5 均给出不通过；修复后 R2/R4/R5 通过，R1/R3 经最小检查集多轮复审在最终快照（final5）上通过；R2/R4/R5 也已在 final5 上补充确认。R3 的两轮阻断（S1-DEV-009 裸“完整”、S1-VAL-007 “相同”）均已修复并记录。最终 5/5 在 final5 快照上通过；剩余建议列为阶段四前清理项。

final5 之后按主会话验收意见新增了真实 E5/Qwen3 对照、passes 消融、10 个 `.doc` revision 映射与 3 项测试（48 项）；默认 lexical-only 报告未改变。final2 验收：全量 899 passed/1 skipped，18 个 bundle（6 lexical + 12 dense）共 1,350 份报告 `--verify` 全部通过，audit `bundles=18 reports=1350 blockers=0`，生产 `rag/` 无改动。

新 gold（dev `f9872cef…`、val `7403e4a9…`）应用后再次重跑同一 18 个 bundle：18/18 `--verify` 通过，audit 仍为 18/1,350/0。逐题 gold 召回、全证据覆盖、路由、token 与 verification 状态**全部不变**；唯一变化是 3 道补丁题缺少 `fact.support` 导致支持率分母调整（见 §4.2 注）。
