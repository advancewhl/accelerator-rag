# Stage 2.7 受控 Embedding 模型比较

## 环境与边界

使用 `accelerator-rag` Conda 环境。正式编码固定为 CPU、6 个 PyTorch threads、batch size 32。模型下载与正式离线运行分开。下载已获用户授权，比较程序始终使用 `local_files_only=True`。

固定 13 份 registered PDFs、`pdf-chunks-v3`、canonical `KnowledgeChunk`、retrieval eligibility、32 条查询和 `evidence-contract-v1`。BM25 只作固定 control。程序校验历史 source/query hashes、资格策略以及 BM25 全部排名和分数。

候选为 `BAAI/bge-small-zh-v1.5`、`intfloat/multilingual-e5-base` 和 `BAAI/bge-base-zh-v1.5`。分别代表历史 control、多语言模型和较大的中文 BGE。不同模型使用各自 tokenizer，同用 `dense-passages-v1`、guard 16、overlap 32 和自然边界策略。没有 Hybrid、reranker 或生成步骤。

## 下载与编码契约

BGE-small 使用已有 Hugging Face cache。新候选下载到工作区 `tmp/stage-two-seven/models/`，模型权重不进入 Git。

```python
from huggingface_hub import snapshot_download, hf_hub_download

snapshot_download(
    "intfloat/multilingual-e5-base",
    local_dir="tmp/stage-two-seven/models/intfloat--multilingual-e5-base",
    allow_patterns=["*.json", "*.txt", "*.safetensors", "README.md", "sentencepiece.bpe.model"],
    ignore_patterns=["onnx/*", "openvino/*"],
)
snapshot_download(
    "BAAI/bge-base-zh-v1.5",
    local_dir="tmp/stage-two-seven/models/BAAI--bge-base-zh-v1.5",
    allow_patterns=["*.json", "*.txt", "README.md"],
    ignore_patterns=["onnx/*", "openvino/*"],
)
hf_hub_download(
    "BAAI/bge-base-zh-v1.5", "pytorch_model.bin",
    local_dir="tmp/stage-two-seven/models/BAAI--bge-base-zh-v1.5",
)
```

复现正式报告时，将 JSON 中 `download_provenance.downloaded_commit` 显式传给下载函数的 `revision` 参数。这个值来自本地下载记录，不由模型名称或目录名推断。

下载完成后，先核对本地 `README.md`、`modules.json` 和 `sentence_bert_config.json`。来源为模型发布者的 [E5 模型卡](https://huggingface.co/intfloat/multilingual-e5-base)和 [BGE-base 模型卡](https://huggingface.co/BAAI/bge-base-zh-v1.5)，正式运行使用下载后的本地文件。

`EmbeddingModel` 明确定义支持的三个检索契约。BGE query 使用 `为这个句子生成表示以用于检索相关文章：{query}`，文档无前缀。E5 query 使用 `query: {query}`，文档使用 `passage: `。两个 BGE 使用模型自带 CLS pooling，E5 使用模型自带 mean pooling。向量均归一化。其他未知模型直接拒绝，先核实契约再增加候选。

E5 前缀参与最终输入 token 审计和 passage contract；正文 offset 仍映射原始 canonical 文本。完整 passage 在实际编码前再次检查上限，超限立即失败。

## 历史验证与运行

以下命令记录 Stage 2.7 的历史 measurement 环境。Stage 2.7.1 已将当前标注升级为 v2，且正式 runtime 拒绝历史无签名 collection。当前复现 judgment 和最终报告应使用[离线审核与重判](evidence-audit.md)，不重新执行本节编码命令。

```bash
conda activate accelerator-rag
pytest -q
ruff check .
git diff --check
python scripts/corpus_inventory.py

OMP_NUM_THREADS=6 MKL_NUM_THREADS=6 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m accelerator_rag.retrieval.model_baseline \
  --models BAAI/bge-small-zh-v1.5 intfloat/multilingual-e5-base BAAI/bge-base-zh-v1.5 \
  --threads 6 --batch-size 32
```

每个模型使用独立 Qdrant path 和 `knowledge_stage27_` collection。指纹记录 requested name、本地路径、可从 cache 路径证明的 snapshot ID、config/tokenizer hashes、逐文件权重 SHA-256、权重 manifest、维度、序列上限和 query/document 模板。权重按 1 MiB 块读取。

BGE-small 逐条验证历史 passage ID、正文和完整父 Chunk，然后复制已有向量到独立 Stage 2.7 集合。程序重新执行全部查询，并检查排名和指标与 Stage 2.6 相同。历史报告没有权重 fingerprint，无法事后证明当时权重的字节身份；本次报告明确记录这一限制。历史实际 embedding 时间单独保留，复制耗时不冒充编码耗时。

完成一个模型后写入 `measurement.json`，保留真实测量。完成的索引有 `model-identity.json`；重跑时，程序核对 fingerprint、passage contract 和完整 payload 后复用向量，重新执行查询。`first_build_timing` 保留首次构建成本。稳定 passage IDs 保证 upsert 幂等，不累积重复 points。

未完成的模型可能留下部分 points。先修复失败原因，再运行同一命令；程序重新编码该模型，upsert 全部 passages 后清理 stale points。程序不会清除整个 collection。模型离线加载失败会记入 `excluded`，其余候选继续执行。

## 结果复核

输出 `reports/rag-stage-two-seven-embedding-comparison.json` 和 `.md`。JSON 保留完整 Top-5 canonical parents、matched passage、score、证据组判断、全部切片、跨语言逐条排名、负例分布、BM25 互补性及两两比较。

所有小样本均为 diagnostic only。两两比较只使用 `first_complete_rank`，未命中记为 Top-5 之外；两个未命中视为相同。Cosine 只在每个模型内部解释，不直接横向比较绝对值，也不设置 threshold。

先检查获胜 passage 是否含 required evidence，再判断父 Chunk 命中。模型选型同时考虑 Hit@1、Hit@5、跨语言、BM25 之外的独立命中、领域负例、维度、大小和实测成本。最终决策依据本轮数据填写报告；重跑自动测量后，应重新审阅结论。

## 回滚与故障处理

历史 Stage 2/2.5/2.6 报告和索引保留，Stage 2.7 只写专用目录与新报告。停止比较后可继续使用原 BGE-small 索引，无需恢复原始 PDF。

遇到本地模型不完整，先检查权重、tokenizer 和模块文件，再单独重新下载缺失文件。遇到 identity mismatch，保留旧目录作证据，修正模型来源或在新的专用运行目录重建；不要把新旧模型混入同一 collection。

审计原始父 Chunk 时，tokenizer 可能打印超长输入提示。原始超长父文本用于确定拆分需求，不直接编码。实际编码以最终 passage 审计为准；所有模型的 `passages_exceeding_limit` 必须为 0。

历史 BGE-small 的 embedding 时间来自 Stage 2.6。旧 JSON 没有单独保存线程数字段，旧运行手册的命令为 2 个线程。新候选统一使用 6 个线程，历史时间只作成本参考，不能据此计算严格的同条件性能倍率。

人工复核发现冻结契约遗漏等价证据时，保留全部正式分数，在 JSON 的 `analysis_notes` 和 `manual_evidence_checks` 中记录额外来源、物理页、父 Chunk 与 passage 的区别。该记录不增加 query、不改变 evidence groups，也不重算冻结指标。
