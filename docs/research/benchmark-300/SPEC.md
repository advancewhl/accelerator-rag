# 300 题独立评测基准：出题与标注规范（v1）

日期：2026-11-07。依据：`docs/research/rag-research-reset-20261107.md` 第 2.1、5、7.1、7.4、9、10 节，以及本目录 `split-policy.json`。

本规范约束三条出题工作流（W2/W3/W4）、真值与干预工作流（W5）和全部审核（R1—R5）。任何题目若违反本规范，审核按阻断处理。

## 1. 总体要求

- 语料唯一来源：`kb-2.0.0-rc.3` 冻结快照（222 个修订、10,793 个父块），本地只读副本位于 `tmp/research-rc3/`。
- 题目只能围绕 `split-policy.json` 分配给本工作流与划分的文档族/对象簇出题；不得引用保留（reserve）族，不得引用 `access_scope=restricted` 的修订。
- 每道题必须是**独立底题**：翻译、改写、换一个数值、换一种问法都不是新的独立样本。同一对象事实的不同问法必须合并为同一道底题，其变体放入 `interventions`。
- 测试计划分（test）的题目只能使用分配给 test 的族与对象簇；出题人不得在 test 题中引用 dev/val 对象（含机柜、线缆编号、修订序列、要求—测试对）。
- 不进入阶段二内容：本阶段只产出数据与规范，不实现事实层、不实现算子、不修改检索/生成代码。

## 2. 文件与命令

- 语料查询：`python3 scripts/research/rc3_query.py search "<正则>" --family <family_id> --limit 40`
- 查看父块：`python3 scripts/research/rc3_query.py chunk <chunk_id>`
- 查看修订目录：`python3 scripts/research/rc3_query.py revision <revision_id>`
- 查看族：`python3 scripts/research/rc3_query.py family <family_id>`
- 结构校验：`python3 scripts/research/validate_benchmark.py <jsonl_file>`

每条题目写成 JSONL 一行，UTF-8，字段见第 3 节。中文题干与答案使用中文标点；引用原文保持原样，不改写、不补字。

## 3. 题目 Schema（benchmark-300-item-v1）

```json
{
  "base_id": "S1-DEV-001",
  "scenario": "s1_connectivity",
  "split": "dev",
  "cluster_id": "S1-DEV-L3L4",
  "family_ids": ["network-cable-table-shine-l3-l3-ext-96be1b"],
  "task_type": "cross_table_join",
  "query": "……",
  "query_lang": "zh",
  "scope": {"mode": "global", "revision_ids": []},
  "gold": {
    "status": "answered",
    "answer": "……",
    "required_facts": [
      {
        "fact_id": "F1",
        "statement": "……",
        "support": ["<chunk_id>"]
      }
    ],
    "forbidden_claims": ["……"],
    "evidence_minimal": [
      {
        "chunk_id": "<chunk_id>",
        "revision_id": "<revision_id>",
        "locator_kind": "cell_range",
        "locator_label": "<chunk 的 position_label 原值>",
        "excerpt": "<chunk 文本的连续子串，允许省略号分段>",
        "role": "fact_support"
      }
    ],
    "verdict_class": "deterministic",
    "recompute_note": "如何仅用 evidence_minimal 复算出 answer"
  },
  "interventions": [
    {
      "intervention_id": "S1-DEV-001-I1",
      "pair_role": "should_change",
      "operation": "swap_adjacent_ports",
      "target_chunk_ids": ["<chunk_id>"],
      "payload": {"description": "把 13-16 与 17-24 两行端口区间互换"},
      "expected_gold_after": {"status": "answered", "answer_summary": "……", "changed_fact_ids": ["F1"]}
    },
    {
      "intervention_id": "S1-DEV-001-I2",
      "pair_role": "should_hold",
      "operation": "paraphrase_query",
      "target_chunk_ids": [],
      "payload": {"query_variant": "……"},
      "expected_gold_after": {"status": "answered", "answer_summary": "不变", "changed_fact_ids": []}
    }
  ],
  "provenance": {
    "authored_by": "W2",
    "authored_on": "2026-11-07",
    "source_checked": true
  },
  "notes": ""
}
```

