# 300 题独立基准：交付说明

日期：2026-11-07。依据 `docs/research/rag-research-reset-20261107.md` 阶段一（第 1—2 周）。

2026-11-08：已按阶段四重设计决定 A 重建为 v2「组合必需」。当前哈希、移出/补入与审计见 `delivery-stats.md` 第 11 节与 `reports/phase4/audit/benchmark-v2/`；本文件其余段落保留为 v1 交付说明。

## 1. 交付物

| 交付物 | 位置 | 说明 |
| --- | --- | --- |
| 冻结基线 | `baseline-freeze.md`、`data/evaluation/research-benchmark-300-v1/baseline/baseline-freeze.json` | rc.3 发布身份、语料/索引签名、模型与提示词指纹、重建命令、已验证/未验证清单 |
| 300 题基准 | `data/evaluation/research-benchmark-300-v1/{dev,val,sealed-test}/questions.json` | 100/50/150；三类场景各 100；含真值、最小证据与配对干预 |
| 合并源与报告 | `data/evaluation/research-benchmark-300-v1/sealed-test/_work/` 下的 `w5-gold-interventions.jsonl`、`w5-report.md`、`template-families.json`、`s3-pairing-inventory.md` | 含 test 题号或原文摘录，随测试集封存（700/600） |
| 划分政策 | `split-policy.json`（v4） | 场景、族、对象簇、配额、prior_exposure、隔离定义 |
| 出题规范 | `SPEC.md` | 底题独立性、证据规则、干预规则、status/verdict 口径 |
| 审核协议与结果 | `review-protocol.md`；本目录其余报告 | R1—R5 分工、分级、复审规则；审核报告见会话记录与修复记录 |
| 统计与论文素材 | `stats.json`、`delivery-stats.md`、`sample-size.md`、`paper-data-section.md` | 规模、配对、样本量、论文场景与数据设置章节素材；场景三配对清单为 review-only，存于 `sealed-test/_work/` |

含题干/答案/证据的文件不进入 Git；`manifest.json`、`stats.json`、`baseline-freeze.json`、规范与统计摘要可入库。

## 2. 复现命令

```bash
python3 scripts/research/build_rc3_inventory.py
python3 scripts/research/validate_benchmark.py --all
python3 scripts/research/audit_benchmark.py
python3 scripts/research/normalize_excerpts.py data/evaluation/research-benchmark-300-v1/sealed-test/_work/w5-gold-interventions.jsonl
python3 scripts/research/assemble_benchmark.py --out data/evaluation/research-benchmark-300-v1 data/evaluation/research-benchmark-300-v1/sealed-test/_work/w5-gold-interventions.jsonl
```

语料本地只读副本位于 `tmp/research-rc3/`（从 GPU 发布目录只读拉取，摘要哈希见 baseline）。测试集封存后，含 test 的源文件与报告置于 `sealed-test/_work/`（700/600）。

## 3. 口径说明

- **旧 100 题**：全部归入已曝光开发与回归材料。旧文件中的 10 条 `split=sealed` 是历史标签，已无盲测含义；本轮已阅读全部 10 条。新基准不复用其题目与真值。
- **两套“30 道版本题”**：旧 100 的 30 条是 `scope.mode=version` 的指定文档题（20 dev/10 sealed，含 18 条单修订题）；新 300 的 30 条是 S2 `scope.mode=explicit_revisions` 的修订比较题（dev/val/test 各 10）。两者都必须与全库检索分开报告，且比较方法时各方法获得相同范围信息。
- **测试隔离**：S2/S3 测试族完全未在旧 100 中出现；S1 因连接链完整性采用“族可共享、对象与行不可共享”的操作定义（见 `split-policy.json` 的 `test_isolation_definition` 与论文素材 §5.3）。R3 已核验电缆编号、设备端点、chunk 与机柜 token 的跨划分交集为 0。
- **场景三**：100 题中 36 个锚定主张为 matched，其余为范围不一致、只有设计值、无测试证据或只有验收结论；论文按实证案例定位，不宣称与前两类等量齐观。
- **方案文档**：工作区中的 `docs/research/rag-research-reset-20261107.md` 是用户提供的执行版本（相对 commit `7b57c7c` 有修改）。本阶段以工作区版本为准；建议在投稿前提交该版本，以固定审计基准。

## 4. 状态与限制

- 结构校验：300 题、100/50/150、三场景各 100、30 道显式题 10/10/10、18 个簇配额精确、0 error。
- 独立审核：R1—R5 首轮均已完成并出具结论；阻断/重要项已按归属返工，正在复审（最终通过状态见第 5 节；未通过前不得宣称五项通过）。
- 未完成：领域专家盲审与人工语义评分；37 道 human 题（dev 13 / val 6 / test 18）未人工验收，主指标暂不覆盖；
- 单题口径提示：S3-DEV-VAC-005 的答案为“验收评审报告缺少一行”，按“负向文档事实”记为 answered；同结构的 VAC-007/015 记为 insufficient。该边界已在 R2 复审中列为建议级，阶段二可统一为按目标主张证据状态标注。扫描件仅 4 题使用且已核对第 46 页，其余测试报告扫描件未用作证据。
- 统计效力：按实际簇规模，150 题可检出约 19—22 个百分点；每场景 50 题仅探索性。不得声称 15—17 个百分点的灵敏度。
- 场景一开发集覆盖：34 题中 24 题主族为 L3/L3-EXT/switch，L4-EXT/BRK 各仅 3 个 family 成员；dev 主要承担 L3 主路径的机制迭代，L4/BRK 关系类型覆盖较薄，阶段二迭代时应补足或说明。
- 基线限制：发布清单 `status=live` 缺 `verification.performance_baseline`，项目校验脚本 exit 1；构建 Python 3.11.15 环境不可得；`prompt_version` 标签无代码常量。引用基线时须同时引用冻结记录与 manifest。

## 5. 审核与返工记录

五份独立审核（R1 独立性、R2 真值、R3 泄漏、R4 方案一致性、R5 统计）首轮均判不通过；按“阻断/重要”逐题返工、两次重新合并与封存后，复审结果全部通过：

| 审核 | 首轮 | 复审 | 说明 |
| --- | --- | --- | --- |
| R1 独立性 | 不通过（2 阻断、1 重要） | **通过** | HF-018 与 HF-004 拆分、DE-016 与 DE-001 拆分、DE-005/006 拆分；3 对模板孪生判独立 |
| R2 真值 | 不通过（2 阻断、22 重要） | **通过** | HF-025/HF-018 修复；16 题摘录精确化、6 题补证；status 语义经 SPEC 澄清 |
| R3 泄漏 | 不通过（1 阻断、5 重要） | **通过** | DE-013 去模板；复审新增 F16（禁答项曝光设备名）与 F17（模板依赖）均已修复；行级与设备 token 零重叠 |
| R4 方案一致性 | 不通过（1 阻断、6 重要） | **通过** | 封存覆盖全部含 test 源文件；policy v4 操作定义、身份映射、SEALED 访问策略落实 |
| R5 统计与规模 | 不通过（1 阻断、6 重要） | **通过** | translate 变体、F4 引用、target/fact 对齐修复；sample-size v2 按实际簇规模重算；N1 闭环 |

剩余非阻断建议（通用文本重复、EMIT OCR 残片、dev 覆盖偏 L3、VAC-005 单题口径）已在 §4 与 `delivery-stats.md` 记录；不影响五审通过。
