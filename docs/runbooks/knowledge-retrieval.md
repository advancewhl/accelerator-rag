# Knowledge Retrieval 运行手册

第一阶段提供真实 PDF 的解析、切块与检索。结果保留物理页码和来源路径，可直接检查证据。入口只返回检索结果。

## 环境与数据入口

在项目根目录运行命令，使用 `accelerator-rag` Conda 环境，并安装项目及开发依赖。

Registry 位于 `data/documents/registry.json`。`source_path` 是项目根目录下的规范 POSIX 相对路径，统一指向 `data/l0_raw/`。`document_id` 使用 Registry 的 `doc_id`，不包含本机目录。`IngestionService` 将逻辑路径解析为本机路径，并检查符号链接是否越出原始数据根目录。

已登记的 13 份 PDF 均有对应原文件。原始目录另有 5 份未登记的 PPTX/DOCX，当前 ingestion 只支持 PDF。`scripts/corpus_inventory.py` 将它们列为 unsupported/unmanaged source files，PDF validation 返回成功。未登记 PDF 和登记文件缺失仍导致失败。程序不为未支持的文件生成 Registry metadata，原始文件保持原样。

`data/l2_evidence/legacy_schema_v1/` 中的 JSON 是历史解析产物。正式 ingestion 直接读取原始 PDF，不复用其中过时的路径。`.gitignore` 继续忽略原始文件和这些历史产物。

## 查询

BM25 查询：

```bash
conda activate accelerator-rag
python -m accelerator_rag.retrieval.cli \
  --document-id shine-epics-ioc-pv-information-management-pcapac2022 \
  --query 'How are IOC and PV information managed in SHINE?' \
  --top-k 3
```

本地 BGE 模型查询：

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m accelerator_rag.retrieval.cli \
  --document-id shine-epics-ioc-pv-information-management-pcapac2022 \
  --retriever dense \
  --query 'SHINE 中 IOC 启动后会向管理系统提交哪些信息？' \
  --top-k 3
```

默认模型为 `BAAI/bge-small-zh-v1.5`，也可通过 `--model` 指定已有本地模型目录。该类使用 BGE 中文 query instruction，其他模型需要独立核对输入约定。

本机缓存的模型卡（revision `7999e1d3359715c523056ef9478215996d62a620`，模型表与 Sentence-Transformers 示例）推荐指令 `为这个句子生成表示以用于检索相关文章：`。`EmbeddingModel.QUERY_TEMPLATE` 统一定义为 `为这个句子生成表示以用于检索相关文章：{query}`，全角冒号是显式分隔符。文档文本不加 query instruction。此结论仅依据本地缓存，没有联网获取材料。

加载默认使用 `local_files_only=True`。模型缓存缺失时明确失败；程序不会下载权重。线程环境变量用于限制 CPU 并行度，可按运行环境调整。

Dense 默认使用 Qdrant 内存实例。通过 `--qdrant-path tmp/knowledge-qdrant` 可保存到本地目录，通过 `--collection` 指定集合。CLI 每次读取指定 PDF，并替换该文档的索引。持久目录必须位于原始数据目录之外。

输出是 JSON，含 Chunk 数量、物理页码和 `results`。每条结果包含 `rank`、`score`、`retriever` 及完整 `chunk`。

## Python 接口与数据流

```python
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.retrieval.bm25 import BM25Retriever

