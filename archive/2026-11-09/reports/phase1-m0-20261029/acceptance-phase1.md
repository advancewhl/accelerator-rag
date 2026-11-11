# PRAB Phase 1 验收报告（2026-10-29）

本报告逐项列出 Phase 1 的已完成内容、实际执行的命令与结果、36 题回归、案例证据、文档版本绑定、
种子题状态、阻塞项与需裁决问题。**不使用“全部完成”掩盖待核实项**；凡未执行或无权核验的环节
均单独列出。

工作区：`/home/whloong/projects/accelerator-rag-prab`（git worktree，branch
`whloong/rag-prab-constraint-grounded`，HEAD `0b62844`）。
Waveform 证据仓库：`/home/whloong/waveform-storage/waveform-storage-system`（只读，HEAD `dc50e08`）。
核验日：2026-10-29（Asia/Shanghai）。

---

## 1. 总览

| # | 交付项 | 状态 | 证据位置 |
| --- | --- | --- | --- |
| 1 | 可复现的现有系统基线 M0 | **已完成**（远程字节重核受限，见 §3.4） | `reports/phase1-m0-20261029/m0-baseline.md` |
| 2 | 最终代码上的旧 36 题完整回归 | **已完成**（36/36 HTTP 200；语义正确性未人工评分） | `regression-36-http.json`、`regression-36-analysis.md`、`regression-36-findings.md` |
| 3 | 有原始证据支持的 Waveform 历史案例 | **已完成**（12 条：已证实 10 / 推断 1 / 待核实 1） | `reports/phase1-m0-20261029/waveform-audit/` |
| 4 | 四份经核验、绑定版本的核心文档 | **已完成**（版本字段已跨文档统一；待人工指派 owner） | `docs/waveform/*.md`、`docs/runbooks/rag-ingestion-verification-rollback.md` |
| 5 | 50 道带标准答案/来源/评分规则的种子题 | **已完成**（开发种子集，无人工复核） | `data/evaluation/seed-questions-v1.json` 等 |
| 6 | 文档入库路径实际验证 | **已实现 md 入库代码 + 本地全链路跑通；生产未部署** | `docs/runbooks/rag-ingestion-verification-rollback.md` §8.3；`reports/phase1-m0-20261029/md-ingestion-report.json` |

**一句话结论**：M0 冻结、36 题回归、12 条案例、4 份文档与 50 道种子题均产出了可复核产物；
计划中“国庆后 Waveform 对齐异常”**作为版本回归不成立**，但“国庆后确有真实对齐现象”成立
（case-07）；Waveform 的 Markdown 文档**尚未入库**，这是 Phase 2 的前置阻塞，不是“已配置待生效”。

分项统计：

- 36 题：24 `answered` / 1 `partial` / 11 `insufficient`；0 契约违规；引用 49 条 / 13 份文档。
- 案例：12 条；关键证据为 git 零提交区间、`alignment.py` 无算法变更、2026-10-12 真实任务 fixture
  独立复算、EPICS Archiver 时序序列。
- 文档：3 份 Waveform + 1 份 RAG 入库手册；共 2562 行；约 210 处 `文件:行`/章节定位。
- 种子题：50 道（8 样例 + 21 语料侧 + 21 Waveform 侧）。

---

## 2. 交付物清单

### 2.1 M0 与回归

| 文件 | 内容 |
| --- | --- |
| `reports/phase1-m0-20261029/m0-baseline.md` | M0 定义、git 状态、运行代码与工作区一致性、模型/配置、语料/索引/预算、环境与命令、限制 |
| `reports/phase1-m0-20261029/regression-36-http.json` | 36 题原始 HTTP 结果（问题、答案、状态、引用、耗时、request_id） |
| `reports/phase1-m0-20261029/regression-36.log` | 逐题执行日志 |
| `reports/phase1-m0-20261029/regression-36-analysis.{json,md}` | 自动分析：状态、引用、耗时、契约检查、冻结证据包含、与历史对比 |
| `reports/phase1-m0-20261029/regression-36-findings.md` | 人工复核的失败清单与修复建议（F1–F5） |
| `reports/phase1-m0-20261029/analyze_regression.py` | 可重跑分析脚本 |

### 2.2 Waveform 案例与证据

