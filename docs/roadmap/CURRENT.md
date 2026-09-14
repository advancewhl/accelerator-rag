# Current Milestone

## 当前阶段

M0：分支与设计基线。

## 已完成

- 风险敏感检索论文现场已保存到 `paper-risk-aware-retrieval` 分支。
- Agent 分支已从 `main` 创建。
- Agent 总体规划与首份 ADR 已建立。

## 正在进行

- 建立 Agent 应用层、工具层和项目文档目录骨架。

## 下一里程碑

M1：最小 Agent 闭环。

验收目标：真实问题能够经过 LangGraph 调用现有检索器，并返回结构化证据；正常、空结果和失败路径具有测试。

## 下一步

1. 增加 LangGraph 依赖和配置。
2. 定义 `AgentState` 与工具契约。
3. 封装 `knowledge_search`。
4. 实现最小四节点 Graph。
5. 增加 CLI 和测试。

## 当前阻塞

无。