chunks = IngestionService(".").ingest_document(
    "shine-epics-ioc-pv-information-management-pcapac2022"
)
results = BM25Retriever(chunks).search("IOC startup", top_k=3)
```

数据流为 Registry → 本机 PDF → `ParsedPdfDocument` → 文本规范化 → `KnowledgeChunk` → BM25，或 Embedding → Qdrant → `RetrievalResult`。

`DenseRetriever(embedder, vector_store).index_document(document_id, chunks)` 负责生成向量并替换文档索引，`search(query, top_k)` 返回统一结果。`TextEmbedder` 协议只约束文档和查询的向量生成方法。

## Chunk 模型与切块规则

`KnowledgeChunk` 的正式字段如下：

```text
chunk_id, document_id, document_title, text,
source_path, document_version, language, category, topic,
page_start, page_end
```

页码从 1 开始，表示 PDF 物理页，而非印刷页码。核心引用字段均为具名字段。

parser 保留原始文本 block 的提取顺序、bbox、物理页号和告警。独立的 `corpus/cleaning.py` 在生成 Chunk 前清洗检索文本，保持原始 parsed representation 不变。

清洗利用页边位置、跨页重复和出版信息形态，过滤重复页眉、页脚、页码、出版编号与边注版权声明。首次摘要前的简短标题、作者信息不进入正文 Chunk；末页明确的参考文献标题后有多条编号引文时，排除该列表。正文中的引用保留。规则不包含出版机构、会议或文件名特例。

清洗后的双栏正文采用简单几何排序：跨栏 block 划分垂直区域，区域内先左栏、后右栏。正文 block 在排序后合并，随后处理跨行及跨相邻 block 的断词。只有文档其他位置存在完整拼写，且没有完整连字符拼写时，才移除换行连字符；真实技术连字符和有歧义的词保留。该规则不提供完整版面恢复。

切块使用清洗后的每页正文，规范化空白和换行，并保留段落分隔。默认硬上限为 1200 字符，软下限为 300 字符。优先在 block、句子、空白边界拆分；连续超长文本才硬切。末尾不足软下限时，提前切分前一个片段。短页可小于软下限。

Chunk 不跨页、不重叠。空页不生成 Chunk，也不影响后续物理页号。参数集中在 `ChunkingConfig`。

Chunk ID 使用文档 ID 前缀和 SHA-256 摘要。摘要输入包括切块算法版本、配置、文档 ID、文档版本、物理页号、页内 Chunk 序号和规范化文本。相同输入确定性地产生相同 ID，不依赖 Python `hash()`、随机数或本机路径。当前算法版本为 `pdf-chunks-v3`。修改清洗或切块逻辑时应更新算法版本。

## 检索与索引语义

BM25 和 Dense 均返回 `RetrievalResult(rank, score, chunk, retriever)`。BM25 分数为未归一化的关键词相关度，只返回正分结果；Dense 分数为 Qdrant 的余弦相似度。两种分数不直接比较。双模型 Dense 的 RRF 仅融合排名，重排使用独立模型分数，见[双模型检索与重排](dense-reranking.md)。Dense 会返回最相似的结果，但尚无最低相关度阈值。

Qdrant payload 保存全部 Chunk 字段，查询时严格恢复模型。读写前检查现有集合必须使用无名称向量、匹配的维度和余弦距离。向量数量、维度、有限值和非零长度均受校验。匹配维度并不能证明两个 Embedding 模型兼容；passage 索引通过 `DenseIndexContract` 绑定模型指纹和 passage 契约，更换模型时应使用新集合。底层 Chunk store 的维度检查不替代该契约。

`upsert_chunks` 按稳定 ID 更新。`replace_document` 先验证输入，再写入新 Chunk，最后仅删除该文档已过时的 ID。中断可能暂时留下新旧 Chunk，重试同一输入可恢复；该过程不是事务。空替换可显式清空指定文档。`delete_chunks` 按 Chunk ID 删除。`DenseRetriever` 拒绝空文档，避免将无文本解析结果误当作清空请求。

## 验证与限制

```bash
pytest -q
ruff check .
git diff --check
python scripts/corpus_inventory.py
```

单元及集成测试使用生成的 3 页 PDF，其中第 2 页为空。测试验证第 3 页的证据定位，以及 Fake Embedder + Qdrant memory 的往返行为，均不依赖 Docker 或模型下载。

真实 SHINE smoke test 的完整结果见 `reports/rag-stage-one-smoke.json`，包含英文、中文查询在 BM25 与真实 BGE + Qdrant 上的结果。2026 年 10 月 19 日验证得到 13 个 Chunk，覆盖 3 个物理页。中文 Dense 首条命中第 3 页的 IOC 信息段落。该验证证明链路和来源字段可用，尚不构成系统性检索质量评估。

当前清洗已减少明显出版与页脚污染，保留正文图注。位置阈值和摘要、参考文献边界仍是启发式规则；特殊版面可能误判，原始证据完整保留以供核查。没有其他完整拼写证据的断词会保留连字符，简单双栏排序和页间断句仍可能影响文本衔接。BM25 对中文问题检索英文资料的能力有限；默认 BGE 中文模型的英语和跨语言表现有限，模型比较见专用报告。正式 passage 路径在编码前校验 token 上限，避免静默截断。

本阶段未实现 OCR、复杂表格或公式识别、PPTX/DOCX 解析、增量 ingestion、完整索引 manifest、Hybrid、LLM 回答或 Agent 接入。独立的双模型重排实验已完成 Stage 2.8.2，尚未切换 CLI 默认路径。