| 文件 | 内容 |
| --- | --- |
| `reports/phase1-m0-20261029/waveform-audit/cases.json` | 12 条结构化案例台账（现象/触发/影响/版本/预期 vs 实际/根因证据/替代解释/修复/验证/未决） |
| `reports/phase1-m0-20261029/waveform-audit/cases.md` | 人读版，含 Archiver 查询点列 |
| `reports/phase1-m0-20261029/waveform-audit/evidence-index.md` | 证据稳定定位（commit / 文件:行 / 日志 / 交付目录 / Archiver 查询） |
| `reports/phase1-m0-20261029/waveform-audit/verify_fixtures.py` | 2026-10-12 真实 fixture 独立复算脚本（可重跑） |
| `reports/phase1-m0-20261029/archiver-timing-pv.md` | Lead 独立取得的 EPICS Archiver 时序证据（5 次查询原始点列） |

### 2.3 四份核心文档

| 文件 | 行数 | 版本绑定 |
| --- | --- | --- |
| `docs/waveform/waveform-storage-dataflow.md` | 408 | `waveform-storage-system@dc50e08 (2026-10-26)`；`alignment_algo_hash` 标“不适用（本文不对齐算法负责）” |
| `docs/waveform/alignment-semantics-and-diagnostics.md` | 796 | 同上版本；`alignment_algo_hash = e8db12d7…`（系统既有）；补充 `alignment_doc_bundle_hash = 390fd8e9…` |
| `docs/waveform/fault-history-and-version-changes.md` | 390 | 同上版本；`alignment_algo_hash = e8db12d7…`（与上一份一致） |
| `docs/runbooks/rag-ingestion-verification-rollback.md` | 968 | `applicable_system_version = 0b62844` + 部署清单 14/15 结论；`alignment_algo_hash` 标“不适用”并说明原因 |
| `docs/waveform/README.md` | 24 | 目录索引与状态说明（含“尚未入库”声明） |
| `docs/runbooks/README.md` | 13 | 新增一行索引（仅追加） |

### 2.4 种子题

| 文件 | 内容 |
| --- | --- |
| `data/evaluation/seed-questions-v1.json` | 元数据 + 8 道完整样例（每类 2 道） |
| `data/evaluation/seed-questions-v1-corpus.json` | 语料侧 21 道（task1 11 + task3 10） |
| `data/evaluation/seed-questions-v1-waveform.json` | Waveform 侧 21 道（task2 11 + task4 10） |
| `scripts/validate_seed_questions.py` | 结构与证据定位校验器（可重跑） |
| `reports/phase1-m0-20261029/seed-questions/README.md` | 题集方法、字段定义、分布、核验状态、使用边界 |

---

## 3. M0 基线要点

### 3.1 身份

- 代码：`0b62844`（2026-10-28 15:59:06 +0800）；`src/`、`config/` 无未提交改动。
- 运行实例：GPU 主机 `10.101.9.190:8003`，经 systemd 隧道 `127.0.0.1:18003` 访问，`/health` 正常。
- 生成 `ds-1017`；嵌入 E5（4746 pts）+ Qwen3-Embedding-0.6B（4532 pts）；重排 Qwen3-Reranker-0.6B。
- 语料：13 份 PDF / 2178 物理页 / 4537 规范父块（4532 eligible）；`pdf-chunks-v3` + `evidence-contract-v2`。
- 预算：2 轮、每轮 ≤20 候选、候选上下文 ≤18000 tokens、最终证据 ≤5 父块/6000 tokens。

### 3.2 工作区代码与实际运行代码一致性

- 2026-10-28 部署清单 15 个文件 expected/local/remote SHA-256 全等（已证实）。
- 今日重算：**14/15 与部署记录一致**；唯一差异 `docs/runbooks/rag-production.md`
  （部署时 `90f617bf…`，现 `7588fae2…`，且该旧值不在 git 历史中 → 部署后被编辑并随 `0b62844` 提交）。
  属**服务器文档副本滞后**，不影响运行代码。
- 结论：代码身份 = 工作区（已证实）；**远程字节今日未重新读取**（无 `10.101.9.190` 登录权限）。

### 3.3 复现坑（已记录）

conda 环境 `accelerator-rag` 为 editable 安装，指向兄弟 checkout `/home/whloong/projects/accelerator-rag`。
复现本阶段脚本须 `PYTHONPATH=src`（`analyze_regression.py` 已内建）。两个 checkout 的 10 个
入库/检索相关文件逐字节相同，仅 `config.py` 不同（生产 RAG 不读它）。

