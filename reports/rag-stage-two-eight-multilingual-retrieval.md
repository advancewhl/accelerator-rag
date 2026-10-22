# Stage 2.8：共享 QueryPlan 双模型检索实验

状态：EXECUTED。32 条 query 使用同一套 plans；两模型分别复用已有 document vectors。

| Method | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
| --- | ---: | ---: | ---: | ---: |
| E5 single | 0.3810 | 0.7143 | 0.8571 | 0.5754 |
| E5 + multi-query | 0.3810 | 0.6190 | 0.7143 | 0.5159 |
| Qwen3 single | 0.3333 | 0.6190 | 0.8095 | 0.5111 |
| Qwen3 + multi-query | 0.3333 | 0.6190 | 0.8095 | 0.4849 |

| Method | normal-energy | ioc-startup | cryo-interlock |
| --- | --- | --- | --- |
| E5 single | 0/1 groups | 0/2 groups | 0/3 groups |
| E5 + multi-query | 0/1 groups | 1/2 groups | 2/3 groups |
| Qwen3 single | complete | 1/2 groups | complete |
| Qwen3 + multi-query | complete | 1/2 groups | complete |

## 结论

保留 E5 single 为正式 Dense；不把本轮 multi-query 固化为默认检索能力。E5 Hit@5 从 18/21 降至 15/21；Qwen3 维持 17/21，MRR@5 下降；两者均未解决 IOC startup。按用户约定，下一步选择 C：更大 embedding model 比较，本轮不下载。

IOC startup 只生成一条英文改写，cryo 的三条改写也较重叠。因此本轮否定的是这套固定 QueryPlan + RRF 方案的收益，不能据此证明有效 decomposition 无用，或证明 embedding 模型容量是唯一瓶颈。

E5 + multi-query 没有新增完整命中，退步为 `control-slow-interlock`、`shine-compressors`、`shine-main-linac`。Qwen3 + multi-query 没有新增或丢失 Hit@5 成功 case，但 MRR@5 从 0.5111 降至 0.4849。两模型的原 query 分支都复现了全部 32 条 single Top-5 parent 排名。

## 实际生成的 subqueries

以下文本直接取自 provider 的固定输出，未手工补写。三条重点问题的输出均为问句，没有填入能量数值、端口或设备连接答案。

### xfel-normal-energy

原 query：欧洲 XFEL 常规运行时电子束能量是多少，与最高设计能量有何区别？

1. What is the electron beam energy during regular operation at European XFEL?
2. What is the maximum designed electron beam energy at European XFEL?
3. What is the difference between the regular operation electron beam energy and the maximum designed energy at European XFEL?

审阅：完成了跨语言改写，并拆开运行能量与最高设计能量。

### shine-ioc-startup

原 query：SHINE 中 IOC 启动后会向管理系统提交哪些信息？

1. What information does SHINE IOC submit to the management system after startup?

审阅：仅完成英文改写，没有形成多个独立检索意图。

### cryo-interlock

原 query：SHINE 低温测试装置如何通过主联锁 PLC 和 CPLD 实现低温设备保护？

1. How does the SHINE low-temperature test device achieve low-temperature equipment protection through the main interlock PLC and CPLD?
2. What is the role of the main interlock PLC and CPLD in protecting low-temperature equipment in the SHINE system?
3. How do the PLC and CPLD in the SHINE low-temperature test device work together to ensure equipment safety?

审阅：三条表述相近，没有分别拆出 PLC 与 CPLD 的独立职责。

## 三条问题的证据覆盖诊断

