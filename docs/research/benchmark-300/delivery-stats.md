# 300 题基准划分与组装统计（W6 交付，最终封存版）

日期：2026-11-07
数据版本：`kb-2.0.0-rc.3`（222 修订 / 10,793 父块）
划分政策：`docs/research/benchmark-300/split-policy.json`（`benchmark-300-split-policy-v4`）
规范：`docs/research/benchmark-300/SPEC.md`
组装输入：`data/evaluation/research-benchmark-300-v1/sealed-test/_work/w5-gold-interventions.jsonl`
组装命令：`python3 scripts/research/assemble_benchmark.py --out data/evaluation/research-benchmark-300-v1 data/evaluation/research-benchmark-300-v1/sealed-test/_work/w5-gold-interventions.jsonl`

本文件只记录统计与核验结论，不含题干、答案、证据摘录或 sealed-test 内容。除特别标注外，统计数字取自同目录 `stats.json`。

## 1. 交付文件、封存与完整性

| 文件 | 题数 | 权限 | sha256 |
| --- | ---: | --- | --- |
| `dev/questions.json` | 100 | 664 | `88e12e4e73888106a15c9b581461512614b80deb9d9d37e2f667228c1e25c524` |
| `val/questions.json` | 50 | 664 | `62c2db1711da5318cedde5934c4bfa07a76c9f7a85efdd6651983b855d08b782` |
| `sealed-test/questions.json` | 150 | 600 | `70359808fb7bc2d8fce8bb653dda4fd5e32b87746a4c2fd3d4ca53c937e361ca` |
| `sealed-test/SEALED.md` | — | 664（位于 700 目录内） | 内含 questions.json 的 SHA-256，与上表一致 |
| `manifest.json` / `stats.json` | — | 664 | — |

封存目录 `data/evaluation/research-benchmark-300-v1/sealed-test/_work/`（权限 700，文件 600）保存全部含 test 内容的输入与报告：

- `w2-scenario1.jsonl`、`w3-scenario2.jsonl`、`w4-scenario3.jsonl`、`w5-gold-interventions.jsonl`
- `w5-report.md`、`template-families.json`
- `s3-pairing-inventory.md`（含 test 题号，已从 `docs/research/benchmark-300/` 移入）
- `tmp-w2/`（含 test 题号的 W2 临时生成脚本）

`data/evaluation/research-benchmark-300-v1/` 根目录已不保留上述文件的副本。

封存字段核验：

- `manifest.json` 的 `source_files` 指向 `sealed-test/_work/w5-gold-interventions.jsonl`，sha256 `c8f9e34f2ea0d692be347fb0a585d1f6d72a138063243541bed1fb902016d710`。
- `manifest.json` 顶层 `sealed=true`，`sealing_policy` 存在（目录 700、文件 600、R1—R5 审核期可读、阶段四显式放行开关、源文件位于 `_work/`）。
- `sealed-test/questions.json` 的 SHA-256 与 `SEALED.md`、`manifest.json` 三处一致。
- `manifest.json` 记录的 SPEC sha256（`cbabdcf05e39a9e6bd327ece27ec22eaaf5e240c927752a6622c1f693ff2446f`）、policy sha256（`2d06fc5ee1d4ef8048cfc86347cd9a8539da17d32c196257550829f1ad463758`）与磁盘文件一致；语料 digest 与 `tmp/research-rc3/inventory/corpus-digest.json` 一致。
- `stats.json` 与从三份题目文件重算的统计逐字段一致，`manifest.stats` 与 `stats.json` 一致。

## 2. 题目数量（三类 × 三划分）

| 场景 | dev | val | test | 合计 |
| --- | ---: | ---: | ---: | ---: |
| `s1_connectivity` | 34 | 16 | 50 | 100 |
| `s2_revision` | 33 | 17 | 50 | 100 |
| `s3_verification` | 33 | 17 | 50 | 100 |
| 合计 | 100 | 50 | 150 | 300 |

## 3. Cluster 配额核验

18 个 cluster 的实际题数全部等于 `split-policy.json` v4 配额（精确命中，无不足或超出）。

