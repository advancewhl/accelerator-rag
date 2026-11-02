# K4：本地候选构建契约检查

执行日期：2026-11-02　｜　构建号：`kb2-local-contract-20261102`
命令：

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/kb2_candidate_build.py \
  --allow-missing-source --build-id kb2-local-contract-20261102
```

## 1. 结果

| 阶段 | 结果 |
| --- | --- |
| validate | 17 个修订被选中；13 份旧 PDF 缺失，已记录并允许继续（仅本地契约检查） |
| parse | 4 份 Markdown 解析成功；13 份缺失；0 失败 |
| chunks | 4 份切块成功；40 个父块；40 个唯一 chunk ID |
| report | 4 个 chunk 文件；40 块；30,876 字符；0 空块；0 重复 ID |
| manifest | `candidate-incomplete`；无索引、无发布目录、无回滚目标 |

产物在 `data/knowledge-builds/kb2-local-contract-20261102/`（`.gitignore` 已覆盖），包括 `parsed/`、`chunks/`、`parse-report.json`、`chunk-report.json`、`quality-report.json`、`release-manifest.draft.json`。

## 2. 这次证明了什么

- Schema v2 清单能加载并通过身份/家族/处置一致性校验。
- 旧 Markdown 修订可以走 `parse → ParsedDocument → chunks` 链路，且沿用 `md-chunks-v1` 的 40 个旧父块身份（8+9+11+12），没有因新增元数据改变 chunk ID。
- 构建脚本在缺原文时不会静默成功：manifest 标记 `candidate-incomplete`，并列出缺失、OCR 未做、索引未建、回滚未验证。
- 构建产物不进入 Git。

## 3. 这次没有证明什么

- 13 份旧 PDF 不可用：迁移后问答是否退化未验证。
- 新批次 DOCX/PPTX/DOC/表格/OCR 未在本构建中解析。
- 没有嵌入、没有 Qdrant、没有 BM25 语料、没有 release 包。
- 没有人工语义评分、性能或回滚演练。
- `--allow-missing-source` 只适用于本地契约检查；冻结候选绝不能使用。

## 4. 下一步（需生产资源/授权）

1. 在生产机只读核对旧 13 份 PDF 与两路索引，记录 SHA-256 与点数。
2. 在新批次上运行 K2 解析器，先做 12–16 份代表样本的质量报告。
3. 合并 218 条处置与文档族，重新生成 `registry-v2.json`，跑通全部 text_index 修订。
4. 构建双路索引，生成完整 `release-manifest.json`（不再是 draft）。
5. 旧 50 题回归 + 新 60 题验证 + 回滚演练后，才进入 K6。
