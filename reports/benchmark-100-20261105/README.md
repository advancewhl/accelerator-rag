# 100 题验证集：核验、修订与扩建（2026-11-05）

状态：**已冻结，用于 `kb-2.0.0-rc.3` 候选与 `kb-2.0.0-rc.2` 生产的对照回归**。
语义正确性仍未人工评分；本文件不宣称准确率。

产物：

- [`data/evaluation/kb2-benchmark-100-v1.json`](../../data/evaluation/kb2-benchmark-100-v1.json)：100 题统一清单。
- [`data/evaluation/validity-pilot-v3.json`](../../data/evaluation/validity-pilot-v3.json)：旧 50 题修订版（只改题干范围，答案不变）。
- 生成脚本：[`scripts/build_benchmark_100.py`](../../scripts/build_benchmark_100.py)（确定性，可重跑）。

## 1. 组成

| 来源 | 题数 | 验证级别 | 用途 |
| --- | ---: | --- | --- |
| `validity-pilot-v3`（旧 50） | 50 | `evidence_machine_verified` | 与 2026-10-30 线上运行保持可比 |
| `cable-lookup-v1`（线缆 20） | 20 | `gold_rows_machine_verified` | 结构化行查找与端口/跨表题 |
| `kb2-question-plan-v1`（已验证子集） | 30 | `verified_from_extracted_text` | 新批次事实、版本比较、边界与表格证据 |
| **合计** | **100** | | |

分布：`answered` 89、`partial` 5、`insufficient` 6；`regression` 50、`dev` 40、`sealed` 10。
分组：旧集 50（pdf_control 10、conditions 15、versions 10、diagnosis 10、limits 5）；
线缆 20；KB2 30（new_facts 12、version 11、conflict_boundary 5、format 2）。
ID 与规范化题干均无重复。

## 2. 核验发现的问题

### 2.1 旧 50 题（`validity-pilot-v2`）

| 问题 | 涉及题号 | 处理 |
| --- | --- | --- |
| 题干未要求、但 `must_cover` 要求的事实，评分口径歧义 | P50-004、012、027、030、039、042、043、045 | 按 `rubric-adjudication.md` §1 在题干末尾补充要求；`gold_answer`、`must_cover`、`forbidden_claims`、证据组原样保留 |
| 严格比较符表达 | P50-005 | 保留，运行后单列复核“小于 10 µs / 小于 100 µs”是否被展开为 ≤ |
| 条件代入 | P50-017 | 保留；该题在 rc.2 上返回 502，作为既有服务缺陷记录，不计为 rc.3 新增失败 |
| “未知”与“不存在”混同 | P50-050 | 保留，按 `rubric-adjudication.md` §2 分开记录“目标事实可回答性”与“展示内容范围” |

未修改任何答案或清单，避免事后提分；v3 只增加题干范围，并写入 `amended_ids`。

### 2.2 新 60 题草案（`kb2-question-plan-v1`）

| 问题 | 数量 | 处理 |
| --- | ---: | --- |
| `needs_source_check`：依赖 PPTX/XLSX/OCR/公式解析，冻结前须人工核对 | 13 | 不纳入 100 题 |
| `derived_from_analysis`：来自二手分析，未回原文核对 | 8 | 不纳入 100 题 |
| 依赖 `access_scope=restricted` 的《网络安全设计报告》 | 2（KB2-FMT-015、KB2-BND-001） | 不纳入；不放宽默认检索范围 |
| `verified_from_extracted_text` | 39 | 选 30（20 dev + 10 sealed），其余 9 题列为 reserve |

Reserve：`KB2-FACT-006/007/008/010/012/014`、`KB2-VER-011`、`KB2-BND-005/009`。
这些题本身可用，只是为保持 100 题的分组比例未纳入；后续可单独启用。

选题规则：覆盖全部已验证分组；优先保留版本比较与边界题（研究主线），
事实题按文档族分散（定时、恒温机柜、激光、真空、PDU、存档）。

### 2.3 线缆 20 题（`cable-lookup-v1`）

- 17 题有金标准行，3 题为负例/版本边界题（`CAB-NEG-001/002`、`CAB-BND-002`），
  没有 `required_values` 是设计如此，判定靠 `forbidden_claims` 与状态。
- 金标准行由独立 `openpyxl` 读取原件生成，但题目与查找代码同一作者，仍属开发集。

### 2.4 默认检索范围与题目范围不一致（已修复）

首次 rc.3 候选运行暴露了一个题集设计错误：30 道 KB2 题大多点名历史归档或待核实版本
（`usage_status=historical/pending_review`），而服务默认检索范围只包含
`current` 与 `reference`。这些题在默认范围下必然回答“没有依据”，测到的是范围拒答，
不是问答能力。首轮 30 题中 27 题 `requirements_supported=0`，属于测量伪失败。

修复：

- 按 `registry-v2.json` 的 `source_path` 把每题映射到具体 `revision_id`；
  版本比较题映射两到三个修订。
