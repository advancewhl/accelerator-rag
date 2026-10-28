# RAG 文档与文件导航

独立 RAG 服务使用 `ds-1017`，执行问题拆解、多路召回、证据选择、生成、核查和有界补检索。通用检索 CLI 与独立问答服务保留各自入口。

## 按任务查找

| 任务 | 入口 |
| --- | --- |
| 查看上次提交后的改动与清理范围 | [相对 4099ce1 的变更说明](changes-since-4099ce1.md) |
| 理解模块职责 | [RAG 代码目录](../../src/accelerator_rag/rag/README.md) |
| 理解四阶段闭环 | [证据闭环设计](../architecture/rag-evidence-workflow.md) |
| 启动、隧道和排障 | [生产运行手册](../runbooks/rag-production.md) |
| 查看实现验收与限制 | [框架验收](../../reports/rag-framework-20261028.md) |
| 查看召回指标 | [指标复核](../../reports/rag-framework-20261028/retrieval-metrics.md) |
| 阅读论文 | [详细章节](../../papers/rag-thesis/README.md)；[论文 LaTeX 工程](../../papers/rag-paper/README.md) |
| 导入语料与传统检索 | [知识检索手册](../runbooks/knowledge-retrieval.md) |

## 文件分区

| 路径 | 用途 |
| --- | --- |
| `src/accelerator_rag/rag/` | 独立服务、证据闭环、文档目录及前端。 |
| `src/accelerator_rag/retrieval/`、`storage/` | 通用检索、重排及只读签名索引。 |
| `src/accelerator_rag/domain/`、`providers/` | 模型消息、结构化参数和可选调用上下文；RAG 不要求安装 Agent 运行模块。 |
| `config/rag-production.json` | 运行配置，凭据在仓库外注入。 |
| `deploy/rag-start.sh`、`rag-requirements.txt` | 当前 GPU 部署入口及依赖。 |
| `deploy/systemd/user/accelerator-rag-tunnel.service` | 本机端口转发与断线重连。 |
| `tests/rag/`、`tests/providers/test_model*.py` | RAG 与共享模型契约测试。 |
| `scripts/rag_framework_{check,review,metrics}.py` | 正式 HTTP 回归、事后核对和已保存结果的指标计算。 |
| `reports/rag-framework-20261028/` | 完整回归、最终复测、过程记录和指标。 |
| `papers/rag-thesis/`、`papers/rag-paper/` | 历史论文章节和完整论文源码、数据及图表。 |
| `output/pdf/` | 两份最终论文 PDF；其它输出在构建时生成。 |
| `tmp/` | 已忽略的模型、索引和本地临时文件，不随源码发布。 |

## 历史证据

[Stage 2.8.2](../../reports/rag-stage-two-eight-two-reranking.md) 是上次提交的检索基线；[Stage 3](../../reports/rag-stage-three-production-loop.md)、[早期生产验收](../../reports/rag-production-readiness-20261026.md)、[前端重建](../../reports/rag-frontend-20261027.md)、[模型切换](../../reports/rag-ds-1017-switch-20261027.md)、[目录与展示](../../reports/rag-catalog-answer-20261027.md) 和 [低温诊断](../../reports/rag-cryo-diagnosis-20261028.md) 保留当时环境与结论。

旧启动和捕获脚本已清理，当前运行以生产手册为准。中间重复回执和逐页预览已移出提交范围，关键失败结论、完整回归与最终复测仍可核查。

## 提交边界

本次提交包含 RAG 服务、必要共享模型组件、检索运行库、前端、部署、测试、文档、验收及论文源码。Agent、Waveform、MCP 的业务实现和运行配置不属于本次提交。

模型上下文模块只在旧 Agent 预算模块已经加载时提供兼容，不会因导入 RAG 而加载 Agent。模型、索引、原始 PDF、凭据、本地清理恢复包及重复生成物不进入 Git。
