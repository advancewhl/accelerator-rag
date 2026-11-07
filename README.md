# SHINE/EPICS Knowledge Retrieval

面向加速器工程知识的 RAG 项目。当前研究主线见[研究重构方案](docs/research/rag-research-reset-20261107.md)：以现有异构知识库和实现为核心，研究跨资料关系、证据组合与可执行核验；Archiver 作为辅助证据源。旧论文草稿和旧计划不再约束后续研究。RAG 文档统一入口见 [RAG 文件导航](docs/rag/README.md)。

## 当前 RAG 状态

**2026-11-07 核查：** GPU 生产容器已挂载 `kb-2.0.0-rc.3`，健康接口正常。登记库包含 225 个修订、104 个文档族；rc.3 构建包含 222 个修订、10,793 个父块、10,654 个可索引父块和 6,989 条表格行记录。现有 100 题仍属于工程回归与开发材料，独立人工语义评分尚未完成。见 [rc.3 实现记录](reports/kb-2.0.0-rc.3-20261105/README.md)、[研究证据快照](reports/research-reset-20261107/evidence-audit.json)。

截至 2026 年 10 月 30 日，独立 RAG 已提供 HTTP 问答、知识库目录、引用及 PDF／Markdown 原文阅读。生产语料为 13 份 PDF 和 4 份 Markdown。生成模型使用 `ds-1017`，问答执行问题拆解、多路召回、证据子集选择、核查和定向补检索。部署及访问见 [生产运行手册](docs/runbooks/rag-production.md)。

服务复用已有签名索引。BM25、E5／Qwen3 语义召回与 Qwen3 重排共同生成候选；最多执行 2 轮检索，最终证据最多保留 5 个父块及 6,000 个证据 token。设计与边界见 [证据闭环](docs/architecture/rag-evidence-workflow.md)。通用 CLI 默认仍使用 BM25。

冻结语料基线包含 13 份 PDF、2178 个物理页和 4537 个规范父块，其中 4532 个符合检索资格。清洗与切块采用 `pdf-chunks-v3`，索引契约绑定模型指纹、编码模板、tokenizer 与 passage 配置。每条引用保留文档版本及物理页。

本次完整回归包含 36 道问题，最后两项修复后复测其中 6 道。21 道正例的完整回归记录中，首轮 Top-5 完整覆盖 19 题，Top-20 与最终证据子集覆盖 21 题。该数据来自开发集，不能等同于全库回答准确率，也不代表最终代码重新跑过全部问题。详细结果见 [验收报告](reports/rag-framework-20261028.md) 和 [召回指标](reports/rag-framework-20261028/retrieval-metrics.md)。

Stage 2.8.2 是上次提交的历史检索基线：双模型重排完整 Hit@5 为 20／21，MRR@5 为 0.6071。新闭环的最终覆盖与首轮排序应分别评价，历史指标不能直接作为当前服务质量。

当前仍缺更大的独立测试集和独立人工回答评分。多格式解析和结构化表格已进入 rc.3；复杂公式、图片关系和 OCR 内容的可用性需按证据核验，不能从解析成功推断语义正确。设计文档也不能证明实时控制读数。

## 历史验证（2026-10-29）

该阶段验证了适用条件、版本依赖和证据缺口。4 份 Markdown 完成双路向量入库并上线，50 题完成线上问答。运行方法见[验证协议](docs/rag/validity-pilot-50.md)，部署、证据覆盖、逐题初审和评分争议见[线上报告](reports/validity-pilot-online-20261030/README.md)。50 次接口成功不等于 50 题答对，独立人工评分仍待完成。

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

- [知识库扩建与上线总体计划](docs/roadmap/knowledge-base-v2-plan.md)：基于 2026 年 11 月 2 日新增资料，规划多格式入库、版本管理、验证、发布与回滚。
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

旧学习期检索实现、演示数据和重复入口已由正式链路替代。历史报告保留测量当时的环境与结论，不能代替当前接口说明。后续研究以[研究重构方案](docs/research/rag-research-reset-20261107.md)为准；该方案中的事实层、证据包检索和学习重排器尚未实现。