| Method | Query | Groups @5 | Groups @10 | Candidate union | First complete rank |
| --- | --- | --- | --- | --- | --- |
| E5 single | xfel-normal-energy | 0/1 | 0/1 | — | 未完整 |
| E5 single | shine-ioc-startup | 0/2 | 0/2 | — | 未完整 |
| E5 single | cryo-interlock | 0/3 | 0/3 | — | 未完整 |
| E5 + multi-query | xfel-normal-energy | 0/1 | 1/1 | 1/1 | 7 |
| E5 + multi-query | shine-ioc-startup | 1/2 | 1/2 | 1/2 | 未完整 |
| E5 + multi-query | cryo-interlock | 2/3 | 2/3 | 3/3 | 未完整 |
| Qwen3 single | xfel-normal-energy | 1/1 | 1/1 | — | 2 |
| Qwen3 single | shine-ioc-startup | 1/2 | 1/2 | — | 未完整 |
| Qwen3 single | cryo-interlock | 3/3 | 3/3 | — | 5 |
| Qwen3 + multi-query | xfel-normal-energy | 1/1 | 1/1 | 1/1 | 3 |
| Qwen3 + multi-query | shine-ioc-startup | 1/2 | 1/2 | 1/2 | 未完整 |
| Qwen3 + multi-query | cryo-interlock | 3/3 | 3/3 | 3/3 | 4 |

Candidate union 指原 query 与所有 subqueries 各自 Top-10 的 parent 并集，不是扩大正式 Top-5。IOC startup 的两个模型并集都只含第 1 组，因此融合无法补出第 2 组。E5 的 normal-energy 在融合第 7 位才完整；cryo 的候选并集虽有 3/3 组，融合 Top-10 只剩 2/3，存在 RRF 证据覆盖损失。

完整 Top-10 parent、document、物理页、score、匹配证据组，以及每个 parent 的 subquery 来源、原始排名和融合贡献，均保存在配套 JSON。

## 固定条件与复用记录

- 冻结 `evidence-contract-v2`：21 条 answerable、11 条 negatives；13 份 PDF、4532 个 eligible canonical parents。
- 固定原 query 加最多 3 条 subqueries；每条取 Top-10 parent；同一 Dense 模型内使用 RRF，参数 `k=60`；正式指标仍为 Top-5。
- 共享 plans SHA256：`f2e74024117642a19bc2899f13aeb9226def64f165fd74a216846293fae2d98a`。两模型读取同一文件，评估后哈希未变。
- planner 只接收原始 query、固定 system prompt 和 schema；未接收 PDF、passage、证据组、页码、ID、score 或模型成败。
- provider 为已授权的 `qwen3-vl`，经 `zyf` 临时 SSH 转发访问原地址。转发已关闭，凭证未写入 plans 或发送给模型。
- E5 复用 4746 个历史 passage 的向量。历史 collection 未签名，正常被 contract 拒绝；经模型身份与全部 passage 核验后，在独立副本补签。前后向量 SHA256 一致，原向量逐字节不变。
- Qwen3 直接复用 4532 个已签名 passage 向量。两模型本轮 document embedding 数量均为 0，点数前后一致。
- 两模型均完成全部 11 条负例检索，均返回结果；无 threshold，不据此宣称具备拒答能力。RRF score 不与 cosine 混比。
- 未下载更大模型，未修改 benchmark、evidence 或 Agent；未新增测试，未跑 pytest，未 commit 或 push。

## 原模型身份与单查询记录

| Model | Resolved revision | Dimensions | Context | Passages | Single Hit@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| BAAI/bge-m3 | `5617a9f61b028005a4858fdac845db406aefb181` | 1024 | 8192 | 4532 | 0.7619 |
| Qwen/Qwen3-Embedding-0.6B | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` | 1024 | 32768 | 4532 | 0.8095 |

BGE-M3 的单查询结果为 16/21，三条重点问题 Top-5 依次为 0/1、1/2、2/3 组。本次续验按用户要求只对 E5 与 Qwen3 做共享 plans 比较。原有权重清单、模型配置、tokenizer SHA256、模型大小与单查询诊断继续保留在 JSON。

[BGE-M3 官方模型卡](https://huggingface.co/BAAI/bge-m3/blob/5617a9f61b028005a4858fdac845db406aefb181/README.md)；[Qwen3 官方模型卡](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/blob/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3/README.md)。
