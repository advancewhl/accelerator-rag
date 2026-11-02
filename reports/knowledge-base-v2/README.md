# kb-2.0.0 扩建报告索引

本目录保存知识库扩建的工程记录。历史报告保留当时状态；本目录不保存原文、索引、凭据或大规模中间产物。

| 报告 | 阶段 | 状态 |
| --- | --- | --- |
| [K0-baseline.md](K0-baseline.md) | K0 基线与范围 | 本地已核对；生产基线待现场 |
| [K1-contract.md](K1-contract.md) | K1 Schema v2/身份/兼容 | 代码与旧库迁移已实现 |
| [K1-governance-candidates.md](K1-governance-candidates.md) | K1 批次治理候选 | 已生成 |
| [K1-governance-merge.md](K1-governance-merge.md) | K1 218 条处置/版本族合并 | 已完成 |
| [K2-format-sample-survey.md](K2-format-sample-survey.md) | K2 代表格式测量 | 已完成只读测量 |
| [K2-parser-validation.md](K2-parser-validation.md) | K2 解析器端到端验证 | 前 6 份批次文档完成 |
| [K3-scope-retrieval.md](K3-scope-retrieval.md) | K3 版本筛选与 API | 代码完成，生产待验证 |
| [K4-local-build.md](K4-local-build.md) | K4 本地候选构建契约 | 已完成 |
| [K4-full-batch-preliminary.md](K4-full-batch-preliminary.md) | K4 全批预跑 | 修复前预跑，保留对照 |
| [K4-full-batch-final.md](K4-full-batch-final.md) | K4 全批最终预跑 | 190 公开候选；159 成功 / 16 待 OCR / 15 DOC 失败；3,671 可索引块 |
| [prod/K4-production-run.md](prod/K4-production-run.md) | K4 生产构建 | 207 修订全部解析；8,431 可索引；双路索引完成 |
| [prod/K5-production-acceptance.md](prod/K5-production-acceptance.md) | K5 工程回归 | 49/50 成功；唯一 502 为旧库既有；语义评分未做 |
| [prod/K6-production-switch.md](prod/K6-production-switch.md) | K6 切换记录 | 8003 已切到 `kb-2.0.0-rc.1`，健康验证通过；旧容器保留可回滚 |
| [K4-production-prerequisites.md](K4-production-prerequisites.md) | K4/K5/K6 生产前置 | 已执行到候选切换前；剩余授权/演练 |
| [K5-question-plan-review.md](K5-question-plan-review.md) | K5 题集与评分 | 规划完成，未冻结 |
| [CODE-REVIEW.md](CODE-REVIEW.md) | 独立代码审查（P0 1 / P1 6 / P2 7） | 快照保留 |
| [CODE-REVIEW-RESPONSE.md](CODE-REVIEW-RESPONSE.md) | 审查发现处置记录 | P0/P1 已修，P2 部分未修 |
| [STATUS.md](STATUS.md) | 阶段状态总表 | 随进展更新 |

## 阅读顺序

1. 先看 [STATUS.md](STATUS.md) 了解哪些已做、哪些被资源/授权阻塞。
2. 看 [K0-baseline.md](K0-baseline.md) 了解本地与生产基线的差别。
3. 看 [K1-contract.md](K1-contract.md) 了解身份、状态与兼容规则。
4. K2/K3 报告只描述已验证范围，不把单元测试通过等同于解析质量验收。
