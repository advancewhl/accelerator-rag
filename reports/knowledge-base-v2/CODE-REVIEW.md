# CODE-REVIEW：kb-2.0.0 K1–K4 当前工作树

审查日期：2026-11-02（约 14:25 快照）
范围：`whloong/rag-prab-constraint-grounded` worktree；K1–K4 新增/修改代码与生成物
方式：只读审查；除本报告外未修改文件、未提交 git、未运行全批解析或长测试。审查期间其他代理仍在改文件，行号以本快照为准。

## 结论

- **P0：1 项**（受限资料可进入候选索引/目录/下载接口）
- **P1：6 项**（引用位置错误、表格行标签、发布清单校验、构建清单范围、release_id、冲突台账）
- **P2：7 项**（状态校验缺口、处置交叉校验、序列化校验、构建报告残留、跨位置类型/同页补全、TOC 误删、混合 PDF OCR）

最严重的 5 条：

1. **P0**：`access_scope=restricted` 没有在建索引/目录/下载层生效；当前 batch 有 3 份受限资料且都是 `text_index`，其中 1 份是 PDF。受限 PDF 一旦 OCR 并按当前流水线入索引，`/v1/rag/documents/{id}` 会直接返回全文。
2. **P1**：DOCX/PPTX/XLSX 引用被统一标成 `locator_kind=page`，`page_start` 实际是段落号/幻灯片号/表序号；模型和 UI 都会显示成“物理页”，阅读器也按 PDF 打开。
3. **P1**：`_table_chunk_label` 的起始行修复只对连续行有效；真实端子表存在空行（`温控柜` 有 22 处空行间隔），分块标签在第一个空行后开始逐行漂移。
4. **P1**：发布清单校验器对 `accepted/live` 仍接受 `created_at`/`git_commit`/回滚目标/索引路径占位符和 0 语料；我已用模板复现 `errors=[]`。
5. **P1**：候选构建清单的 `revision_count` 取自完整注册表，而不是本次选中范围；`--allow-missing-source`、失败/待 OCR 明细和选中修订数没有进入清单，校验器也不交叉核对。

---

## P0

### P0-1 受限资料不受 `access_scope` 门控，可进入目录和下载接口

**文件/位置**

- `scripts/kb2_candidate_build.py:104-120`：`selected_revisions()` 只按 `disposition` 选择，未排除 `access_scope=restricted`。
- `scripts/kb2_candidate_build.py:303-318`：`indexable_chunk_ids` 直接来自 `eligible` + 长度过滤，未按访问范围筛选。
- `src/accelerator_rag/rag/runtime.py:126-138`：运行时把索引中所有位于 `source_root` 下的 `.pdf`/`.md` 加入 `self.documents` 和 `DocumentCatalog`，没有 access 检查。
- `src/accelerator_rag/rag/catalog.py:58-92`、`155-163`：目录收录全部 chunk，`document_url` 对存在的原文无条件生成。
- `src/accelerator_rag/rag/api.py:174-184`（`GET /v1/rag/documents`）、`186-204`（`/view`）、`206-218`（`/sections`）、`221-238`（原文下载）均没有 `access_scope` 检查。
- 证据数据：`data/documents/v2/registry-v2.json` 中 3 条 `restricted`，均为 `text_index`：
  - `network-configuration-snapshot-de63544f-rev`（PDF，`pending_ocr`，OCR 完成后可入索引）
  - `cybersecurity-subsystem-design-06ac7820-rev`（DOCX）
  - `shine-data-storage-and-archive-rev-a7be1e00`（DOCX）
- `reports/knowledge-base-v2/K1-governance-merge.md:45` 和 `data/documents/v2/README.md:42` 明确要求受限资料“不进入公共目录、搜索片段、下载接口或回答日志”；计划 §9.3 同义。

**可复现状态**

- 当前 r2 预跑中两份受限 DOCX 已切块，分别有 9/337 个 `indexable_chunk_ids`；受限 PDF 因无文本层暂未切块，但 OCR 是 K4 上线前置。
- 用当前 `kb2_candidate_build.py` 选择全部 `text_index` 修订时，受限资料不会被排除；只要索引构建使用这些 `indexable_chunk_ids`，运行时 `catalog.add()` 就会收录它们，`/v1/rag/documents/{id}` 会对 PDF 返回全文。

