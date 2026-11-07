# 阶段三设计：证据包检索、短路径与端到端链路

日期：2026-11-08。依据：`docs/research/rag-research-reset-20261107.md` §4.2、§6（P0/P1）、§8、§10 阶段三。

本文件是阶段三全部工作流（W1—W6）与独立审核（R1—R5）的共同契约。凡与本文件冲突的实现，审核按阻断处理。

## 1. 范围

本阶段只做六件事：

1. 问题驱动的需要解析与动态 token 预算（§4.2）。
2. 文本、表格、修订、事实图多路关联召回与短路径（§4.2、§6）。
3. 以“覆盖必要关系的证据包”替换“最多 5 个父块”的选择对象，并与同预算父块选择对照（§4.2、§6 P0）。
4. 规则版证据包重排器；在有足够训练标签时提供学习版，并按文档族整体划分验证其跨族泛化（§4.2）。
5. Archiver 只读观测适配器（扩展接口，§8）。
6. 端到端规则版与重排版链路、批量复算、审计与论文检索/组合方法素材。

明确不做：

- 不改生产预算、检索、生成、证据子集选择与工作流代码（`src/accelerator_rag/rag/` 保持字节不变）。
- 不训练或调用生成模型；默认输出可复核的主张集合与模板化回答。模型生成作为适配接口留给阶段四。
- 不读取 `data/evaluation/research-benchmark-300-v1/sealed-test/`。
- 不把 `gold` 用于检索、选择、重排或回答；`gold` 只在批量运行结束后用于计算证据覆盖率等开发指标。
- 不把“证据覆盖必要关系”写成“工程主张已被证明”；自然语言语义仍需人工/模型复核。

## 2. 数据边界

- 语料：`tmp/research-rc3/` 只读快照（rc.3，即生产 `kb2-prod-20261105-v3` 的 v2 快照）。
- 构建追溯：10 个 `.doc` 操作手册 revision 在该快照中共 213 个 chunk；复核的 48 个唯一 evidence id 与 dev/val gold 的 48 条证据 id 全部命中；40 道受影响题重放 40/40 与最终包哈希一致，未出现假性 `insufficient`。映射见本地 `reports/phase3/revision-chunk-map.json`；不得改用旧 `kb2-batch-full-20261102-r3` 的 v1 id。
- 检索范围：dev/val 题目 `family_ids` 对应的文档族；这是题目元数据给出的资料范围，所有对照方法获得相同范围。
- 题目：只允许 `data/evaluation/research-benchmark-300-v1/{dev,val}/questions.json`。
- `verdict_class=deterministic` 的题才进入回答状态统计；`rubric/human` 一律 `not_evaluated`，不作为正确性依据。
- 含逐字原文的报告写入 `reports/phase3/`、`data/evidence-pack/`，二者不进入 Git；代码、测试、文档入库不含内部原文。
- 训练样本按文档族整体划分：dev 族训练、val 族验证；不得把同一底题或同一族的扰动拆到两侧。

## 3. 模块结构

```
src/accelerator_rag/evidence_pack/
  schema.py       Need/Atom/Candidate/Pack/Coverage/Observation 等不可变记录与校验
  needs.py        W1 规则式问题解析：实体、关系需要、短路径、范围
  budget.py       W1 动态预算策略与 token 估计
  index.py        共用：BM25、行索引、事实索引、修订索引、邻接索引
  dense.py        可选 E5/Qwen3 稠密通道适配器（注入 embedder；hashing 仅测试替身）
  recall.py       W2 多路召回与轮次控制
  relations.py    W2 关系补全（单位/条件/对端/角色/版本侧/枚举）
  pack.py         W1 证据包选择、冲突保留、父块对照基线
  rerank.py       W3 规则版与学习版证据包重排器
  archiver.py     W4 Archiver 只读适配器与观测证据原子
  verify.py       W5 主张装配、算子调用与状态判定
  pipeline.py     W5 端到端链路（规则版 / 重排版）
scripts/research/
  run_evidence_pack.py     批量运行、--verify 重放、证据覆盖指标
  audit_evidence_pack.py   独立审计（预算、冲突、引用、算子、隔离）
  train_pack_reranker.py   学习版训练与跨族验证
  ingest_archiver.py       Archiver 导出规范化与证据原子生成
tests/evidence_pack/       单元测试与 corpus 测试
docs/research/phase3/
  DESIGN.md 本文件
  README.md 交付说明与运行结果
  paper-retrieval-composition.md  W6 论文素材
  reviews/R1..R5.md 独立审核记录
```