### 3.4 M0 限制

1. 远程字节不可重核；容器镜像 ID、`docker ps`、`/opt/accelerator-rag` 内容未独立核验。
2. 本次回归**无 trace 权限**，轮次/子集预算/补检索未复核（只能引用 2026-10-28 归档）。
3. 本机无原始语料 PDF（`data/l0_raw` 不存在），无法重放解析/切块/嵌入。

---

## 4. 36 题回归结果

### 4.1 执行

- 时间：2026-10-29 13:09:47–13:22:42（+0800），wall ≈ 12 min 55 s；`--workers 2`；base-url `http://127.0.0.1:18003`。
- 题面：冻结基准 32 题（SHA-256 `f5578371…`）+ 4 道附加题；请求只发 `query`。

### 4.2 汇总

| 指标 | 本次 | 历史（2026-10-28） |
| --- | --- | --- |
| HTTP 200 / 客户端错误 | 36 / 0 | 36 / 0 |
| 状态 | **24 answered / 1 partial / 11 insufficient** | 23 / 2 / 11 |
| 状态自洽 | 36/36 | 36/36 |
| 引用 | 49 条 / 13 份文档 | 51 条 / 13 份文档 |
| 契约违规（独立检查） | **0** | 0 |
| 冻结证据包含（组） | 29/35 | 30/35（同规则回算） |
| 完整覆盖（题） | 16/21 | 17/21（同规则回算） |
| 耗时中位 / P95 / 最大 | **29.47 / 63.77 / 109.74 s** | 17.29 / 42.86 / 59.86 s |

唯一状态变化：`xfel-version-scopes` `partial` → `answered`（与 2026-10-28 修复后的 6 题复测一致）。
**评测基线文件哈希漂移**：历史 HTTP 运行记录 `3994d8eb…`，当前 `f5578371…`，但 32 题 id 与问题文本
逐条一致（0 差异），差异在证据/判定元数据 → 冻结目标指标只能作方向性比较。

### 4.3 失败清单（详见 `regression-36-findings.md`）

| 编号 | 严重度 | 问题 | 证据 |
| --- | --- | --- | --- |
| F1 | **中（Phase 2 必修）** | `interlock-latency` 把“应小于 10 µs / 100 µs”答成“设计指标为 10 µs / 100 µs”，丢失比较符并与实测值并列 → 危险部分正确 | 回答原文 + 基准摘录 p2 |
| F2 | 低-中 | 引用逐字覆盖下降 2 题（`shine-ioc-management` 3/3→1/3；`timing-wrtd` 1/1→0/1，quote 被截断） | 分析 JSON |
| F3 | 信息 | 耗时中位上升 1.7×（17.29→29.47 s），代码/配置未变，原因未定位 | 分析 JSON |
| F4 | 信息 | 历史 36 题结果不能代表最终代码（其后有 2 项修复、仅复测 6 题）；本次才是最终代码全量 | 2026-10-28 报告 |
| F5 | 已核实正常 | 4 道附加题（低温 3 题 + 跨年份 1 题）行为符合修复后预期，缺项被显式标注 | 回答原文 |

### 4.4 不得宣称的事

- `answered` ≠ 人工判定正确；本次**未**做语义评分。
- 36 题是开发回归集，不是独立测试集。
- 未复核内部过程（无 trace）。

---

## 5. Waveform 故障案例审计

### 5.1 台账

12 条案例（`cases.json`）：**已证实 10 / 推断 1 / 待核实 1**。真实运行事故与测试构造、
设计设想严格分节（`cases.md` §3；`fault-history-and-version-changes.md` §3）。

关键真实事故：

