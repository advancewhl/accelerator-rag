# Stage 2.8.1：双模型检索组合

状态：EXECUTED。冻结 evidence-contract-v2、21 条可回答问题、11 条负例、13 份 PDF 和 4532 个 eligible parents。只编码原始 query，复用现有签名索引；document embedding、LLM 请求均为 0。

| Method | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
| --- | ---: | ---: | ---: | ---: |
| E5 single | 0.3810 | 0.7143 | 0.8571 | 0.5754 |
| Qwen3 single | 0.3333 | 0.6190 | 0.8095 | 0.5111 |
| Language Router | 0.3810 | 0.7619 | 0.9048 | 0.6048 |
| E5 + Qwen3 RRF | 0.3810 | 0.7619 | 0.9048 | 0.5786 |

Language Router：19/21；Dual Dense RRF：19/21。单模型历史指标直接复用；本轮重新检索的两路 Top-5 parent IDs 均与历史 32/32 一致。

## 固定方法与成本

路由仅根据原始 query 是否含明显 CJK 字符选择模型。英文走 E5，中文走 Qwen3。每条 query 一次 encoding/search；部署需能加载两套本地模型。

RRF 对原始 query 分别取两模型 Top-10 canonical parents，按 rank 等权融合，固定 k=60，按 canonical parent ID 去重并返回 Top-5；同分按 parent ID 排序。没有跨模型相加 cosine score。每条 query 两次 encoding/search，不增加 document indexing。本实验共享原始检索缓存，合计 64 次 query encoding/search。

## 精确互补性

- E5_only（3）：`epics-pp`、`shine-control-layers`、`shine-main-linac`。
- Qwen3_only（2）：`xfel-normal-energy`、`cryo-interlock`。
- both_hit（15）：`epics-reconnect`、`epics-cli`、`xfel-rf`、`undulator-tuning`、`xfel-mirror-angle`、`xfel-soft-mono`、`xfel-bpm-types`、`shine-ioc-management`、`interlock-latency`、`interlock-platform`、`cryo-integration`、`timing-wrtd`、`timing-jitter`、`control-slow-interlock`、`shine-compressors`。
- both_miss（1）：`shine-ioc-startup`。

成功集合并集：20/21。Qwen3 相对 E5 的 3 条 Top-5 回退即 E5_only 列表。

候选并集 evidence coverage：20/21。它最多包含 10 个 parent，只表示候选池覆盖上界，不是正式 Hit@5。

## 重点问题

| Method | normal-energy | ioc-startup | cryo-interlock |
| --- | --- | --- | --- |
| E5 single | 0/1 groups | 0/2 groups | 0/3 groups |
| Qwen3 single | complete | 1/2 groups | complete |
| Language Router | complete | 1/2 groups | complete |
| E5 + Qwen3 RRF | complete | 1/2 groups | 2/3 groups |

## 8 条中文可回答问题

| query_id | selected model | E5 rank | Qwen3 rank | router rank |
| --- | --- | ---: | ---: | ---: |
| xfel-normal-energy | Qwen3-Embedding-0.6B | miss | 2 | 2 |
| shine-ioc-startup | Qwen3-Embedding-0.6B | miss | miss | miss |
| interlock-latency | Qwen3-Embedding-0.6B | 3 | 2 | 2 |
| interlock-platform | Qwen3-Embedding-0.6B | 2 | 2 | 2 |
| cryo-interlock | Qwen3-Embedding-0.6B | miss | 5 | 5 |
| control-slow-interlock | Qwen3-Embedding-0.6B | 1 | 1 | 1 |
| shine-compressors | Qwen3-Embedding-0.6B | 4 | 1 | 1 |
| shine-main-linac | Qwen3-Embedding-0.6B | 1 | miss | miss |

## 所有 query 的模型选择

| query_id | detected language | selected model |
| --- | --- | --- |
| epics-pp | en | E5-base |
| epics-reconnect | en | E5-base |
| epics-cli | en | E5-base |
| xfel-rf | en | E5-base |
| xfel-normal-energy | zh | Qwen3-Embedding-0.6B |
| undulator-tuning | en | E5-base |
| xfel-mirror-angle | en | E5-base |
| xfel-soft-mono | en | E5-base |
| xfel-bpm-types | en | E5-base |
| shine-ioc-management | en | E5-base |
| shine-ioc-startup | zh | Qwen3-Embedding-0.6B |
| interlock-latency | zh | Qwen3-Embedding-0.6B |
| interlock-platform | zh | Qwen3-Embedding-0.6B |
| shine-control-layers | en | E5-base |
| cryo-integration | en | E5-base |
| cryo-interlock | zh | Qwen3-Embedding-0.6B |
| timing-wrtd | en | E5-base |
| timing-jitter | en | E5-base |
| control-slow-interlock | zh | Qwen3-Embedding-0.6B |
| shine-compressors | zh | Qwen3-Embedding-0.6B |
| shine-main-linac | zh | Qwen3-Embedding-0.6B |
| no-answer-finance | en | E5-base |
| no-answer-recipe | zh | Qwen3-Embedding-0.6B |
| no-answer-token | en | E5-base |
| no-answer-hard-live-pv | zh | Qwen3-Embedding-0.6B |
| no-answer-hard-live-ioc-count | en | E5-base |
| no-answer-hard-live-interlock | zh | Qwen3-Embedding-0.6B |
| no-answer-hard-live-cryo | en | E5-base |
| no-answer-hard-deployed-firmware | en | E5-base |
| no-answer-hard-current-ioc-ip | zh | Qwen3-Embedding-0.6B |
| no-answer-hard-live-bpm-calibration | en | E5-base |
| no-answer-hard-live-beam-energy | zh | Qwen3-Embedding-0.6B |

## 结论

下一步选择 **A**。实测落入原决策规则未覆盖的 19/21 分支。两种组合 Hit@5 相同，Language Router 的 MRR@5 更高（0.6048 对 0.5786），每条 query 仅需一次 encoding/search，因此下一步选择 A：固化 Language Router。它仍有 IOC startup 和 main linac 两条 miss，尚未达到 20/21；本轮不修改生产默认配置。

- E5 single miss：`xfel-normal-energy`、`shine-ioc-startup`、`cryo-interlock`。
- Qwen3 single miss：`epics-pp`、`shine-ioc-startup`、`shine-control-layers`、`shine-main-linac`。
- Language Router miss：`shine-ioc-startup`、`shine-main-linac`。
- E5 + Qwen3 RRF miss：`shine-ioc-startup`、`cryo-interlock`。

当前所有已验证 embedding retrieval strategy 均无法在 Top-5 完整覆盖 `shine-ioc-startup` 的 multi-evidence query。候选并集的唯一 miss 与实际组合的 miss 列表须分别解读。

以上为固定小样本的描述性结果。11 条负例保留在 JSON 中，但没有校准拒答阈值。索引点数、冻结源码、benchmark、PDF 和 canonical parent 哈希已核对；未修改 Agent，未新增测试、运行 pytest、commit 或 push。完整排名、融合贡献和索引签名见同名 JSON。
