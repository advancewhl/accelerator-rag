# 300 题基准划分与组装统计（W6 交付，最终封存版）

日期：2026-11-08（v2 重建）
数据版本：`kb-2.0.0-rc.3`（222 修订 / 10,793 父块）
划分政策：`docs/research/benchmark-300/split-policy.json`（`benchmark-300-split-policy-v4`）
规范：`docs/research/benchmark-300/SPEC.md`
组装输入（v1）：`data/evaluation/research-benchmark-300-v1/sealed-test/_work/w5-gold-interventions.jsonl`
组装命令（v1）：`python3 scripts/research/assemble_benchmark.py --out data/evaluation/research-benchmark-300-v1 data/evaluation/research-benchmark-300-v1/sealed-test/_work/w5-gold-interventions.jsonl`

v2 重建输入：`reports/phase4/audit/benchmark-v2/new-questions-dev-val.json` 与 `sealed-test/_work/v2-new-test-questions.json`；生成与修补脚本在 `sealed-test/_work/v2-build-s1.py`、`v2-fix-review-blocking.py` 与 `reports/phase4/audit/benchmark-v2/build_v2_s3.py`。

本文件只记录统计与核验结论，不含题干、答案、证据摘录或 sealed-test 内容。除特别标注外，统计数字取自同目录 `stats.json`。2026-11-08 的 v2「组合必需」重建见第 11 节；第 1、4—7 节已按 v2 重算，第 2、3、8 节不变，第 9、10 节保留为 v1 审计历史。2026-11-08 的 v2「组合必需」重建见第 11 节；第 1、4—7 节已按 v2 重算，第 2、3、8 节不变，第 9、10 节保留为 v1 审计历史。

## 1. 交付文件、封存与完整性

| 文件 | 题数 | 权限 | sha256 |
| --- | ---: | --- | --- |
| `dev/questions.json` | 100 | 644 | `42bbe002e0d962a1f9c22e56d2220eba736324e8d212d548d3d9f9e1e633163a` |
| `val/questions.json` | 50 | 644 | `dcedc7e2062d4243edca61e177a8844411c8fdf36c0c5d07f45351894c121c6e` |
| `sealed-test/questions.json` | 150 | 600 | `cf0e8d2f6c9654dec923ad6622e4117a5153fccbc560c6219c4b620ace3ce59a` |
| `sealed-test/SEALED.md` | — | 664（位于 700 目录内） | 内含 questions.json 的 SHA-256，与上表一致 |
| `manifest.json` / `stats.json` | — | 664 | — |

封存目录 `data/evaluation/research-benchmark-300-v1/sealed-test/_work/`（权限 700，文件 600）保存全部含 test 内容的输入与报告：

- `w2-scenario1.jsonl`、`w3-scenario2.jsonl`、`w4-scenario3.jsonl`、`w5-gold-interventions.jsonl`
- `w5-report.md`、`template-families.json`
- `s3-pairing-inventory.md`（含 test 题号，已从 `docs/research/benchmark-300/` 移入）
- v2：`v2-new-test-questions.json`、`v2-review-test.md`、`v2-answerability-test.md`、`v2-answerability-classifications-test.json`、`v2-build-s1.py`、`v2-fix-review-blocking.py`
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
| S1 | `set_enumeration` | 41 |
| S1 | `negative_boundary` | 2 |
| S1 | `cross_table_join` | 57 |
| S2 | `version_same` | 56 |
| S2 | `version_added` | 20 |
| S2 | `version_diff` | 14 |
| S2 | `version_boundary` | 7 |
| S2 | `version_removed` | 3 |
| S3 | `verdict_check` | 27 |
| S3 | `requirement_test_match` | 23 |
| S3 | `scope_mismatch` | 21 |
| S3 | `design_test_conflict` | 15 |
| S3 | `acceptance_gap` | 14 |

## 5. verdict_class 与 gold status