**后果**

默认检索路径（BM25/dense/rerank）确实通过 `RetrievalScope` 排除了 `restricted`；但目录、原文阅读/下载接口和 release 计数没有。若按当前流水线构建候选并上线，构成权限泄露。

**建议修复**

1. 建索引前按 `AccessScope.RESTRICTED` 排除，或为受限资料建立独立 collection/发布区。
2. `DocumentCatalog.add/snapshot`、`/documents`、`/documents/{id}`、`/view`、`/sections` 统一检查访问范围；不可只依赖检索 scope。
3. 增加端到端测试：受限 PDF/MD 入索引后，目录、下载、view、answer 日志均不可见。

**置信度**：高（代码路径明确）；实际泄露取决于是否构建含受限资料的候选索引，当前 K4 尚未建索引。

---

## P1

### P1-1 新格式引用的位置类型被误标为“物理页”

**文件/位置**

- `src/accelerator_rag/rag/context.py:69-80`：`locator_kind` 仅按后缀判断，`.md/.markdown` 为 `section`，其余一律 `page`。
- `src/accelerator_rag/rag/answer.py:1024-1029`：同样逻辑，把 DOCX/PPTX/XLSX 全部标成 `page`。
- `src/accelerator_rag/rag/web/app.js:46,108,113,186`：UI 只区分 `section` 与“物理页”，其余都显示 `物理页 ${page_start}`。
- `src/accelerator_rag/rag/web/pdf-reader.js:56-98`：非 Markdown 一律按 PDF 用 `getDocument({url})` 打开，并 `page = page_start`。
- 新格式实际位置契约见 `src/accelerator_rag/corpus/chunking_v2.py:343-373`：DOCX 段落/表格为 `paragraph`，PPTX 为 `slide`，XLSX/CSV 为 `cell_range`。

**可复现状态**

- DOCX 段落 chunk：`position_kind=paragraph`、`position_label=paragraph-123`、`page_start=123`；citation/context 输出 `locator_kind=page`、UI 显示“物理页 123”。
- PPTX 幻灯片 chunk：`page_start=8`，UI 显示“物理页 8”。
- XLSX 表格 chunk：`page_start=1`（表序号），`position_label=Sheet!A2:K14`；UI 显示“物理页 1”。
- `document_url` 对 DOCX/PPTX/XLSX 也指向 `/v1/rag/documents/{id}`，但 `RagRuntime.documents` 只收录 PDF/MD，端点返回 404；`/view` 对非 PDF/MD 返回 501。`openReader` 仍会尝试按 PDF 加载。

**后果**

模型看到的来源位置是错误类型，可能把 DOCX 第 123 段写成“第 123 页”、把 PPTX 第 8 页/表格第 1 表写成物理页；UI 的引用定位和“阅读原文”对新格式不可用。违反计划 §8.3、§9.1 的“引用可定位到 PDF 页、Markdown 章节、DOCX 段落、PPT 幻灯片或表格单元格”。

**建议修复**

- 从 `KnowledgeChunk.position_kind` / `position_label` 生成 citation 和 context，不要按文件后缀推断；对 `cell_range` 使用 `position_label`。
- UI 按 `position_kind` 选择文案；DOCX/PPTX/XLSX 使用对应阅读副本/定位器；在阅读器未实现前显式禁用“阅读原文”，不要按 PDF 打开。
- 评估/题集（`src/accelerator_rag/evaluation/validity.py` 的 `Literal["page","section"]`）也要扩展位置类型。

**置信度**：高。

### P1-2 表格分块行标签在有空行的真实工作表中错误

**文件/位置**

