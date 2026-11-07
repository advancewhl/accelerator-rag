# 阶段二设计：事实提取层与确定性核验算子

日期：2026-11-07。依据：`docs/research/rag-research-reset-20261107.md` §4.1、§4.3、§6（P0）、§10 阶段二。

本文件是阶段二全部工作流（W1—W6）与独立审核（R1—R5）的共同契约。凡与本文件冲突的实现，审核按阻断处理。

## 1. 范围

本阶段只做四件事：

1. 三类有来源的工程事实层（参数与条件、连接与归属、过程与依赖），对应 §4.1。
2. 六类确定性可执行核验算子（精确关联、端口区间归属、集合枚举、单位换算、边界比较、版本差异），对应 §4.3。
3. 三个可复算的单点任务原型（线缆跨表关联、手册修订对齐、工程主张核验），对应 §4.3 与 §6 P0。
4. 论文核心机制章节素材（中文），对应 §10 阶段二产出。

明确不做：

- 不做证据包选择与学习重排（阶段三，§4.2）。
- 不改生产预算、检索、生成、证据子集选择与工作流代码。
- 不把自然语言解释形式化；算子的 `ok` 只表示该算子输入上的确定结论，不表示整段回答已被证明。
- 不纳入图片中的接线或流程关系；图片只保留图注文本，且仅当图注本身可定位时。图文对齐未核对前不建立关系。

## 2. 数据边界

- 语料：`tmp/research-rc3/` 只读快照（rc.3，222 修订 / 10,793 父块）。
- 题目：只允许 `data/evaluation/research-benchmark-300-v1/{dev,val}/questions.json`。
- **禁止读取** `data/evaluation/research-benchmark-300-v1/sealed-test/` 下任何文件（含 `SEALED.md`），禁止在代码、测试、报告、提交信息中引用 test 题号、题干或真值。
- 事实构建默认只覆盖 dev/val 题目引用的 15 个文档族（48 个修订）。族清单由 `facts/corpus.py` 从 dev/val 题目文件机读得到，不手工维护。
- 事实输出含逐字原文摘录，与阶段一一致：写入 `data/facts/`，该目录不进入 Git；代码、测试、文档与匿名小样例入库。

## 3. 模块结构

```
src/accelerator_rag/facts/
  schema.py        事实记录、UNKNOWN 哨兵、校验、JSONL 读写（共用，冻结）
  corpus.py        rc.3 只读加载、dev/val 族范围、表格行→父块定位（共用，冻结）
  params.py        W1 参数与条件事实层
  connectivity.py  W2 连接与归属事实层
  process.py       W3 过程与依赖事实层
  cli.py           一条命令构建事实层
src/accelerator_rag/verify/
  operators.py     W4 六类确定性算子
  cli.py           W4 算子命令行
scripts/research/
  build_facts.py       事实构建入口（薄封装）
  audit_facts.py       全量逐字引用审计（主控）
  show_facts.py        单条事实查看（主控）
  coverage_report.py   基准证据覆盖统计（主控，开发用）
  verify_op.py         单算子命令行封装（主控）
  audit_prototypes.py  原型算子/证据重放审计（主控）
  prototypes/p1_cable_cross_table.py      W5 线缆跨表关联
  prototypes/p2_manual_revision_align.py  W5 手册修订对齐
  prototypes/p3_requirement_test_claim.py W5 工程主张核验
  prototypes/run_prototypes.py            W5 批量复算与报告
tests/facts/       事实层测试（schema + 三个提取器）
tests/verify/      算子测试
tests/research/    原型测试
docs/research/phase2/
  DESIGN.md        本文件
  paper-mechanism.md  W6 论文机制素材
  reviews/R1..R5.md  独立审核记录
```

文件所有权：W1 只写 `facts/params.py` 与其测试；W2 只写 `facts/connectivity.py` 与其测试；W3 只写 `facts/process.py` 与其测试；W4 只写 `verify/*` 与其测试；W5 只写 `scripts/research/prototypes/*`、`scripts/research/build_facts.py` 与其测试；W6 只写 `paper-mechanism.md`。共用文件（`schema.py`、`corpus.py`、`cli.py`）由主控维护，工作流不得修改；确需扩展时在报告中提出，由主控统一改。

## 4. 事实记录（§4.1）

每条事实是一条 `Fact`，必须记录九个面向：

