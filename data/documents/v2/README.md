# Schema v2 治理数据

本目录保存可审阅的知识库元数据，**不保存原文、索引或凭据**。运行时只读取发布包中的冻结副本，不直接读取本目录的编辑中文件。

2026 年 11 月 7 日，按用户授权将现有 225 个登记修订纳入研究范围，逐项记录见[研究准入台账](research-admission-20261107.json)。这是研究用途批准；原文档的签发状态、历史属性和访问范围分别保留。该台账不修改生产注册表，也不表示完成逐页语义复核。研究主线见[重构方案](../../../docs/research/rag-research-reset-20261107.md)。

## 文件

| 文件 | 内容 | 当前状态 |
| --- | --- | --- |
| `registry-v2.json` | 正式候选修订、文档族、逐文件处置 | 210 条修订（旧 17 + 新批次 193）、235 条处置、89 个族（F11 将 31 个操作手册修订拆为 16 个设备族） |
| `registry-v2.legacy-baseline.json` | 旧库迁移快照 | 17 条修订；合并脚本的唯一合法输入 |
| `dispositions.draft.json` | 2026-11-02 批次 218 个文件的处置候选 | 已生成并通过 Schema 校验 |
| `family-candidates.draft.json` | 版本族候选 | 已生成（21 个族） |
| `conflict-candidates.draft.json` | 冲突台账候选 | 已生成（6 项） |
| `conflicts.json` | 受校验的冲突台账 | 由合并脚本写出 |

## 生成与校验

```bash
# 1) 旧库迁移快照（只在需要重建时运行；不要覆盖合并结果）
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/migrate_registry_v2.py

# 2) 从批次草案重新生成正式注册表（必须显式使用旧库快照）
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/merge_v2_governance.py \
  --registry data/documents/v2/registry-v2.legacy-baseline.json
```

`merge_v2_governance.py` 在合并末尾应用已评审的 F11 设备族拆分（31 个操作手册修订 → 16 个族），无需再手工运行后处理脚本；独立脚本 `scripts/split_operation_manual_families.py` 仅用于检查或迁移旧注册表。

加载时会经过 `accelerator_rag.corpus.schema_v2.RegistryV2` 全量校验：

- 修订/家族/处置身份唯一；
- 每个修订属于一个存在的家族，且家族成员与注册表一致；
- 每个修订有同批次、同路径、同处置的处置记录；
- `current` 必须有适用范围；`current + approved` 必须有审核记录；
- `excluded` 与 `disposition=excluded` 必须一致；
- 来源路径、扩展名、日期精度和受控词表均校验。

## 编辑规则

1. **不要手工改 `registry-v2.json`**；修改生成脚本或治理输入后重新生成。
2. 未知日期、批准状态、责任人写 `unknown` 或留空，不按月补日、不按文件名猜批准。
3. 新批次资料在确认前使用 `usage_status=pending_review` 或 `reference`，不能自动升为 `current`。
4. 同一逻辑文档的多个修订使用同一 `family_id`；合并必须有版本、标题、正文或责任人证据。
5. 受限资料使用 `access_scope=restricted`；在责任人确认访问范围前，不进入公共目录、搜索片段、下载接口或回答日志。
6. 原始资料仍只存放在 `data/l0_raw/`（不进入 Git）；本目录只保存元数据。
