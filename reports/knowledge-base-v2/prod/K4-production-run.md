# K4 生产构建记录：kb-2.0.0-rc.1

执行日期：2026-11-02　｜　主机：`10.101.9.190`（经 `waveform-zyf-oneclick` 跳板）
构建号：`kb2-prod-20261102`　｜　候选目录：`/opt/accelerator-rag-build/kb-2.0.0-rc.1/release`

## 1. 输入与范围

- 注册表：`data/documents/v2/registry-v2.json`（210 条修订）。
- 公开候选：**207 条**；3 条 `access_scope=restricted` 被构建选择排除，未进入索引、目录或下载接口。
- 原文：旧 13 PDF + 4 Markdown + 2026-11-02 批次 218 个文件（`data/l0_raw/incoming/2026-11-02-shine-control/资料/`）。
- 构建环境：独立 Python 3.11 parse env + LibreOffice 7.1 + tesseract 4.1（chi_sim/eng）。

## 2. 解析/切块结果

| 项目 | 结果 |
| --- | ---: |
| 选中修订 | 207 |
| 解析成功 | **207** |
| 解析失败 | **0** |
| 待 OCR | **0** |
| 缺失原文 | **0** |
| 父块 | 8,622 |
| eligibility 合格 | 8,614 |
| 可索引父块 | 8,431 |
| 短块过滤（<20 字符） | 183 |
| 空块 / 重复 ID | 0 / 0 |
| 总字符 | 6,405,181 |

覆盖：旧 13 PDF/4 MD、DOCX、PPTX、XLSX 与 15 份 `.doc` 转换、16 份扫描 PDF OCR。

### OCR 质量边界

OCR 已跑通，但文本质量不能等同人工核对。抽查《24. 控制需求工作联系单》47 页：正文可读，**第 3 页表格已出现明显错字/串行**。这些块带 `manual_review_required=true`，仍不能独立支撑精确数值或表格结论；关键参数必须回原页复核。

## 3. 双路索引

| 路由 | 父块 | passages/points | 向量合同 | 构建耗时 |
| --- | ---: | ---: | --- | ---: |
| E5 `intfloat/multilingual-e5-base` | 8,431 | 10,608 | `ccd4601d…`（与旧索引一致） | 782 s |
| Qwen3 `Qwen/Qwen3-Embedding-0.6B` | 8,431 | 8,431 | `6698d553…`（与旧索引一致） | 2,299 s |

- 两路 `parent_set_sha256`、`parent_text_sha256`、`parent_evidence_sha256` **完全一致**；`point_counts_match_embedded=true`。
- Qwen3 首次构建在 GPU0 `batch=16` OOM（其他服务占满显存）；退回索引脚本增加 `--route/--resume` 后，用 GPU1 `batch=2` 只重建 Qwen3，E5 报告被复用，未重嵌入。
- 最终候选配置：`/workspace/config/rag-production.json`（容器路径），release_id=`kb-2.0.0-rc.1`。

## 4. 候选服务核对

`kb2-candidate`（GPU1，端口 8013，只读挂载候选目录）健康：

```json
{"release_id":"kb-2.0.0-rc.1","build_id":"unknown","document_count":207,"revision_count":207,"family_count":72,"indexed_section_count":8431,"source":"runtime-config"}
```

- 目录覆盖 207 份文档；DOCX/PPTX/XLSX 可见但 `reader_available=false`（阅读页未接入），不伪装成 PDF。
- 受限资料不在目录/下载/默认检索范围。

## 5. Subagent 交付审查

| 交付 | 结论 | 说明 |
| --- | --- | --- |
| 索引构建器 | 首次不合格，退回反修后接受 | 首次无 `--route/--resume`，Qwen OOM 后必须重做 E5；反修后支持单路续建、OOM 保护、双路齐全才写配置，测试通过 |
| 50 题回归器 | 接受 | 仅标准库、只发送 query、不跟随重定向、0600 输出；旧服务 3 题 smoke 3/3、50 题 48/50（2 个既有 502） |
| 格式解析/OCR | 接受工程链路 | 207/207 解析；OCR 质量仍需人工复核 |

## 6. 候选验收结果

- 候选 50 题工程回归：**49/50 HTTP 成功**，唯一 502 为旧库同样存在的 P50-017；无新增请求失败；45 answered / 4 partial；91 条引用定位完整；无受限文档命中。
- P95 26.6 s，旧库 19.5 s，约 1.36×；略高于计划 1.3× 目标，需观察期分析。
- 唯一状态收紧：P50-038 从 answered 变 partial，因为证据未明确“失败文件是否删除”；属于更保守，不是答错。
- 详细报告：[`K5-production-acceptance.md`](K5-production-acceptance.md)。

## 7. 待完成

- **K6 生产切换已完成**：2026-11-02 将 8003 切到 `kb-2.0.0-rc.1`，健康与冒烟验证通过；旧容器保留为 `accelerator-rag-md-rollback-20261102`。详见 [`K6-production-switch.md`](K6-production-switch.md)。
- 人工语义评分、新 60 题冻结与业务审核。
- 回滚演练与 2 个工作日观察期。
- 维护交接与 K7 报告。
