# 论文核心机制素材：有来源的工程事实与确定性核验

**状态**：阶段二 W6 素材稿。机制主张对应 `src/accelerator_rag/facts/`、`src/accelerator_rag/verify/operators.py` 与 `docs/research/phase2/DESIGN.md`；规模数字取自 `data/facts/manifest.json`，原型运行统计见 §5。本文只描述机制与可复算结构，不将机制状态计数表述为准确率或实验结论。

## 1. 机制问题

真实加速器工程问答的主要失败，不是找不到相关段落，而是找到了相关段落却组合错误：对象、条件、证据角色或修订被接错。检索按主题相关性排序，引用校验按文本存在性判定；两者都不编码跨段落的对象同一性、条件适用性、证据角色与修订归属。系统因此可以在召回与引用上都表现良好，却在工程主张层面给出错误组合。

四类具体错误在已整理的工程资料中可观察到，也对应 `docs/research/rag-research-reset-20261107.md` §4.2 列出的近似错误组合与 §7.4 的配对干预：

1. **对象串柜**。同一设备标识在多个机柜表中以相同词面出现，检索返回邻近表的行，回答把 A 柜的端口区间接到 B 柜的设备。区分信息通常在表题或表头，不在行文本里；错误行与正确行词面几乎相同，相似度无法区分。
2. **条件/测量端点缺失**。数值被正确检索，但适用模式、量程、上下界或测量端点写在表头、脚注或另一段，回答只带走数值。承载条件的段落往往很短、与问题词面不相似，排序靠后，被组合阶段遗漏。
3. **证据角色替代**。设计指标、实测结果与验收结论在词面和数值上都可能接近；回答把设计值放在“测试结果”的位置，或把验收结论当作测量数据。角色是文档级属性，不写在句子内部，引用有效不排除角色错误。
4. **版本混用**。不同修订的手册或报告段落同时存在，系统把旧版步骤、旧版阈值拼到新版对象。每条引用对其所在修订都成立，但组合跨越了修订边界。

三种区分失效可概括为：相似度衡量主题相关性，不衡量关系正确性；引用校验衡量文本存在性，不衡量使用正确性；单段证据的有效性不能排除跨段组合错误。排除这些错误，需要在原文旁保留可定位的结构化事实，并把标识关联、区间归属、集合比较、单位换算、边界比较与版本差异交给确定性算子。

## 2. 有来源的工程事实层

事实层不替代原文，也不构建推断型知识图谱；它在现有父块与引用体系旁增加可定位的记录（`facts/schema.py` 模块 docstring；DESIGN §1、§4）。每条 `Fact` 记录 §4.1 要求的九个面向：

| 面向 | 字段 | 记录规则 |
| --- | --- | --- |
| 对象 | `subject: EntityRef` | 原文标识；`raw_id` 逐字保留 |
| 属性 | `attribute` | 属性名或关系类型；无依据为 `UNKNOWN` |
| 原始值 | `raw_value` | 原文逐字；不改写、不补单位 |
| 单位 | `unit` | 原文单位逐字；未印出为 `UNKNOWN` |
| 比较关系 | `comparator` | `eq/lt/le/gt/ge/range/in/unknown` |
| 条件 | `conditions` | 每条条件自带 `Citation`；未找到为 `()` |
| 修订 | `revision_id` | 与 `citation.revision_id` 一致 |
| 证据角色 | `source_role` + `evidence_role` | 文档角色与事实角色分开 |
| 原文位置 | `citation` | chunk、修订、定位类型、标签、逐字摘录 |

证据角色在实现中拆成两个字段，故 `FACETS` 有十项：`source_role` 表示文档角色（如 `design_target`、`test_result`、`acceptance_conclusion`、`operating_step`、`historical_record`、`background_reference`，取自修订元数据），`evidence_role` 表示该事实在证据中的用途（`fact_support`、`condition`、`unit`、`header`、`provenance`）。该拆分使“设计值当测试值”这类错误可在记录层面识别，不必依赖数值本身（`facts/schema.py`；`facts/corpus.py` 的 `revision_source_role`）。

