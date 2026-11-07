# 阶段二独立审核协议（R1—R5）

日期：2026-11-07。适用范围：`docs/research/phase2/`、`src/accelerator_rag/facts/`、`src/accelerator_rag/verify/`、`scripts/research/prototypes/`、`tests/facts/`、`tests/verify/`、`tests/research/`，以及本地产物 `data/facts/`、`reports/phase2/`。

## 1. 原则

1. 审核代理只读，不修改任何代码、数据、文档；各自独立上下文，不参与实现。
2. 默认从严：无法从原文复算的事实、无法定位的证据、范围不明的关联，一律按阻断处理。
3. 每条 finding 必须给出具体文件与用例（函数名、fact_id、题号或请求 JSON），并说明判定理由与复现命令。
4. 审核代理只出意见，不提供改好的实现；修复由对应工作流执行，阻断项修复后由原审核代理复审。
5. 不得读取 `data/evaluation/research-benchmark-300-v1/sealed-test/` 下任何文件。审核中若发现实现引用了 test 题号、题干或真值，直接阻断。

## 2. 分级

| 级别 | 含义 | 处理 |
| --- | --- | --- |
| 阻断 | 事实被无依据填充、身份串柜、算子错误、原型不可复算、越界进入阶段三或改动生产 | 必须修复并重审 |
| 重要 | 覆盖不足、定位类型混用、边界用例缺失、报告口径不清 | 修复后复审该项 |
| 建议 | 命名、可读性、补充说明 | 记录，酌情采纳 |

存在任一阻断即总判定 `不通过`；R1—R5 全部 `通过` 才可交付。

## 3. 输入与复现命令

```bash
# 事实层（含逐字摘录，仅本地）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/build_facts.py --splits dev,val --out data/facts

# 测试
~/miniconda3/envs/accelerator-rag/bin/python -m pytest tests/facts tests/verify tests/research -q

# 算子
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/verify_op.py --op <name> --request <request.json>

# 原型（逐题）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/prototypes/p1_cable_cross_table.py --question <base_id> --out /tmp/p1.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/prototypes/p2_manual_revision_align.py --question <base_id> --out /tmp/p2.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/prototypes/p3_requirement_test_claim.py --question <base_id> --out /tmp/p3.json

# 批量复算
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/prototypes/run_prototypes.py --split dev --out reports/phase2/dev.json
```

## 4. 分工与检查清单

### R1 事实完整性

- 抽样 ≥30 条事实（三层各 ≥8 条，覆盖 paragraph/table_row/table_header/footnote/figure_caption），逐条回到 chunk/row_text 核对 `excerpt` 是否逐字。
- `unknown_fields` 是否精确：是否有字段其实有依据却被标 UNKNOWN（过度保守可接受但要说明）；是否有字段无依据却被填充（阻断）。
- 条件是否只在原文显式写出时记录；是否有从“没写条件”推出“无条件”的记录方式。
- `source_role` 与 `evidence_role` 是否齐全且区分正确（设计/测试/验收/操作步骤 vs fact_support/condition/unit/header/provenance）。
- 表格行事实是否带 `table_block_id`/`row_number`；表头、脚注、图注是否保留各自定位类型。
- 数值/单位是否逐字；`25±0.5`、`3.15.1及以上` 等表达是否被错误解析。
- 输出：逐条判定、不可复算清单、错误填充清单。

### R2 对象身份

- 抽样 ≥20 条连接/归属事实，核对 `raw_id` 是否逐字、`keys` 是否都能在原文定位。
- `DEVSW001` 类设备标识：是否只在同引用位置给出机柜/范围时参与关联；`scope=UNKNOWN` 的实体是否被算子拒绝或仅作未解析记录。
- 同名不同柜：同一设备标识在不同机柜表中是否被错误合并；跨表关联是否带 `scope_keys`。
- 原始标识是否被规范化覆盖（如把 `UN_FEL1-CN-01` 改写成 `UN-FEL1-CN-01` 后丢失原值）。
- 端口区间、VLAN、PV、系统名是否保留原文。
- 输出：串柜清单、无范围关联清单、标识丢失清单。

### R3 算子正确性

- 端口区间：边界相等（45-48 含 45/48、不含 49/44）、反向区间、列表、全角数字与中文连接符、区间 probe 重叠。
- 单位换算：ns/μs/µs/ms/s 往返、跨量纲拒绝、未知单位拒绝、Decimal 精度。
- 边界比较：相等时 le/ge 与 lt/gt；单位不同先换算；非标量拒绝。
- 集合枚举：缺失、多余、重复、universe 越界；不得声称超出输入范围的完整性。
- 精确关联：同名多范围拒绝（AMBIGUOUS_SCOPE）、scope_keys 消歧、未匹配保留。
- 版本差异：added/removed/changed/same、重复对齐键拒绝、两侧文本保留。
- 输出：错误用例、错误输出、期望输出、复现请求 JSON。

### R4 可复算性

- 三个原型是否各自一条命令复现；批量报告是否可从 `data/facts` + dev/val 题目重建。
- 报告中的 `operators` 请求/响应是否完整到可以重放；`evidence` 是否与事实 citation 一致。
- 同一命令重复运行是否字节级稳定（除时间戳外应无差异）。
- 原型是否只对 `verdict_class=deterministic` 声称结果；`rubric/human` 是否明确标 `not_evaluated`。
- 输出：不可复现清单、结果不一致清单、口径错误清单。

### R5 方案一致性

- 是否只实现 §4.1（三类事实）、§4.3（六类算子）、§6 P0（三个原型）；是否越界实现证据包选择、学习重排、动态预算。
- 是否修改生产预算、检索、生成、证据子集选择与工作流代码（`git diff` 核对）。
- 是否只使用 dev/val；是否读取或引用 sealed-test。
- 是否把“代码可执行”写成“整段回答已被形式化证明”；报告是否保留语义复核边界。
- 阶段一 37 道 human 题是否被当作正确性依据。
- 输出：越界清单、生产改动清单、口径违规清单。

## 5. 结论与复审

每个审核代理给出总判定 `通过` / `不通过`，列阻断数、重要数、建议数，并给出复审所需的最小检查集。阻断项修复后原审核代理复审；复审通过才计入最终通过。