| verdict_class | 题数 |
| --- | ---: |
| `deterministic` | 209 |
| `rubric` | 56 |
| `human` | 35 |

| gold.status | 题数 |
| --- | ---: |
| `answered` | 249 |
| `partial` | 32 |
| `insufficient` | 19 |

## 6. 干预操作分布

共 600 条干预：`should_change` 300 条、`should_hold` 300 条；300 道题均为每题 1 条 `should_change` + 1 条 `should_hold`。

| pair_role | operation | 条数 |
| --- | --- | ---: |
| `should_hold` | `add_irrelevant_similar` | 27 |
| `should_change` | `change_unit` | 1 |
| `should_change` | `change_value` | 206 |
| `should_hold` | `convert_unit` | 11 |
| `should_change` | `delete_condition` | 33 |
| `should_change` | `delete_row` | 34 |
| `should_hold` | `paraphrase_query` | 208 |
| `should_change` | `remove_link_edge` | 11 |
| `should_hold` | `reorder_paragraphs` | 11 |
| `should_change` | `replace_revision` | 4 |
| `should_change` | `substitute_design_for_test` | 10 |
| `should_change` | `swap_adjacent_ports` | 1 |
| `should_hold` | `translate_query` | 43 |

## 7. 证据覆盖

- 被引用 evidence chunk：577 个。
- 被引用修订：75 个。
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

- 2026-11-08：应用专家代理复核的 5 条补丁（含 1 条题干重写），三份 questions.json 哈希已更新，见 manifest.patches。

## 11. v2 重建（2026-11-08，组合必需）

按 `docs/research/phase4-redesign-20261108.md` 决定 A 重建：

- **移出**：dev 21（18 道 S1 单源 + 3 道 S3 单修订 verdict_check）、val 7（S1 单源）、test 34（23 exact_record + 8 negative_boundary + 3 单 chunk 的 cross_table_join）。
- **补入**：dev 21、val 7、test 34；新题均为组合必需（S1 跨表连接，test 另有完备集合枚举，S3 要求—测试配对）。
- **可答上限**：dev 100/100=1.000、val 50/50=1.000、test 150/150=1.000（严格 grounded 分别为 98/46/144，其余为逐题记录的负向/派生断言）。明细：`reports/phase4/audit/benchmark-v2/answerability-v2.md`。
- **组合审计**：`reports/phase4/audit/benchmark-v2/composition-audit.md`；test 组合审计：`test-composition-audit.md`。
- **移出/补入记录**：`reports/phase4/audit/benchmark-v2/removed-added.md`。
- **新题来源与复核**：`new-questions-dev-val.json`、`sealed-test/_work/v2-new-test-questions.json`、`review-new-questions.md`（test 逐题复核在 `sealed-test/_work/v2-review-test.md`）。
- **校验**：`validate_benchmark.py` 对 300 题报 0 errors / 0 warnings。
- **封存**：v1 sealed sha `dc7a8cf9c251f46a2e7e75cb298f3df615235f1c3e3286a982dc814d54985028` 标记 `invalidated-by-benchmark-v2`；v2 sealed sha 见第 1 节与 `sealed-test/SEALED.md`。`docs/research/phase4/freeze.json`、`OPENED.json` 仍是 v1 记录，v2 打开前必须重新 freeze。
- **口径变化**：单源 `exact_record` 题已全部移出（v1 的 40 道 exact_record 全为单源），因此 task_type 分布不再与 v1 相同；这不是缺口，而是决定 A 的直接结果。场景计数 100/50/150 与三场景各 100 不变。

- **2026-11-08 追加**：移除 dev `S1-DEV-027`/`S1-DEV-030` 的内部表标签 D2/D3/D4（全库 0 命中），改用元数据中的确切文档标题；保留 E 范围、预留段与前缀语义，顶层镜像同步。记录：`reports/phase4/audit/benchmark-v2/patch-internal-labels.md`；dev sha 更新为第 1 节所示。