**未知即未知。** 原文不支持的字段保持 `UNKNOWN`（`raw_value` 必须存在），由 `unknown_fields` **恰好**列出；`validate_fact` 重新计算实际未知集合，多列或少列触发 `UNKNOWN_FIELDS_MISMATCH`（DESIGN §4.1）。`comparator="unknown"` 与 `value_kind="unknown"` 是“已记录为未知”的取值，不重复列入；`number/low/high` 是派生字段，由 `value_kind` 说明未解析原因。提取器不得用常识、文件名、相邻行或另一修订补齐；表格空单元格产生 `UNKNOWN`，不是空字符串。

**条件只在显式时记录。** 条件必须出现在同一行、表头、表题、同段或紧邻脚注中，且每条条件带自己的 `Citation`。原文未写条件时 `conditions=()` 并计入未知；由“没写”推出“无条件”是禁止的推断。因此 `conditions=()` 只表示该位置未显式给出条件，不表示参数无条件适用（DESIGN §4.1）。

**对象身份。** `EntityRef.raw_id` 必须逐字来自原文；`keys` 只保存可在原文逐字定位的身份分量，并记录 `basis`（如 `parenthesized`、`table_title`、`row_column`）。形如 `DEVSW001` 的设备标识只有在**同一引用位置**同时给出机柜或范围时才可参与关联：`scope` 非 `UNKNOWN`，`scope_source` 说明依据；否则 `scope` 保持 `UNKNOWN`，`extra` 记 `scope_status=unresolved`。同一标识在两个机柜表中出现即产生两个独立 `EntityRef`，不合并；同名字段不得跨柜直接连接。原始标识永不丢弃，规范化只用于比较，`raw_id` 与 `keys.value` 保持原文（`facts/connectivity.py` docstring；DESIGN §4.2）。

**定位类型。** 五类主要定位类型是段落 `paragraph`、表行 `table_row`、表头 `table_header`、脚注 `footnote`、图注 `figure_caption`；表题另记 `table_title`，其余父块用 `section`、`pdf_page`、`slide`。表行与表头必须带 `table_block_id` 与 `row_number`，表题带 `table_block_id`；`excerpt` 必须是父块 chunk 中该行的逐字原文；xlsx 的 cell_range 表用 `verbatim_row_line` 取逐字行，docx/pdf/ppt 的 markdown 表用行原文（DESIGN §4.3；`facts/corpus.py`）。定位类型不可混用：同一句话出现在表头与脚注中，其适用范围不同。

抽象示例（占位符，不对应任何实际文档）：对象“设备 A”（范围“机柜 X”），属性端口归属，原始值“端口区间 P”，另一端“系统 S”，条件“VLAN V”，修订“R”：

```
subject      = 设备 A（raw_id="设备 A"；scope="机柜 X"；scope_source=table_title；
               keys: DEVSW001 @ parenthesized）
attribute    = port_system
object_ref   = 系统 S
raw_value    = 端口区间 P（逐字）
unit         = UNKNOWN
comparator   = in
conditions   = (Condition(kind="vlan", raw="VLAN V", citation=脚注 F),)
revision_id  = R
source_role  = design_target
evidence_role= fact_support
citation     = table_row；table_block_id=T；row_number=n；excerpt=逐字行
unknown_fields = ("unit",)
```

条件已显式记录，`conditions` 不列入 `unknown_fields`；单位未印出，`unit` 列入。若条件未写出，`conditions=()` 且 `conditions` 进入 `unknown_fields`；两种情况在记录层面可机械区分。

当前构建规模（来源：`data/facts/manifest.json`）：**23,266 条事实**（parameter 376、connectivity 22,692、process 198），覆盖 15 个文档族、48 个修订，`citation_problems=0`。事实数随提取器修订变化，引用时以 manifest 为准；该数字只说明构建范围，不说明正确性。

## 3. 确定性核验算子

六类算子位于 `verify/operators.py`，是纯函数，无网络、无模型、无时钟、无文件系统依赖，不导入 `facts` 包；请求与响应为普通 JSON。六类算子分别承担：显式键连接、端口/区间归属、集合枚举与完整性比较、同量纲单位换算、数值与边界比较、修订对齐项分类。统一响应为 `{op, status, value, trace, assumptions, refusal}`。`status=refused` 时必须带稳定的大写下划线拒绝码；`trace` 记录实际用到的输入与中间值；`assumptions` 只回显调用方显式传入的假设，算子不自行假定单位、范围或身份（DESIGN §5）。

