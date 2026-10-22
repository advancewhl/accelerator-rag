# Stage 2.7.1：索引契约与离线重判

## 输入与边界

本阶段读取 Stage 2.7 JSON 中保存的完整 Top-5 父 Chunk 和 passage trace。只重新解析源 PDF、验证 evidence alternatives 并计算 judgment。不构造模型或 Qdrant 客户端，不重新检索、编码或写入历史向量。

固定 13 份 PDF、21 条可回答问题和 11 条负例。`retrieval-baseline-v1.json` 保留原始标注；`retrieval_baseline.json` 使用 `evidence-contract-v2`。新增 alternatives 的组内 OR、组间 AND 语义不变。

## 复现命令

在项目根目录使用 `accelerator-rag` Conda 环境：

```bash
pytest -q
ruff check .
git diff --check
python scripts/corpus_inventory.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m accelerator_rag.evaluation.evidence_audit
```

输出为 `reports/rag-stage-two-seven-one-evidence-audit.json` 和同名 Markdown。原 Stage 2.7 报告及三个 SQLite 文件的摘要必须与 review artifact 一致。文件缺失或摘要变化时直接失败。

## 审核数据与判断

- `data/evaluation/stage271-evidence-audit.json`：全部 21 条问题的原始 groups、搜索术语、全语料候选位置、接受/拒绝记录和 canonical chunk 身份。
- `data/evaluation/stage27-manual-review.json`：Stage 2.7 人工复核、解释和验证文字，绑定原 measurement rankings 摘要。
- `data/evaluation/stage271-manual-review.json`：本阶段建议、验证记录及历史文件摘要。

审核从每条问题及原 group 语义出发，对全部 PDF 进行规范化重复搜索、技术术语搜索和宽 BM25 搜索，再检查源证据。它不保证找全所有改写。新增 excerpt 必须通过 `load_queries()` 对原始物理页及 eligible canonical chunk 的严格子串校验；无法同时通过的候选不加入标注。

`rejudge(cases, queries)` 无须 retriever。它拒绝查询元数据变化，重算相关性、完整首次排名、Top-K 证据组数量和各切片。互补性与两两排名比较复用正式评测函数。摘要覆盖 rank、score、完整父 Chunk payload 与完整 passage trace，只排除可重判的 `judged_relevant`。

`passage_trace` 中的 `matched_evidence` 和 `matched_evidence_groups` 是冻结的 v1 历史注释。v2 的 `first_complete_passage_rank` 另存于 case，不回填 trace。

离线生成器还从 measurement 与人工 review 逐字重建 Stage 2.7 Markdown 到临时目录，并与历史文件比较。`model_baseline.py` 的正式报告输出也读取人工 review，若 measurement rankings 不同则拒绝套用旧 review。本轮不运行该历史编码程序；其冻结控制及旧版标注前提不适用于当前 v2 标注。

## 正式 Dense runtime

`QdrantPassageStore` 必须显式接收 `DenseIndexContract`。契约包含模型权重 manifest、模型和编码配置、tokenizer、查询模板、文档前缀及模板、维度、序列上限、归一化、距离和 passage policy。稳定 JSON 与 SHA-256 生成身份；路径、批次、线程和耗时不参与身份。模型指纹按已加载模型实例缓存，返回副本。

每个 point 保存契约摘要及完整契约。非空 collection 读写前完整扫描，拒绝无签名或 mixed-contract payload。`search()` 在 query encoding 前验证；单文档与全语料索引在 encoding 和 mutation 前验证。相同 768 维、不同模型也必须失败。

同一契约下更新 A 只替换 A，保留 B 的向量和 payload。模型或 passage policy 改变时，调用方应使用新 collection 或明确完整重建。程序不会隐式迁移。历史 Stage 2.7 索引保持只读，不为补加签名重写已有 points。
