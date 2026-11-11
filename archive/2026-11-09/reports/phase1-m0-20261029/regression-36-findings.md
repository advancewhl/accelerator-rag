# 36 题回归：执行记录、汇总与失败清单（2026-10-29）

- 执行对象：M0 运行实例（`127.0.0.1:18003` SSH 隧道 → GPU 主机 `10.101.9.190:8003`）
- 执行时间：2026-10-29 13:09:47 – 13:22:42（+0800），wall ≈ 12 min 55 s
- 命令：见 [`m0-baseline.md`](m0-baseline.md) §6；原始输出 [`regression-36-http.json`](regression-36-http.json)，日志 [`regression-36.log`](regression-36.log)
- 题面：冻结基准 32 题（`data/evaluation/retrieval_baseline.json`，SHA-256 `f5578371…`）+ 4 道附加题；**请求只发送 `query`**，标签留在客户端
- 自动分析：[`regression-36-analysis.json`](regression-36-analysis.json) / [`regression-36-analysis.md`](regression-36-analysis.md)（脚本 [`analyze_regression.py`](analyze_regression.py)，可重跑）

## 1. 汇总

| 指标 | 本次（2026-10-29） | 历史（2026-10-28 全量） | 说明 |
| --- | --- | --- | --- |
| HTTP 200 | 36/36 | 36/36 | 只证明接口完成 |
| 客户端错误 | 0 | 0 | |
| 状态 | 24 `answered` / 1 `partial` / 11 `insufficient` | 23 / 2 / 11 | 唯一变化：`xfel-version-scopes` partial→answered |
| 状态自洽（脚本检查） | 36/36 `status_consistent=true` | 36/36 | 状态与 requirements/citations 不矛盾 |
| 引用 | 49 条 / 13 份文档 | 51 条 / 13 份文档 | |
| 契约违规（本次独立检查） | 0 | 0（历史记录） | 文档登记、页码范围、chunk 前缀、重复引用、状态一致性 |
| 冻结证据包含（组） | 29/35 | 30/35（同规则回算） | 定义见 §3 |
| 冻结证据完整覆盖（题） | 16/21 | 17/21（同规则回算） | 同上 |
| 耗时中位 | 29.47 s | 17.29 s | 同 base-url、同 2 工作线程 |
| 耗时 P95 | 63.77 s | 42.86 s | |
| 耗时最大 | 109.74 s | 59.86 s | `shine-ioc-management` |

逐题表见 [`regression-36-analysis.md`](regression-36-analysis.md) §逐题结果。

**结论分级**：接口层与引用契约全部通过（已证实）；回答语义正确性**未**人工评分（未做）；冻结证据覆盖比历史低 1 题（已证实，原因见 F2）。

## 2. 与历史记录的差异

1. **状态差异仅 1 题**：`xfel-version-scopes` 从 `partial` 变为 `answered`，与 2026-10-28 修复（跨年份 `scope_differences`）+ 日期前导零归一化后的 6 题定向复测结果一致。说明当前实例具备修复后行为。
2. **评测基线文件哈希漂移**：历史 HTTP 运行 `benchmark_sha256=3994d8eb…`，当前文件 `f5578371…`；但 32 题的 `id` 与 `query` 文本逐条一致（脚本核对，0 差异），差异在证据摘录/判定元数据。落盘的 `reports/rag-framework-20261028/independent-review.json` 已按 `f5578371…` 计算。因此**冻结目标包含率在两次运行之间不是严格同文件口径**，只能作方向性比较。
3. **耗时整体上升约 1.7 倍**（中位 17.29 → 29.47 s）。本次运行期间工作区代码、配置、索引契约均未变化（见 `m0-baseline.md` §3），因此不能归因于代码修改；可能因素为服务负载、模型排队、GPU 状态。**未定位，不作结论。**

## 3. “冻结证据包含”指标定义（必须与历史口径一致才可比）

规则与 `scripts/rag_framework_review.py` 相同：`citation.document_id == target.document_id` 且 `page_start <= target.page <= page_end` 且 `normalize_evidence(target.excerpt)` 是 `normalize_evidence(citation.quote)` 的子串；`judgment_mode` 全为 `all`，即 21 道可答题要求全部证据组命中。本脚本用 `accelerator_rag.evaluation.retrieval.normalize_evidence` 原文实现，未自造归一化。

**该指标只是诊断量**：命中不等于语义正确，未命中也不等于答案错误（见 F2）。

## 4. 失败与关注清单

### F1（严重度：中，建议 Phase 2 必修）比较符与边界语义丢失