| 算子 | 输入 | 输出 | 拒绝条件与码 |
| --- | --- | --- | --- |
| `exact_join` | `left/right` 记录集（`{id, keys, scope, payload}`）、`join_keys`、可选 `scope_keys` | 匹配对、未匹配项及原因、计数、`scope_mode` | 同键多范围或缺范围且无 `scope_keys`：`AMBIGUOUS_SCOPE` |
| `port_range_membership` | `spec`（单端口、区间或逗号列表）、`probe`（端口或区间） | `contained`、`overlap`、`spec_ranges`、`probe_ranges`、`matched_range` | 规格端口非法：`BAD_PORT_SPEC`；探测值非法：`BAD_PROBE` |
| `set_enumeration` | `observed`、`expected`、可选 `universe` | `missing/extra/duplicates`、`complete/exact`、`out_of_universe`、`scope_note` | 输入非字符串列表：`BAD_REQUEST` |
| `unit_convert` | `value`、`from`、`to` | 换算值字符串、`factor`、`exact`、`dimension` | 未知单位：`UNKNOWN_UNIT`；跨量纲：`UNIT_DIMENSION` |
| `boundary_compare` | `value`、`unit`、`op`、`bound`、`bound_unit` | `result`、`converted_value`、`boundary_equal`、`exact` | 非法比较符：`BAD_OP`；非标量：`NON_SCALAR`；未知/跨量纲单位：`UNKNOWN_UNIT`/`UNIT_DIMENSION` |
| `version_diff` | `left/right`（`revision_id`、`items`）、`normalizer` | `same/added/removed/changed` 与计数，两侧文本均保留 | 对齐键重复：`DUPLICATE_ALIGN_KEY`；规范化器非法：`BAD_NORMALIZER` |

请求形状、字段类型与缺必填字段的错误统一为 `BAD_REQUEST`（端口算子缺字段分别用 `BAD_PORT_SPEC`、`BAD_PROBE`）。

六个边界行为的处理如下，均可在 `tests/verify/test_operators.py` 中找到对应用例：

- **边界相等**：`boundary_compare` 先把 `value` 换算到 `bound_unit`，相等时 `le/ge/eq` 为真、`lt/gt` 为假，响应置 `boundary_equal=true`；不把相等归入严格不等。
- **单位不匹配**：先显式换算再比较；跨量纲拒绝 `UNIT_DIMENSION`，未知单位拒绝 `UNKNOWN_UNIT`。数据量单位按十进制 SI（KB=1000B），二进制单位不接受；算子不猜测单位。
- **端口闭区间**：区间端点属于区间（`45-48` 含 45 与 48）；反向区间被规范化并在 `trace` 标 `reversed=true`；支持 `-`、`~`、`～`、`至`、`—` 与全角数字（NFKC）。
- **集合缺失**：`set_enumeration` 分别报告 `missing`、`extra`、`duplicates`；`complete` 只表示“没有 missing”，`exact` 还要求没有 extra 与 duplicates；`scope_note` 明确完整性只相对于给定输入。
- **同名多范围**：`exact_join` 在没有 `scope_keys` 时，只要任一侧存在携带 join key 但 scope 缺失、或同一键对应多个 scope 的记录，整个请求拒绝 `AMBIGUOUS_SCOPE`，即使该键没有对侧候选；带 `scope_keys` 时，缺 scope 的记录以 `missing_scope_key` 记为未匹配，不取第一条、不做模糊匹配。
- **重复对齐键**：`version_diff` 在任一侧发现重复 `item_id` 即拒绝 `DUPLICATE_ALIGN_KEY`，不覆盖、不合并，避免把两个不同条目对齐成一条。

必须强调：`status=ok` 只表示**该算子在其输入上**得到确定结论，不表示整段回答已被形式化证明。输入如何由事实层选出、单位是否被正确解释、两个标识是否同一物理对象，都在算子之外；算子只保证给定输入下的计算与比较可复算（DESIGN §1、§5）。

## 4. 三个单点原型的机制设计

三个原型已交付（`p1_cable_cross_table.py`、`p2_manual_revision_align.py`、`p3_requirement_test_claim.py`），均按 `scripts/research/prototypes/common.py` 固定的报告契约：`question_id/status/answer/claims/operators/evidence/unresolved_conditions/recompute`；每条 claim 绑定 `fact_id` 列表，`operators` 内嵌完整请求与响应，`recompute` 记录命令与 `facts_sha256`。共同数据流是“**事实 → 算子 → 结论/证据缺口**”（DESIGN §6）。