| 案例 | 时间 | 事实 | 证据 |
| --- | --- | --- | --- |
| case-02 | 2026-10-02 | 20 台设备中 18 台零字节，任务 PARTIAL_DEVICE_FAILURE | 采集日志 `logs/capture-BI-5Hz-…-24fbc7de…json` |
| case-03 | 2026-10-02 | 采集中途服务关停，状态 cancelled | 日志 `…-5c9321c5…json` |
| case-04 | 2026-10-02 | 现场服务端接受 5 Hz，而当时代码仅支持 1000/100/50/2 → 部署 ≠ 任何提交 | 日志 + `git log -S` |
| case-06 | 2026-10-07 引入 / 10-19 移除 | 历史页把 `(末−首 bunchID)/10⁶` 当“数据时长秒” | `git show 61b47db` / `f7f28fb` |
| case-07 | 2026-10-12 | 真实任务跨 25 台严格共同点仅 422/621/455/375/288（保留率 **1.44%–3.11%**），根因单台 L1 冷 BPM 步长 28–76 vs 其余 24 台 2000 | 归档 fixture 独立复算 5 段逐位一致（`verify_fixtures.py`） |
| case-08 | 2026-10-26 修复 | timing PV 读到 10 Hz → 白名单无 10 Hz → `TIMING_FREQUENCY_FAILED` | 交付/20261026-timing-10hz-r1 + `CURRENT_STATUS.md:25-49` |
| case-09/12 | 2026-08-17 起 | timing PV 是多值运行量；10 Hz 至少自 2026-08-17 反复出现，不存在国庆一次性 5→10 切换 | EPICS Archiver（`archiver-timing-pv.md`，5 次查询） |

### 5.2 对“国庆后 Waveform 对齐异常”的裁定

**作为版本回归：不成立（已证实）**。三条可证伪检查全部否定：

1. 2026-08-26 15:32 → 2026-10-07 16:30 共 **41 天 23 小时零提交**，不存在“国庆前改动”可供回归。
2. `processing/alignment.py` 自 2026-07-25 建立后仅 `25e6b73`（2026-10-20）改过一次，
   diff 只加 `DeviceSeries.metadata` 字段，**无算法变更**。
3. `docs/` 检索“对齐异常”零命中；无用户报告、无失败测试、无日志记录“国庆后对齐偏移”。

**作为国庆后真实观察到的现象：成立**。case-07（2026-10-12）是最接近的现场证据，但根因是
设备 bunchID 步长不相容（设备/数据属性），不是软件回归；真正与“时基”相关的是 case-06
（显示层缺陷，非对齐算法）。计划措辞的可替换版本见 `fault-history-and-version-changes.md` §6.2。

**Archiver 证据推翻了另一条隐含前提**：10 Hz 不是国庆后才出现的新频率（8 月已反复出现），
`cae6b64` 是**补支持**，不是对假期后新状态的反应。

### 5.3 未决缺口（保留，不填补）

1. 2026-08-17–10-25 是否有采集因 10 Hz 被拒（需现场 `state/*.json`）。
2. 2026-10-02 现场服务端二进制 SHA-256（部署未知）。
3. `AC_LA_L1_BI_COLDBPM05` 设备侧说明（决定 case-07 是“差异”还是“故障”）。
4. 白名单仍为枚举式，20 Hz 不在表内（Archiver 有 20 Hz 记录）——需现场裁决。
5. timing PV 多值性的物理含义；Archiver 原始（非降采样）序列。
6. `PRAB_PLAN` 措辞的仓库外来源。

---

## 6. 四份核心文档与版本绑定

### 6.1 绑定字段处理（先核查、不编造）

| 字段 | 系统是否已有 | 处理 |
| --- | --- | --- |
| `applicable_system_version` | 无此字段名；有 `release_id`/`source_revision`/`binary_sha256` 等交付机制 | 取真实 git 提交：`waveform-storage-system@dc50e08 (2026-10-26)`；RAG 文档用 `0b62844` + 部署清单结论 |
| `alignment_algo_hash` | **有等价机制**：`agent_v2_service.py:54` 的 `alignment_source_hash`（= `sha256(processing/alignment.py)`），`:618-619` 输出为 `algorithm_source_sha256` | **直接采用系统值** `e8db12d7…3d5346`，给重算命令；RAG 手册标“不适用”并说明原因 |
| `verified_date` | 无 | `2026-10-29`（实际核验日） |
| `owner` | 无（git 作者 ≠ 责任人） | `未指派（待项目负责人裁决）`，全文无人名 |

**跨文档统一（2026-10-29 13:45，Lead 修订）**：两份 Waveform 文档曾各用不同值（4 文件集合哈希
vs 系统单文件摘要）。已统一为“系统已有定义优先”：`alignment_algo_hash = e8db12d7…`；
4 文件集合哈希降级为文档侧 `alignment_doc_bundle_hash = 390fd8e9…`，不写 front-matter、不称系统能力。
修订记录见 `reports/phase1-m0-20261029/waveform-docs-verification.md` 末节。

