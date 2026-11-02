# Waveform 使用与维护文档

从采集数据到分析结果，按当前任务选择文档。

| 你现在要做什么 | 阅读哪份文档 |
| --- | --- |
| 找回一次采集，弄清任务、数据段和设备文件 | [存储与数据流技术说明](waveform-storage-dataflow.md) |
| 对齐多台设备，判断结果能否继续分析 | [对齐语义、参数与诊断手册](alignment-semantics-and-diagnostics.md) |
| 排查类似故障，判断历史案例和版本变化是否适用 | [历史故障记录与版本变更说明](fault-history-and-version-changes.md) |
| 把文档加入 RAG，检查检索、引用和答案 | [RAG 知识入库、验证与回滚手册](../runbooks/rag-ingestion-verification-rollback.md) |

三份 Waveform 文档以 `waveform-storage-system@dc50e08` 为代码基线，核验日为 2026-10-29。现场任务的实际版本仍需查其部署记录。四份文档的负责人尚未指派。

文档已于 2026-10-29 按读者任务重写，旧稿保存在[重写前归档](../../reports/phase1-review-20261029/before-reader-rewrite/)。源码和审计定位移入文末，历史案例保留原编号。故障结论的修正见新版案例正文；旧审计汇总和种子题不会因此自动变成已复核材料。

Markdown 解析与入库路径已在工作区实现。生产是否加载本次修订，应以实际发布和服务验证记录为准。修改正文后，按[入库手册](../runbooks/rag-ingestion-verification-rollback.md)更新快照和解析报告；旧章节号和摘录需要重新核对，不能直接沿用旧题集的核验标签。

本轮已重新编写并绑定 [50 题开发集](../../data/evaluation/validity-pilot-v2.md)。4 份文档的本地解析、索引更新测试与线上目录核验见[本轮报告](../../reports/validity-pilot-20261029/README.md)。