| §4.1 面向 | 字段 | 规则 |
| --- | --- | --- |
| 对象 | `subject: EntityRef` | 原文标识；`raw_id` 逐字保留 |
| 属性 | `attribute` | 属性名或关系类型；无依据为 `UNKNOWN` |
| 原始值 | `raw_value` | 原文逐字；不改写、不补单位 |
| 单位 | `unit` | 原文单位逐字；未印出为 `UNKNOWN` |
| 比较关系 | `comparator` | `eq/lt/le/gt/ge/range/in/unknown`；无显式关系且非表格赋值时为 `unknown` |
| 条件 | `conditions: tuple[Condition,...]` | 每条条件带自己的 `Citation`；未找到为 `()` 且 `conditions` 计入未知 |
| 修订 | `revision_id` | 取自 chunk/parsed 文件 |
| 证据角色 | `source_role` + `evidence_role` | 前者为文档角色（`design_target/test_result/...`），后者为 `fact_support/condition/unit/header/provenance` |
| 原文位置 | `citation: Citation` | `chunk_id/revision_id/locator_kind/locator_label/excerpt` |

附加字段：

- `layer`：`parameter | connectivity | process`。
- `fact_type`：`attribute | relation | step | prerequisite | test_scope | requirement_link | acceptance_state` 等，首段小写 ASCII。
- `object_ref`：仅关系事实使用；属性事实必须为 `UNKNOWN`。
- `value_kind`：`number | quantity | text | enum | version | boolean | date | range | unknown`。
- `number/low/high`：只在原文明确给出可解析数值时填写；`±`、区间等展开必须同时给出中心值与容差，并在 `extra` 记录 `derivation`。
- `unknown_fields`：**恰好**列出本记录中未知的面向字段名，不得多列或少列。校验器强制一致。`comparator="unknown"` 与 `value_kind="unknown"` 表示原文没有给出比较关系/值类型，属于“已记录为未知”的取值，不重复列入 `unknown_fields`；`number/low/high` 是派生字段，为 `null` 表示未解析出数值，由 `value_kind` 说明原因。
- `extra`：`(name, value)` 原始字符串对，用于记录解析依据（如 `comparator_basis=table_cell_assignment`、`derivation=center±tolerance`）。

### 4.1 未知即未知

- 提取器不得用常识、文件名、相邻行或另一修订补齐字段。
- 表格单元格为空 → 该字段 `UNKNOWN`，不是空字符串值。
- 条件只在原文（同一行、表头、表题、同段或紧邻脚注）明确写出时记录；从“没有写条件”推出“无条件”属于禁止的推断，此时 `conditions=()` 且计入未知。
- `comparator=eq` 只允许两种情况：原文有等号/“为”等显式关系，或表格行把属性列与值列结构性地绑定；后者必须在 `extra` 写 `comparator_basis=table_cell_assignment`。

### 4.2 对象身份（§4.1）

- `EntityRef.raw_id` 必须逐字来自原文；`keys` 只保存原文中可逐字定位的身份分量（如括号中的 `DEVSW001`），每项记录 `basis`（`parenthesized/prefix/whole/row_column/table_title/section_heading/explicit_in_text`）。
- `DEVSW001` 这类设备标识只有在**同一引用位置**给出机柜/工作表/表题范围时才可参与关联：`scope` 必须非 `UNKNOWN`，`scope_source` 说明依据。
- 同名字段不得跨机柜直接连接：关联算子在没有 `scope_keys` 且同一标识对应多个范围时必须拒绝（`AMBIGUOUS_SCOPE`），不得取第一条或做模糊匹配。
- 原始标识永不丢弃：规范化只用于比较，`raw_id` 与 `keys.value` 保持原文。

### 4.3 定位类型（§4.1）

`locator_kind` 取值必须区分：

- `paragraph`：段落块；
- `table_row`：表格数据行（`TableRecord`）；
- `table_header`：表头行；
- `footnote`：脚注/表注（`block_type=note`）；
- `table_title`：表格标题/题注行（如“表1 …”或表上方标题行）；必须带 `table_block_id`；
- `figure_caption`：非表格图注（`block_type=caption` 且非表格题注）；
- `section` / `pdf_page` / `slide`：其余父块定位。

表格标题不得标成 `table_header`（表头是列名行，`row_number=0`）；表格题注不得标成 `figure_caption`。`table_title` 的 `row_number` 只表示题注行在原块中的打印序号（通常为 1），不表示数据行；表后 `note` 用 `footnote`，所注表格记入 `extra.table_note_of`。

表格行事实的 `citation.table_block_id` 与 `row_number` 必须填写；`excerpt` 必须是父块 chunk 中该行的逐字 markdown 原文（允许 `……` 连接多个连续片段）。