**（1）线缆跨表关联。** 事实输入为 connectivity 层的 `port_span`、`port_system_label`、`port_assignment`、`port_system`、`cable_membership`、`cable_endpoint_start/end` 与 `reserved_slot`。原型从题干解析锚点（机柜+设备、端口区间、电缆编号、E 编号），按 citation 的 `(revision_id, table_block_id, row_number)` 还原表格行；`port_range_membership` 判断端口是否落在配置行或电缆行印出的区间内，`set_enumeration` 做跨表配平、缺号边界与端口块清单比较。槽位模型是唯一的表内推演：电缆行按 `row_number` 排序，E 编号即槽位号，预留行尾数为声明的槽位数，逐行累加得到下一槽位；编号与槽位计数不一致时在报告中标出。算子完成区间归属与集合比较；仍需语义复核关系方向、对象同一性、预留项与线缆端点的区分。缺口出现在锚点无法唯一定位或表行不完整时，报告 `insufficient`/`partial`/`unsupported` 并写入 `unresolved_conditions`。

**（2）手册修订对齐。** 事实输入是两个修订的 chunk，比较不依赖参数层数值。原型先确定修订：`scope.mode=explicit_revisions` 时按给定顺序，否则按 `revision_label` 的版次/归档标记匹配；无标记时按族内前两个版本回退，标记匹配到零个或多个候选即 `unsupported`，不猜。再用题干中的字面锚点（引号短语、显式标识符、功能关键词）在两侧各对齐一个段落，要求每侧唯一命中；段落级歧义时退到句子级共现，仍不唯一则 `unsupported`，不使用相似度。`item_id=chunk_id`、`text=chunk.text`，以 `version_diff` 和 `normalizer=whitespace` 比较；只声称 exact/whitespace 级一致，语义等价留人工复核。算子完成对齐后的分类；修订替代关系来自元数据，不由算子证明。缺口出现在版本目标歧义、锚点无法对齐或扫描文本噪声过大时。

**（3）工程主张核验。** 事实输入包括 parameter 层的设计要求/测试结果（`source_role=design_target`/`test_result`/`historical_record`）与 process 层的 `test_scope`；`unit_convert` 统一单位，`boundary_compare` 判定实测是否落在要求边界内，`set_enumeration` 比较要求项与报告项。对“验收栏为空/结论列错位”这类结构问题，原型直接读取冻结表格检查指标—实测—结论三元组与验收结论栏，不把栏目名存在当作结果。算子完成换算、边界比较与集合差异；仍需语义复核条件是否同一工况、验收结论是否适用于该对象、文本判据是否等价；角色替代由 `source_role` 与原文核对识别。缺口包括条件/端点未解决、原文未印出结果、结构栏缺失；此时输出“当前证据无法判断”或 `insufficient`，不从缺失推出不合格。

## 5. 原型运行结果

| 划分 | 题数 | deterministic 总数 | answered | partial | insufficient | unsupported | not_evaluated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dev | 100 | 68 | 61 | 7 | 0 | 0 | 32 |
| val | 50 | 36 | 26 | 8 | 1 | 1 | 14 |
| 合计 | 150 | 104 | 87 | 15 | 1 | 1 | 46 |

表中为机制状态计数，不是准确率；`rubric`/`human` 题一律 `not_evaluated`，阶段一 human 题未经人工验收，不得作为正确性依据；`gold_alignment` 仅做字符串级定位，不构成语义正确性判定。三个原型均只对 `deterministic` 题声称结果，`answered/partial/insufficient/unsupported` 的逐题原因见报告 `unresolved_conditions`；按场景与原型拆分的计数见逐题 `reports`（每条含 `scenario`/`task_type`/`status`）。复算：`python3 scripts/research/prototypes/run_prototypes.py --split dev --verify reports/phase2/dev.json`；`python3 scripts/research/prototypes/run_prototypes.py --split val --verify reports/phase2/val.json`。报告与 manifest 的 `facts_sha256` 一致（`49bd544fa252607e2ab0453b8ea42f8cd833b84fdd6a701bf4f1d01bae179a71`）；`recompute` 还固定 `questions_sha256` 与 `corpus_snapshot`（rc.3 inventory + 48 个修订 chunk 文件），`scripts/research/audit_prototypes.py` 可逐条重放 169 条算子记录并核验无 fact_id 证据的逐字性。