### 3.1 枚举值

- `scenario`: `s1_connectivity` | `s2_revision` | `s3_verification`
- `split`: `dev` | `val` | `test`
- `task_type`:
  - S1：`exact_record`（单行精确记录）、`cross_table_join`（跨表/跨机柜关联）、`set_enumeration`（完整集合）、`negative_boundary`（否定/边界）
  - S2：`version_diff`（版本差异）、`version_added`（新增内容）、`version_removed`（删除内容）、`version_same`（应保持不变）、`version_boundary`（适用条件/版本归属）
  - S3：`requirement_test_match`（要求与测试的对象/端点/条件匹配）、`acceptance_gap`（证据缺口）、`design_test_conflict`（设计值与测试值冲突）、`scope_mismatch`（测量范围不一致）、`verdict_check`（验收结论核验）
- `gold.status`: `answered` | `partial` | `insufficient`
  - 语义：表示**目标工程主张在当前冻结语料中的证据状态**，不是模型回答的可用性标签，也不是工程验收结论。
    - `answered`：有同对象、同端点、同条件的完整证据支持该主张；
    - `partial`：只有部分证据，或测量范围/条件不一致，只能有条件成立；
    - `insufficient`：语料中没有可支撑该主张的测试或验收证据，包括“文档栏为空”“只有设计值”“无对应测试项”。
  - 因此，当题目问“是否存在证据”时，确定地答“没有”仍对应 `insufficient`；判定依据写入 `recompute_note`。
- `verdict_class`: `deterministic` | `rubric` | `human`
  - `deterministic`：答案可由证据中的结构化字段（行、端口区间、数值、修订号）按明确规则复算，不需要语义解释。
  - `rubric`：答案需要按评分要点判断文本覆盖与等价（例如功能可用性比较），但真值仍可由原文逐条核对。
  - `human`：答案依赖测量语义、工程约定或资料缺失判断，必须由领域人员确认；本阶段只标注，不宣称已人工验收。
- `role`（evidence 项）: `fact_support` | `condition` | `unit` | `header` | `provenance`
- `pair_role`: `should_change` | `should_hold`
- `scope.mode`: `global` | `explicit_revisions`

## 4. 证据规则（本规范的核心）

1. **可定位**：`chunk_id` 必须存在于 rc.3 快照；`revision_id` 与 chunk 一致；`locator_kind`/`locator_label` 原样取自 chunk。
2. **可复算**：`excerpt` 必须是 chunk 文本的连续子串（允许用 `……` 连接多个连续片段，每个片段仍须逐字出现）。禁止改写、翻译、补全单位。
3. **最小且充分**：`evidence_minimal` 是能支撑全部 `required_facts` 的最小集合。每条证据必须至少被一个 fact 引用，或在 `role` 中说明为 `condition`/`unit`/`header`/`provenance` 且该角色是解释事实所必需。删除任一条 `fact_support` 后若有 fact 失去支撑，则最小性成立；R2 会逐题抽查。
4. **充分性**：`answer` 中每个断言都必须能映射到 `required_facts`；`required_facts` 中每条都必须有 support。`partial` 与 `insufficient` 题必须写明缺什么（材料不存在、范围不一致、只有设计值没有测试值等）。
   - 例外：题目锚点（电缆编号、机柜名、修订号、开关名）用于标识被问对象，不要求逐条列为 `required_fact`；由锚点推出的属性、数量、归属与结论仍必须映射。
   - 同一父块可以在一条 `evidence_minimal` 中以多个 excerpt 出现（如同一表格的不同行）；每个 excerpt 仍须逐字可查，fact 通过 chunk_id 与 excerpt 内容对应。