- xlsx 的 cell_range 表：用 `TableRecord`；`TableRecord.row_text` 会丢弃空单元格，**不是** chunk 原文的子串，取原文一律用 `corpus.verbatim_row_line(record, chunk_text)`（已对 dev/val 全部 3,196 行验证可解析）。
- docx/pdf/ppt 的 markdown 表：用 `corpus.markdown_tables(chunk, revision_id)`；`MarkdownRow.line` 即逐字行，`block_id` 与 `row_number` 直接用于 citation。表头用 `locator_kind="table_header"`、`row_number=0`、`header_line` 作摘录。

## 5. 确定性算子（§4.3）

统一 JSON 请求/响应，纯函数，无网络、无模型、无时钟依赖。

响应结构：

```json
{
  "op": "port_range_membership",
  "status": "ok | refused",
  "value": {},
  "trace": [],
  "assumptions": [],
  "refusal": null
}
```

- `status=refused` 时必须给出 `refusal.code`（大写下划线）与 `refusal.message`；不得用 `ok` 掩盖缺输入、单位不匹配或范围不明。
- `trace` 记录实际用到的输入与中间值（如换算因子、解析出的区间），供复算。
- `assumptions` 必须为空数组或仅含调用方显式传入的假设；算子不得自行假定单位、范围或身份。

六类算子：

1. `exact_join`：按显式键连接两条记录集；`scope_keys` 用于限定对象范围；同键多范围且未给 `scope_keys` 时拒绝。
2. `port_range_membership`：端口区间/列表归属与区间包含；边界相等按闭区间；支持 `-~～至—` 与全角数字；探测值可为单端口或区间。
3. `set_enumeration`：集合枚举与完整性比较；输出 missing/extra/duplicates，可选 `universe` 检查越界；只在给定证据范围内声称完整。`complete` 仅表示“无 missing”，集合全等看 `exact`；`scope_note` 必须写明这一区分。
4. `unit_convert`：同量纲单位换算；使用 `Decimal`/`Fraction`；未知/跨量纲单位拒绝；`µ` 与 `μ` 视为同一微前缀。数据量单位按十进制 SI（KB=1000B），二进制单位（KiB 等）拒绝。
5. `boundary_compare`：数值与上下界比较；单位不同先显式换算；边界相等时 `le/ge` 为真、`lt/gt` 为假；非标量输入拒绝。
6. `version_diff`：两侧对齐项的 same/added/removed/changed 分类；两侧内容都保留；对齐键重复时拒绝；`normalizer` 缺省为 `exact`。

`exact_join` 的 scope 检查按全局从严：只要任一侧存在携带 join key 但 scope 缺失或同键多 scope 的记录，且调用方未给 `scope_keys`，整个连接拒绝（`AMBIGUOUS_SCOPE`），即使该键没有对侧候选。

算子命令：

```bash
python3 scripts/research/verify_op.py --op <name> --request <request.json>
```

## 6. 原型（§4.3、§6 P0）

每个原型一条命令可复算，输出可机读报告：

```bash
python3 scripts/research/build_facts.py --splits dev,val --out data/facts
python3 scripts/research/prototypes/p1_cable_cross_table.py --question S1-DEV-009 --out report.json
python3 scripts/research/prototypes/run_prototypes.py --split dev --out reports/phase2/dev.json
```

报告必须包含：

- `question_id`、`status`（`answered/partial/insufficient/unsupported`）、`answer`；
- `claims`：每条断言对应的 `fact_id` 列表；
- `operators`：实际执行的算子请求与响应（完整可复算）；
- `evidence`：`chunk_id` 与 `excerpt`；
- `unresolved_conditions`：未解决的条件/范围；
- `recompute`：复算命令与输入哈希。

原型只对 `gold.verdict_class=deterministic` 的 dev/val 题目声称结果；`rubric/human` 题一律标 `not_evaluated`，不作正确性依据。阶段一 37 道 human 题未人工验收，不得作为正确性依据。

## 7. 测试与复现

- 单元测试使用内存小样例，不依赖语料。
- 语料测试标记 `@pytest.mark.corpus`，只读 `tmp/research-rc3/`，缺失时跳过。
- 全量检查：

```bash
~/miniconda3/envs/accelerator-rag/bin/python -m pytest tests/facts tests/verify tests/research -q
~/miniconda3/envs/accelerator-rag/bin/python -m ruff check src/accelerator_rag/facts src/accelerator_rag/verify scripts/research/prototypes
```

## 8. 审核

R1 事实完整性、R2 对象身份、R3 算子正确性、R4 可复算性、R5 方案一致性。审核代理只读、独立上下文、默认从严；findings 分阻断/重要/建议；阻断项修复后必须由原审核代理复审。最终交付前五项必须全部给出通过结论。审核记录写入 `docs/research/phase2/reviews/`。
