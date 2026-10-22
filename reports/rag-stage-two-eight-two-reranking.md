# Stage 2.8.2：双模型候选重排

| Method | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
| --- | ---: | ---: | ---: | ---: |
| E5 single | 0.3810 | 0.7143 | 0.8571 | 0.5754 |
| Language Router | 0.3810 | 0.7619 | 0.9048 | 0.6048 |
| E5 + Qwen3 RRF | 0.3810 | 0.7619 | 0.9048 | 0.5786 |
| E5 + Qwen3 + Reranker | 0.3810 | 0.8095 | 0.9524 | 0.6071 |

状态：EXECUTED。Top-10 + Top-10 canonical parent candidate coverage：20/21；实际 winning passage coverage：19/21；final reranked Hit@5：20/21。候选覆盖率不是正式 Top-5 指标。

## 方法与模型

复用 E5 和 Qwen3-Embedding-0.6B 既有签名索引，对每条原始 query 各取 Top-10 canonical parents。两路 Top-10 parent IDs 与 Stage 2.8.1 均为 32/32 一致。按 parent ID 去重，只将各模型实际 winning passage text 送入本地 reranker；同 parent 的不同 passage 分别评分，完全相同文本合并并保留来源。parent 取 child 最大分数，最终按 reranker 分数排序，返回 Top-5 canonical KnowledgeChunk。未混加 cosine score。

采用下载版本的[官方模型说明](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)中的 Transformers contract：固定默认 instruction、system/user/assistant 前后缀、末 token 的 yes/no logits 归一化概率。CPU FP32，左填充，固定 batch size 4、max length 8192；无截断。只计算末位置 logits，不生成答案。所有 benchmark 推理离线执行。

模型 revision：`e61197ed45024b0ed8a2d74b80b4d909f1255473`。本地大小：1.125 GiB。完整 weights/config/tokenizer SHA256、prompt 和配置见 JSON。

## 命中变化

相对 E5 single：

- 新增完整命中：`cryo-interlock`、`xfel-normal-energy`。
- 丢失完整命中：无。

相对 Language Router：

- 新增完整命中：`shine-main-linac`。
- 丢失完整命中：无。

## 重点问题

| Method | normal-energy | ioc-startup | main-linac | cryo-interlock |
| --- | --- | --- | --- | --- |
| E5 single | 0/1 groups | 0/2 groups | complete | 0/3 groups |
| Language Router | complete | 1/2 groups | 0/1 groups | complete |
| E5 + Qwen3 RRF | complete | 1/2 groups | complete | 2/3 groups |
| E5 + Qwen3 + Reranker | complete | 1/2 groups | complete | complete |

候选完整但 final Top-5 仍 miss：无。

parent 完整、实际 winning passages 不完整：`shine-main-linac`。canonical parent coverage 不能证明重排器已看到这些证据。正式指标仍按冻结 canonical parent evidence contract 计算；即使 parent 最终命中，也须区分是否由已评分 passage 支持。

最终 miss：`shine-ioc-startup`。

最终 Top-5 winning passages 的证据覆盖：19/21。这是来源诊断，不替代冻结的 canonical parent 指标。

IOC startup 的候选缺失与重排失败分别记录在 JSON。若候选仍为 1/2 groups，重排无法补齐缺失证据。未为任何 query 改写、扩 Top-K 或特判。

## 性能与完整性

CPU threads：6；model load：1.26 s；32 条 query 总 rerank：801.83 s。平均每条 query：16.25 个 parents、16.78 个 passages；共评分 537 对。最大输入 839 tokens，无截断。

冻结 evidence-contract-v2、21 条可回答问题、11 条负例、13 份 PDF、4532 个 eligible parents。11 条负例均得到 5 条结果，score 有限且位于 0～1；没有阈值或拒答结论。document embedding 为 0，未重建索引；冻结文件/PDF/parent 哈希和索引点数核对通过。

补充：Qwen3 single Hit@5 为 17/21。主表历史指标直接复用。每个最终结果的来源、两路原始 rank、winning passage ID/text/source 和全部候选评分见 JSON。

## 决定

**A**：达到 20/21，推荐固化双模型候选生成加 Qwen3-Reranker-0.6B；停止本轮实验。

未新增测试或运行 pytest，未修改 Agent、benchmark、evidence、chunking 或 eligibility，未调用 qwen3-vl，未 commit 或 push。本轮结束，不自动进入下一阶段。