共用文件 `schema.py`、`index.py` 由主控维护；工作流只写自己模块与测试。

## 4. 记录模型

所有记录为不可变 dataclass，JSON 序列化字段固定、排序稳定。

### 4.1 EntityNeed

```json
{"raw": "DEVX002", "normalized": "devsw002", "kind": "device|cabinet|cable|pv|port|revision|number|term", "source": "query"}
```

- `raw` 逐字取自问题；`normalized` 只用于比较，永不替换原文。
- 只从问题文本和 `scope.revision_ids` 提取；不读 `gold`。

### 4.2 RelationNeed

```json
{"name": "value|unit|condition|counterpart|scope|enumeration|version_left|version_right|requirement|design|test_result|test_scope|acceptance|boundary|external_observation", "required": true, "role_filter": [], "revision_filter": [], "reason": "问题出现端口/VLAN 线索"}
```

- 需要由问题文本线索产生，不按 `task_type` 查表；`task_type` 只用于报告分组与评价。
- 必需关系缺失时状态为 `partial`/`insufficient`，不得用相似段落顶替。

### 4.3 Atom

证据包的最小单位，必须可直接定位：

```json
{"atom_id": "A...", "chunk_id": "...", "revision_id": "...", "locator_kind": "paragraph|table_row|table_header|table_title|footnote|figure_caption|section|pdf_page|slide|external_observation",
 "locator_label": "...", "excerpt": "...", "row_number": 3, "table_block_id": "...",
 "source_role": "design_target|test_result|acceptance_conclusion|...",
 "evidence_role": "fact_support|condition|unit|header|provenance|external_observation",
 "fact_ids": ["F..."], "route": "bm25|row_exact|fact|revision|graph|neighbor|dense|archiver",
 "score": 1.0, "tokens": 12, "conflict_group": ""}
```

- `excerpt` 必须是父块原文的连续子串（允许 `……` 连接多个连续片段，规则同阶段二）。
- 行原子用 `verbatim_row_line` 或 markdown 表行原文；不得用 `row_text` 的丢空单元格版本。
- 段落原子是句子级 span；表头、表题、脚注各自保留定位类型。
- Archiver 原子是时间序列观测，`locator_kind=external_observation`，必须携带来源/时间窗/聚合与警告。

### 4.4 Candidate

候选是父块级检索结果，不直接进入证据包：

```json
{"chunk_id", "score", "routes": [{"channel","query","rank","detail"}], "revision_id", "source_role"}
```

### 4.5 Pack

```json
{"atoms": [Atom], "parents": [{"chunk_id","tokens","source_role"}], "tokens": 1234,
 "budget": 2400, "coverage": [Coverage], "conflicts": [Conflict],
 "unresolved": ["..."], "selection": {"policy":"relation_pack_v1","passes":2,"objective":...}}
```

- `tokens` 只计证据包中的原子与固定元数据，不计“供查阅”的完整父块。
- `parents` 记录**全部**被原子引用的父块（供查阅），每个带 `full_text` 标记；`max_parents` 是对 `full_text=true` 的完整父块查阅列表的上限，不是原子来源数的上限。原子自身已携带逐字定位，消费者可按需加载标记为 `full_text=true` 的父块全文。

### 4.6 Coverage / Conflict

```json
{"name": "test_result", "required": true, "satisfied": true, "atom_ids": ["A..."], "missing": ""}
{"conflict_id": "C...", "kind": "value|role|version|scope", "subject": "...", "attribute": "...",
 "atom_ids": ["A...","A..."], "resolution": "preserved|affects_target|not_affecting|unresolved", "reason": "..."}
```

