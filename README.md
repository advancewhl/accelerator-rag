# SHINE/EPICS Trusted Agent

面向加速器控制、EPICS 和 SHINE 领域知识的可私有化部署 Agent 项目。

项目以 LangGraph 作为编排层，保留并持续完善原有 PDF/PPTX/DOCX 解析、BM25、Dense 和 Qdrant 检索能力。RAG 作为 Agent 的第一个领域工具，与任务规划、工具调用、结果核验、澄清、人工确认、可观测和部署能力并行建设。

完整的长期目标、边界、架构、阶段出口和目录责任见 [Agent 总体设计规划](docs/AGENT_MASTER_PLAN.md)。当前唯一执行状态见 [当前里程碑](docs/roadmap/CURRENT.md)。

## 当前状态

已有基础：

- PDF 文档解析与切块；
- 文档 Registry 和语料盘点；
- BM25、内存 Dense 和 Qdrant 检索；
- 固定问题的基础检索评价；
- Pytest、Ruff 和 Qdrant Docker Compose。

正在进入 M1：

- LangGraph 状态和最小工作流；
- 框架无关的工具契约；
- 将现有检索封装为 `knowledge_search`；
- CLI 端到端问答与测试。

尚未实现的 Agent、API、持久化、Web、可观测和完整部署能力不得描述为已完成。

## 设计边界

- 第一阶段采用单 Agent 和显式状态图；
- 所有领域工具默认只读；
- 不接入真实 EPICS 写操作；
- 权限、参数校验和审批由确定性代码控制；
- RAG 与 Agent 通过稳定工具接口解耦；
- 风险敏感检索研究暂不阻塞 Agent 主线。

## 目标结构

```text
accelerator-rag/
├── config/                  # 应用和服务配置
├── data/                    # 原始、处理、评测和测试夹具
├── deploy/                  # Docker 与部署配置
├── docs/
│   ├── architecture/        # 组件与接口设计
│   ├── decisions/           # Architecture Decision Records
│   ├── roadmap/             # 当前里程碑和后续计划
│   └── runbooks/            # 开发、部署与运维手册
├── scripts/                 # 可执行迁移和维护入口
├── src/accelerator_rag/
│   ├── agent/               # LangGraph 状态、节点和策略
│   ├── api/                 # FastAPI 服务
│   ├── corpus/              # 文档解析与切块
│   ├── domain/              # SHINE/EPICS 领域模型
│   ├── evaluation/          # RAG 与 Agent 评测
│   ├── memory/              # 会话、任务和 checkpoint 适配
│   ├── observability/       # trace、日志和指标
│   ├── retrieval/           # BM25、Dense 和混合检索
│   ├── storage/             # 数据存储适配
│   └── tools/               # 框架无关的领域工具
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

旧模块暂时保留原位置，在测试保护下逐步接入新边界，不进行一次性大搬迁。

## 环境

```bash
conda env create -f environment.yml
conda activate accelerator-rag
python -m pip install -e ".[dev]"
```

已有环境可直接更新：

```bash
conda activate accelerator-rag
python -m pip install -e ".[dev]"
```

## 当前验证命令

```bash
pytest -q
ruff check .
accelerator-rag
```

需要 Qdrant 时：

```bash
docker compose up -d
docker compose ps
```

## 历史分支

- `main`：原 30 天 RAG 学习项目基线；
- `learning-pause-2026-09-09`：原学习项目暂停检查点；
- `paper-risk-aware-retrieval`：风险敏感混合检索论文工作区；
- `codex/agent-platform`：当前完整 Agent 开发主线。
