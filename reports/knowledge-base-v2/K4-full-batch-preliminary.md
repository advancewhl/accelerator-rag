# K4：全批解析/切块预跑报告（修复前）

执行日期：2026-11-02　｜　构建号：`kb2-batch-full-20261102`　｜　状态：**预跑，不是候选**

命令：

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/kb2_candidate_build.py \
  --build-id kb2-batch-full-20261102 --stage all --allow-missing-source
```

本次选中 registry 中全部 210 条修订（旧库 17 + 新批次 193）。`--allow-missing-source` 只用于本地预跑；冻结候选不得使用。

## 1. 汇总

| 阶段 | 结果 |
| --- | ---: |
| 选中修订 | 210 |
| 原文缺失（旧库 13 份 PDF） | 13 |
| 解析成功 | 180 |
| 解析失败 | 17 |
| 切块成功 | 163 |
| 切块失败 | 34 |
| 父块总数 | 4,174 |
| 总字符 | 2,651,890 |
| 空块 | 0 |
| 重复 chunk ID | 0 |
| 少于 20 字符 | 237（5.7%） |
| 少于 50 字符 | 379（9.1%） |

## 2. 按格式

| 格式 | 成功切块文档 | 父块 | 字符 | 少于 20 字符 |
| --- | ---: | ---: | ---: | ---: |
| DOCX | 121 | 3,584 | 2,372,815 | 201 |
| PDF（有文本层） | 19 | 88 | 91,791 | 1 |
| PPTX | 17 | 411 | 98,228 | 35 |
| XLSX | 2 | 51 | 58,180 | 0 |
| Markdown（旧库） | 4 | 40 | 30,876 | 0 |

PDF 另有 17 份无文本层（OCR 待处理），未产生父块。

## 3. 失败清单

### 3.1 解析失败（17）

| 类型 | 数量 | 原因 | 处理 |
| --- | ---: | --- | --- |
| `.doc` → DOCX | 15 | LibreOffice 在沙箱内 `ERROR: no valid pipe path found` | 环境限制；适配器显式抛 `DocConversionError`，需在无沙箱构建环境重跑 |
| PPTX 未知形状 | 2 | `NotImplementedError: Shape instance of unrecognized shape type` | 解析器应对未知 shape 记 warning 并跳过，而不是整份失败（已提交修复） |

### 3.2 无块可切（17）

- 17 份扫描 PDF 整本无文本层（OCR 未做）。
- 另有少量空表/空工作表；解析器记录了 `empty_sheet` 或 `no_extractable_text`，没有静默当成成功。
- 这些在 K4 中应标为 `pending_ocr` 或 `deferred`，不是“已入库”。

### 3.3 切块失败（34）

34 = 17 个解析失败的下游缺失 + 17 个无块文档；没有额外的切块逻辑错误。

## 4. 质量观察

1. **短块主要是目录/标题**：237 个少于 20 字符的块中，大量是 Word 目录条目（“目录”“1 概述”“2 设计目标”“3.1 总体方案…”）、空章节标题和 PPTX“谢谢 !”。这些不是可用证据。
2. **候选构建已加索引门槛**：`MIN_INDEXABLE_CHARS=20`；全部块保留在 `chunks/*.json` 供审计，只有 `indexable_chunk_ids` 进入索引。预跑时尚未启用该门槛，修复后重跑会报告 `indexable_chunks` 与 `short_chunks_filtered`。
3. **目录块仍应在解析层识别**：只靠 20 字符门槛会漏掉较长的目录项；已要求 DOCX 解析器识别 TOC 样式/域并记为 `toc`。
4. **标题回退有效**：例如 2022 设备控制技术设计报告 `heading_style_count=0`、`heading_outline_count=8`、`heading_heuristic_count=22`，最终 30 个标题；联锁技术设计报告 outline 82 + heuristic 3，最终 85 个标题。
5. **表格/公式**：V6 597 张表、160 公式段；表格合并单元格以重复文本呈现，未丢失列，但需要人工确认列关系。
6. **短块比例 5.7%** 不能作为最终质量指标；目录/标题修复后必须重跑并重新报告。

## 5. 结论

- 解析链路已覆盖新批次全部格式；失败集中在 **环境 DOC 转换**、**2 个 PPTX 形状** 和 **17 份待 OCR 扫描件**，不是全批不可解析。
- 本次结果**不能**作为 `kb-2.0.0` 候选：没有索引、没有问答、没有人工复核，且目录/PPTX 修复尚未重跑。
- 下一步：等待解析器修复 → 用 `--batch-id 2026-11-02-shine-control` 重跑 193 份 → 报告 `indexable_chunks`、`short_chunks_filtered`、`pending_ocr`、失败清单 → 再进入索引阶段。
