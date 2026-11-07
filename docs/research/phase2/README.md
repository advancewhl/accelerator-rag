# 阶段二交付说明：事实提取与核验算子研发

日期：2026-11-07。依据：`docs/research/rag-research-reset-20261107.md` §4.1、§4.3、§6（P0）、§10 阶段二。契约见 `DESIGN.md`，审核协议见 `review-protocol.md`。

## 1. 交付物

| 交付物 | 位置 | 说明 |
| --- | --- | --- |
| 结构化事实提取模块 | `src/accelerator_rag/facts/` | `schema.py` 九面向记录与未知校验；`params.py`、`connectivity.py`、`process.py` 三类事实层；`cli.py` 一条命令构建 |
| 确定性核验算子库 | `src/accelerator_rag/verify/` | 六类算子与统一 JSON 请求/响应；拒绝码；命令行 |
| 可复算单点任务原型 | `scripts/research/prototypes/` | 线缆跨表关联、手册修订对齐、工程主张核验；每份报告内嵌算子请求/响应 |
| 论文核心机制素材 | `docs/research/phase2/paper-mechanism.md` | 机制、算子语义、原型走查、评价口径与局限 |
| 审核记录 | `docs/research/phase2/reviews/` | R1—R5 独立审核与复审结论 |
| 事实构建与审计工具 | `scripts/research/{build_facts,audit_facts,show_facts,coverage_report,audit_prototypes}.py` | 构建、逐字引用审计、抽样查看、证据覆盖统计、算子重放审计 |

事实输出写入 `data/facts/`（含逐字原文摘录，仅本地保存，不进入 Git）。原型报告写入 `reports/phase2/`（同样仅本地）。

## 2. 数据边界

- 语料：`tmp/research-rc3/` 只读快照（rc.3）。
- 事实构建范围：dev/val 题目引用的 15 个文档族、48 个修订，由 `facts/corpus.py` 从题目文件机读得到。
- 题目：只使用 `data/evaluation/research-benchmark-300-v1/{dev,val}/questions.json`。
- `sealed-test/` 未被任何代码、测试、报告或审核读取。

## 3. 复现命令

```bash
# 1. 构建事实层（参数/连接/过程）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/build_facts.py --splits dev,val --out data/facts

# 2. 审计逐字引用与未知字段
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/audit_facts.py --facts data/facts/facts.jsonl

# 3. 测试
~/miniconda3/envs/accelerator-rag/bin/python -m pytest tests/facts tests/verify tests/research -q

# 4. 六类算子
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/verify_op.py --op boundary_compare --request /tmp/req.json

# 5. 三个原型（逐题与批量）
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/prototypes/p1_cable_cross_table.py --question S1-DEV-009 --out /tmp/p1.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/prototypes/p2_manual_revision_align.py --question S2-DEV-TM-01 --out /tmp/p2.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/prototypes/p3_requirement_test_claim.py --question S3-VAL-FI-001 --out /tmp/p3.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/prototypes/run_prototypes.py --split dev --out reports/phase2/dev.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/prototypes/run_prototypes.py --split val --verify reports/phase2/val.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/coverage_report.py --out reports/phase2/evidence-coverage.json
~/miniconda3/envs/accelerator-rag/bin/python scripts/research/audit_prototypes.py
```

构建清单 `data/facts/manifest.json` 记录事实数量、按层计数、修订清单、`facts_sha256` 与 `citation_problems`（必须为 0）。

## 4. 事实层口径

当前 dev/val 构建（`data/facts/manifest.json`）：**23,266 条事实**（parameter 376、connectivity 22,692、process 198），15 个文档族、48 个修订，`citation_problems=0`。`facts_sha256` 见 manifest；事实数随提取器修订变化，交付时以 manifest 为准。

- 每条事实记录对象、属性、原始值、单位、比较关系、条件、修订、证据角色与原文位置；无依据字段为 `UNKNOWN`，`unknown_fields` 与校验器强制的实际未知集合完全一致。
- 条件只在原文显式写出时记录；找不到条件时 `conditions=()` 且计入未知，不由“没写”推出“无条件”。
- 表格行保留 `table_row`、列名表头 `table_header`（row_number=0）、表题 `table_title`（row_number 为题注打印序号）、表注 `footnote`（所注表格记 `extra.table_note_of`）、非表格图注 `figure_caption`，段落与页面不混用；表题不得标成表头，表格题注不得标成图注。
- xlsx 的 cell_range 表用 `TableRecord`，摘录用 `verbatim_row_line` 取父块逐字行；docx/pdf/ppt 的 markdown 表用 `markdown_tables`，摘录用行原文。
- 连接与归属事实保留原始标识；设备标识只有在同引用位置给出机柜/范围时才填 `scope`，否则 `scope=UNKNOWN` 并记 `scope_status=unresolved`；关联算子在没有 `scope_keys` 且同键多范围时拒绝（`AMBIGUOUS_SCOPE`）。

## 5. 算子口径

六类：`exact_join`、`port_range_membership`、`set_enumeration`、`unit_convert`、`boundary_compare`、`version_diff`。