5. **禁止事后结论**：不得把入库手册、诊断文档中的事后定位结论当作题目真值；这类材料不作为任何题目的证据。
6. **版本归属**：版本题中每个数值/功能必须绑定到具体修订；不得把 A 版的值说成 B 版，或把归档副本当作新版本。
7. **角色保留**：设计要求、测试结果、验收结论分别保留其 `evidence_role`；不得用设计值替代测试值，也不得用验收结论替代测试数据。

## 5. 配对干预规则

每道底题至少包含 1 条 `should_change` 与 1 条 `should_hold`，成对登记。允许的 `operation`：

- `should_change`：`delete_condition`、`delete_row`、`swap_adjacent_ports`、`change_value`、`replace_revision`、`substitute_design_for_test`、`remove_link_edge`、`change_unit`
- `should_hold`：`paraphrase_query`、`reorder_paragraphs`、`add_irrelevant_similar`、`convert_unit`、`translate_query`

要求：

- `should_change` 必须指明被修改的证据（`target_chunk_ids`）、具体改法（`payload`）和修改后应有的答案（`expected_gold_after`，含 `status` 与 `answer_summary`）。修改后若应从 `answered` 变为 `insufficient`，必须写明。
- `should_hold` 必须说明为什么答案不变，且不得引入新的对象或版本。
- `paraphrase_query` / `translate_query` 的 `payload` 必须给出变体问法：字段可用 `query_variant`，或在 `description` 中完整写出变体；两种写法等价。其余 `should_hold` 操作在 `payload`/`description` 中写清扰动内容与不变理由。
- 干预是受控评价手段，不是新题；不得把干预另立 `base_id`。
- 同一底题的多个改写、翻译、单位变换只能出现在该题的 `interventions` 中，且共享同一 `base_id`。

## 6. 划分与配额

- 全局：dev 100、val 50、test 150；三个场景各 100。
- 每个 cluster 的配额见 `split-policy.json`，必须精确满足；不足或超出均视为阻断。
- 30 道显式修订范围题只出现在 S2，dev/val/test 各 10 道，`scope.mode=explicit_revisions` 且 `revision_ids` 完整列出被比较的修订。
- test 题不得引用 dev/val 族与对象；dev/val 题也不得引用 test 族与对象（双向隔离，便于泄漏审核）。
- 同一连接链、同一要求—测试对、同一修订序列及其扰动进入同一划分。跨表的连接链（例如 L3↔EXT-L3、L4↔EXT-L4）必须与包含它的交换机配置同划分。

## 7. 质量门槛（审核口径）

- R1 独立性：底题按对象关系与来源划分；同义改写/翻译/单值变化不得计为独立题；同底题扰动共享 `base_id`。
- R2 真值：逐题抽查 gold 能否从 `evidence_minimal` 复算；证据最小且充分；`verdict_class` 分类正确。
- R3 泄漏：test 文档族与对象簇与 dev/val 完全隔离；无同一连接链、同一要求—测试对、同一修订序列跨划分。
- R4 方案一致性：100 题曝光口径、30 道版本题范围、225 修订访问范围（3 个受限修订不进入默认证据）、本阶段不进入事实层与算子研发。
- R5 统计与规模：三类各 100、100/50/150、配对干预成对、置信区间所需样本量说明。

## 8. 交付格式

- W2：`data/evaluation/research-benchmark-300-v1/sealed-test/_work/w2-scenario1.jsonl`（封存路径）
- W3：`data/evaluation/research-benchmark-300-v1/sealed-test/_work/w3-scenario2.jsonl`（封存路径）
- W4：`data/evaluation/research-benchmark-300-v1/sealed-test/_work/w4-scenario3.jsonl`（封存路径）
- W5：`data/evaluation/research-benchmark-300-v1/sealed-test/_work/w5-gold-interventions.jsonl`（封存路径）（合并后的最终底题，含完整 gold 与配对干预）
- W6：`dev/questions.json`、`val/questions.json`、`sealed-test/questions.json` 与各自 manifest

所有含原文摘录的文件均不进入 Git；只提交规范、划分政策、统计摘要与校验脚本。