- 冲突不得通过删除一方来解决。比较题并列保存；核验题说明是否影响目标主张。
- 同一对象、同一属性、同一条件、同一证据角色、不同值 → 真冲突；设计值与测试值不同角色 → 角色差异，不是数值矛盾。角色差异仍被记录为 `kind=role`：比较题按并列保存处理，核验题标为 `affects_target` 并使状态降为 `partial`，因为目标主张需要同角色证据，而不是用另一角色顶替。
- 值冲突检测只针对 `parameter` 层事实。`connectivity` 事实的端口区间是行键，同一设备的不同行必然不同；跨表身份由 `exact_join` 的 `AMBIGUOUS_SCOPE` 拒绝处理，不按值冲突统计。
- 同一修订、同一表、同一证据角色的多行差异按“不同行/不同项”处理；同一修订、同一角色但位于不同段落/图的不同值，也按不同测试图/量程处理。若同一段落的多个抽取 span 是同一句的变体（字符重合 ≥0.8 或互相包含），也不判为冲突。以上是阶段二事实粒度的限制，报告中必须说明；跨修订或跨角色的差异仍按冲突检测。
- 预算不足以同时保留冲突双方时，`Conflict.resolution` 必须写 `unresolved`（不是只写自由文本说明）；`verify` 读取 `pack.unresolved` 并把状态降为 `partial`/`insufficient`。

## 5. 短路径与动态预算（W1）

### 5.1 路由（只看问题文本）

1. 出现版本线索（版本/修订/第一版/第二版/第三版/N版/初版/上一版/新版/旧版/历代/归档）→ `document_explanation`。
2. 出现两类及以上角色线索（要求/设计/指标；测试/实测/结果；验收/结论）或跨资料线索（对比/分别/两者/对应/是否满足）→ `cross_source`。
3. 出现“完整清单/枚举 + 连接/端口/线缆”线索 → `cross_source`（完整集合需要跨表枚举，不是单行精确查询）。
4. 出现标识符**且**属性线索（端口/系统/VLAN/归属/位置/编号/型号/用途/连接/线缆/表）→ `exact_record`。
5. 出现解释线索（说明/介绍/功能/作用/如何/步骤/界面/路径/流程）→ `document_explanation`。
6. 其余 → `cross_source`。

“相同/一致/差异”等措辞本身不构成路由线索，避免把单表标识符查询升级为跨资料；它们仍用于冲突/比较语义。路由只决定召回策略、预算与轮次；不决定答案。

### 5.2 预算

| 路由 | 基础 token | 完整父块查阅上限 | 最多轮次 |
| --- | ---: | ---: | ---: |
| exact_record | 1200 | 3 | 1 |
| document_explanation | 2400 | 5 | 2 |
| cross_source | 3600 | 8 | 2 |

- 只按**必需**关系附加：每多一个必需关系加 150 token，上限 6000；可选关系不增加预算。预算写入报告。
- 第二轮只在某个必需关系零候选时触发；焦点查询只用于 BM25，`fact/row_exact` 仍按实体做结构化召回，但不会重跑原始派生查询；literal/structure/neighbor/dense/revision 等通道在第二轮跳过。报告逐轮记录实际查询与通道调用。
- 生产 `rag/` 的 6000 token/5 父块预算不变；本阶段预算只作用于离线证据包。

### 5.3 token 估计

离线复算使用公开、确定的估计器：`tokens = ASCII 词数 + CJK 字符数 + 标点符号数`。报告同时记录字符数。阶段四使用生产 tokenizer 时必须重跑并说明差异。

## 6. 多路召回（W2）

通道：

1. `bm25`：问题原文与至多 4 个派生查询（实体+属性组合、角色查询）的 BM25 top-k。
2. `row_exact`：结构化行索引，按问题中的标识符/端口/表名精确匹配，返回父块。
3. `fact`：事实索引，按主体规范化键、属性词与证据角色匹配，返回 citation 父块与事实原子。
4. `revision`：版本题按显式修订或版本序号定位两侧修订，逐侧召回。
5. `neighbor`：已选候选的同修订阅读序邻接块，只补解释上下文，不跨修订。
6. `literal`：问题中的数字、端口区间、百分比、稀有标识符按字面扫描父块，补 BM25 截断漏掉的数值/截图页。
7. `structure`：按表头/栏名（测试结果、结论、要求、验收指标）定位结构表，补“栏为空/未填写”类证据缺口。
8. `graph`：关系补全引入的对端、角色、版本侧原子，标记来源为事实图。
9. `dense`：E5/Qwen3 适配接口。默认回放标 `unavailable`，不得因缺失而失败；full 对照使用生产同版权重与 `PassageBuilder` 在 CPU float32 计算的向量（E5 取父块内最佳 passage、Qwen3 每父块一个 passage；E5+Qwen3 先 RRF 融合），不读取生产 CUDA 索引。
10. `archiver`：仅在提供只读导出且问题含匹配 PV 时加入外部观测原子。