- 现象：`interlock-latency`（SHINE 快联锁单节点/节点间响应时间）回答为
  “单节点响应时间的设计指标为 **10 µs**；实测平均值为 328.81 ns……节点间响应时间的设计要求为 **100 µs**”。
- 原文与冻结证据：`shine-accelerator-fast-interlock-2024` 物理页 2：“联锁系统单节点响应时间**应小于**10 µs，节点间的响应时间**应小于**100 µs。”
- 问题：把“上界要求（<）”表述为等值“为”，且把实测值与设计指标并列；对安全阈值而言，`=10 µs` 与 `<10 µs` 的工程含义不同。2026-10-28 报告已记录同类问题（“未显式保留设计要求页的‘小于’边界”），本次全量回归**再次出现**。
- 影响：属于计划中的“危险部分正确”模式。若回答被直接用于判断联锁是否满足指标，可能把刚好等于阈值的实现误判为合格。
- 建议：在约束核查器中加入“比较符保真”规则（答案数值周围必须出现原文比较符或显式说明）；并把 `S1-PARAM-002` 作为该规则的首个回归用例。
- 证据位置：`regression-36-http.json#cases[interlock-latency].response.answer`；`data/evaluation/retrieval_baseline.json#interlock-latency`。

### F2（严重度：低-中）引用逐字覆盖下降 2 题

- `shine-ioc-management`：历史 3/3 证据组命中 → 本次 1/3。本次引用 quote 是页面区块开头（如 “ARCHITECTURE OVERVIEW The data flow view …”）而非冻结句子；答案正文实际复述了 PV service / web service / IOC 启动登记三类事实。
- `timing-wrtd`：历史 1/1 → 本次 0/1。唯一引用的 quote 在 “the max repetit…” 处截断，冻结摘录更长，归一化子串判断失败。
- 影响：指标下降，但**不能据此判定答案错误**；同时说明“引用摘录”不总是完整句，作为证据单元不稳定。
- 建议：引用摘录按完整句/冻结目标句截取；Phase 2 的引用精准度评测需要区分“摘录完整性”和“答案语义”。
- 证据位置：`regression-36-analysis.json#frozen_evidence_containment.per_question`。

### F3（信息）耗时上升，原因未定位

见 §2.3。需要 GPU 主机侧观测（`nvidia-smi`、容器日志、并发请求数）才能判断；本次无权限，未执行。

### F4（信息）历史结果不能直接当最终代码的 36 题结论

历史全量回归之后还有两项修复（跨版本冲突、日期前导零），当时只复测 6 题。本次才是在（行为上）最终代码上重跑 36 题。两者必须分开报告，不能把历史 36 题数字标注为最终代码结果。

### F5（已核实为正常）4 道附加题行为符合修复后预期

- `cryo-original` / `cryo-paraphrase`：`answered`，保留“主 PLC 执行复杂安全逻辑 + CPLD 双向电光转换”，并显式写明“原文未描述 CPLD 在联锁链路中的位置与连接”。
- `cryo-missing-details`：`partial`，逐项列出缺失的端口接线表与保护阈值，未把“未给出”当作已提供。
- `xfel-version-scopes`：`answered`，分版本并列 2007 TDR（20 GeV 设计 / 17.5 GeV 常规）与 2010 参数表（Maximum energy 17.5 GeV），未合并口径。

## 5. 本次没有做的事（不得默认已完成）

1. **没有人工语义评分**：24 个 `answered` 只说明模型自报完整，未逐题判定正确性。F1 就是“状态 answered 但表述有工程风险”的实例。
2. **没有内部过程核查**：无 trace 访问权限，轮次、候选、子集预算、补检索未复核；相关结论只能引用 2026-10-28 归档。
3. **没有把 36 题当独立测试集**：它是开发回归集，题目来自冻结基准与截图问题；不得据此报告泛化性能。
4. **没有重跑 36 题以外的评测**（如 Stage 2.8.2 检索基线），也未重建索引。
5. **没有修改任何代码或配置**：本次只采集证据。

## 6. 修复建议清单（供 Phase 2 排期）

| 优先级 | 项 | 验收方式 |
| --- | --- | --- |
| P0 | 比较符/边界保真规则（F1） | `S1-PARAM-002` 与新增比较符回归用例全部通过；危险误导率单列 |
| P1 | 引用摘录按完整句/冻结目标截取（F2） | 同规则回算冻结证据包含率 ≥ 历史 17/21，且 quote 不以截断词结尾 |
| P2 | 服务耗时基线复测（F3） | 在 GPU 主机侧记录负载后重跑 36 题，与本次/历史三者对照 |
| P2 | 评测基线版本固定（F4） | 把 `benchmark_sha256` 写入每次运行记录并在报告中比对 |