| Cluster | 划分 | 实际/配额 |
| --- | --- | ---: |
| `S1-DEV-L3L4` | dev | 34/34 |
| `S1-VAL-L2` | val | 16/16 |
| `S1-TEST-WOBDUAN` | test | 50/50 |
| `S2-DEV-TIMING` | dev | 10/10 |
| `S2-DEV-VACUUM` | dev | 13/13 |
| `S2-DEV-CONSTTEMP` | dev | 10/10 |
| `S2-VAL-INTERLOCK` | val | 10/10 |
| `S2-VAL-ARCHIVE-QUERY` | val | 7/7 |
| `S2-TEST-POWER-SUPPLY` | test | 20/20 |
| `S2-TEST-POWER-SOURCE` | test | 12/12 |
| `S2-TEST-TEMPHUM` | test | 8/8 |
| `S2-TEST-FOURDOF` | test | 6/6 |
| `S2-TEST-COLLIMATOR` | test | 4/4 |
| `S3-DEV-CONSTTEMP` | dev | 15/15 |
| `S3-DEV-VACUUM` | dev | 18/18 |
| `S3-VAL-FASTINTERLOCK` | val | 17/17 |
| `S3-TEST-HIFRAME` | test | 25/25 |
| `S3-TEST-DEVENV` | test | 25/25 |

## 4. task_type 分布

| 场景 | task_type | 题数 |
| --- | --- | ---: |
| S1 | `exact_record` | 40 |
| S1 | `set_enumeration` | 21 |
| S1 | `negative_boundary` | 18 |
| S1 | `cross_table_join` | 21 |
| S2 | `version_same` | 56 |
| S2 | `version_added` | 20 |
| S2 | `version_diff` | 14 |
| S2 | `version_boundary` | 7 |
| S2 | `version_removed` | 3 |
| S3 | `verdict_check` | 29 |
| S3 | `requirement_test_match` | 23 |
| S3 | `scope_mismatch` | 19 |
| S3 | `design_test_conflict` | 15 |
| S3 | `acceptance_gap` | 14 |

## 5. verdict_class 与 gold status

| verdict_class | 题数 |
| --- | ---: |
| `deterministic` | 207 |
| `rubric` | 56 |
| `human` | 37 |

| gold.status | 题数 |
| --- | ---: |
| `answered` | 247 |
| `partial` | 34 |
| `insufficient` | 19 |

## 6. 干预操作分布

共 600 条干预：`should_change` 300 条、`should_hold` 300 条；300 道题均为每题 1 条 `should_change` + 1 条 `should_hold`。

| pair_role | operation | 条数 |
| --- | --- | ---: |
| `should_change` | `change_value` | 191 |
| `should_change` | `delete_row` | 46 |
| `should_change` | `delete_condition` | 33 |
| `should_change` | `remove_link_edge` | 13 |
| `should_change` | `substitute_design_for_test` | 9 |
| `should_change` | `replace_revision` | 4 |
| `should_change` | `swap_adjacent_ports` | 3 |
| `should_change` | `change_unit` | 1 |
| `should_hold` | `paraphrase_query` | 207 |
| `should_hold` | `translate_query` | 43 |
| `should_hold` | `add_irrelevant_similar` | 27 |
| `should_hold` | `convert_unit` | 12 |
| `should_hold` | `reorder_paragraphs` | 11 |

## 7. 证据覆盖

- 被引用 evidence chunk：436 个。
- 被引用修订：74 个。
- 被引用文档族：27 个。

## 8. 30 道显式修订范围题

| 划分 | 题数 |
| --- | ---: |
| dev | 10 |
| val | 10 |
| test | 10 |
| 合计 | 30 |

- 30 道全部为 `s2_revision`，`scope.mode=explicit_revisions`。
- 28 道列出 2 个比较修订，2 道列出 3 个比较修订；全部修订 ID 存在于 rc.3 登记表且属于该题 `family_ids` 对应族（审计结果）。

## 9. 隔离核验结论

审计输入为封存后的 `sealed-test/_work/w5-gold-interventions.jsonl`（sha256 `c8f9e34f…`）。方向性检查（dev/val → test、test → dev/val）与三个层面的跨划分检查均通过：

