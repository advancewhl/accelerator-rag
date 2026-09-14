# SHINE/EPICS 可信领域 Agent 总体设计规划

## 0. 文档定位

本文档是 `codex/agent-platform` 分支的长期设计基线，用于约束产品范围、系统架构、开发顺序和验收口径，避免开发过程中因上下文缺失而退化为局部功能堆叠。

- 项目主线：构建可私有化部署的 SHINE/EPICS 可信领域 Agent。
- 当前策略：LangGraph 与 RAG 并行推进，RAG 作为 Agent 的知识工具持续演进。
- 研究策略：风险敏感检索、结构反事实和学习式路由暂不阻塞 Agent 主线，在系统形成稳定数据与评测闭环后按价值恢复。
- 变更规则：架构、数据边界、安全边界或里程碑发生实质变化时，先更新本文档或新增 ADR，再修改代码。

## 1. 项目愿景

系统面向加速器控制、EPICS 和 SHINE 领域知识使用者，提供能够理解问题、规划步骤、调用领域工具、核验证据、请求澄清并保留完整审计轨迹的 Agent 服务。

它不是通用聊天机器人，也不是只展示向量检索的 RAG Demo。第一阶段需要形成从用户入口、Agent 编排、知识检索、工具调用、状态持久化、可观测、评测到私有化部署的完整纵向闭环。

## 2. 当前基线

Agent 分支从 `main` 创建，继承原 30 天学习计划截至 Day 9 的能力：

- PDF、PPTX、DOCX 解析基础；
- 文档 Registry 与语料盘点；
- 内存 Dense、BM25 和 Qdrant 检索；
- 基础检索评价；
- Python 单元测试和 Docker Compose 中的 Qdrant。

当前缺口：

- 没有 Agent 状态图、任务规划和工具协议；
- 没有完整的文档导入到问答链路；
- 没有生成、引用、澄清和拒答闭环；
- 没有 API、Web、会话持久化和人工确认；
- 没有 Agent trace、端到端评测和完整部署；
- 现有脚本以学习日程组织，尚未形成稳定应用边界。

## 3. 产品目标与非目标

### 3.1 第一阶段目标

1. 用户能够通过 Web 或 API 提交领域问题。
2. Agent 能够判断任务类型并选择合适工具。
3. Agent 能够检索 PDF、PPTX、DOCX，并返回可核验来源。
4. Agent 能够查询文档 Registry 和离线控制对象数据。
5. Agent 能在证据不足、实体歧义或工具失败时澄清或拒答。
6. Agent 执行状态能够持久化、恢复和审计。
7. 系统能够通过 Docker Compose 在单台服务器私有化部署。
8. 每次发布都能运行固定的 RAG 与 Agent 回归测试。

### 3.2 暂不纳入第一阶段

- 真实 EPICS 写操作和自主控制；
- 无人工监督的故障处置；
- 为展示而构造的多 Agent 对话；
- 大规模长期记忆和用户画像；
- Kubernetes、高可用集群和复杂租户计费；
- 学习式风险重排、结构反事实训练和学习式路由；
- 将框架或低代码平台本身作为项目成果。

## 4. 核心用户与首批场景

### 4.1 用户角色

- 控制系统工程师：定位 PV、IOC、设备和文档依据。
- 运行与值班人员：查询操作背景、关联对象和排查材料。
- 研究与开发人员：检索设计报告、培训材料和实现细节。
- 系统管理员：管理知识库、模型、权限、任务和审计日志。

### 4.2 首批纵向场景

#### 场景 A：带引用的控制知识问答

Agent 检索多格式资料，读取必要上下文，生成回答，并附文档、页码或幻灯片号、章节和版本。

#### 场景 B：PV/IOC/设备对象定位

Agent 抽取区域、子系统、设备、信号和限定符，联合 Registry 与文档证据，输出候选对象及无法确认的字段。

#### 场景 C：只读运维任务辅助

Agent 根据现象或日志规划查询步骤，调用知识检索、Registry、文档读取和离线 PV 快照工具，形成可审核的排查建议。第一阶段不执行控制写操作。