### 6.2 文档质量与核验

| 文档 | 参数/语义条目 | 代码定位锚点 | 公式 | 文档-代码差异 | 未实现能力 | 核验状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 存储与数据流 | 10 阶段数据流、8 个标识符、5 个时间戳字段 | 121 处 | 5 个块级 | 6 条（D1–D6，已核） | — | 未跑测试/未连现场（文末列明） |
| 对齐语义与诊断 | §4 参数全集 10 小节（92 行表格）、§5 诊断场景 9 个 | 174 处 | 6 个块级 | 8 条（A1–A8，已核） | §6.1 已有 12 条 / §6.2 未实现 11 条 | 同上 |
| 故障历史与版本变更 | 12 案例、时间线条目、措辞裁定 4 条 | 48 处 | — | — | — | 证据可复算（fixture） |
| RAG 入库/验证/回滚 | 6 步链路、7 个探针、回滚 7 步 | 68 处 | 4 个块级 | — | Markdown 入库、自动回滚 | 本地实跑（见 §7） |

Lead 已独立复核的关键点：`algorithm_source_sha256` 计算位置（`:54`）、`algorithm_version`（`:618`）、
`provenance.pop('algorithm_source_sha256')`（`:655`）、4 文件集合哈希可复现、
`_CAPTURE_INTERVAL_SECONDS`（含 `10.0: 2100`）、`TIMING_FREQUENCY_PV`（`:503`）、
`alignment.py` 默认参数与 `(0,1]` 校验、`registry.py:76-77`、`ingestion.py:55-56`、`pdf_parser.py:192-193`。

### 6.3 必须区分的“已有能力 vs 未实现”

- 已有：整数 bunchID 交集/共识（strict/coverage）、`valid_mask`、HDF5 v2 schema、
  对齐算法摘要 provenance、请求级 timing PV 单次读取与跟随、原始步长预检查。
- 未实现：段间/整任务对齐、容差式时间对齐、bunchID→物理时钟换算、重采样式对齐、
  自动对齐、真实 fixture 现场重放、系统级 `alignment_algo_hash` 字段、段内逐采样点时间戳、
  自动备份/回滚。

---

## 7. 文档入库路径验证（先阻塞，后实现）

**2026-10-29 14:40 更新**：Markdown 入库已按方案 A 实现并通过本地测试（解析 / 切块 / 登记 /
快照 / 干跑 151 chunks 全 eligible / 7 项新测试 / 全套 269 项通过）。**生产实例未部署**：
索引未重建、容器未重启，生产仍是 13 份 PDF。实现细节与生产步骤见
[`docs/runbooks/rag-ingestion-verification-rollback.md`](../../docs/runbooks/rag-ingestion-verification-rollback.md) §8.3。
下面保留 13:12–13:30 的原始阻塞核验，作为实现依据与回滚时的对照。

**当时的结论：Markdown 文档不能入库**，两层独立阻塞，均有实测与代码证据：

1. **路径层**：`source_path` 必须在 `data/l0_raw/` 下（`corpus/registry.py:76-77`），
   `docs/waveform/*.md` 原地登记被拒（探针 P2b 实测输出）。
2. **格式层**：复制进 `data/l0_raw` 并登记后，`ingestion.py:55-56` 抛
   `ValueError: only PDF ingestion is supported`；批量入口 `ingest_all_registered_pdfs()`
   对非 PDF **静默跳过（0 文档/0 chunk）**；`pdf_parser.py:192-193` 只接受 `.pdf`；
   全仓库无 Markdown 解析器；runtime catalog 只收 `.pdf` 来源。

**因此**：4 份文档当前状态是“已保存到仓库”，**不是“已入库”**；RAG 检索不到它们。

**最小改造路线（需裁决）**：B 方案 = 离线 md→PDF 后按现有链路入库（零代码，但引入转换保真问题）；
A 方案 = 新增 Markdown 解析器 + 解析器映射 + 版本策略 + catalog/预览端点 + 测试（改动大、
需重建索引 4532 父块）。手册 §8.3 给了两方案与 5 个必答问题。

---

## 8. 50 道种子题

规范文件：`data/evaluation/seed-questions-v1.json`（50 道，含元数据与 `sources` 哈希）；
方法/字段/边界说明：`reports/phase1-m0-20261029/seed-questions/README.md`；
组装脚本 `scripts/build_seed_questions.py`；校验脚本 `scripts/validate_seed_questions.py`。