- `src/accelerator_rag/corpus/structured_parser.py:169-225`、`255-266`：按非空行压缩保存 `rows`，只保留 `row_numbers[0]`/`row_numbers[-1]` 作为范围；`TableData` 不保存每行对应的物理行号。
- `src/accelerator_rag/corpus/chunking_v2.py:149-198`：`first/last` 是压缩后表格行序号。
- `src/accelerator_rag/corpus/chunking_v2.py:207-234`：`_table_chunk_label` 已正确使用 `block.position.start` 作为起始行（这部分已修复），但仍假设表格行连续。

**可复现状态**

实际文件 `data/l0_raw/incoming/2026-11-02-shine-control/资料/3 样机验收/陈广花补充材料/端子对应表最终版3.8现场改造.xlsx`：

- `主控柜 (调整)`：解析块 `A2:K319`、`rows=316`；工作簿非空行 317（含标题行），中间有 `280-281` 两行空行。
- `温控柜`：解析块 `A2:K561`、`rows=538`；共有 22 处空行间隔（例如 `26-28, 52-54, ...`）。

由于压缩后的行号与物理行号不同，第一个空行后的 chunk 标签会按“压缩序号 + base_start”偏移，最多累计 22 行；`_table_chunk_label` 的 `A2:K2;A3:K...` 形式看似精确，实际指向错误行。K2 报告中的 `主控柜 (调整)!A1:K1;A2:K14` 类标签在修复前/后都需重新按真实行核对。

**后果**

端子表等结构化证据的引用定位到错误行，可能把相邻端子/信号行当成同一记录；违反计划 §7.4 的“检索返回完整记录和单元格定位，避免把不同版本的相邻行拼在一起”。

**建议修复**

- `TableData` 增加每行物理行号（或 `row_locations`），`_table_pieces` 返回真实起止行；不要从压缩后的 ordinal 推算。
- `_cell_range_position` 的范围也应能表达非连续行，或至少把空行位置保留在定位信息中。
- 为带空行的 XLSX 增加回归测试（断言每个 piece 的 `position_label` 与工作簿实际行一致）。

**置信度**：高（代码与工作簿行分布均已核对）。

### P1-3 发布清单校验器接受占位符/空语料的 `accepted` 清单

**文件/位置**

- `scripts/validate_release_manifest.py:78-101`：`build_id`/`git_commit` 以 `<` 开头只在 `candidate-incomplete` 时警告；完整状态直接跳过。
- `:85-90`：`created_at` 以 `<` 开头直接跳过日期校验。
- `:103-110`：`corpus.revision_count/total_chunks/eligible_chunks` 只要求非负整数，允许全 0。
- `:122-135`：完整状态只要求两个 index 对象、非空 `dense_index_contract_id` 和正数 `parent_count/point_count`；不要求模型名/collection/路径/两路点数一致。
- `:143-151`：`verification` 只要非空 dict；`rollback_target` 只排除空串和 `"unknown"`，`"<previous-complete-release>"` 可通过；`rollback_verified` 只要为 `True`。
- `config/knowledge-releases/kb-2.0.0-candidate.template.json` 本身含大量 `<...>` 占位符。

**可复现状态**

把模板改成 `status=accepted`、`build_id=kb2-build-1`、两个 index 的 `parent_count/point_count=1`、`verification={"x":1}`、`operations.rollback_verified=true`，保留 `created_at="<YYYY-MM-DD>"`、`git_commit="<git-commit>"`、`rollback_target="<previous-complete-release>"`、`corpus.revision_count=0,total_chunks=0`，运行 `validate()` 得到 `errors=[] warnings=[]`。这说明占位符/不完整候选可以被判为可发布。

`generation_max_tokens` 的凭据误报已验证不存在：`_SECRET_KEYS` 不匹配复数 `tokens`，模板通过凭据检查。

**后果**

发布负责人只要手工补两个 index 条目并改状态，就能让含占位符、0 语料或未完成语料的清单通过门禁；违反计划 §10.3/§11.2 的“完整发布清单”要求。

**建议修复**

- 完整状态拒绝所有 `<...>` 占位符（`created_at`、`git_commit`、`index collection/path`、`rollback_target`、`verification` 路径）。
- 要求 `corpus.revision_count > 0`，并与 `chunked_revisions`、parse 报告、`indexable_chunks`、两路 `parent_count` 交叉校验。
- 要求 `verification` 含具体通过记录（题集 revision、工程报告、阅读器、性能、回滚演练路径），不能任意非空 dict。
- 要求两个 index 的模型/collection/contract 不同且与运行时配置一致。

