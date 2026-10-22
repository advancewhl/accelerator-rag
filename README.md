# SHINE/EPICS Knowledge Retrieval

面向加速器控制、EPICS 和 SHINE 文档的本地知识检索工程。当前交付覆盖 PDF 解析、语料审计、BM25、Dense、证据评测及双模型候选重排。Agent 是后续独立交付范围。

## 当前状态

RAG 已完成 Stage 2.8.2。13 份已登记 PDF 共 2178 个物理页，生成 4537 个 canonical KnowledgeChunk，其中 4532 个符合检索资格。每条结果保留文档、来源路径和物理页码。

- PDF 清洗与切块采用 `pdf-chunks-v3`。
- Dense 使用独立的 token-safe passage，检索后聚合回 canonical parent。
- 索引契约绑定模型指纹、编码模板、tokenizer 与 passage 配置，拒绝混用不兼容索引。
- 冻结评测包含 21 条可回答问题和 11 条负例，采用 `evidence-contract-v2`。
- Stage 2.8.2 复用 E5 与 Qwen3 的签名索引，各取前 10 个 parent，用 Qwen3-Reranker-0.6B 评分后返回前 5 个。

固定样本上，双模型重排的 Hit@5 为 20/21，MRR@5 为 0.6071。实际评分 passage 的证据覆盖为 19/21。`shine-ioc-startup` 仍缺少完整证据，parent 命中也不保证被评分 passage 含有全部证据。结果属于小样本诊断，尚未校准负例拒答阈值。

当前推荐保留双模型候选加重排方案，但尚未改为通用 CLI 的默认路径。未实现 OCR、复杂公式与表格识别、PPTX/DOCX 解析、Hybrid、LLM 回答或 Agent 检索工具接入。

## 环境

```bash
conda env create -f environment.yml
conda activate accelerator-rag
python -m pip install -e ".[dev]"
```

原始文件位于 `data/l0_raw/`，由 `data/documents/registry.json` 登记。原始 PDF、模型权重和本地 Qdrant 索引均不进入 Git。模型需单独准备，正式编码使用离线加载。

## 使用与验证

```bash
python scripts/corpus_inventory.py
python -m accelerator_rag.retrieval.cli \
  --document-id shine-epics-ioc-pv-information-management-pcapac2022 \
  --query 'How are IOC and PV information managed in SHINE?' \
  --top-k 3
pytest -q
ruff check .
git diff --check
```

默认 CLI 使用 BM25。Dense 的本地模型、集合与 passage 规则见运行手册。Stage 2.8.1 和 Stage 2.8.2 脚本依赖对应的历史报告、模型和索引，运行条件见[双模型检索与重排](docs/runbooks/dense-reranking.md)。

## 文档入口

- [当前 RAG 里程碑](docs/roadmap/CURRENT.md)：现状、指标与限制。
- [检索运行手册](docs/runbooks/knowledge-retrieval.md)：数据边界、查询和索引语义。
- [全语料基线](docs/runbooks/corpus-baseline.md)：清洗、资格策略和证据评测。
- [Dense passage](docs/runbooks/dense-passages.md)：token 预算与 parent 聚合。
- [Embedding 比较](docs/runbooks/embedding-comparison.md)：模型契约、指纹和离线测量。
- [证据审核](docs/runbooks/evidence-audit.md)：标注审核、重判与索引签名。
- [双模型检索与重排](docs/runbooks/dense-reranking.md)：最新实验入口与结果。

旧学习期检索实现、演示数据和重复入口已由正式链路替代。历史报告保留测量当时的环境与结论，不能代替当前接口说明。长期 Agent 目标见 [Agent 总体设计规划](docs/AGENT_MASTER_PLAN.md)。