- 100 题 JSON 中每道 KB2 题增加 `scope: {"mode": "version", "revision_ids": [...]}`；
  `scripts/kb2_run_regression.py` 在请求体中透传该字段（只含文档身份，不含标签或答案）。
- 30/30 题均完成映射，修订 ID 均存在于注册表；新增测试锁定该约束。
- 旧 50 题与线缆 20 题使用默认范围，不受影响。

### 2.5 来源抽查

对选入的 30 道 KB2 题逐题定位 `candidate_source`，在
`reports/incoming-2026-11-02/tmp/doc-txt/` 的 15 份提取文本中核对：

- 30/30 找到对应原文文件；
- 备注中的整段引文有 9 条因用“……”拼接而不连续，按关键短语逐条核对均可命中；
- 未发现整题原文缺失或数值与原文相反的情况。

这不是人工语义评分；原文与答案边界是否完全一致仍需业务复核。

## 3. 本轮结果（2026-11-05 / 06）

构建：222/222 条公开修订解析成功，0 失败、0 待 OCR；10,793 父块、10,654 可索引父块；
6,989 条行记录全部指向包含该行的父块（0 错位）；3,086 个媒体文件（631 MB）；102 个族。

索引：E5 13,766 points，Qwen3 10,654 points；两路 `parent_*` 哈希一致。

| 指标（100 题） | rc.2 生产 | rc.3 候选 |
| --- | ---: | ---: |
| HTTP 成功 | 98/100 | 97/100 |
| answered / partial / insufficient | 69 / 13 / 16 | 75 / 18 / 4 |
| 旧 50 题状态匹配 | 42/50 | 41/50 |
| 线缆 20 题状态匹配 | 3/20 | 16/20 |
| KB2 30 题状态匹配（scoped） | 24/30 | 17/30 |
| P50（全部） | 24.7 s | 24.7 s |
| P95（全部） | 57.3 s | 84.2 s |

- 线缆能力：结构化查找 best-hit 17/17，`status_ok` 15/19、`values_ok` 15/19、
  `forbidden_ok` 19/19、`citation_row_ok` 14/16。
- 单并发定向探针（10 道旧题）：rc.3 10/10 成功、总耗时 188.7 s；rc.2 9/10、179.4 s，
  约 +5%；并发 3 时 rc.3 的 P95 尾部明显变长，属于排队/负载放大。
- 定向 scoped 30 题（单并发）：rc.3 29/30，P50 11.0 s、P95 27.0 s；
  rc.2 30/30，P50 8.9 s、P95 20.0 s。
- 502 均为 `INVALID_GROUNDED_ANSWER`（模型结构化输出两次未通过）；同样题目重试或
  单独运行可恢复，不是确定性代码错误。rc.3 3/100、rc.2 2/100，量级相同。
- KB2 由 answered 转 partial 的题主要来自 rc.3 新增的冲突/未复核 OCR 值判定：宁可
  标“部分支持”也不再替未核实数值背书。没有人工语义评分，不能把该变化称为准确率提升或下降。
- 本轮运行文件还没有把旧 50 题的证据组保留为 `evidence_groups`，所以
  `comparison.md` 的“引用命中父块”列为 0/0；该字段已在本轮结束前修复，下一次运行可恢复。
  本轮引用质量只按引用条数（rc.3 129、rc.2 144）和空引用数（24、17）作旁证，未用于决策。

结论：rc.3 已切换到 8003，`kb-2.0.0-rc.2` 保留为唯一回滚版本；回滚演练已实际执行。
人工语义评分与 K7 观察期仍未完成。

## 4. 运行方式

```bash
# 100 题问答回归（工程指标：HTTP 成功、状态、引用覆盖）
python scripts/kb2_run_regression.py \
  --questions data/evaluation/kb2-benchmark-100-v1.json \
  --base-url http://127.0.0.1:8013 \
  --output reports/benchmark-100-20261105/rc3-candidate.json

# 只重跑带 version scope 的 30 题，并把结果合并回 100 题报告
python scripts/kb2_run_regression.py \
  --questions data/evaluation/kb2-benchmark-30-scoped.json \
  --base-url http://127.0.0.1:8013 \
  --output reports/benchmark-100-20261105/rc3-candidate-scoped30.json
python scripts/merge_benchmark_runs.py \
  --base reports/benchmark-100-20261105/rc3-candidate.json \
  --override reports/benchmark-100-20261105/rc3-candidate-scoped30.json \
  --output reports/benchmark-100-20261105/rc3-candidate-final.json

# 线缆 20 题的结构化查找检查（可单独跑）
python scripts/run_cable_benchmark.py \
  --base-url http://127.0.0.1:8013 \
  --output reports/benchmark-100-20261105/rc3-cable-lookup.json
```

## 5. 不得宣称的事项

- 100 题没有独立人工语义评分；自动检查只覆盖状态、引用与必需值出现与否。
- 旧 50 题与线缆 20 题都不是独立测试集；KB2 30 题来自同一批资料的开发性阅读。
- `sealed` 10 题只表示此前未用于调参，不等于外部盲测。
- 本集不覆盖受限资料，也不能据此评价受限文档的问答质量。