- 统一响应 `{op, status, value, trace, assumptions, refusal}`；拒绝必须有稳定 code。
- 端口闭区间与边界相等、单位换算使用 `Decimal`/`Fraction`、边界相等时 `le/ge` 为真而 `lt/gt` 为假、集合只声称输入范围内的完整性、版本差异保留两侧文本。
- `status=ok` 只表示该算子输入上的确定结论，不表示整段自然语言回答已被形式化证明。

## 6. 原型口径

- 每个原型只对 `gold.verdict_class=deterministic` 的 dev/val 题目声称结果；`rubric/human` 标 `not_evaluated`。阶段一 37 道 human 题未人工验收，不作为正确性依据。
- 报告包含 `claims`、`operators`、`evidence`、`unresolved_conditions`、`recompute`；`run_prototypes.py --verify` 可重放并逐题比对。
- `gold_alignment` 只做字符串级定位，不构成语义正确性判定。

当前运行（`reports/phase2/{dev,val}.json`，均已 `--verify` 重放通过）：

| 划分 | 题数 | deterministic | answered | partial | insufficient | unsupported | not_evaluated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dev | 100 | 68 | 61 | 7 | 0 | 0 | 32 |
| val | 50 | 36 | 26 | 8 | 1 | 1 | 14 |

这些是机制状态计数，不是准确率；逐题原因见报告 `unresolved_conditions`。

## 7. 状态与限制

- 本阶段不实现证据包选择、动态预算、学习重排与 Archiver 适配（阶段三）。
- 未修改生产预算、检索、生成、证据子集选择与工作流代码。
- 图片中的接线/流程关系未纳入；只保留可定位的图注文本。
- 事实层覆盖 dev/val 的 15 个文档族，不外推到全库。
- 扫描件 OCR 噪声较大的修订（如真空测试报告扫描页）不产出数值事实；这是有意的保守处理。mixed chunk 中的原生文本照常抽取，只逐块过滤 OCR 块。
- 已知保守项（R1 复审 S1）：9 条原文可读但句式较远的数值仍为 `UNKNOWN`，如脚注内“风扇开度能实现任意 0-100% 的调节”、正文“激光的重复频率范围在 0-1MHz”、`5-24V/12-24V/10us以内` 等；按“无依据即未知、过度保守可接受”处理，不计入错误。
- 多 chunk 块（R1 复审 S2）：一个块被拆分到多个 chunk 时，当前按块的首个贡献 chunk 抽取；dev/val 中受影响的 `acceptance_report` 块不含可解析数值，实际漏抽为 0，属已验证的潜在限制。
- `table_title` 的 `row_number` 只表示题注行在原块中的打印序号（通常为 1），不表示表格数据行；数据行一律用 `table_row`。

## 8. 事实层对基准证据的覆盖（开发用，不作正确性依据）

以 dev/val 题目的 `gold.evidence_minimal` 父块是否被至少一条事实引用统计：

| 划分 | 场景 | 全覆盖 | 部分覆盖 | 未覆盖 |
| --- | --- | ---: | ---: | ---: |
| dev | 场景一 连接 | 34 | 0 | 0 |
| dev | 场景二 修订 | 25 | 4 | 4 |
| dev | 场景三 核验 | 11 | 19 | 3 |
| val | 场景一 连接 | 16 | 0 | 0 |
| val | 场景二 修订 | 8 | 4 | 5 |
| val | 场景三 核验 | 6 | 11 | 0 |

- 场景一全覆盖，说明连接/归属事实层覆盖了这些题的全部证据父块。
- 场景二的未覆盖项是纯段落级修订文本；原型按 DESIGN §6 直接读取修订 chunk 并用 `version_diff` 比较，不依赖参数事实。
- 场景三的部分/未覆盖项多为“验收栏为空”“结论列对象错位”这类**结构性缺失**：事实层不伪造空值，原型改为检查表格结构并引用具体行。
- 该表只说明事实层与证据父块的对应关系，不表示任何答案正确。生成命令：`scripts/research/coverage_report.py --out reports/phase2/evidence-coverage.json`，本次生成对应 `facts_sha256=49bd544f…`；覆盖 JSON 逐题记录 `covered_chunks`（每个证据父块的 `covered` 与命中层），可据以重建本表。

## 9. 审核

R1—R5 独立审核（只读、不读 sealed-test）均已复审通过，记录见 `reviews/`：

| 审核 | 关注点 | 首轮 | 复审结论 |
| --- | --- | --- | --- |
| R1 | 事实完整性：未知字段、证据角色、原文位置 | 不通过（1 阻断 / 7 重要） | **通过**（0 阻断 / 0 重要 / 3 建议） |
| R2 | 对象身份：同名跨柜、范围、原始标识 | 不通过（2 阻断 / 5 重要） | **通过**（最终构建 23,266 / 49bd…） |
| R3 | 算子正确性：边界、单位、端口、集合 | 不通过（1 阻断 / 2 重要） | **通过**（0 阻断 / 0 重要） |
| R4 | 可复算性：单命令复算、结果与记录一致 | 不通过（2 阻断 / 3 重要） | **通过**（169 算子可重放、63 证据逐字） |
| R5 | 方案一致性：范围、边界、生产隔离 | 通过（2 重要待修） | **通过**（0 阻断 / 0 重要） |

最终交付要求五项全部 `通过`；当前五项均已给出通过结论。