- **族/簇隔离**：dev/val/test 两两之间的 `family_ids`、`cluster_id` 交集均为 0；test 题只使用 test cluster 的族，dev/val 同理。
- **Chunk 隔离**：三划分两两之间无共享 `evidence_minimal` chunk；无共享 intervention `target_chunk_ids`。
- **修订序列隔离**：evidence 修订与 `scope.revision_ids` 在三划分两两之间均无重复；30 道显式范围题的修订列表不跨划分。
- **连接链/对象锚点**：S1 电缆编号、机柜 token（含 `UN-`/`LA-` 前缀归一）、终端 token（含 `UN-`/`LA-` 前缀归一）在三划分两两之间交集均为 0；dev/val 的题干、答案、证据与干预文本中未出现任何 test 机柜 token；test 题目文本中未出现任何 dev/val 机柜 token。
- **更深的 chunk 文本检查**：dev/val 引用的 evidence chunk 全文中未出现 test 机柜 token；test 引用的 chunk 全文中未出现带 `-CN` 后缀的 dev/val 机柜 token。
- **曝光清单反向检查**：test 题中 `exposed_cabinets`（完整 token，含前缀归一）、`exposed_manual_families`、fast-interlock 族及其名称短语命中数均为 0。
- **旧 100 题曝光复核**：test 与旧 100 题的 evidence chunk、电缆编号、机柜 token、设备 token 交集均为 0；旧派生文件中已移除的曝光设备名不再出现在新 questions.json。
- **保留族/受限修订**：reserve 族使用 0；restricted 修订在 evidence、干预目标与显式范围中引用 0。
- **内容保真**：组装后的 300 条与封存 W5 源文件逐字段一致，仅新增 5 个兼容别名（`id`、`expected_status`、`gold_answer`、`required_facts`、`forbidden_claims`）；无题目增删、无题干/答案/证据/干预内容修改；每题 `base_id` 唯一，文件按 `base_id` 升序。
- **封存残留**：`tmp/` 与 `dev/`、`val/` 中 test 题号命中数为 0；`sealed-test/` 之外的全仓库（排除 `.git`）test 题号命中数为 0。含 test 题号的文档 `s3-pairing-inventory.md` 已移入 `_work/`。
- **结构校验**：封存 W5 文件 `validate_benchmark.py` 为 `0 errors, 0 warnings`，EXIT 0。
- **仓库只读审计**（`scripts/research/audit_benchmark.py`）：blocking 0；major 180（`evidence_excerpt_reuse` 94、`shared_object_anchor` 83、`near_duplicate_query` 3），全部发生在同一划分内部；建议级 443。

### 非阻断观察（移交 R3/R1 判定）

- 3 条 `required_facts` 语句与 1 条 excerpt 文本在不同划分间重复，均为无对象锚点的通用措辞/表头（归档副本说明、验收意见栏），不构成共享 evidence chunk 或共享要求—测试对。
- 设备用途词（恒温机柜、真空、准直器、电源控制、功率源、激光、联锁等）作为 S1 线缆/配置表的用途标签或手册正文用语跨划分出现，但对应机柜、电缆、终端、族、chunk 与修订均无交集；`subsystem_alignment` 是否需进一步收紧由 R3 判定。
- test evidence chunk 全文中有 4 处大写 `EMIT` 字样，均为表格残片，无 `-CN` 后缀，不构成对 dev/val 对象簇的引用。
- 3 对近重复问法（`near_duplicate_query`）均在 test 内部，即 W5 报告已列出的模板孪生对；R1 复审判定为独立（不同信号行/参数行/要求—测试对），已登记在 `template-families.json`。

## 10. 封存清理记录

- 本轮（末次）从 `_work` 新 W5（sha256 `c8f9e34f…`）重新生成三份 `questions.json`，替换 20:16 旧派生文件；W2 提示的已移除曝光设备名不再存在（test 与旧 100 题的设备 token 交集为 0）。
- `sealed-test/_work/` 创建时权限 700，全部文件 chmod 600；`sealed-test/` 700，`sealed-test/questions.json` 600。
- `tmp/research-rc3/w2/` 中 6 个含 test 题号的临时脚本（`gen.py`、`t1.py`—`t5.py`）已移入 `sealed-test/_work/tmp-w2/`（700/600）；W2 派生的线缆行临时文件 `rows.json`（含 test 机柜行）也已移入并 chmod 600。
- 语料快照 `tmp/research-rc3/{index,chunks,parsed}` 按规范保留为只读语料，不属于 test 题内容；`tmp/` 非语料文件中的 test 题号与 test 机柜行命中数均为 0。
- `docs/research/benchmark-300/s3-pairing-inventory.md` 已移入 `_work/`；`README.md` 与 `paper-data-section.md` 对该文件的引用现指向封存路径，需协调者决定是否在 docs 保留公开索引说明。
- W5 报告已同步为 split-policy v4（配额按 v3 生成，v4 仅增加 `test_isolation_definition` 与 `prior_exposure.identity_mapping`，配额不变）。
