# SHINE/EPICS Knowledge Retrieval

面向加速器运行诊断与波形数据处理的适用条件与版本有效性 RAG 项目。当前研究与实施主线见 [PRAB 计划](PRAB_PLAN.md)，RAG 文档统一入口见 [RAG 文件导航](docs/rag/README.md)，上次提交后的改动见 [变更说明](docs/rag/changes-since-4099ce1.md)。

## 当前 RAG 状态

**2026-11-05 本地进展（rc.3 未上线）：** SHINE 网络线缆表与交换机配置表（15 份 XLSX/XLS）已登记并可在本地构建为 6,115 条行记录，支持按电缆编号、机柜、交换机与端口区间精确查询；修复了表格行指错父块、Qdrant 族过滤不一致、冲突与 OCR 校验漏洞及候选截断问题；工作台重建为“文档问答 / 表格查询 / 资料库”三视图；新增线缆 20 题开发集。GPU 主机构建、候选服务和线上题集运行尚未执行，生产仍为 rc.2。见 [rc.3 本地实现记录](reports/kb-2.0.0-rc.3-20261105/README.md)。

截至 2026 年 10 月 30 日，独立 RAG 已提供 HTTP 问答、知识库目录、引用及 PDF／Markdown 原文阅读。生产语料为 13 份 PDF 和 4 份 Markdown。生成模型使用 `ds-1017`，问答执行问题拆解、多路召回、证据子集选择、核查和定向补检索。部署及访问见 [生产运行手册](docs/runbooks/rag-production.md)。

服务复用已有签名索引。BM25、E5／Qwen3 语义召回与 Qwen3 重排共同生成候选；最多执行 2 轮检索，最终证据最多保留 5 个父块及 6,000 个证据 token。设计与边界见 [证据闭环](docs/architecture/rag-evidence-workflow.md)。通用 CLI 默认仍使用 BM25。

冻结语料基线包含 13 份 PDF、2178 个物理页和 4537 个规范父块，其中 4532 个符合检索资格。清洗与切块采用 `pdf-chunks-v3`，索引契约绑定模型指纹、编码模板、tokenizer 与 passage 配置。每条引用保留文档版本及物理页。

本次完整回归包含 36 道问题，最后两项修复后复测其中 6 道。21 道正例的完整回归记录中，首轮 Top-5 完整覆盖 19 题，Top-20 与最终证据子集覆盖 21 题。该数据来自开发集，不能等同于全库回答准确率，也不代表最终代码重新跑过全部问题。详细结果见 [验收报告](reports/rag-framework-20261028.md) 和 [召回指标](reports/rag-framework-20261028/retrieval-metrics.md)。

Stage 2.8.2 是上次提交的历史检索基线：双模型重排完整 Hit@5 为 20／21，MRR@5 为 0.6071。新闭环的最终覆盖与首轮排序应分别评价，历史指标不能直接作为当前服务质量。

当前仍缺更大的独立测试集和独立人工回答评分；OCR、复杂公式与表格识别、PPTX／DOCX 解析、文档上传及在线索引重建尚未实现。设计文档也不能证明实时控制读数。

## 本轮计划与验证（2026-10-29）

[新计划](PRAB_PLAN.md)将表头绑定降为解析基础能力，重点验证适用条件、版本依赖和证据缺口。4 份 Markdown 已完成双路向量入库并上线，50 题全部完成线上问答。运行方法见[验证协议](docs/rag/validity-pilot-50.md)，部署、证据覆盖、逐题初审和评分争议见[线上报告](reports/validity-pilot-online-20261030/README.md)。50 次接口成功不等于 50 题答对，独立人工评分仍待完成。

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

旧学习期检索实现、演示数据和重复入口已由正式链路替代。历史报告保留测量当时的环境与结论，不能代替当前接口说明。后续工作以 PRAB 计划为准；现有功能和历史实验不代表计划中的新能力已经实现。