**置信度**：高（已实测复现）。

### P1-4 候选构建清单不代表实际选中范围，且 `--allow-missing-source` 未留痕

**文件/位置**

- `scripts/kb2_candidate_build.py:454-503`：`stage_manifest()` 的 `corpus.revision_count = len(registry.revisions)`（完整 210 条），`family_count/text_index_count` 同样取完整注册表；`chunked_revisions = quality.chunk_files`。
- `:202-260`：`stage_parse()` 只在 `allow_missing=True` 时记录失败并继续；`allow_missing` 没有进入 manifest。
- `:382-440`：`stage_report()` 用 `glob("*.json")` 读取 build_dir 内全部 chunk 文件，包含上一次运行留下的文件。
- `:104-120`：未知 `--batch-id` 返回空列表而不报错；`--stage all` 可继续生成空构建。
- 当前 r2 manifest（14:13 生成）示例：`revision_count=210`、`chunked_revisions=161`；实际选中 193，15 份 DOC 失败、17 份待 OCR，但这些只在外部报告，清单的 `incomplete_reasons` 仍是固定三条（当前代码新增了 `parse_status_counts`，但 `revision_count` 仍是完整注册表）。

**后果**

候选清单可能把“选中 193 份、实际 161 份可切块”的构建表示成 210 条修订；`--allow-missing-source` 可以静默吞掉解析失败；复用 build 目录时旧 chunk 文件会污染统计。校验器不会交叉检查这些数字，组合 P1-3 会把不完整候选误判为可发布。

**建议修复**

- `stage_manifest` 接收 `selected_revisions`/`allow_missing`/parse-report 失败清单，写入 `corpus.selected_revisions`、`parse_status_counts`、`failed_revisions`、`pending_ocr_revisions`。
- 冻结候选要求 `selected_revisions == revision_count` 且 `chunked + pending_ocr + failed` 完整对账；`--allow-missing-source` 时禁止生成可发布清单。
- 每次构建使用全新 build 目录，或按 `selected revision IDs` 清理 `chunks/` 后再报告。
- 未知 `--batch-id`/空选择直接失败。

**置信度**：高（代码路径和 r2 清单均核对）。

### P1-5 `release_id` 来自不可信请求，未校验也未参与检索，却写进响应/日志

**文件/位置**

- `src/accelerator_rag/rag/api.py:54`：`release_id` 只是 `StrictStr(max_length=128)`，无 slug/白名单校验。
- `src/accelerator_rag/rag/api.py:112-135`：任意 `release_id` 直接放入 `default_scope`/`version_scope`/`reference_scope`。
- `src/accelerator_rag/rag/service.py:79-91`：响应 `release_id` 优先取 `scope.release_id`，即请求值；`_attach_scope` 同时写 `retrieval_scope`。
- `src/accelerator_rag/rag/service.py:93-130`：`_save_trace` 保存 `scope.describe()` 和响应，请求值进入本地 trace。
- `src/accelerator_rag/storage/qdrant_passages.py:75-100`：scope filter 没有 `release_id` 轴；`RetrievalScope.allows` 也不检查 release。
- `src/accelerator_rag/rag/release.py:59-80`：运行时真实 release 只来自配置；生产配置当前没有 `release_id`，实际为 `unknown`。

**可复现状态**

客户端发送 `{"query":"...", "scope":{"release_id":"kb-9.9.9"}}`，`RagService` 会返回 `release_id="kb-9.9.9"`，trace 的 `retrieval_scope.release_id` 也是它；检索仍使用当前进程加载的索引，不会因 `release_id` 改变。测试 `tests/rag/test_version_scope_api.py:41-43` 明确允许该行为。

**后果**

响应和请求日志可以声明一个并未使用的发布号；用户/审计无法从 `release_id` 判断实际索引快照，违反计划 §8.3/§10.3 的“响应记录实际使用发布”与“请求记录保存实际修订及筛选理由”。若未来同一 collection 混放多 release，`release_id` 也不会隔离。