规则：

- BM25 与结构化的分数不混合；候选融合按通道排名倒数求和（RRF，k=60），与生产一致。
- 每个通道的前 48 个候选进入原子化；`row_exact` 命中的行优先保留。
- 候选必须属于题目给定的文档族范围；版本题若给出 `scope.revision_ids`，两侧都必须在范围内。
- 召回轨迹记录每个查询、通道、排名与候选数，供 R3/R4 复核调用成本。

## 7. 关系补全（W2）

初始原子生成后，按关系和事实图补全：

1. 数值事实：补同事实的单位与条件 citation；单位未知不补猜。
2. 关系事实：补对端身份（同一行另一列或另一表的关联记录），保留 `scope`；无范围不跨柜连接。
3. 角色矩阵：同一对象/属性的设计、测试、验收事实分别补入；角色缺失记为缺口，不用其他角色顶替。
4. 测试范围：补 `test_scope` 过程事实或“测试条件/测量范围”参数事实。
5. 版本侧：按修订顺序定义 left（较早）/right（较晚）；两侧同主题句子按词元重合对齐，补入两侧原文。
6. 枚举：补目标表/对象的全部行；预算不足时标记 `enumeration_incomplete`，不得声称完整。
7. 冲突：同对象+属性+条件+角色出现不同值 → `conflict_group`，两原子都标记；核验题比较角色差异是否影响目标主张。

补全过程写入 `completion` 轨迹（触发关系、新增原子、未解决原因）。

## 8. 证据包选择（W1）

### 8.1 目标

下式是贪心增益与终态 objective 的合成描述；`selection.objective` 记录终态 objective，不含仅用于贪心排序的 term/extra witness/enumeration 增益项。

```
value(pack) = 100 * 必需关系覆盖数
            + 10 * 可选关系覆盖数
            + 25 * 覆盖的实体数
            + 6 * 关系证据的额外修订来源数（最多 3）
            + 3 * 新增查询词覆盖数（每原子最多 4）
            + 30 * 必需关系的额外见证块数（达到目标前）
            + 12 * 枚举行进度
            - 3 * 重复原子数
            - tokens / budget
            - 0.05 * 原子数
            + 0.01 * 归一化通道分
```

### 8.2 算法

1. 贪心：每步选择“新增关系价值 / token 成本”最大的原子；稳定排序键为 `(-ratio, atom_id)`。
2. 冲突约束：检测到冲突时，若预算允许必须同时包含双方；只包含一方则相关关系不计覆盖，并写 `unresolved`。
3. 枚举约束：完整性只在所有目标行都在包内时声明。
4. 预算填充：覆盖必需关系后，按候选排名（默认）或重排器分数把剩余原子填充到 90% 预算；填充只加入候选父块中的原子，不加入未召回内容。
5. 局部改进：最多 2 轮，用剩余预算替换低价值原子；不改变已覆盖关系集合，不删除冲突双方或版本对齐原子。
   消融：在 18 道 S1 dev 题、每题目候选池限制 16 原子的穷举对照中，passes=0/1/2/3 的必需/可选关系覆盖得分相对穷举最优的损失均为 **0.00 个百分点**（其中 2 题池内无可达覆盖，双方均为 0）。完整 dev/val 的 passes 消融（`reports/phase3/ablation-passes.json`）gold 证据块召回为 dev 0.9534/0.9571/0.9571/0.9498、val 0.7917/0.8009/0.7917/0.7917；差异小于 1 个百分点，保留预注册的 `passes=2`，不按开发指标挑选超参数。
6. 父块对照基线 `parent_top5`：与证据包使用**同一候选列表**（前 24 个候选）按 RRF 分排序取前 5 个父块完整文本；超预算时从尾部裁剪，不跳过前面的父块；基线不处理冲突，也不产生主张。

### 8.3 覆盖判定

