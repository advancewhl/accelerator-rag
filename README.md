# SHINE/EPICS Knowledge Retrieval

面向加速器控制、EPICS 和 SHINE 文档的知识检索与问答工程。RAG 文档统一入口见 [RAG 文件导航](docs/rag/README.md)，上次提交后的改动见 [变更说明](docs/rag/changes-since-4099ce1.md)。

## 当前 RAG 状态

截至 2026 年 10 月 28 日，独立 RAG 已提供 HTTP 问答、知识库目录、引用和页内 PDF 阅读。生成模型使用 `ds-1017`，问答执行问题拆解、多路召回、证据子集选择、核查和定向补检索。部署及访问见 [生产运行手册](docs/runbooks/rag-production.md)。

服务复用已有签名索引。BM25、E5／Qwen3 语义召回与 Qwen3 重排共同生成候选；最多执行 2 轮检索，最终证据最多保留 5 个父块及 6,000 个证据 token。设计与边界见 [证据闭环](docs/architecture/rag-evidence-workflow.md)。通用 CLI 默认仍使用 BM25。

冻结语料基线包含 13 份 PDF、2178 个物理页和 4537 个规范父块，其中 4532 个符合检索资格。清洗与切块采用 `pdf-chunks-v3`，索引契约绑定模型指纹、编码模板、tokenizer 与 passage 配置。每条引用保留文档版本及物理页。

本次完整回归包含 36 道问题，最后两项修复后复测其中 6 道。21 道正例的完整回归记录中，首轮 Top-5 完整覆盖 19 题，Top-20 与最终证据子集覆盖 21 题。该数据来自开发集，不能等同于全库回答准确率，也不代表最终代码重新跑过全部问题。详细结果见 [验收报告](reports/rag-framework-20261028.md) 和 [召回指标](reports/rag-framework-20261028/retrieval-metrics.md)。

Stage 2.8.2 是上次提交的历史检索基线：双模型重排完整 Hit@5 为 20／21，MRR@5 为 0.6071。新闭环的最终覆盖与首轮排序应分别评价，历史指标不能直接作为当前服务质量。

当前仍缺更大的独立测试集和独立人工回答评分；OCR、复杂公式与表格识别、PPTX／DOCX 解析、文档上传及在线索引重建尚未实现。设计文档也不能证明实时控制读数。

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

- [RAG 文件导航](docs/rag/README.md)：代码、部署、测试与验收记录的统一入口。
- [RAG 提交后变更](docs/rag/changes-since-4099ce1.md)：相对 `4099ce1` 的改动和共享依赖。
- [独立 RAG 运行手册](docs/runbooks/rag-production.md)：生产服务、本机隧道与排障。
- [证据闭环设计](docs/architecture/rag-evidence-workflow.md)：需求覆盖、核查和反馈。
- [当前 RAG 里程碑](docs/roadmap/CURRENT.md)：现状、指标与限制。
- [检索运行手册](docs/runbooks/knowledge-retrieval.md)：数据边界、查询和索引语义。
- [全语料基线](docs/runbooks/corpus-baseline.md)：清洗、资格策略和证据评测。
- [Dense passage](docs/runbooks/dense-passages.md)：token 预算与 parent 聚合。
- [Embedding 比较](docs/runbooks/embedding-comparison.md)：模型契约、指纹和离线测量。
- [证据审核](docs/runbooks/evidence-audit.md)：标注审核、重判与索引签名。
- [双模型检索与重排](docs/runbooks/dense-reranking.md)：最新实验入口与结果。

旧学习期检索实现、演示数据和重复入口已由正式链路替代。历史报告保留测量当时的环境与结论，不能代替当前接口说明。长期 Agent 目标见 [Agent 总体设计规划](docs/AGENT_MASTER_PLAN.md)。