**建议修复**

- 请求中的 `release_id` 只能是当前 runtime 配置/发布清单中的值；否则 422 `RELEASE_NOT_FOUND`。响应始终写实际运行 release。
- 若确需客户端选择历史 release，则应在 payload/collection 层实现真正的 release 过滤，或明确每 release 独立入口。
- 至少把非法/长度异常值拒绝，并在 trace 中区分 `requested_release_id` 与 `effective_release_id`。

**置信度**：高（行为代码明确）；产品是否允许客户端指定 release 需确认，故严重度可能降为 P2。

### P1-6 冲突台账的 `revision_a/revision_b` 不是修订 ID，无法与注册表关联

**文件/位置**

- `src/accelerator_rag/corpus/schema_v2.py:739-776`：`ConflictRecord` 对 `revision_a/revision_b` 只做 `_require_text`，没有 slug/存在性校验。
- `src/accelerator_rag/corpus/schema_v2.py:780-796`：`ConflictLedger` 只检查 `(topic, revision_a, revision_b)` 重复，不检查引用。
- `scripts/merge_v2_governance.py:476-483`：直接把候选 JSON 构造成 `ConflictRecord`，不做路径→修订映射。
- `data/documents/v2/conflicts.json`：6 项冲突的 12 个字段中，10 个是 `data/l0_raw/...` 源路径，1 个是 `docs/roadmap/knowledge-base-v2-plan.md`，1 个是 `data/documents/registry.json#shine-accelerator-preliminary-design-report-2017`；**没有任何一个是注册表中的 revision_id**。

**后果**

冲突台账不能按修订/家族/状态连接；计划 §6.3 要求“两侧修订、证据位置”，当前只有人类可读路径，且第二项冲突一侧根本不是资料。后续若要用“未解决冲突不得产生单一当前答案”做检索/生成门控，无法实现；测试只检查数量和状态，未覆盖引用。

**建议修复**

- 生成时把源路径映射为 `revision_id`；非资料侧（如计划文档/registry 片段）另设 `revision_note` 或明确标记为 `external_reference`。
- `ConflictRecord` 校验 revision 为 slug；`ConflictLedger` 加载时与 `RegistryV2` 交叉校验（或提供带 registry 的验证函数）。
- 保留路径作为 `evidence_document` 单独字段，不占用 `revision_a/b`。

**置信度**：高（实际生成物已核对）；若团队有意让这两个字段存路径，需把字段语义/文档改清楚。

---

## P2

### P2-1 Schema 允许 `current + withdrawn/draft`，且默认检索不看 approval_status

- `src/accelerator_rag/corpus/schema_v2.py:445-458`：只要求 `current` 有 scope；只在 `current + approved` 时要求 review 记录。`current + withdrawn`、`current + draft` 均可通过。
- `src/accelerator_rag/retrieval/scope.py:120-145`：默认只过滤 usage/access，不检查 `approval_status`；`reference + withdrawn` 也会进入默认结果。
- 复现：取现有 revision，改成 `usage_status=current, approval_status=withdrawn, scope=["x"]`，`RevisionRecord.from_dict` 接受。
- 后果：将来若有人把撤回/草稿资料标成 current，默认检索会把它当现行依据；建议增加 `withdrawn -> usage != current`（至少）和完整状态迁移规则，并把 approval 纳入默认过滤或显式标注。
- 置信度：高（代码行为）；当前批次无 current/withdrawn，故暂未影响现有答案。

### P2-2 `RegistryV2` 的“处置一致”只比较 disposition 值，未比较 kind/format/target_family

- `src/accelerator_rag/corpus/schema_v2.py:625-642`：只比较 `item.disposition != revision.disposition`。
- 实际数据已出现不一致：`shine-accelerator-preliminary-design-report-2017` 的 disposition `target_family_id` 仍指向自身，revision 已合并到 `accelerator-overall-design`；RegistryV2 全量加载仍通过。
- 建议同时比较 `source_format/document_kind/target_family_id`（或规定 target 仅用于生成，不进入最终校验）。
- 置信度：高；影响是治理/生成端可能按旧 target 路由。