- 覆盖必须同时满足“关系名”和“对象相关性”：原子要提到问题实体，或覆盖足够的查询词/来自该题的候选父块；否则一个通用数字/通用角色不能算覆盖。
- `value/unit/condition/counterpart/scope/boundary/external_observation` 只接受强相关原子；`requirement/design/test_result/test_scope/acceptance/version_left/version_right/enumeration` 允许来自候选父块的结构性相关原子。
- 端口实体按闭区间包含判定：问题问 33-36，行记录 33-48 算同一记录；机柜按身份键判定：`CAB-A-CN01`、`LA-CAB-A:CN-01` 同键，`EXT-CAB-A-CN01` 不同键；设备允许路径前缀，机柜实体负责消歧。
- 枚举完整性只在目标表所有行都入选时声明；不把“没有找到”写成“集合为空”。

### 8.3 输出

证据包必须能回答三个问题：哪些必要关系被覆盖、每条关系由哪些原子支持、哪些关系/条件未解决。禁止只给一个排序列表。

## 9. 重排器（W3）

### 9.1 规则版（默认交付）

特征与权重固定、可审计（实现见 `rerank.py`）：

- 对象实体匹配 +2；查询词匹配 +1/项（最多 6）；
- 候选排名倒数 +1.5；角色匹配 +1，错位 -1；
- 表头匹配 +0.5；单位/条件/fact 原子 +0.5；
- 重复文本 -2；token 成本 -1（按 100 token 归一）；冲突标记 -5。

规则版必须在报告 `rerank.atoms[].score_breakdown` 中逐特征写出分数；`rerank.weights` 写出权重。覆盖/范围/修订侧由证据包选择阶段处理，不重复进入重排特征。

### 9.2 学习版（条件交付）

- 模型：线性打分（logistic/线性回归），权重可导出 JSON；不依赖 GPU。
- 训练样本：本阶段实现为**点式原子重排器**：正例为 dev gold 最小证据中与 gold excerpt 重合的原子；负例为同题其余原子，并额外构造近似错误组合（交换相邻端口、加 `EXT-` 前缀的同名不同柜、删除条件子句、测试角色替换为设计角色）。pack 级的“设计值替测试值、跨版本混用、遗漏脚注”组合训练留待阶段四。
- 划分：按文档族整体；dev 训练、val 验证。不得使用 val 或 test 调参。
- 报告必须给出：训练/验证族清单、逐族指标、与规则版的配对比较、是否达到“跨族不退化”的交付门槛。
- 若学习版未在 val 族上稳定优于规则版，保留规则版为默认，学习版仅作为条件实验记录，不宣称通用贡献。

## 10. Archiver 适配器（W4）

- 只读：不实现写操作、不触发采集、不改变归档配置。
- 输入：MCP 导出的 JSON（`archiver-probes.json` 结构）或等价的 `{request, response}` 记录。
- 规范化：保留 PV 原文、请求窗口（UTC）、策略、`bin_seconds`、点数、`in_range_point_count`、`context_point_count`、`data_state`、`segments[].warnings`、`downsampled`、`truncated`、`complete`、`source_ids`、单位未知状态。
- 有效性：`downsampled=true` 不得用于声称连续物理状态；`truncated=true` 或分段警告必须随证据保留；窗口外 context 点不计入窗口统计。
- 证据原子：`locator_kind=external_observation`，`source_role=external_observation`，`evidence_role=external_observation`；excerpt 为可复核的规范化摘要（PV、窗口、策略、点数、值集合），不是原始二进制。
- 主实验不得依赖 Archiver；只有显式提供导出且问题含匹配 PV 时才加入，报告中单列。
- 真实 MCP 调用在代理进程外；Python 侧只消费导出文件，保证离线复算。

## 11. 端到端链路（W5）

`pipeline.run(question, index, reranker, archiver=None)`：

1. 解析需要与路由（W1）。
2. 召回第 1 轮（W2），生成候选与原子。
3. 关系补全（W2），检测冲突/枚举缺口。
4. 预算内选择证据包（W1）。
5. 规则版或学习版重排（W3）；重排只改变原子顺序与取舍，不改变覆盖语义。
6. 主张装配与算子执行（W5）：只在包内证据上运行 `exact_join`、`port_range_membership`、`set_enumeration`、`unit_convert`、`boundary_compare`、`version_diff`。
7. 状态判定：`answered|partial|insufficient|not_evaluated|unsupported`，附 `unresolved`。
8. 输出证据包、覆盖、冲突、算子请求/响应、模板化回答、轨迹与复算哈希。

