# Retrieval evidence judgments

`retrieval_baseline.json` 使用 `schema_version: 2`，当前 judgment revision 为 `evidence-contract-v2`。查询集包含 21 条可回答问题、3 条明显负例、8 条领域负例。标注覆盖全部 13 份 PDF，已完成 Stage 2.7.1 的全语料 alternative 审核，仍不保证穷尽所有改写。

每条 query 包含 `judgment_mode` 和 `evidence_groups`。每组的 `alternatives` 绑定 `document_id`、从 1 开始的物理 `page` 和原始 PDF `excerpt`。组内为 OR；`all` 模式要求所有组，`any` 模式要求任一组。普通问题可以只用一组。

相关 Chunk 必须匹配文档、覆盖物理页，并包含规范化后的摘录。同页其他 Chunk 不自动相关。规范化执行 NFKC、大小写折叠、NULL 移除、空白折叠，以及英文连字符后的换行断词合并。行内技术连字符保留。不使用模糊距离或 embedding 判断。

加载时逐条验证全部 alternative：摘录存在于原始页，也存在于至少一个 eligible Chunk。缺失即失败，并报告 query ID、文档、页号和摘录。这个约束强于每组仅有一个可检索 alternative。正文切块边界可以导致验证失败，不能把标注失败计为检索失败。

21 条旧问题均已逐页复核，具体修改原因见 JSON 中的 `review` 和 `judgment_note`。重点修正 CLI 三种命令、XFEL 两个参数、SHINE 连续波模式、低温主 PLC 与 CPLD 职责，以及 IOC 提交字段。标注在 Stage 2.5 排名前固定。原 Stage 2 报告保存旧标注与结果，用作历史记录。

负例使用 `negative_type: obvious | hard_domain`，且证据组为空。领域负例均询问 2026 年 10 月 19 日的运行实测或部署状态。静态设计文档不能提供这些值。JSON 保存全语料日期搜索、主题搜索和上下文样本。日期词未出现并非单独充分证明；同时检查了文档年代、设计参数性质和相关运行机制描述。8 条负例集中于时效性缺口，尚未覆盖所有领域负例类型。

Hit@K 表示可回答问题中，Top-K 覆盖所需证据的问题比例。`all` 模式要求全部组。`first_complete_rank` 表示首次满足完整判断的排名，MRR@5 使用该排名。无答案问题不进入指标分母。完整命令见[运行手册](../../docs/runbooks/corpus-baseline.md)。

Stage 2.7.1 保留 `retrieval-baseline-v1.json`，新增审核记录和人工 review artifact。离线重判不会重新检索或 embedding，详见[运行手册](../../docs/runbooks/evidence-audit.md)。
