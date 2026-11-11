# Waveform 知识文档（M6）

本目录保存 PRAB Phase 1 建设的 Waveform 核心文档。三份文档都以
`/home/whloong/waveform-storage/waveform-storage-system` 的代码与历史为证据，
核验日 2026-10-29，适用版本 `waveform-storage-system@dc50e08 (2026-10-26)`。

| 文档 | 内容 | front-matter 版本绑定 |
| --- | --- | --- |
| [存储与数据流技术说明](waveform-storage-dataflow.md) | 采集请求 → capture_sequence → BPM 文件 → HDF5/元数据 → 历史查询；标识符唯一性、目录命名、新旧接口差别、存储边界 | `applicable_system_version`；`alignment_algo_hash` 标“未定义” |
| [对齐语义、参数与诊断手册](alignment-semantics-and-diagnostics.md) | 对齐 = 整数 bunchID 交集/共识（非时间对齐）；参数默认值/边界/错误行为；9 个诊断场景；能力 vs 未实现；文档-代码差异 | `applicable_system_version` + 系统既有 `alignment_algo_hash` |
| [历史故障记录与版本变更说明](fault-history-and-version-changes.md) | 版本时间线、真实案例（已证实/推断/待核实）、修复与验证证据、对“国庆后对齐异常”措辞的裁定 | 同上 |

## 状态说明（不得简化）

- Markdown 入库能力**已实现**（工作区代码）：解析、切块（`md-chunks-v1`）、登记
  `data/documents/registry-md.json`、`data/l0_raw/waveform/` 快照、干跑报告与建索引脚本齐备；
  干跑结果：4 份文档 → 40 节 → 151 chunks 全部 eligible（`reports/phase1-m0-20261029/md-ingestion-report.json`）。
- 但**生产索引尚未包含这批文档**：未在 GPU 主机执行 `build_markdown_index.py --apply`、未更新
  `point_count`、未重启服务。生产检索仍只有 13 份 PDF。步骤见
  [RAG 知识入库、验证与回滚手册](../runbooks/rag-ingestion-verification-rollback.md) §8.3。
- “文件已保存 + 可解析”不等于“生产可检索”；在本目录新增/修改文档后必须重跑
  `scripts/snapshot_markdown_docs.py` 与干跑报告。
- `owner` 字段未指派（待项目负责人裁决），不得据本文档推断责任人。
- `alignment_algo_hash` 统一为**系统既有值** `sha256(processing/alignment.py) = e8db12d7…3d5346`
  （等于 API v2 provenance 的 `algorithm_source_sha256`）。文档 2 另给一个 4 文件集合哈希
  `390fd8e9…c4e65d`，是**文档侧补充标识** `alignment_doc_bundle_hash`，不是系统能力、不可互比。
  文档 1（存储与数据流）不对齐算法负责，故该字段标“未定义（不适用）”。