## 6. 评价口径

基准题的 `gold.verdict_class` 分三类：`deterministic`、`rubric`、`human`。原型只对 `deterministic` 题声称结果；`rubric` 与 `human` 题一律输出 `not_evaluated`（`common.py` 的 `guard_verdict_class`；DESIGN §6）。阶段一的 37 道 human 题未经领域人员人工验收，不得作为正确性依据（DESIGN §6）。

`gold_alignment` 只是在 gold answer 与 `required_facts` 的拼接串中做字符串包含，用于定位 claim 值是否出现，不构成语义正确性判定；字符串出现不等于主张正确，字符串缺失也不等于主张错误。原型报告的是机制层面的状态（`answered/partial/insufficient/unsupported/not_evaluated`）、证据缺口与可复算的算子轨迹，不是准确率。研究计划 §4.3 的“成立/不成立/有条件成立/当前证据无法判断”是**研究标签**，不能直接映射为工程验收结论。

## 7. 与方案条款的对应

| 条款 | 阶段二对应 | 边界与状态 |
| --- | --- | --- |
| §4.1 有来源的工程事实与依赖 | `facts/schema.py` 九面向与未知校验；`params.py`、`connectivity.py`、`process.py` 三类事实层；DESIGN §4.2 身份规则与 §4.3 定位类型 | 已实现于事实层，覆盖 dev/val 的 15 个族，不外推全库 |
| §4.1 研究问题（相同候选数量下依赖是否提高完整证据检索） | 阶段二只提供事实表示与算子，不回答该问题 | 需阶段四的同预算对照与消融 |
| §4.3 可复算核验 | `verify/operators.py` 六类算子；原型报告记录结论、证据、算子请求/响应与未解决条件 | 算子与原型均已实现；运行统计见 §5 |
| §6 P0 `corpus/table_records.py` 身份映射与显式关联 | `facts/schema.py` 的 `EntityRef`、`connectivity.py` 的 `scope`/`keys` 记录与 `exact_join` | 生产 `table_records.py` 未修改 |
| §6 P0 `rag/context.py` 结构化证据上下文 | 事实记录已保留行、条件、角色与定位类型 | 生产 `context.py` 未修改，集成留待阶段三 |
| §6 P0 `rag/evidence.py` 同预算证据包比较 | 不在阶段二范围 | 属 §4.2 阶段三机制与阶段四实验 |
| §6 P0 `rag/answer.py` 结构性核验与提示词分离 | `verify/operators.py` 提供独立算子层；原型按此调用方式设计 | 生产 `answer.py` 未修改，集成留待阶段三 |

阶段三之前明确不实现：证据包选择、动态预算、学习重排与 Archiver 适配（DESIGN §1；研究计划 §10 阶段三）。本阶段也未修改生产预算、检索、生成、证据子集选择与工作流代码。

## 8. 局限与效度威胁

- **覆盖范围**：事实层只覆盖 dev/val 题目引用的 15 个文档族、48 个修订，不代表全库；不能据此外推未见文档族或未见对象簇。
- **事实分布偏斜**：connectivity 22,692 条，占 23,266 条的绝大多数；parameter 376、process 198。机制证据主要来自连接表，参数与过程机制被数据检验的机会较少。
- **条件提取稀疏**：条件只在原文显式写出时记录，大量事实的 `conditions` 为未知；条件敏感的主张难以在现有规模上系统核验。
- **图片关系未纳入**：只保留可定位的图注文本；图片中的接线与流程关系未建立，不声称视觉知识图谱或图文对齐。
- **扫描件噪声**：OCR 噪声较大的修订不产出数值事实，这是有意的保守处理；由此造成的覆盖损失未被计为错误，也不能反过来当作精度。
- **语义解释未形式化**：对象同一性、条件等价、证据角色适用与文本判据仍需语义复核；算子只覆盖显式结构，`status=ok` 不构成整段回答的证明。
- **原型不是端到端系统**：三个原型是单点机制展示，未接入检索、生成与预算选择，不能据此作端到端准确率、延迟或工程适用性结论。
- **评价口径**：human 题未人工验收，rubric 非权威判定，deterministic 子集可能偏向可机制化的题目；`gold_alignment` 仅字符串级。规模数字随提取器修订变化，引用以 `data/facts/manifest.json` 为准。