## 5. 总体设计原则

1. **单 Agent 优先**：先完成受控单 Agent 工作流，只有明确出现任务隔离或上下文冲突时才拆分多 Agent。
2. **确定性边界优先**：权限、参数校验、证据检查和审批由代码控制，不交给模型自由决定。
3. **RAG 工具化**：检索是 Agent 的工具，不与 Agent 编排耦合；检索实现升级不应修改主工作流。
4. **所有输出可追溯**：答案、工具结果和引用均绑定数据版本、调用参数和任务 ID。
5. **只读默认**：领域工具默认只读；未来任何写操作必须独立授权、审批和审计。
6. **失败显式化**：未知、冲突、超时和证据不足是合法状态，禁止静默降级为编造答案。
7. **先纵向闭环，再横向扩张**：先打通一个场景的界面、服务、工具、数据、评测和部署。
8. **框架可替换**：LangGraph 只存在于编排层，领域模型与工具契约不依赖其内部对象。

## 6. 系统架构

### 6.1 分层

```text
Client Layer
  Web UI / REST API / CLI

Application Layer
  Session / Task / Streaming / Authentication

Agent Orchestration Layer
  LangGraph / State / Nodes / Policies / Checkpoints

Domain Tool Layer
  Knowledge Search / Registry Lookup / Document Reader / PV Snapshot

Knowledge Layer
  Ingestion / Parsing / Chunking / Embedding / BM25 / Qdrant / Citation

Platform Layer
  PostgreSQL / Qdrant / Model Provider / Observability / Docker Compose
```

### 6.2 模块所有权

- LangGraph：节点调度、状态流转、中断恢复和人工介入。
- 应用代码：领域状态、工具契约、安全策略、错误语义和任务结果。
- RAG 子系统：文档导入、证据单元、索引、召回和引用。
- FastAPI：外部 API、SSE/流式事件、鉴权和健康检查。
- PostgreSQL：用户、会话、任务、checkpoint 元数据和反馈。
- Qdrant：向量索引与检索元数据。
- Phoenix/OpenTelemetry：模型、检索、工具和节点级 trace。

## 7. Agent 运行模型

### 7.1 状态对象

`AgentState` 至少包含：

- `task_id`、`session_id`、`user_id`；
- 原始请求与规范化请求；
- 意图、领域实体和缺失字段；
- 计划步骤与当前步骤；
- 工具请求、工具结果和错误；
- 检索证据和引用；
- 风险等级与审批状态；
- 最终答案、终止原因和运行指标。

状态必须使用显式 Schema，禁止以无约束字典在节点间传递核心数据。

### 7.2 首版状态图

```text
START
  -> understand
  -> decide_route
      -> clarify -> END
      -> plan
  -> execute_tool
  -> verify_result
      -> retry_or_replan -> execute_tool
      -> require_approval -> wait_for_human
      -> compose_answer
  -> finalize
  -> END
```

### 7.3 终止状态

- `completed`：任务完成并具有足够证据。
- `clarification_required`：需要用户补充对象或范围。
- `approval_required`：后续步骤需要人工批准。
- `insufficient_evidence`：检索或工具结果不足。
- `tool_failed`：工具失败且重试/替代策略耗尽。
- `policy_blocked`：权限或安全策略拒绝执行。

## 8. 工具体系

### 8.1 工具统一契约

每个工具必须定义：

- 稳定的工具名称和用途；
- Pydantic 输入/输出模型；
- 权限级别与只读/写入属性；
- 超时、重试和幂等性；
- 来源、数据版本与时间戳；
- 可返回的结构化错误；
- trace 属性和脱敏规则；
- 单元测试与模拟实现。

### 8.2 第一批工具

