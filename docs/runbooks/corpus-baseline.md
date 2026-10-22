# 全知识库 ingestion、审计与证据检索基线

本文保留 Stage 2.5 运行说明。当前 Stage 2.6 入口见 [Dense Passage Compatibility](dense-passages.md)。本工作区的 Stage 2.5 报告和集合属于历史 A 侧，复核时只读使用。

## 范围与前置条件

本历史入口执行 Stage 2.5。Registry 的 13 份 PDF 串行 ingestion，审计覆盖全部 Chunk。BM25 和 Dense 仅索引 eligible Chunk。Agent、Hybrid、reranker、LLM、OCR 和其他文件类型保持本阶段范围外。

使用 `accelerator-rag` Conda 环境和本地 `BAAI/bge-small-zh-v1.5` 缓存。模型缺失时失败，不下载或替换。

```bash
conda activate accelerator-rag
pytest -q
ruff check .
git diff --check
python scripts/corpus_inventory.py
```

Inventory 应报告 13 个注册 PDF、5 个 unsupported/unmanaged sources，并返回 0。

## 执行

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m accelerator_rag.retrieval.corpus_baseline \
  --project-root . \
  --collection knowledge_stage25 \
  --qdrant-path tmp/stage-two-five-qdrant \
  --batch-size 32
```

集合名必须以 `knowledge_stage25` 开头。路径与原始数据隔离。程序拒绝写入含 corpus 外文档的集合。Stage 2 的 `tmp/stage-two-qdrant` 和 `knowledge_stage2` 保留为历史索引，不清空。

当前输出统一使用以下文件名：

- `reports/rag-stage-two-five-corpus-audit.json`
- `reports/rag-stage-two-five-corpus-audit.md`
- `reports/rag-stage-two-five-retrieval-baseline.json`
- `reports/rag-stage-two-five-retrieval-baseline.md`

`rag-stage-two-*` 保留为历史诊断基线。当前基线以 `two-five` 为准。`--queries` 默认为 `data/evaluation/retrieval_baseline.json`；`--generated-on` 仅指定记录日期。完整源文件、代码和查询集 SHA-256 写入报告。dirty 工作树不能仅用 HEAD 标识运行版本。

## 清洗与资格策略

Raw parser 保留完整布局证据。检索清洗移除 NULL，并检测稳定位置的跨页重复短页眉和页码。新增检测窗口为顶部 18% 或底部 18%，重复要求至少 6 页且占文档 10%，位置按页面高度百分位取整。普通文本保留数字；仅独立页码折叠为共同 signature，避免混淆章节标题。重复正文保留。规则仍可能漏掉与正文合并的页眉。

清洗文本变化，因此算法版本为 `pdf-chunks-v3`，Chunk ID 重建。页面与文档 citation 语义不变。Eligibility 是独立索引策略，不修改 Chunk。

资格策略排除明确的致谢、单独页码或 running code、完全无有效字符和严重替换字符损坏。短数值加单位、设备型号和短技术正文保留。严重损坏阈值由 `EligibilityConfig` 配置：至少 8 个 U+FFFD，且占非空白字符至少 20%。这个保守起点依据 corpus 损坏比例审查与边界测试确定，不是模型质量最优阈值。索引报告记录原因和全部排除样本。

U+FFFD 原样保留在 corpus 和审计中；不伪造公式恢复。未解释的 PUA 保留。没有足够跨文档证据时，不做 bullet 映射。字符统计覆盖全部 Chunk，点数只对应 eligible 集合。

## Dense 输入审计

实际输入统一为 `document_title + "\n" + chunk.text`。审计复用同一模板，从已加载模型获取 `max_seq_length`。使用真实 tokenizer，按 Transformer 的 strip / lower 预处理，包含 special tokens，关闭截断与 padding，得到截断前长度。

报告列出 token 长度分布、超限数量与比例、语言和文档归属、最严重样本。模型 encode 仍按真实上限截断。统计只能确认输入风险，不能单独证明检索失败原因。

每轮 eligible Chunk 只进入一次 embedding batch。所有新 points 写入后清理过时 ID。重复执行会重算向量，但稳定 ID 防止重复。索引不具备多文档事务，失败后修复并重跑同一专用集合。

## Evaluation contract

Query schema 和人工判断见[查询集说明](../../data/evaluation/README.md)。运行先验证 raw evidence 和 eligible Chunk 的包含关系，再做排名。相关性判断要求文档、页码和摘录同时匹配。

Hit@K = fraction of answerable queries with at least one accepted evidence target in Top-K

`all` 模式进一步要求全部证据组。组内 OR，组间由 `any` / `all` 决定。`groups_satisfied_at_k` 记录 Top-1、3、5 覆盖的组数。MRR@5 使用 `first_complete_rank`，深度外记为 0。

报告提供 overall、query language、same/cross language、category、expected document 切片。每片包含 count、Hit@1/3/5、MRR@5，均标记 `diagnostic only`。`zh-en` 支持任一语言；存在任一其他语言目标时保守归为 cross-language。一个问题可出现在多个 expected document 切片中，不能将切片计数相加当作样本总量。

明显负例、领域负例和可回答问题分别统计 Top-1 分数。无答案问题不进入 Hit/MRR 分母，不使用分数阈值。

Stage 2 历史页级指标与 Stage 2.5 证据级指标不可直接归因比较。对照报告同时复判旧 Top-5，分别展示口径变化和同口径排名变化造成的 fail→hit / hit→fail。没有根据旧排名选择新标注。

## 数据保护与限制

原始 PDF 与 Agent 源码保持原样。程序不 commit、不 push、不删除历史集合。文档阅读顺序、公式提取和标注穷尽性仍有限制。没有新增 OCR、公式重建或替代解析器。

当前 corpus 的非空白 U+FFFD 比例存在明显间隔：最严重 3 个 Chunk 为 25.16%、38.92%、40.39%，下一名为 8.70%。20% 位于这个间隔内，排除 3 个高度损坏样本，保留包含局部公式损坏的其余正文。测试覆盖 19%、20%、21% 和少于 8 个替换字符的边界。这个资格阈值不属于检索分数阈值。
