# K1：Schema v2、修订身份与兼容层

实现日期：2026-11-02　｜　状态：代码与旧库迁移已实现；新批次修订/家族待合并
对应计划：§5（身份与元数据）、§6（重复与版本族）、§7.1（统一中间表示）、§10.2（迁移）

## 1. 本次落地内容

| 模块 | 作用 |
| --- | --- |
| `src/accelerator_rag/corpus/schema_v2.py` | 五类身份、四种状态、受控枚举、修订/家族/处置/注册表校验 |
| `src/accelerator_rag/corpus/taxonomy_v2.py` | 在 v1 词表上扩展网络、存储、存档、报警、电源、真空、激光、运动控制、网络安全等主题 |
| `src/accelerator_rag/corpus/parsed_document.py` | 格式无关的 `ParsedDocument` / `ParsedBlock` / `TableData` / `SourcePosition` |
| `src/accelerator_rag/corpus/chunking_v2.py` | `kb2-chunks-v1` 切块，位置类型显式化，表格记录保留表头 |
| `src/accelerator_rag/domain/position.py` | `PositionKind`、`BlockType` 领域枚举 |
| `src/accelerator_rag/retrieval/scope.py` | 请求级 `RetrievalScope`，所有召回路径共用 |
| `scripts/migrate_registry_v2.py` | 从 v1 注册表生成 `data/documents/v2/registry-v2.legacy-baseline.json` |
| `scripts/merge_v2_governance.py` | 合并旧库、218 条处置、21 个族候选和 6 项冲突 |
| `data/documents/v2/registry-v2.json` | 正式候选：210 条修订（旧 17 + 新批次 193）、235 条处置、89 个族（后续 F11 设备族拆分） |
| `data/documents/v2/registry-v2.legacy-baseline.json` | 旧库迁移快照：17 条修订（4 current / 13 reference） |
| `tests/corpus/test_schema_v2.py` 等 | 契约、适配、切块、范围过滤测试 |

## 2. 五类身份

| 身份 | 本实现 |
| --- | --- |
| `family_id` | 逻辑文档族；旧文档每份暂时单独成族，待证据合并 |
| `revision_id` | 不可变来源修订，同时作为新检索记录的 `document_id` |
| `asset_id` | 原件/转换件/OCR/阅读副本身份；`ParsedDocument.asset_id` |
| `build_id` | 候选构建身份；发布清单阶段生成，本阶段尚未产生 |
| `release_id` | `kb-2.0.0` 目标发布；API/目录先返回配置值或 `unknown` |

旧 17 份资料的 `document_id` **未重命名**，直接作为对应修订的 `revision_id`。新修订必须使用新的 `revision_id`，禁止用逻辑族 ID 调用按 `document_id` 删除旧 passage 的接口。

## 3. 元数据契约要点

- 身份：`family_id`、`revision_id`、`title`、`revision_label`。
- 来源：`batch_id`、`original_asset_id`、`source_path`、`source_format`、`language`。
- 分类：`document_kind`（业务类型）、`category`/`topic`（子系统与主题）、`evidence_role`（设计指标/规范要求/测试结果/验收结论/操作步骤/历史记录/背景参考）。
- 时间：`received_at`、`document_date`、`effective_from`、`effective_to`、`date_precision`；未知保持 `unknown`，不按月补日。
- 适用范围：`scope`、`applicable_versions`。
- 状态：`approval_status`（来源是否批准）与 `usage_status`（知识库使用角色）分开；另有 `BuildStatus`、`ReleaseStatus` 枚举。
- 关系：`supersedes`、`equivalent_to`、`contains`、`supplements`、`derived_from`。
- 处理记录：`parser_profile`、`conversion_profile`、`ocr_profile`、`review_record`。
- 使用决定：`disposition`、`reason`、`reviewed_by`、`reviewed_at`。

强制规则（违反即拒绝加载）：