| 工具 | 用途 | 第一阶段数据源 | 风险级别 |
| --- | --- | --- | --- |
| `knowledge_search` | 检索文档证据 | BM25、Dense、Qdrant | 低 |
| `document_reader` | 读取命中证据的上下文 | 解析后的文档与原文定位 | 低 |
| `registry_lookup` | 查询文档、PV、IOC、设备关系 | Registry 或离线导出 | 低 |
| `pv_snapshot` | 查询离线或模拟 PV 快照 | Fixture/脱敏快照 | 中 |
| `report_export` | 导出任务与证据报告 | 当前任务状态 | 低 |

任何真实控制写工具都不进入第一阶段代码路径。

## 9. RAG 子系统规划

### 9.1 导入流水线

```text
Source registration
  -> file validation
  -> PDF/PPTX/DOCX parsing
  -> structure-aware chunking
  -> metadata normalization
  -> embedding and sparse indexing
  -> index manifest
  -> retrieval smoke test
```

### 9.2 证据单元最小字段

- chunk ID、document ID；
- 标题、正文、语言；
- 文件路径、文件哈希和文档版本；
- 页码、幻灯片号、章节路径或表格位置；
- 解析器版本和切块策略版本；
- 可选的 area、subsystem、device、signal、IOC、PV 元数据。

### 9.3 检索演进顺序

1. 保持现有 BM25 和 Dense 可运行。
2. 建立统一 Retriever 协议与结果 Schema。
3. 完成 Qdrant 持久索引和增量更新。
4. 实现简单固定融合和 Metadata 过滤。
5. 建立引用完整性和固定回归集。
6. 系统稳定后再评估风险重排、反事实训练和学习式路由。

## 10. 数据与状态

### 10.1 数据类别

- 原始资料：只读文档和导出快照。
- 处理数据：解析结果、Chunk 和实体关联。
- 索引数据：Qdrant collection、BM25 索引和 manifest。
- 应用数据：用户、会话、任务、消息、反馈和审批。
- 观测数据：trace、日志、指标和异常。
- 评测数据：固定问题、工具期望、引用真值和端到端任务。

### 10.2 版本原则

- 原始文件以哈希识别，不覆盖历史版本。
- 每个索引记录语料快照、模型和切块配置。
- 每次 Agent 运行记录工作流版本、Prompt 版本、模型和工具版本。
- 评测结果能够回溯到代码提交和数据快照。

## 11. 安全与权限

1. 用户、服务和工具采用最小权限。
2. 第一阶段领域工具只读，PV 数据使用模拟、离线或脱敏快照。
3. 工具调用前执行参数 Schema、资源范围和权限检查。
4. 中高风险操作必须进入显式审批节点。
5. Prompt、日志、trace 和错误信息不得泄露密钥或敏感字段。
6. 每次调用记录用户、任务、工具、参数摘要、结果摘要和时间。
7. 模型无法绕过 Policy 层直接访问底层连接器。

## 12. 可观测与评测

### 12.1 可观测范围

- 请求总时延和首 Token 时延；
- 每个节点耗时与状态转换；
- 模型调用、Token 和成本；
- 检索查询、候选和引用；
- 工具参数、结果、错误和重试；
- 澄清、拒答、人工接管和任务终止原因。

### 12.2 评测层级

- RAG：Recall@K、MRR、引用命中率、引用完整率。
- 工具：工具选择正确率、参数正确率、结果解析成功率。
- Agent：任务完成率、步骤成功率、重规划率、错误终止率。
- 安全：越权阻断率、应澄清命中率、错误回答率。
- 系统：P50/P95 延迟、恢复成功率、部署健康检查和资源消耗。

首版评测集以 20 至 30 个端到端任务为目标，同时保留小型检索回归集。未经人工核验的数据不得作为发布门槛的测试真值。

## 13. 部署设计

### 13.1 第一阶段拓扑

Docker Compose 管理：

- `api`：FastAPI 与 Agent 应用；
- `worker`：异步或长任务执行；
- `web`：用户界面；
- `postgres`：应用状态与 checkpoint；
- `qdrant`：向量索引；
- `phoenix`：trace 与评测界面；
- 可选本地模型或 OpenAI-compatible 模型网关。

### 13.2 部署验收