### P2-3 `_as_tuple` 接受 JSON object，数组字段校验不严格

- `src/accelerator_rag/corpus/schema_v2.py:313-322`：只要值是可迭代且元素是字符串就接受；JSON object 的 key 会被当成数组值（实测 `{"tags":{"a":"b","c":"d"}}` 通过，得到 `("a","c")`）。
- 建议显式拒绝 `Mapping`/dict，并校验 `tags` 等受控词表。
- 置信度：高；影响是畸形注册表可能被接受。

### P2-4 构建报告会扫入旧 chunk 文件；未知 batch-id 可静默生成空构建

- `scripts/kb2_candidate_build.py:382-440`：`glob("*.json")` 包含 build 目录中历史残留文件；我构造一个 stale chunk 文件后 `stage_report` 仍把它计入 `chunk_files/total_chunks/indexable_chunks`。
- `scripts/kb2_candidate_build.py:104-120`：未知 `--batch-id` 返回 `selected_revisions=0`，`--stage validate` 成功；后续可生成空 parse/chunk/report/manifest。
- 建议构建目录按 build_id 独占/清理，`stage_report` 只统计选中 revision 的 chunk 文件；未知 batch 直接失败。
- 置信度：高（stale 行为已复现）。

### P2-5 跨 position kind 检查不完整；同页补全键不包含位置类型（当前解析器未触发）

- `src/accelerator_rag/corpus/chunking_v2.py:378-382`：只检查 `first.position.kind != last.position.kind`。构造 `[section, slide, section]` 块组会被接受为一个 `section` chunk（实测通过）。
- `src/accelerator_rag/rag/retrieval.py:21-25`、`78-85`：`by_page` 键是 `(document_id, document_version, page)`，没有 `position_kind`；若一个 ParsedDocument 混用 paragraph/slide/cell_range，同页补全会把不同位置轴的内容拼在一起（实测可把 `cell_range` 表块作为 `paragraph` anchor 的同页邻居）。
- 当前各解析器每种文档只产生一种 position kind，故暂未触发；建议检查块组内全部 kind 一致，并在 by_page 键中加入 `effective_position_kind`，只对同类位置补全。
- 置信度：高（合成输入复现）；当前真实解析路径未发现混合输入。

### P2-6 DOCX TOC 启发式可能误删带制表符+数字的正文段落（需确认）

- `src/accelerator_rag/corpus/docx_parser.py:276-296`：`_has_toc_leader` 把任何“制表符 + 尾部数字”的短段落判为 TOC；`_detect_toc` 在全文范围直接跳过这些段落。
- 合成例：正文段落 `"响应时间\t100"` 会被 `_TOC_TAB_PAGE` 命中并删除。抽样 8 份较小 DOCX 未发现实际误删，但全批 121 份 DOCX 尚未逐份核对。
- 建议把 tab+数字启发式限制在 `目录/Contents` 标题后的 span 内，或要求同时有 TOC 样式/域/点引导符；TOC 块保留到审计数据（即使不索引）。
- 置信度：中；“需确认”实际语料是否有此模式。

### P2-7 混合型扫描 PDF 不会被标 `pending_ocr`，也不会触发页面级 OCR（需确认）

- `scripts/kb2_candidate_build.py:202-260`：只有 `not document.blocks and revision.ocr_profile` 才标 `pending_ocr`；有部分文本层的混合 PDF 会产生 blocks，从而记为 `parsed`。
- `src/accelerator_rag/corpus/ocr.py:96-119` 的 `plan_pdf_ocr` 能按页判断 `no_text_layer/sparse_text`，但构建脚本没有调用它，也没有“已有文本 + OCR 页”合并流程。
- 后果：混合 PDF 的扫描页可能静默缺失，无法进入 `pending_ocr` 统计；与计划 §7.3 的混合 PDF 处理不一致。
- 建议解析阶段保存逐页 OCR 计划，混合文档即使有文本也标记待 OCR 页；manifest 记录 `ocr_page_count`。置信度：高（代码未接线）；实际影响需确认批次中是否存在混合 PDF。

