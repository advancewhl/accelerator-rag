# kb-2.0.0 候选构建手册（本地/K4）

本手册描述**已实现**的构建命令及其边界。它不包含生产索引、容器切换或回滚命令；这些属于 K6，需单独授权和现场核对。

## 1. 前置

- 使用 conda 环境 `accelerator-rag`。
- 已生成 `data/documents/v2/registry-v2.json`。
- 原始资料在 `data/l0_raw/`；该目录不进入 Git。
- 构建产物写入 `data/knowledge-builds/<build-id>/`，不进入 Git。

## 2. 生成/更新 Schema v2 清单

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/migrate_registry_v2.py
```

当前命令只从旧 v1 注册表生成 17 条修订；218 条新批次处置与家族合并后，必须重新运行并校验。

### 2.1 追加线缆/交换机配置表批次（2026-11-05）

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/register_cable_tables.py <解压后的 SHINE线缆表 目录>
```

脚本把原件复制到 `data/l0_raw/incoming/2026-11-05-shine-cables/SHINE线缆表/`，按 sha256 判重（名称含“副本/copy”的一份记为 `excluded`），幂等写入 15 条 `structured_index` 修订。只构建这一批：

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/kb2_candidate_build.py \
  --build-id cables-local-<date> --batch-id 2026-11-05-shine-cables --stage all
```

`.xls` 在构建期经 LibreOffice 转为 XLSX 后解析（`source_format` 仍为 `xls`），需要本机 `soffice` 且必须安装 **LibreOffice Calc**（RHEL/Rocky 包名 `libreoffice-calc`）。只有 Writer/Impress 时，`soffice --convert-to xlsx` 会报 `source file could not be loaded`；GPU 主机 2026-11-05 已补装该组件。表格按分组行、重复表头切成独立块，行记录写入 `records/<revision_id>.json` 并指向包含该物理行的父块。

## 3. 构建阶段

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/kb2_candidate_build.py \
  --build-id <lowercase-slug> --stage all
```

阶段：

| 阶段 | 内容 | 失败处理 |
| --- | --- | --- |
| validate | 加载 Schema v2、检查 source 是否存在 | 缺原文默认失败；**冻结候选不得使用 `--allow-missing-source`** |
| parse | PDF/Markdown/Office/表格 → `ParsedDocument` | 单篇失败默认中止；扫描件无文本层标 `pending_ocr`，不是解析成功 |
| chunks | 旧 PDF/Markdown 用旧算法保 ID；其余用 `kb2-chunks-v1` | 重复/空 chunk ID 中止 |
| report | 汇总块数、字符、空块、重复 ID、可索引块 | 结果写入 `quality-report.json` |
| manifest | 生成 `release-manifest.draft.json` | 无索引/发布目录时必须是 `candidate-incomplete` |

切块后应用两层门槛：

1. `eligibility_audit`：既有语料资格策略；不合格块保留在构建目录，不进入 `eligible_chunk_ids`。
2. `MIN_INDEXABLE_CHARS=20`：目录条目、空章节标题、短表题等保留在 `chunks/*.json` 供审计，但只有 `indexable_chunk_ids` 进入索引。质量报告同时给出 `eligible_chunks`、`indexable_chunks`、`short_chunks_filtered`、`ineligible_chunks`。

本地只做契约检查时，可显式允许缺失原文：

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/kb2_candidate_build.py \
  --allow-missing-source --build-id kb2-local-contract-<date>
```

## 4. 产物

```text
data/knowledge-builds/<build-id>/
  parsed/<revision-id>.json
  chunks/<revision-id>.json
  parse-report.json
  chunk-report.json
  quality-report.json
  release-manifest.draft.json
```

`release-manifest.draft.json` 的 `status` 只有在以下条件全部满足后才能改为 `candidate`：

- 全部 `text_index`/`structured_index` 修订解析成功；
- 两路索引已构建且父块集合/正文一致；
- 发布目录、回滚目标和验证材料已写入；
- 人工复核与题集结果已归档。

## 5. 当前不包含

- 嵌入与 Qdrant 索引构建（需 GPU/生产环境）。
- OCR（本机无 tesseract）。
- DOC→DOCX 的生产级转换（需验证 LibreOffice 环境）。
- 发布目录创建、容器启动/停止、入口切换、回滚演练。

这些步骤未实现前，不得把任何构建标记为 `accepted` 或 `live`。
