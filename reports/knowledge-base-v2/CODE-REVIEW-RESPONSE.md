# CODE-REVIEW 处置记录

审查报告：[`CODE-REVIEW.md`](CODE-REVIEW.md)（2026-11-02 快照）
本记录说明主线在审查后做了哪些修改；**不修改审查报告原文**，保留发现时的状态。

| 编号 | 处置 | 证据/测试 |
| --- | --- | --- |
| **P0-1 受限资料** | **已修**：候选选择默认排除 `restricted`；`DocumentCatalog.add` 忽略 restricted；`RagRuntime` 不把 restricted 加入 documents/catalog；下载/view/sections 因此不可见 | `tests/test_candidate_build_selection.py`、`tests/rag/test_catalog_v2.py::test_restricted_chunk_is_not_listed_in_public_catalog` |
| **P1-1 位置类型** | **已修（API/引用/UI）**：context 与 citation 使用 `effective_position_kind`（pdf_page→page，paragraph/slide/cell_range 保留），增加 `position_label`；非 PDF/Markdown 的 `document_url=None`，UI 不再按 PDF 打开，显式提示阅读页未接入 | `tests/rag/test_locator_kind.py`、`tests/rag/test_catalog_v2.py::test_new_office_formats_have_no_pdf_reader_url` |
| **P1-2 表格空行** | **已修**：XLSX 保留首末非空行之间的空行，物理行连续；表格文本跳过全空行，但位置标签按真实行；`_table_chunk_label` 使用 `block.position.start` | `tests/corpus/test_structured_parser.py::test_xlsx_interior_blank_rows_keep_physical_range`、真实端子表重建为 `A2:K2;A3:K15` |
| **P1-3 发布清单占位符** | **已修**：完整状态拒绝任意 `<...>` 占位符、0 语料、`allow_missing_source`、失败/待 OCR/缺失源；要求两路不同模型/合同、索引路径、具体 verification 键 | `tests/test_release_manifest.py`，包括审查给出的占位符复现用例 |
| **P1-4 构建范围/残留** | **已修**：manifest 写 `selected_revisions`、`registry_revision_count`、`allow_missing_source`、`parse_status_counts`；chunks 阶段清理旧 chunk 文件；report 只统计选中 revision；空选择直接失败 | `--stage chunks/report/manifest` 重跑；最终 r3 清单 `revision_count=190` |
| **P1-5 release_id** | **已修**：请求 `release_id` 必须是运行时实际发布号；未知/不匹配返回 422 `RELEASE_NOT_CONFIGURED`/`RELEASE_NOT_FOUND`，不再回显客户端声称的发布号 | `tests/rag/test_version_scope_api.py::test_requested_release_must_match_the_running_release` |
| **P1-6 冲突台账引用** | **已修**：`ConflictRecord` 增加 `revision_a_id`/`revision_b_id`/`external_reference`；10/12 侧映射到注册表 revision，计划文档侧明确标 external | `data/documents/v2/conflicts.json`、`tests/corpus/test_registry_v2_batch.py::test_conflicts_link_to_registry_revisions_where_possible` |
| **P2-1 current+withdrawn/draft** | **已修**：`current` 不允许 `withdrawn`/`draft` | `tests/corpus/test_schema_v2.py` |
| **P2-3 数组字段接受 object** | **已修**：数组字段显式拒绝 `Mapping` | 同上 |
| **P2-4 旧 chunk/空 batch** | **已修**：见 P1-4 | 构建脚本 |
| **P2-5 跨 position kind/同页混轴** | **已修**：chunk 组内所有块必须同 kind；同页 key 增加 `effective_position_kind` | `tests/corpus/test_chunking_v2.py::test_mixed_position_kinds_in_one_group_are_rejected`；现有 retrieval 测试 |
| **P2-2 处置 target_family 一致性** | **已修**：合并时把 `target_family_id` 更新为最终修订所属族；`RegistryV2` 加载时校验两者一致 | `load_registry_v2` 通过；target mismatch=0 |
| **P2-6 TOC tab+数字误删风险** | **未修/需确认**：现有 TOC 测试覆盖样式、域、点引导符、`sdt`；tab+数字启发式仍可能误判正文。未逐份人工核对 121 份 DOCX。 | 审查报告 P2-6 |
| **P2-7 混合 PDF OCR** | **未修/需确认**：`plan_pdf_ocr` 已有，但构建未按页接线；整本无文本 PDF 标 pending_ocr，混合 PDF 部分扫描页尚未标。 | 审查报告 P2-7 |

## 仍未完成的上线前置（独立于审查 finding）

- DOC 真实转换环境、OCR 工具、两路索引、release manifest 完整冻结、K6 切换/回滚。
- DOCX/PPTX/XLSX 阅读页（当前返回 501 或禁用链接），`mode=compare` 仍未实现。
- 人工内容抽查与业务语义评分。
