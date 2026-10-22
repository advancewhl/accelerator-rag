# RAG Stage 2.7.1：索引契约与证据审核

本轮只验证源证据并重判已保存的 Top-5。所有小样本指标仅用于诊断。

## Dense index contract

每个 point 保存完整 contract 与 dense_index_contract_id。初始化绑定模型指纹和 passage policy；非空 collection 在读取、写入、删除前完整扫描，search 在 query encoding 前验证。不匹配或缺少签名均拒绝，要求新 collection 或完整重建。模型指纹按加载实例缓存。

contract 包含：requested model、weights manifest、model config、encoding config、tokenizer、query template、document prefix/template、dimension、max sequence length、normalization、distance、passage contract ID/algorithm。路径、batch、线程和耗时不参与身份。

持久化测试覆盖同 contract 更新 A 时 B 的 vector/payload 不变、不同 passage policy 零写入拒绝、768 维不同模型在 query encode 前拒绝，以及 reopen 后继续拒绝。历史 Stage 2.7 索引未加签、未打开，保留只读 measurement；正式 runtime 拒绝无签名的历史 payload。

- `BAAI/bge-small-zh-v1.5`：`60798827a14d109fde21123738183e743b8868205540dff4023303be154e075c`。
- `intfloat/multilingual-e5-base`：`ccd4601d1698d3bff5b46589f11fc036e035ca57c1d8d179cd56b6b2d50e16f4`。
- `BAAI/bge-base-zh-v1.5`：`095ac254cffadf6f49086e3a0e70f8cc72f0e27d1328ab5ece24c4933328ae3c`。

## Evidence contract v1 → v2

审核 21/21 条可回答问题，每条搜索全部 13 份 PDF。原有 37 个 alternatives，新增 39 个，修订后共 76 个。11 条问题新增证据。查询文本、数量、类别、语言与 group 的 AND/OR 语义保持不变。

21 answerable queries × all 13 raw PDFs; normalized exact repeats, semantic terminology probes, BM25 broad query/probe search; source review independent of Stage 2.7 model Top-5. No claim of exhaustive paraphrase recall.

问题 | 新增 alternatives | 审核说明
--- | ---: | ---
epics-pp | 9 | DB input link 的 Passive/PP 条件与取值前处理时序分别保留。只增加时序的实例不替代条件组；PVA、CA link、PACT 防循环语义不混用。
epics-reconnect | 1 | docs p63 是独立重复说明。p372 的断连重试属于机制相关段，跨页主语且重启条件不完整；pvAccess 的重连规则不替代 CA。
epics-cli | 2 | 接受明确解释 read/write 工具角色的 p8。裸命令清单、不同 PV 的命令回显、dbCa 内部 API、caExample/caMonitor 示例程序均不替代命名 PV 的完整示例。p10 仅说明 deadband，不单独给出监视命令。
xfel-rf | 17 | 频率与 20 GeV 设计能量仍是两个 AND 组。接受本装置 RF/加速结构与设计能量的重复参数说明；FLASH 历史、RF gun 单独频率、噪声测试振荡器、参考文献及其他装置不接受。
xfel-normal-energy | 2 | p67 与 p68 同时区分 17.5 GeV 基准运行和 20 GeV 设计上限。只出现 17.5 GeV、升级到 24 GeV、束线吸收体能量或新版不同设计范围均不足以覆盖整组。这里评估的是源文档设计陈述，不将 2007 年预测表述为当前实测运行事实。
undulator-tuning | 0 | 其余 CDR 页面仅有装置标题、晶体结构或调谐方法。2007 TDR p221–225 分别描述自发辐射、单色器、固定能量调隙，未在一个 eligible canonical chunk 中完整给出原组的窄带选择与调段用途；p230/231 为阿秒/自种子方案。optics p131 说明 K 调节和自发辐射但未说明窄带选择，不增加。
xfel-mirror-angle | 0 | p44 有 6–20 mrad，但没有从旧范围缩小及波前畸变原因。p29/31 是一般镜面误差和校正，p135 为安装月份，p161/162 为文献；旧 TDR 范围不说明更改原因。
xfel-soft-mono | 1 | p43 同时说明改善时间响应和三个端口共享垂直 in-line 光束，合法替代。p9 是布局图解，未说明设计改变原因。
xfel-bpm-types | 1 | p2 直接比较 re-entrant cavity 与 standard button 的分辨率。2007 TDR p138 把 striplines 也归入旧版常规方案，未与 2010 版标准 button 分类完全一致；SHINE BPM 不替代 European XFEL。
shine-ioc-management | 2 | p1 摘要提供 CA/pvAccess 采集与数据库存储；p3 结论提供 MySQL/web 显示。p2 注册段没有 server address，p3 后续解析没有 startup trigger，均不单独替代完整注册组；其他 MySQL 泛论不足。
shine-ioc-startup | 1 | 新增 p3 IOC panel 完整陈述安装路径、启动时间和 records；原 p3 IP、CA server/repeater ports 组仍独立要求。p1 摘要没有启动时间/端口，不能使整条 complete。
interlock-latency | 1 | p7 测试说明明确重述单节点 10 µs 和节点间 100 µs 设计要求，接受。p8 只报告实测值；早期 presentation p21/23 使用 ≤ 而现组为 <，保守不等价；慢联锁 ms、其他设备微波参数均拒绝。
interlock-platform | 0 | 芯片型号与 Verilog 两组原证据唯一。p2 只述 FPIO/FPGA，p3 工具表的 ISE/Spartan 6 不给完整芯片型号；其他 FPGA 方案不等价。
shine-control-layers | 0 | 完整四层名称及职责集中于原 p1。status p3 是高层软件三层架构、cryo p3 是低温三层架构，不能替代全设施四层；preliminary 的功能划分不相同。
cryo-integration | 0 | 原 cryo p3 同时给 PLC 逻辑/PID 和 soft IOC 采集/PV 转换。p6 为非关键流程可迁移至 IOC 的例外，不能替代常规分工；preliminary p380 只是全设施泛论，未给低温 PLC/PID 分工。
cryo-interlock | 0 | 三对 DI/DO、master PLC 逻辑交换、CPLD 电光转换三组仍全保留。原 cryo p6 是唯一完整描述；p8 仅缩写和参考资料；preliminary p129/367/380 没有测试装置对应连接关系。
timing-wrtd | 0 | 只有 timing p2 同时指出高重复率、需 10 Gigabit WR、尚无商业产品。p5 只给外部参考文献；一般 WR 介绍不等价。
timing-jitter | 0 | 只接受 Prototype II p5 的 beam-sync、slave/reference 与 random-event 数值。p2/4 是 Prototype I 或测试方法，p3 没有测量数值，不能替换。
control-slow-interlock | 0 | 仅 presentation p21 同时给慢联锁站内 20 ms、站间 100 ms。fast-interlock 文献为快联锁 µs 指标，p2 慢联锁毫秒级没有两项界限。
shine-compressors | 0 | 仅 p61 完整解释 BC1 尾场与空间电荷权衡、BC2 CSR 与稳定性、270 MeV/2.1 GeV。p60/63/68 只给布局和能量；p279 为诊断布局，不给选择原因。原单组要求没有缩短。
shine-main-linac | 2 | p60 连续完整摘录覆盖超导连续波和最终 8 GeV，已加入；p63 的杂散电子风险及功能段说明也同时具备两事实。p59 只有能量，p98 为其他装置耦合器，均不足。长 excerpt 为保留单组语义所必需，不能将两个不相邻子串拼接。

