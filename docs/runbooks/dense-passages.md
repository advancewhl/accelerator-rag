# Dense Passage Compatibility

## 当前入口与边界

Stage 2.6 保留 `pdf-chunks-v3` 和 canonical `KnowledgeChunk`。BM25、citation 和 ground truth 继续使用 KnowledgeChunk。Dense 使用独立的 `dense-passages-v1` 表示，搜索后恢复父 Chunk。

当前实验只改变 Dense 表示。模型固定为本地 `BAAI/bge-small-zh-v1.5`，query template、cosine distance、清洗、资格策略和查询集保持 Stage 2.5 状态。原始 PDF、Agent 源码、Stage 2/2.5 报告和集合保留。

## 执行

使用现有 `accelerator-rag` Conda 环境和本地模型缓存：

```bash
pytest -q
ruff check .
git diff --check
python scripts/corpus_inventory.py

OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m accelerator_rag.retrieval.passage_baseline \
  --project-root . \
  --collection knowledge_stage26 \
  --qdrant-path tmp/stage-two-six-qdrant \
  --batch-size 32
```

入口只接受 `knowledge_stage26` 前缀，拒绝原始数据目录和两个历史索引路径。A 侧只读复用 Stage 2.5 真实向量，重新执行固定查询。程序逐点验证历史父 Chunk 与当前 corpus 相同，并核对 A 的完整排名、指标以及 BM25 排名、指标和分数。控制变量不一致时，在 B 写入前失败。

B 侧每个 passage 每轮只编码一次。所有新 points 写入后，按文档清理 stale passage IDs。重跑会重新编码，稳定 ID 防止点数累积。索引不是多文档事务，失败后需修复原因并重跑专用集合。

输出为 `reports/rag-stage-two-six-dense-passage.json` 和 `.md`，历史报告保持原样。

## Passage 与预算

`EmbeddingPassage` 包含 `passage_id`、canonical `parent`、`passage_ordinal`、`text`、`char_start`、`char_end`、最终输入 `token_count` 和 `contract_id`。`parent_chunk_id` 与 `document_title` 由父对象派生。Passage 不成为 citation 单元。

实际输入统一复用 `document_title + "\n" + passage.text`。Tokenizer adapter 镜像 Transformer 的 strip/lower 行为，包含 special tokens。拆分使用真实 token IDs 和 source offsets，直接截取原始父文本，避免 decode 改写原始证据。

模型上限由已加载 SentenceTransformer 获取。完整父输入已适配时，保留一条完全相同的 passage；这包括恰好达到模型上限的输入。超限父输入才拆分，窗口预算扣除实际标题、模板和 special tokens，再预留 16 tokens。Overlap 为 32 个原始正文 tokenizer tokens。

优先选择窗口后半段的段落、句子和空白边界，最后才按 token offset 硬切。每个窗口都重新计算完整输入长度；substring 边界改变 tokenization 时继续缩短。空 passage、标题占满预算或不前进的拆分均失败。

Builder 验证全部最终输入。实际 encode 前再次通过 `embed_token_safe_documents` 验证；超过模型上限即失败，不允许静默截断。`--guard-tokens` 和 `--overlap-tokens` 集中配置并写入报告。Guard 用于拆分窗口，已适配父输入保持原状。

Passage ID 使用 SHA-256，输入包括独立算法版本、模型/tokenizer contract、passage config、parent ID、ordinal、标题、正文和字符范围。Tokenizer contract 排除运行中可变的 padding/truncation 状态，但包含真实 tokenizer 配置摘要。修改 passage config 不修改 canonical Chunk ID。

## 存储与搜索

Qdrant payload 包含 passage identity、ordinal、正文、范围、token count、contract，以及完整 parent 正文与 provenance。`QdrantPassageStore` 验证 payload owner/type。重复 parent 正文增加存储量，但允许重开 persistent Qdrant 后直接恢复 canonical KnowledgeChunk，无需额外数据库或运行期 lookup。

`DenseRetriever.search()` 初始请求 `top_k * 4` 条 passage。按 parent ID 去重，parent score 为最大 child cosine score。最终 rank 连续，public result 的 `.chunk` 始终是完整 canonical KnowledgeChunk。

如果候选去重后不足 Top-K，则将候选量翻倍，最多达到集合 point count。循环有限，query vector 只计算一次。`last_passage_trace` 保存获胜 passage ID、ordinal、正文、分数和候选量序列，供报告使用。

`DirectChunkDenseRetriever` 仅保留为历史 A 侧诊断实现。当前单文档 Dense CLI 和 Stage 2.6 baseline 使用 passage store。

## 评测与截断诊断

查询集冻结为 schema v2、`evidence-contract-v1`，21 条可回答、3 条明显负例、8 条领域负例。加载规则和完整证据组判断保持不变。

报告包括总体、语言、语言关系、类别、预期文档切片，以及全部 21 条 query 的完整命中排名变化。所有切片仅作诊断。明显负例和领域负例分别比较 Top-1 分布，不实现 score threshold。

历史截断诊断使用真实 tokenizer 的 max-length offsets，定位实际输入的可见原始文本前缀，再用固定 normalization 判断 evidence 在上限之前、跨越上限或完全位于之后。规范化在边界处无法可靠对应时，记录为 unclassified。该诊断描述证据位置，不证明 embedding 理解，也不能单独证明检索失败原因。

## 限制

Overlap 只能保护有限跨度的边界证据，不能保证任意长度摘录都完整落入某个 passage。Zero truncation 消除了模型输入超限，但没有修复公式损坏、目录点线、合并页眉或模型语义判别能力。

Max-child 聚合会增加长父 Chunk 获得高相似度的机会。需结合 hard negatives 和逐 query 回归结果判断，不按总体 Hit 单独评价质量。Stage 2.6 结论已通过 review。Stage 2.7 按独立运行手册比较模型，不重新调整 passage policy。

## Stage 2.6 工程修正

`index_document(document_id, chunks)` 只替换指定文档。程序先写入新 passages，再删除该文档的 stale IDs，保留其他文档的 points。更新 A 不重新编码 B，也不删除 collection。

`index_corpus()` 仍表示完整 corpus indexing。程序拒绝集合中存在 corpus 之外的文档，并核对最终 passage 点数。两种入口共享 passage 校验和批量写入小函数，各自保留独立语义。

`QdrantVectorStore` 和 `QdrantPassageStore` 分别继承 `QdrantCollection`。公共基类只管理 collection、维度、point ID 和删除。Chunk 写入、替换、检索和删除接口只属于 Chunk store；Passage store 只公开 passage payload 写入与检索。

持久化多文档测试覆盖 A 写入、关闭、重开、B 写入、A 替换和再次重开。测试逐点比较 B 的 payload/vector，并检查编码调用。

Stage 2.7 的指纹和受控比较见 [`embedding-comparison.md`](embedding-comparison.md)。本次修正保持 passage 算法、BGE-small tokenizer contract、输入文本和查询集不变，历史 Stage 2.6 报告继续有效。