- 新机器按文档可完成部署；
- 服务提供健康检查；
- 配置通过环境变量和受控配置文件注入；
- 数据卷、备份和恢复路径明确；
- 容器重启后会话和任务状态可恢复；
- 未配置可选服务时具有明确错误，而非静默降级。

## 14. API 与交互

第一批 API：

- `POST /sessions`：创建会话；
- `POST /tasks`：提交 Agent 任务；
- `GET /tasks/{id}`：读取任务状态；
- `GET /tasks/{id}/events`：流式事件；
- `POST /tasks/{id}/resume`：补充信息或批准后恢复；
- `POST /knowledge/documents`：登记/导入文档；
- `POST /knowledge/reindex`：启动索引任务；
- `GET /health/live` 与 `GET /health/ready`。

Web 第一版只需支持对话、任务步骤、引用查看、审批按钮和运行轨迹，不追求复杂视觉设计。

## 15. 技术决策

### 已确定

- 使用 LangGraph 作为 Agent 编排框架。
- 使用 FastAPI 暴露服务。
- 保留 Qdrant 作为向量存储。
- RAG 通过工具接口接入 Agent。
- 第一阶段采用单 Agent 和显式状态图。
- 第一阶段只提供只读领域工具。
- 以 Docker Compose 完成单机私有化部署。

### 推迟决定

- PostgreSQL checkpoint 的具体实现；
- Web 使用轻量 Python UI 还是独立前端；
- 模型网关采用 LiteLLM 还是内部适配层；
- 异步任务采用内置后台任务、Redis 队列还是独立工作流系统；
- 是否以及何时拆分多 Agent；
- 是否恢复风险敏感检索研究模块。

推迟项必须由实际需求或测试数据触发，不因框架示例而提前引入。

## 16. 目录蓝图

第一阶段不重命名 Python 包，避免无价值的大规模迁移。在现有 `accelerator_rag` 中增加 Agent 应用层：

