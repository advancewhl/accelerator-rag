# 36 题回归结果分析（2026-10-29）

数据来源：`reports/phase1-m0-20261029/regression-36-http.json`（本次实跑）与 `reports/rag-framework-20261028/http-results.json`（历史全量）。

## 汇总

- 执行：real production HTTP via 127.0.0.1:18003；HTTP 工作线程 2
- HTTP 200：36/36；客户端错误 0
- 状态：{'answered': 24, 'insufficient': 11, 'partial': 1}
- 引用：49 条，涉及 13 份文档
- 耗时（本次）：中位 29.47 s，P95 63.77 s，最大 109.74 s
- 耗时（历史）：中位 17.29 s，P95 42.86 s，最大 59.86 s
- 冻结证据包含（定义：document_id + 物理页 + 归一化摘录被引用 quote 包含）：29/35 个证据组命中；完整覆盖 16/21 道可答题（同一规则回算历史运行：17/21）
- 契约违规：0 项
- 评测基线文件哈希：本次 `f5578371bca4589e…`，历史 `3994d8ebfd9a05b8…`，**不同**

## 逐题结果

| # | id | 期望可答 | 状态 | 历史状态 | 需求支持 | 引用 | 耗时 s | 历史耗时 s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | epics-pp | 是 | answered | answered | 1/1 | 1 | 15.16 | 24.1 |
| 2 | epics-reconnect | 是 | answered | answered | 2/2 | 2 | 38.71 | 33.03 |
| 3 | epics-cli | 是 | answered | answered | 3/3 | 1 | 44.76 | 19.5 |
| 4 | xfel-rf | 是 | answered | answered | 2/2 | 3 | 17.45 | 19.33 |
| 5 | xfel-normal-energy | 是 | answered | answered | 3/3 | 4 | 34.22 | 17.51 |
| 6 | undulator-tuning | 是 | answered | answered | 1/1 | 4 | 40.03 | 20.71 |
| 7 | xfel-mirror-angle | 是 | answered | answered | 1/1 | 1 | 28.43 | 13.05 |
| 8 | xfel-soft-mono | 是 | answered | answered | 1/1 | 2 | 38.94 | 14.01 |
| 9 | xfel-bpm-types | 是 | answered | answered | 2/2 | 2 | 22.62 | 17.64 |
| 10 | shine-ioc-management | 是 | answered | answered | 4/4 | 5 | 109.74 | 59.1 |
| 11 | shine-ioc-startup | 是 | answered | answered | 1/1 | 3 | 19.34 | 16.13 |
| 12 | interlock-latency | 是 | answered | answered | 2/2 | 1 | 30.51 | 14.17 |
| 13 | interlock-platform | 是 | answered | answered | 2/2 | 1 | 36.13 | 13.06 |
| 14 | shine-control-layers | 是 | answered | answered | 1/1 | 2 | 21.3 | 20.43 |
| 15 | cryo-integration | 是 | answered | answered | 2/2 | 3 | 34.35 | 25.85 |
| 16 | cryo-interlock | 是 | answered | answered | 3/3 | 2 | 63.77 | 38.05 |
| 17 | timing-wrtd | 是 | answered | answered | 1/1 | 1 | 25.81 | 19.74 |
| 18 | timing-jitter | 是 | answered | answered | 2/2 | 1 | 23.65 | 14.76 |
| 19 | control-slow-interlock | 是 | answered | answered | 2/2 | 1 | 37.76 | 12.72 |
| 20 | shine-compressors | 是 | answered | answered | 2/2 | 1 | 31.77 | 19.58 |
| 21 | shine-main-linac | 是 | answered | answered | 2/2 | 1 | 26.31 | 17.06 |
| 22 | no-answer-finance | 否 | insufficient | insufficient | 0/1 | 0 | 74.15 | 14.91 |
| 23 | no-answer-recipe | 否 | insufficient | insufficient | 0/2 | 0 | 56.0 | 23.48 |
| 24 | no-answer-token | 否 | insufficient | insufficient | 0/1 | 0 | 16.77 | 14.44 |
| 25 | no-answer-hard-live-pv | 否 | insufficient | insufficient | 0/1 | 0 | 5.58 | 8.83 |
| 26 | no-answer-hard-live-ioc-count | 否 | insufficient | insufficient | 0/1 | 0 | 6.83 | 9.45 |
| 27 | no-answer-hard-live-interlock | 否 | insufficient | insufficient | 0/1 | 0 | 5.86 | 7.49 |
| 28 | no-answer-hard-live-cryo | 否 | insufficient | insufficient | 0/1 | 0 | 18.89 | 7.28 |
| 29 | no-answer-hard-deployed-firmware | 否 | insufficient | insufficient | 0/1 | 0 | 5.78 | 6.41 |
| 30 | no-answer-hard-current-ioc-ip | 否 | insufficient | insufficient | 0/1 | 0 | 7.01 | 7.36 |
| 31 | no-answer-hard-live-bpm-calibration | 否 | insufficient | insufficient | 0/1 | 0 | 6.73 | 7.16 |
| 32 | no-answer-hard-live-beam-energy | 否 | insufficient | insufficient | 0/1 | 0 | 7.73 | 7.89 |
| 33 | cryo-original | 否 | answered | answered | 3/3 | 2 | 51.28 | 42.86 |
| 34 | cryo-paraphrase | 否 | answered | answered | 2/2 | 2 | 41.34 | 33.25 |
| 35 | cryo-missing-details | 否 | partial | partial | 0/2 | 1 | 38.79 | 36.39 |
| 36 | xfel-version-scopes | 否 | answered | partial | 3/3 | 2 | 31.22 | 59.86 |

## 状态相对历史的变化

- `xfel-version-scopes`：partial → answered

## 契约违规

- 无（状态一致性、引用存在性、文档登记、页码范围、chunk 前缀、重复引用均通过）

## 冻结证据逐题包含情况

| id | 证据组 | 命中 |
| --- | --- | --- |
| epics-pp | 2 | 2 |
| epics-reconnect | 1 | 1 |
| epics-cli | 3 | 3 |
| xfel-rf | 2 | 2 |
| xfel-normal-energy | 1 | 1 |
| undulator-tuning | 1 | 1 |
| xfel-mirror-angle | 1 | 1 |
| xfel-soft-mono | 1 | 0 |
| xfel-bpm-types | 1 | 1 |
| shine-ioc-management | 3 | 1 |
| shine-ioc-startup | 2 | 2 |
| interlock-latency | 1 | 0 |
| interlock-platform | 2 | 2 |
| shine-control-layers | 5 | 4 |
| cryo-integration | 1 | 1 |
| cryo-interlock | 3 | 3 |
| timing-wrtd | 1 | 0 |
| timing-jitter | 1 | 1 |
| control-slow-interlock | 1 | 1 |
| shine-compressors | 1 | 1 |
| shine-main-linac | 1 | 1 |

## 解释边界

- 本表只评价接口行为（状态、引用、契约）与冻结证据的逐字包含关系，**不评价答案语义是否正确**。
- `answered` 是模型自报状态，不等于人工判定正确。
- 本次无 trace 访问权限，未复核轮次、子集预算与补检索过程。
- 36 题属于开发回归集，不是独立测试集；不得据此宣称泛化性能。