### 8.1 分布（实测）

| 类别 | 道数 | answerable | partial | insufficient | overlaps_36q |
| --- | --- | --- | --- | --- | --- |
| task1 设备参数与适用工况 | 13 | 10 | 1 | 2 | 13 |
| task2 Waveform 对齐与分析准备 | 13 | 11 | 1 | 1 | 0 |
| task3 跨版本/跨子系统比较 | 12 | 9 | 2 | 1 | 12 |
| task4 故障复盘与诊断路径 | 12 | 6 | 2 | 4 | 2 |
| **合计** | **50** | **36** | **6** | **8** | **27** |

- 非 answerable 14 道（28%）；负例 13 道，全部标注构造方式：
  `hidden_evidence` 6 / `live_data_absent_by_design` 3 / `absent_semantics` 2 /
  `out_of_bounds` 1 / `wrong_version` 1。
- 每题 evidence 平均 3 条（共 150），must_cover 平均 4.2 条（共 208），
  hazardous_patterns 共 116 条。
- 证据定位：语料侧指向冻结基准/请求记录的逐字摘录（document_id + 物理页/引用号），
  Waveform 侧指向 `src/...:行号`、`docs/waveform/*#章节`、`cases.json#cases[case-0N]`。

### 8.2 8 道样例 → 50 道的流程

1. Lead 先写 8 道完整样例（每类 2 道），确定字段契约、评分规则与证据定位格式；
2. 用 `scripts/validate_seed_questions.py` 校验样例（OK）；
3. 两个并行作者按同一 schema 扩充：语料侧 21 道（task1 11 + task3 10）、
   Waveform 侧 21 道（task2 11 + task4 10）；
4. `scripts/build_seed_questions.py` 合并、去重、排序、记录 part 哈希；
5. 终检：`validate_seed_questions.py ... --expect-total 50` → **OK**。

### 8.3 核验状态（不得夸大）

- **50/50 `machine_verified`，0 道 `pending_human`，0 道经人工语义复核。**
- `machine_verified` 只表示：schema 完整、id 唯一、locator 可解析、excerpt 非空、
  must_cover 的 `match` 能在 evidence 或 gold_answer 中找到（作者自检 + 校验器）。
  **不代表专家确认答案正确。**
- 29 道题的 `verification.pending` 非空，逐条列出仍需人工确认的事项。
- 27 道 `overlaps_36q=true`，**不得进入未来独立测试集**；50 道
  `independent_test_allowed` 全为 `false`。

### 8.4 已知限制

- task2/task4 的目标知识库包含 4 份 Waveform 文档，而它们**尚未入库**（见 §7）→
  在 M0 上这些题预期为 `insufficient`，不是题目缺陷。
- `S3-VERSION-010` 只有 1 个文档来源（CDR2011 不在语料），故设为 `partial`；
  若要求每道 task3 ≥2 文档来源，需补语料或撤题（需裁决）。
- 全部题目的 `alignment_algo_hash` 已统一为系统值 `e8db12d7…`；
  `390fd8e9…` 只以“文档侧集合哈希”身份出现。

---

## 9. 实际执行的命令（节选，均可重跑）