1. `usage_status=current` 必须有 `scope` 或 `applicable_versions`；
2. `current` + `approved` 必须记录 `reviewed_by` 和 `reviewed_at`；
3. `excluded` 与 `disposition=excluded` 必须同时出现；
4. `text_index` 只允许可解析文本格式；`structured_index` 只允许 XLSX/CSV/ODS；
5. 每个修订必须有同批次、同路径的处置记录，且处置一致；
6. 来源路径必须在 `data/l0_raw` 下，扩展名与 `source_format` 一致；
7. 关系字段不能引用自身；slug 只允许小写字母、数字和单连字符。

## 4. 旧库迁移决策

`from_legacy_records()` 的保守映射：

| v1 状态 | v2 `usage_status` | 理由 |
| --- | --- | --- |
| `active`（waveform 3 份、RAG 回滚手册） | `current` | 有明确 `applicable_system_version` 和验证日期，范围可写 |
| `active`（13 份 PDF） | `reference` | 只有 v1 标签，未独立核实现场适用性 |
| `reference` | `reference` | 原样保留 |
| `draft`/`unknown` | 按 `pending_review` 处理（本批无） | 不自动升为现行 |

所有旧文档 `approval_status=unknown`，`review_record` 明确写“migrated from v1 status=…; no re-review”。因此默认查询仍可使用它们作为背景依据，但回答不得声称它们“已经批准”或“现场已部署”。

## 5. 统一中间表示与位置类型

`ParsedDocument` 不再借用 PDF 页码字段：

| 位置类型 | 含义 | 当前来源 |
| --- | --- | --- |
| `pdf_page` | 物理 PDF 页 | PDF 适配器 |
| `section` | Markdown 章节序号 | Markdown 适配器 |
| `paragraph` | DOCX 正文块序号 | K2 DOCX 解析器 |
| `slide` | PPTX 幻灯片序号 | K2 PPTX 解析器 |
| `cell_range` | 工作表/CSV 单元格范围 | K2 表格解析器 |
| `line_range` | 纯文本行号 | 预留 |

`KnowledgeChunk` 仍是检索证据契约，新增可选字段（`family_id`、`revision_label`、`asset_id`、`document_kind`、`evidence_role`、`usage_status`、`approval_status`、`scope`、`position_kind`、`position_label`、`access_scope`），全部带空默认值：

- 旧 Qdrant payload 解码时缺失字段用默认值补齐，**不需要重建旧索引即可读取**；
- 旧 `pdf-chunks-v3` / `md-chunks-v1` 的 chunk ID 计算不变；
- 新批次使用 `kb2-chunks-v1`，ID 包含修订、资产、位置类型和处理契约，避免与旧 ID 混用。

## 6. 验证结果

| 检查 | 结果 |
| --- | --- |
| 旧测试回归 | 278/278 通过（K1 改动前基线） |
| K1 新增测试 | Schema、适配、切块、范围过滤共 49 项通过 |
| 全量测试 | K1 完成时 **315 passed**；K2/K3/K4 合并后最终 **454 passed, 2 skipped** |
| 旧注册表迁移 | 17 条修订、17 个家族、17 条处置；4 current / 13 reference |
| 批次治理合并 | 210 条修订、89 个族（F11 拆分后）、235 条处置、6 项冲突；218 个批次文件全覆盖 |
| `registry-v2.json` 加载 | 通过 Schema v2 全量校验 |
| Ruff | 新增/修改模块无错误 |

## 7. 未完成 / 待合并

1. **新批次 218 条处置**：已合并；但处置中的版本族、重复、访问范围仍是候选，需责任人确认。
2. **文档族合并**：21 个候选族已合并；medium confidence 的族仍标 `needs_confirmation`，操作手册三版、设计代次、标准规范合并版/单项版需要证据确认。
3. **候选构建与 release manifest**：`build_id`、`release_id` 尚未写入清单；K4 实现。
4. **旧索引重写**：新 payload 字段只有在候选构建时才会写入；旧索引仍可读，但显式版本筛选需重建。
5. **生产迁移**：未连接服务器、未读取生产原文、未修改索引；K4/K6 需授权。
