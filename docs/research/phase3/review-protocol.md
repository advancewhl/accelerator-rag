# 阶段三独立审核协议（R1—R5）

日期：2026-11-08。适用范围：`docs/research/phase3/`、`src/accelerator_rag/evidence_pack/`、`scripts/research/{run_evidence_pack,audit_evidence_pack,train_pack_reranker,ingest_archiver}.py`、`tests/evidence_pack/`，以及本地产物 `reports/phase3/`、`data/evidence-pack/`。

## 1. 原则

1. 审核代理只读，不修改代码、数据、文档；各自独立上下文，不参与实现。
2. 默认从严：无法定位的证据、预算越界、冲突单边保留、越界读取 sealed-test、改动生产 `rag/`，一律按阻断处理。
3. 每条 finding 必须给出具体文件、题号或报告路径，并说明判定理由与复现命令。
4. 审核代理只出意见；修复由实现方执行，阻断项修复后由原审核代理复审。
5. 不得读取 `data/evaluation/research-benchmark-300-v1/sealed-test/` 下任何文件；不得在报告或文档中引用 test 题号、题干或真值。

## 2. 分级

| 级别 | 含义 | 处理 |
| --- | --- | --- |
| 阻断 | 预算越界、证据非逐字、冲突单边、算子不可重放、重放不一致、越界读 test、生产 `rag/` 改动、rubric/human 被当作正确性依据 | 必须修复并重审 |
| 重要 | 覆盖口径不清、短路径成本未记录、报告缺字段、学习版声明过度 | 修复后复审该项 |
| 建议 | 命名、可读性、补充说明 | 记录，酌情采纳 |

存在任一阻断即总判定 `不通过`；R1—R5 全部 `通过` 才可交付。

## 3. 输入与复现命令

```bash
# 全量测试与静态检查
~/miniconda3/envs/accelerator-rag/bin/python -m pytest tests/evidence_pack -q
~/miniconda3/envs/accelerator-rag/bin/python -m ruff check src/accelerator_rag/evidence_pack scripts/research tests/evidence_pack

# 三版链路（规则基础 / 规则重排 / 学习重排）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --reranker none --out reports/phase3/dev.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split val --reranker none --out reports/phase3/val.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --reranker rule --out reports/phase3/dev-rule.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split val --reranker rule --out reports/phase3/val-rule.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/train_pack_reranker.py
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split val --reranker learned --learned data/evidence-pack/reranker.json --out reports/phase3/val-learned.json

# 逐字节重放（对每个 bundle）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --verify reports/phase3/dev-rule.json

# 审计（必须 0 阻断）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/audit_evidence_pack.py

# Archiver 适配器（只消费导出，不联网）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/ingest_archiver.py --export reports/research-reset-20261107/archiver-probes.json
```

## 4. 分工与检查清单

### R1 预算与完整性

- 每份报告的 `pack.tokens <= pack.budget`；父块数不超过预算策略；预算计算只含原子与固定元数据，不含“供查阅”的父块全文。
- 必需关系覆盖：`coverage` 中 required 项是否与实际原子一致；枚举完整性是否只在所有目标行入选时声明。
- 动态预算：路由、基础预算、关系附加、上限（6000）是否按 DESIGN §5.2 计算；生产 `rag/` 的 6000 token/5 父块未被改动。
- 证据包与 `parent_top5` 基线是否使用同一 token 预算；基线是否真的按生产形状最多 5 个父块。
- 输出：预算越界清单、覆盖率与原子不一致清单、枚举虚假完整清单。

### R2 冲突处理

- 冲突检测键是否合理：同对象/属性/条件/角色；`connectivity` 事实是否因行键被排除；同文档同表同角色的多行是否按不同项处理（并在报告中说明这是限制）。
- 冲突双方是否都被保留；预算不足时是否标记 `unresolved` 且不据此下确定结论；是否存在删除反对证据后让覆盖“通过”的路径。
- 比较题是否并列保存差异；核验题是否说明差异是否影响目标主张（`affects_target`）。
- 输出：单边保留清单、静默删除清单、冲突口径错误清单。

### R3 短路径与调用成本

- 路由是否只依据问题文本，不读 `task_type`/`gold`；短路径是否区分精确记录、文档解释、跨资料组合。
- 预算与轮次：exact_record 1 轮、其余最多 2 轮；第二轮是否只在必需关系缺失时触发，是否只补缺失关系。
- 通道调用是否记录 `calls/candidates`；BM25 派生查询数是否受限；`dense` 离线是否标 `available=false` 而不是假装调用。
- 输出：路由泄漏清单、轮次/调用口径错误、成本未记录项。

### R4 可复算性与端到端重放

- `--verify` 是否对每个 bundle 逐字节一致；`report_sha256` 是否可由报告重算；`recompute` 是否固定 facts/questions/corpus 哈希。
- 报告中的算子请求/响应是否可重放；证据 excerpt 是否逐字；`fact_ids` 是否与事实 citation 一致。
- 同一命令重复运行是否稳定（无时间戳、无集合迭代顺序导致的差异）。
- 输出：不可重放清单、哈希不一致清单、逐字引用失败清单。

### R5 方案一致性与生产隔离

- 是否只实现 §4.2、§6 P0/P1、§8 与阶段三范围；是否越界改动生产预算、检索、生成、证据子集选择与工作流代码。
- 是否只使用 dev/val；是否读取或引用 sealed-test；文档/报告是否含 test 题号或内部原文入库。
- 是否把“证据覆盖关系”写成“工程主张已被证明”；状态计数是否被写成准确率。
- 学习版是否按文档族整体划分（dev 训练/val 验证）；若未稳定优于规则版，是否保留规则版且不宣称通用贡献。
- 阶段一 37 道 human 题是否被当作正确性依据。
- 输出：越界清单、生产改动清单、口径违规清单、学习版声明问题。

## 5. 结论与复审

每个审核代理给出总判定 `通过` / `不通过`，列阻断数、重要数、建议数，并给出复审所需的最小检查集。阻断项修复后原审核代理复审；复审通过才计入最终通过。