```text
accelerator-rag/
├── config/
├── data/
│   ├── raw/
│   ├── parsed/
│   ├── processed/
│   ├── evaluation/
│   └── fixtures/
├── deploy/
├── docs/
│   ├── architecture/
│   ├── decisions/
│   ├── roadmap/
│   └── runbooks/
├── scripts/
├── src/accelerator_rag/
│   ├── agent/
│   │   ├── nodes/
│   │   ├── graph.py
│   │   ├── state.py
│   │   └── policies.py
│   ├── api/
│   ├── corpus/
│   ├── domain/
│   ├── evaluation/
│   ├── memory/
│   ├── observability/
│   ├── retrieval/
│   ├── storage/
│   └── tools/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

现有模块先保留原位置，通过适配器接入；只有在测试覆盖下才移动旧代码。

## 17. 分阶段路线

### M0：分支与设计基线

- 保存论文分支检查点；
- 从 `main` 创建 Agent 分支；
- 固化总体规划、ADR 机制和目录责任。

出口：历史可恢复，Agent 与论文主线互不污染。

### M1：最小 Agent 闭环

- LangGraph 状态与四节点流程；
- 现有检索器封装为 `knowledge_search`；
- CLI 完成提问、检索、回答；
- 节点和工具具有单元测试。

出口：真实问题能够经过 Graph 调用真实检索器并返回结构化来源。

### M2：统一知识流水线

- PDF/PPTX/DOCX 统一导入；
- 结构化 Chunk、增量索引和索引 manifest；
- BM25、Dense、Qdrant 统一协议；
- 引用定位与检索回归测试。

出口：新文档能够从导入一直进入 Agent 回答。

### M3：领域工具与受控执行

- Registry、文档读取和 PV 快照工具；
- 计划、执行、验证、重试和澄清；
- 工具权限、参数校验和结构化错误；
- 20 至 30 个端到端任务。

出口：至少一个对象定位或只读运维场景完整可演示。

### M4：服务化与状态恢复

- FastAPI、流式事件和会话 API；
- PostgreSQL/checkpoint；
- Human-in-the-loop；
- Web 最小界面。

出口：浏览器可使用，任务能在中断和重启后恢复。

### M5：可观测、评测与部署

- Phoenix/OpenTelemetry；
- Agent、工具、RAG 和安全评测；
- Docker Compose 完整服务；
- 部署、备份、恢复和故障排查文档。

出口：新环境可重复部署，固定任务集通过发布门槛。

### M6：能力扩展

根据真实使用反馈选择：

- 运维报告和知识维护工作流；
- MCP 工具接入；
- 多 Agent 拆分；
- 风险敏感重排与结构反事实；
- 更严格的鉴权、租户隔离和高可用。

## 18. 每周工作分配

在 M1 至 M3 期间建议：

- 50% Agent 编排、工具和应用接口；
- 35% 文档处理、索引和 RAG；
- 15% 测试、文档、部署和复盘。

任何一周都必须产生可运行的端到端增量，不能只增加抽象层、Prompt 或离线脚本。

## 19. 完成定义

一个功能只有同时满足以下条件才算完成：

1. 通过用户入口或稳定接口可调用；
2. 输入输出具有 Schema；
3. 正常、空结果和失败路径均有测试；
4. 具有日志或 trace；
5. 不绕过权限和安全策略；
6. 文档说明如何运行和验证；
7. Docker 环境中的行为与本地一致；
8. 不破坏现有 RAG 回归结果。

## 20. 防止上下文丢失的项目机制

- 本文档：保存长期目标、范围和总体架构。
- `docs/decisions/`：每个重大技术决策一份 ADR，记录背景、选择和后果。
- `docs/roadmap/CURRENT.md`：只记录当前里程碑、完成项、阻塞项和下一步。
- `docs/runbooks/`：记录开发、部署、索引、备份和故障处理步骤。
- GitHub Issue 或等价任务列表：保存可验收工作项，不把计划只放在聊天记录中。
- 每次提交只服务于一个可描述目标，并在提交前运行相关测试。
- 每个里程碑结束时更新 `CURRENT.md`，禁止让旧计划与代码状态长期不一致。

## 21. 首批执行清单

1. 建立规划中的目录骨架与责任说明。
2. 新增 LangGraph 依赖和最小运行配置。
3. 定义 `AgentState` 与终止状态。
4. 定义框架无关的 Tool 输入、输出和错误契约。
5. 将现有检索封装为 `knowledge_search`。
6. 实现 `understand -> retrieve -> verify -> answer`。
7. 增加 CLI 入口和最小真实语料演示。
8. 为 Graph 路由、工具失败和引用生成补测试。
9. 建立 `CURRENT.md` 并记录 M1 状态。
10. M1 验收后再进入 FastAPI、持久化和更多领域工具。

## 22. 主要风险

| 风险 | 控制措施 |
| --- | --- |
| 同时学习太多框架组件 | 只学习当前纵向功能需要的 LangGraph API |
| RAG 与 Agent 两套代码脱节 | 所有 RAG 能力通过稳定工具契约进入 Agent |
| 一开始追求多 Agent | M3 前保持单 Agent，使用显式节点分工 |
| 文档处理持续占用全部时间 | 先支持现有三类格式和可核验引用，再扩格式 |
| 模型结果不可复现 | 固定评测集、Prompt 版本、模型配置和 trace |
| 工具误调用 | Schema、权限、超时、幂等和审批节点 |
| 目录重构破坏旧代码 | 添加新边界优先，旧模块只在测试保护下移动 |
| 原研究方案反复抢占主线 | 将研究项保持为 M6 候选，不进入 M1-M5 门槛 |

## 23. 项目级成功标准

第一阶段成功不是“接入了 LangGraph”，而是：

- 一个新用户能够部署并打开系统；
- 上传或登记文档后能够完成索引；
- Agent 能规划并调用多个真实领域工具；
- 回答具有可核验引用；
- 歧义、无证据和工具失败得到正确处理；
- 任务状态可恢复、调用过程可追踪；
- 固定端到端任务集能够持续回归；
- 系统始终保持只读安全边界。