---

## 已验证且当前未发现问题的点

以下按协调者要求复核：

1. **`RagService` 默认 scope**：`src/accelerator_rag/rag/service.py:48-57` 在 `scope=None` 时构造 `default_scope(release_id)`，所有 recall 路径收到非空 scope；目标测试 `tests/rag/test_version_scope_api.py` 等 60 项通过。
2. **`build_scope_filter(default_scope())` 不再返回 `None`**：`src/accelerator_rag/storage/qdrant_passages.py:75-100` 对任何非空 scope 都返回 filter。用 in-memory Qdrant 验证：缺 `usage_status/access_scope` 的 legacy payload、显式空串、`"unknown"` 被准入；`historical`、`pending_review`、`restricted` 被排除；`version_scope(["hist"])`/`reference_scope` 行为符合定义。`tests/retrieval/test_scope_filtering.py::test_dense_sends_scope_filter...` 当前通过。
3. **`_table_chunk_label` 使用 `block.position.start`**：连续行合成测试从 `Sheet1!A5:B45` 得到 `A5:B5;A6:B18` 等，起始行偏移已修复；剩余问题仅为空行压缩（P1-2）。
4. **`MIN_INDEXABLE_CHARS`**：`stage_chunks` 保留全部 chunks、`eligible_chunk_ids` 与 `indexable_chunk_ids` 分开；r2 报告中 `chunks=4,135 / eligible=4,132 / indexable=3,950 / short_filtered=182`，审计数据未被删除。
5. **merge 幂等防护**：`merge_v2_governance.py:412-420` 拒绝已含 batch 修订的输入；用 `registry-v2.legacy-baseline.json` 连续运行两次，registry/conflicts 的 SHA-256 完全一致（`3e974c64...`/`cd5c3895...`）；`RegistryV2` 能发现重复 revision/family/source_path、家族成员与修订不一致、处置值不一致。
6. **状态语义（数据）**：当前 `registry-v2.json` 中 193 条新批次全部 `approval_status=unknown`，无 `current`/`approved`；4 条 `current` 全部是 legacy。默认 scope 对已知 `historical/pending_review` 不返回。
7. **`pending_ocr` 与 `failed`**：用当前代码对一份无文本层扫描 PDF 跑 `--stage parse` 得到 `pending_ocr=1`，`--stage chunks` 仍为 `pending_ocr=1`；DOC 转换失败走 `failed`。
8. **凭据误报**：`generation_max_tokens` / `max_evidence_tokens` 不被 `_SECRET_KEYS` 命中（模板验证通过）；`api_key` 等仍被拒绝。
9. **API 契约**：顶层和 scope 均 `extra=forbid`；`mode=compare` → `COMPARE_NOT_IMPLEMENTED`，`mode=version` 缺修订/家族 → `VERSION_SCOPE_REQUIRED`，非法 usage/kind/topic → `INVALID_RAG_INPUT`；旧 `{"query":...}` 在 API 层仍返回 `scope=None`，由 service 套默认策略。相关 60 项目标测试通过。

## 未覆盖/需后续确认

- 未在生产双路索引上验证 Qdrant filter、payload index 和默认全扫描的延迟。
- 未跑全批 193 份解析/人工语义评分；本报告不声称解析内容正确。
- 未验证 15 份 DOC 在无沙箱环境的转换、17 份扫描 PDF 的 OCR，以及混合 PDF 的实际分布。
- `release_status` 的 `read_only_attachment_count` 固定为 0、目录由索引而非 release manifest 构建，属于 K3/K4 未完成项；未作为 correctness finding 计入。

---

**审查方式说明**：以上行号为 2026-11-02 约 14:25 快照；审查期间 `docx_parser.py`、`chunking_v2.py`、`qdrant_passages.py`、`kb2_candidate_build.py` 仍被并行代理修改，若后续行号/行为变化，以新代码重新核对 P1-1/P1-2/P1-4/P2-5/P2-6。