逐条原始 groups、术语搜索、宽 BM25 候选、物理页、接受/拒绝原因及合法 canonical chunk ID 见同名 JSON。审核依据源文本，未以模型命中作为接受条件。候选召回不构成全语料不存在其他改写的数学证明。

## 重判指标

Retriever | v1 Hit@1/3/5 | v2 Hit@1/3/5 | v1 MRR@5 | v2 MRR@5
--- | --- | --- | ---: | ---:
BM25 | 0.3810/0.6667/0.7143 | 0.5238/0.7619/0.7619 | 0.5198 | 0.6270
BAAI/bge-small-zh-v1.5 | 0.0952/0.2381/0.4286 | 0.1905/0.2857/0.4286 | 0.2040 | 0.2635
intfloat/multilingual-e5-base | 0.2857/0.6190/0.7619 | 0.3810/0.7143/0.8571 | 0.4778 | 0.5754
BAAI/bge-base-zh-v1.5 | 0.0952/0.4286/0.6190 | 0.1429/0.4762/0.6190 | 0.2754 | 0.3111

### 判断变化

- BM25：`epics-pp` 完整首次排名 1 → 1，Top-5 groups 2 → 2；`epics-reconnect` 完整首次排名 1 → 1，Top-5 groups 1 → 1；`xfel-rf` 完整首次排名 None → 3，Top-5 groups 1 → 2；`xfel-soft-mono` 完整首次排名 2 → 1，Top-5 groups 1 → 1；`interlock-latency` 完整首次排名 3 → 1，Top-5 groups 1 → 1；`shine-main-linac` 完整首次排名 4 → 1，Top-5 groups 1 → 1。
- BAAI/bge-small-zh-v1.5：`epics-reconnect` 完整首次排名 4 → 1，Top-5 groups 1 → 1；`shine-ioc-management` 完整首次排名 None → None，Top-5 groups 0 → 1；`interlock-latency` 完整首次排名 2 → 1，Top-5 groups 1 → 1。
- intfloat/multilingual-e5-base：`epics-reconnect` 完整首次排名 1 → 1，Top-5 groups 1 → 1；`xfel-rf` 完整首次排名 5 → 2，Top-5 groups 2 → 2；`xfel-soft-mono` 完整首次排名 2 → 1，Top-5 groups 1 → 1；`shine-ioc-management` 完整首次排名 None → 4，Top-5 groups 2 → 3；`interlock-latency` 完整首次排名 3 → 3，Top-5 groups 1 → 1；`shine-main-linac` 完整首次排名 None → 1，Top-5 groups 0 → 1。
- BAAI/bge-base-zh-v1.5：`xfel-rf` 完整首次排名 None → None，Top-5 groups 0 → 1；`xfel-bpm-types` 完整首次排名 1 → 1，Top-5 groups 1 → 1；`shine-ioc-management` 完整首次排名 4 → 3，Top-5 groups 3 → 3；`shine-ioc-startup` 完整首次排名 None → None，Top-5 groups 1 → 1；`interlock-latency` 完整首次排名 3 → 1，Top-5 groups 1 → 1。

