# K1：批次治理合并报告

生成日期：2026-11-02　｜　批次：`2026-11-02-shine-control`
命令：

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/merge_v2_governance.py \
  --registry data/documents/v2/registry-v2.legacy-baseline.json
```

输入：旧库迁移快照、218 条处置草案、21 个版本族候选、6 项冲突候选。
输出：[`registry-v2.json`](../../data/documents/v2/registry-v2.json)、[`conflicts.json`](../../data/documents/v2/conflicts.json)、[`governance-merge-report.json`](../../data/documents/v2/governance-merge-report.json)。

## 1. 结果

| 项目 | 数量 |
| --- | ---: |
| 总修订 | 210 |
| 旧库修订 | 17 |
| 新批次修订 | 193（191 文本索引 + 2 结构化索引） |
| 逐文件处置 | 235（旧库 17 + 新批次 218） |
| 文档族 | 74（21 个候选族被采用；53 个单修订占位族） |
| 冲突台账 | 6 项 |
| 批次内非文本修订 | 25（目录/附件/暂存/排除） |

## 2. 使用状态

| `usage_status` | 修订数 | 说明 |
| --- | ---: | --- |
| `current` | 4 | 仅旧库中带明确系统版本/验证范围的 4 份 Markdown |
| `reference` | 118 | 设计、规范、测试/验收等背景证据 |
| `pending_review` | 43 | 批次 P0、操作手册、安装维护、未知类型；不得作为现行依据 |
| `historical` | 45 | 位于“归档文档”路径下的历年资料 |

**没有一份新批次资料被标为 `current`。** 全部 210 条修订的 `approval_status` 都是 `unknown`，`review_record` 明确说明没有逐份复核。

## 3. 访问范围

3 份资料标为 `restricted`：

- `硬X射线自由电子激光装置网络安全设计报告.docx`
- `SHINE加速器设备运行数据的安全管理.docx`
- `20. 一号测试大厅控制网络地址分配.docx`

它们不会进入默认 `RetrievalScope`（默认只允许 `internal`）。在责任人确认允许使用群体前，不进入公共目录、搜索片段、下载接口或回答日志。

## 4. 版本族

21 个候选族全部至少有一个成员被纳入，没有完全悬空的候选。较大的族：

| 族 | 修订数 |
| --- | ---: |
| `shine-control-operation-manual-series` | 31 |
| `shine-timing-system-design` | 13 |
| `shine-prototype-fast-interlock-acceptance` | 11 |
| `shine-prototype-high-frame-rate-image-acquisition-acceptance` | 11 |
| `shine-prototype-control-system-development-environment-acceptance` | 10 |

未纳入族的成员包括目录/附件/暂存/排除文件，已在族描述中注明“未纳入修订”。这些族关系是**候选**，`needs_confirmation` 仍需资料责任人确认，尤其是“技术设计是否整篇替代初步设计”“第三版操作手册是否替代前两版”。

## 5. 冲突台账

6 项冲突均保持未解决：

1. 设计能量 8 GeV vs 7.2 GeV（open）
2. 网络安全报告封面日期晚于批次日期且审核栏为空（needs_source_check）
3. V6“返回通读版本”的批准状态与替代范围（needs_source_check）
4. 白兔定时设计指标 vs 原型实测口径（needs_source_check）
5. 快联锁响应时间的测量范围（站内/站间、FPGA/PLC）（needs_source_check）
6. 准直器操作手册第一版与第三版操作步骤差异（open）

冲突记录只说明“存在不同口径/待核对”，不判断哪一侧正确。未解决冲突不得产生单一“当前确定答案”。12 个冲突侧中有 10 个已映射到注册表 `revision_id`；网络安全报告的“晚于批次日期”一侧引用计划文档，保留为 `external_reference`，不伪装成资料修订。

## 6. 关键规则

- 新批次 `P0` 一律 `pending_review`，不因文件新或优先级高而升为现行。
- 位于“归档文档”路径的资料标 `historical`，可用于旧设备/历史追溯，不用于默认现行答案。
- 操作手册、安装维护、未知类型标 `pending_review`；默认查询不会使用，需显式参考模式。
- 设计、规范、测试/验收标 `reference`，可作为背景依据，但回答必须说明资料性质。
- `document_date` 仅从文件名解析；解析不到就保持空值和 `date_precision=unknown`，不用文件修改时间补。
- 未做全文去重/内容相似度比对；完全重复、合并版/单项版、扫描副本的关系仍需 K2/K4 逐份确认。

## 7. 校验

- `RegistryV2` 全量校验通过：身份唯一、家族成员一致、每个修订有同批次同路径处置、处置一致、`current` 有范围、`excluded` 一致。
- `validate_batch_coverage` 通过：218 个批次文件全部有处置。
- 冲突台账 `ConflictLedger` 校验通过。
- 新增测试 `tests/corpus/test_registry_v2_batch.py` 覆盖 218 条覆盖、193 条修订、无批次 `current`、3 份受限资料、6 项冲突。
- 旧库快照保存在 `registry-v2.legacy-baseline.json`；合并脚本拒绝再次合并已含批次修订的注册表，防止重复。

## 8. 未完成 / 待确认

- 未解析这 193 份修订的正文；任何“内容已入库”的说法都不成立。
- 未确认版本族关系、批准状态、生效日期和现场部署依据。
- 未处理完全重复/合并版/扫描副本的最终取舍。
- 未做 OCR；17 份扫描件仍是 `pending-ocr`。
- 25 个非文本文件的具体去向（目录/附件/暂存/排除）仍需 K4 逐项落实。
