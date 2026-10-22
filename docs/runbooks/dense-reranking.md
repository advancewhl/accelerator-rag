# 双模型检索与重排

## 当前方案

Stage 2.8.2 采用 E5 与 Qwen3-Embedding-0.6B 生成候选，再用 Qwen3-Reranker-0.6B 重排。两路各取前 10 个 canonical parent。相同 parent 去重，各模型实际命中的 passage 分别评分；相同文本仅评分一次。parent 取最高 child 分数，返回前 5 个 parent。

该方案保留 `KnowledgeChunk` 的来源路径和物理页码。重排分数不与 cosine 分数相加。通用检索 CLI 仍使用显式选定的 BM25 或单路 Dense。

## 前置条件

在项目根目录激活 `accelerator-rag` Conda 环境，并安装开发依赖。准备 Registry 中的 13 份 PDF、冻结的评测文件、历史报告和离线模型。原始文件、模型与索引均在 Git 之外，单独克隆仓库不能直接重跑完整实验。

Stage 2.8.1 使用 Stage 2.8 报告中记录的模型路径、签名索引和固定查询。Stage 2.8.2 继续读取 Stage 2.8.1 JSON，并依赖 `tmp/stage-two-eight-two/` 中的重排模型与下载来源记录。先逐项核对脚本中的路径，避免误写既有实验目录。

在线 query planner 依赖 Model Provider，本次 RAG 提交不包含该集成。Stage 2.8 的固定 plans、提示词和来源记录保存在报告 JSON 的 `query_planning` 中。离线分析可读取这些固定 plans，无需调用模型服务。

## 运行与产物

以下命令读取历史索引并覆盖对应实验报告。执行前备份同名 JSON、Markdown 和实验目录。脚本按固定 CPU 配置运行，不调用 Agent 或在线模型服务。

```bash
conda activate accelerator-rag
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python scripts/stage281_dense_composition.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python scripts/stage282_reranking.py --prepare
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python scripts/stage282_reranking.py
```

Stage 2.8.1 输出 `reports/rag-stage-two-eight-one-dense-composition.json` 和同名 Markdown。Stage 2.8.2 输出 `reports/rag-stage-two-eight-two-reranking.json` 和同名 Markdown。JSON 保存完整候选、排名、实际评分 passage、模型指纹与索引完整性记录。

重排采用官方模型契约中的 yes/no logits，CPU FP32，batch size 为 4，最大输入为 8192 tokens。超长输入立即失败，不静默截断。模型权重需单独下载；本次命令不会下载权重。

## 结果解释

固定评测采用 `evidence-contract-v2`，包括 21 条可回答问题和 11 条负例。双模型重排的 Hit@5 为 20/21，MRR@5 为 0.6071；实际评分 passage 的证据覆盖为 19/21。

`shine-ioc-startup` 的候选仍缺少一组证据，重排无法补齐。`shine-main-linac` 的完整 parent 命中不等于被评分 passage 含完整证据。必须同时检查 parent 指标和 passage 来源诊断。

全部负例仍返回结果，当前没有拒答阈值。32 条查询共评分 537 对，总重排耗时为 801.83 s。该耗时来自单次 CPU 实验，不能外推为线上吞吐量。

## 故障与回滚

模型或索引缺失时，先按报告中的指纹恢复到独立目录，再执行。遇到签名不匹配，保留原目录并停止运行，核查权重、编码模板、tokenizer 与 passage 配置；避免直接给未知索引补签。

脚本不重建 document vectors。哈希、点数或历史排名核验失败时，先定位差异，再决定是否重建独立实验索引。回滚只需恢复备份的报告与实验目录；原始 PDF 和单路检索入口保持可用。