## E5 与 BM25 互补性

- both_hit（16）：`epics-pp`、`epics-reconnect`、`epics-cli`、`xfel-rf`、`undulator-tuning`、`xfel-mirror-angle`、`xfel-soft-mono`、`xfel-bpm-types`、`interlock-latency`、`interlock-platform`、`cryo-integration`、`timing-wrtd`、`timing-jitter`、`control-slow-interlock`、`shine-compressors`、`shine-main-linac`。
- bm25_only（0）：无。
- dense_only（2）：`shine-ioc-management`、`shine-control-layers`。
- both_miss（3）：`xfel-normal-energy`、`shine-ioc-startup`、`cryo-interlock`。

## 跨语言证据覆盖

Retriever | 问题 | Top-5 满足 group | 完整覆盖
--- | --- | --- | ---
BM25 | xfel-normal-energy | 0/1（[]） | False
BM25 | shine-ioc-startup | 0/2（[]） | False
BM25 | cryo-interlock | 0/3（[]） | False
BAAI/bge-small-zh-v1.5 | xfel-normal-energy | 0/1（[]） | False
BAAI/bge-small-zh-v1.5 | shine-ioc-startup | 0/2（[]） | False
BAAI/bge-small-zh-v1.5 | cryo-interlock | 0/3（[]） | False
intfloat/multilingual-e5-base | xfel-normal-energy | 0/1（[]） | False
intfloat/multilingual-e5-base | shine-ioc-startup | 0/2（[]） | False
intfloat/multilingual-e5-base | cryo-interlock | 0/3（[]） | False
BAAI/bge-base-zh-v1.5 | xfel-normal-energy | 0/1（[]） | False
BAAI/bge-base-zh-v1.5 | shine-ioc-startup | 1/2（[0]） | False
BAAI/bge-base-zh-v1.5 | cryo-interlock | 2/3（[1, 2]） | False

## 排名完整性与可复现性

0 embeddings recomputed；0 document vectors changed；全部 Stage 2.7 Top-5 排名、父 Chunk payload、score 和完整 passage_trace 的 canonical SHA-256 前后一致。JSON 包含每个 retriever 的摘要、历史 SQLite 文件摘要及完整重判 cases。

passage_trace 中的 matched_evidence / matched_evidence_groups 保留 v1 历史注释，不代表 v2 判断；v2 first_complete_passage_rank 单独重算。

measurement + v1/v2 ground truth + 人工 review artifact 可离线重建报告。Stage 2.7 Markdown 已在临时目录逐字重建并比对摘要，历史文件不修改。

## 最终判断

B．继续 cross-language / multi-evidence Dense investigation。v2 下 E5 完整命中 18/21，BM25 完整命中 16/21；两者 both_hit 为 16，bm25_only 为 0，dense_only 为 IOC management 和 control layers 两条。三个共同 miss 恰为三条跨语言问题。BGE-base 对 IOC startup 有 1/2、cryo interlock 有 2/3 部分覆盖，说明需要定位完整证据召回和排序缺口。审核确实修复了 benchmark 漏标，但现有结果不足以支持直接实施 RRF；本轮不执行下一阶段。

## 验证

- pytest -q：317 passed。
- ruff check .：通过。
- git diff --check：通过。
- python scripts/corpus_inventory.py：13 份 registered PDFs，validation OK。
- 离线 audit/rejudge：全部 v1 指标重现，v2 全部 alternatives 通过 raw PDF 与 eligible canonical chunk 强校验。
- 在阻断模型加载、document/query encoding 与 Qdrant 打开的守卫下运行离线生成器；未触发任何被阻断操作。
- 三个历史 SQLite 文件、Stage 2.7 JSON/Markdown 及 13 份原始 PDF 的 SHA-256 未变；所有 Top-5 ranking 摘要一致。
- Stage 2.7 Markdown 由保存的 measurement 与独立人工 review artifact 逐字重建。