不变量：

- 没有包内证据不得生成主张。
- 算子 `refused` 必须原样保留拒绝码；不得降级为 `ok`。
- 冲突未解决时不得输出单一确定值。
- 回答中的每个值必须能追到原子与事实/行；不能追到的值不得出现。
- `rubric/human` 题只输出证据包与 `not_evaluated`，不输出主张值。

## 12. 复算、指标与审计

### 12.1 批量报告

`run_evidence_pack.py --split dev|val --out ...` 输出：

- 逐题链路记录（不含 gold）；
- 汇总：状态计数、路由计数、通道调用数、轮次、token、父块数、算子数；
- 开发指标（运行后用 gold 计算，单独字段）：gold 证据块召回、gold 必要事实支持召回、冲突保留率、枚举完整性、预算满足率；
- 与 `parent_top5` 基线的同预算对照。

`--verify` 重放：重新运行并逐题比较规范化 JSON，必须逐字节一致。汇总同时给出全量与 deterministic 子集的平均 token/预算/父块；报告记录证据包字符数。`recompute.report_sha256` 覆盖流水线报告本身（含 `baseline`、不含批量运行器随后添加的 `evaluation` 开发指标）；审计按同一边界重算。

### 12.2 审计

`audit_evidence_pack.py` 必须检查并输出 0 阻断：

1. 最终 pack、每轮 pack、baseline 的 atom excerpt 均在父块逐字可查；
2. 所有 `fact_ids` 存在且 citation 一致；
3. 报告预算按 required-only 公式复算；`pack.tokens` 按原子 + 父块元数据重算；`parents` 列出全部被引用 chunk，`full_text=true` 数不超上限；
4. 冲突双方未被静默删除；单边/零边只能以 `resolution=unresolved` 出现，且与 `Pack.unresolved` 一致；
5. 枚举完整性按目标表全部行重建，不只查子集；
6. 算子请求可重放且响应一致；
7. `not_evaluated` 题无主张值；所有 claim 至少有一个 atom/fact 追溯；
8. `rubric/human` 未被当作正确性依据；
9. 未读取 sealed-test（阶段三代码静态扫描与运行时 split 检查）；
10. `src/accelerator_rag/rag/` 与 HEAD 字节一致（生产隔离）；
11. `facts_sha256/questions_sha256/corpus_snapshot` 与当前 dev/val 输入一致（含 parsed 文件）。

### 12.3 指标口径

- 证据覆盖率使用 gold `evidence_minimal` 的 chunk 级匹配；行级子串匹配单列。
- 统计按 `cluster_id`/文档族聚类报告，不把 100/50 题当作 300 个独立样本。
- 状态计数是机制状态，不是准确率。

## 13. 测试与复现

```bash
~/miniconda3/envs/accelerator-rag/bin/python -m pytest tests/evidence_pack -q
~/miniconda3/envs/accelerator-rag/bin/python -m ruff check src/accelerator_rag/evidence_pack scripts/research tests/evidence_pack
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --out reports/phase3/dev.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/run_evidence_pack.py --split dev --verify reports/phase3/dev.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/audit_evidence_pack.py
```

单元测试使用内存小样例，不依赖语料；语料测试标记 `@pytest.mark.corpus`，缺失快照时跳过。

## 14. 审核（R1—R5）

- R1 预算与完整性：预算、父块上限、覆盖计算、枚举完整性。
- R2 冲突处理：冲突检测、保留、任务相关处理、反对证据。
- R3 短路径与调用成本：路由、轮次、通道调用、缓存/成本口径。
- R4 可复算性与端到端重放：两次运行逐字节一致、算子重放、报告哈希。
- R5 方案一致性与生产隔离：§4.2/§6/§8 范围、dev/val 边界、生产 `rag/` 不变、学习版声明边界。

审核代理只读、独立上下文、默认从严；findings 分阻断/重要/建议；阻断修复后由原审核代理复审；五项全部 `通过` 才可交付。