| # | 命令 | 结果 |
| --- | --- | --- |
| C1 | `curl --noproxy '*' -fsS http://127.0.0.1:18003/health` | 200 `{"status":"ok"}` |
| C2 | `python scripts/rag_framework_check.py --base-url http://127.0.0.1:18003 --output reports/phase1-m0-20261029/regression-36-http.json --workers 2` | 36/36 HTTP 200；exit 0 |
| C3 | `python reports/phase1-m0-20261029/analyze_regression.py --current … --history …` | 0 契约违规；生成 analysis.json/md |
| C4 | `python scripts/build_seed_questions.py` | 合并 50 道；`sources` 记录 part 哈希 |
| C4b | `python scripts/validate_seed_questions.py data/evaluation/seed-questions-v1.json --expect-total 50` | **OK**（50 道，13/13/12/12） |
| C5 | `PYTHONPATH=src python -m pytest tests/corpus -q` | 93 passed |
| C6 | `PYTHONPATH=src python reports/phase1-m0-20261029/ingestion-path/run_ingestion_path_probe.py` | exit 0，7 组探针 0 断言失败 |
| C7 | `python scripts/corpus_inventory.py` | exit 1（本机无 `data/l0_raw`，预期） |
| C8 | `PYTHONPATH=src python scripts/rag_framework_review.py` | exit 1（需原始 PDF，本机无，预期） |
| C9 | `PYTHONPATH=src python scripts/rag_framework_metrics.py` | exit 0（读已保存报告：21 题/35 组，quoted 17/21） |
| C10 | `python reports/phase1-m0-20261029/waveform-audit/verify_fixtures.py` | `RESULT: ALL CHECKS PASSED`（5 段逐位一致） |
| C11 | `curl … /v1/rag/documents` | 13 份文档 / 4532 索引节 / 2178 页 |
| C12 | `sha256sum src/waveform_storage/processing/alignment.py`（Waveform 仓库） | `e8db12d7…3d5346`（= 文档 front-matter） |
| C13 | `printf … \| LC_ALL=C sort \| xargs sha256sum \| sha256sum` | `390fd8e9…c4e65d`（= `alignment_doc_bundle_hash`） |
| C14 | MCP `archiver_query_series` ×5 + `archiver_query_live` ×1 | 点列见 `archiver-timing-pv.md` |

---

## 10. 阻塞项与需裁决的最少问题

1. **Markdown 入库方案 A/B**：是否需要 Phase 2 支持 4 份文档直接入库？若走 A，是否接受重建索引
   （4532 父块重嵌入）的时间与回滚成本？
2. **`owner` 指派**：4 份文档与题集的责任人；当前一律“未指派”。
3. **M0 远程字节复核**：是否提供 GPU 主机只读访问（或运维签发哈希清单），把“部署未变”
   从推断升为证实？
4. **`alignment_algo_hash` 字段名**：本阶段采用系统 `algorithm_source_sha256` 值；是否需要在
   Waveform 系统侧正式定义该字段名（否则文档字段名与系统字段名不一致，需长期映射说明）？
5. **是否允许修改 `PRAB_PLAN.md` 措辞**：审计给出 4 条裁定与替换措辞（`fault-history…` §6.2），
   但计划文件不属于本阶段写入范围。
6. **36 题 F1（比较符保真）是否提前到 Phase 2 之前修**：这是安全相关表达缺陷，修复面小
   （约束核查器的数值/比较符规则）。

---

## 11. 未完成与未核实（不得当作已完成）

| 项 | 原因 |
| --- | --- |
| 36 题语义人工评分 | 未获人工评审资源；只做了接口/引用/契约与部分人工抽查（F1 即抽查发现） |
| 回归内部过程（轮次、预算、补检索）复核 | 无服务器 trace 读取权限 |
| 远程部署字节重核 | 无 `10.101.9.190` SSH 权限 |
| 语料重建/索引重建 | 本机无语料与索引，且不允许写生产索引 |
| 测试执行（Waveform 仓库） | 按 Waveform `AGENTS.md` 的长期验证范围限制，本阶段未获授权 |
| 现场 EPICS/MongoDB/systemd 验证 | 未连接现场 |
| Markdown 入库 | 系统不支持（阻塞，见 §7） |
| 自动回滚脚本 | 未实现 |
| 种子题人工复核 | 无复核人；全部标 machine_verified 或 pending_human |
| Archiver 原始（非降采样）序列 | 工具 max_points ≤ 2000 且返回 `downsampled=true` |
| 文档导航两处未改 | `docs/roadmap/CURRENT.md`（仍是“Waveform 文档是待完成工作”的旧表述）与 `docs/rag/README.md`（导航表未加入新文档）：两份文件在本次开始前已有未提交改动，为避免混入他人改动未编辑。`docs/runbooks/README.md` 只追加了一行索引 |
| 种子题人工语义复核 | 无复核人；50 道全为 `machine_verified`，29 道带 pending 项 |

---

## 12. 边界声明

- 未 `git commit` / `push` / 部署 / 重启任何服务；生产 RAG 与 Waveform 仓库均未被修改。
- 未写索引、未改 `src/`、`config/`、`data/documents/registry.json`。
- 未写入任何密钥或凭据；服务凭据未出现在任何产物中。
- 未覆盖工作区既有改动（`git status` 中 9 个修改、1 个删除原样保留；新增文件见 §2）。
- 只读访问：Waveform 仓库、EPICS Archiver、生产 RAG HTTP 接口。
