# RAG 入库路径实测记录（Phase 1 / M0）

- 执行任务：共享任务板 `task-3`（RAG 知识入库、验证与回滚手册 + 入库路径实测）
- 实测日期：2026-10-29
- 工作区：`/home/whloong/projects/accelerator-rag-prab`，git HEAD `0b62844`
- Python：`/home/whloong/miniconda3/envs/accelerator-rag/bin/python`（3.11.15，pymupdf 1.28.2 / httpx 0.28.1 / pytest 8.4.2）
- 被测生产服务：`http://127.0.0.1:18003`（SSH 转发到 GPU 主机 `10.101.9.190:8003`）
- 隔离声明：本次没有写索引、没有重启或部署服务、没有改 `src/`、没有 git commit/push。临时语料与临时 registry 全部位于本目录 `tmp-probe/` 下。

配套手册：[docs/runbooks/rag-ingestion-verification-rollback.md](../../../docs/runbooks/rag-ingestion-verification-rollback.md)

## 0. 结论摘要

| 问题 | 结论 | 证据 |
| --- | --- | --- |
| 当前系统能否把 `docs/waveform/*.md` 直接入库？ | **阻塞。不能。** 两层阻塞：① `source_path` 必须在 `data/l0_raw/` 下，`docs/` 原地登记被拒；② 即使复制进 `data/l0_raw` 并登记，`IngestionService` 只接受 PDF（显式抛错），`parse_pdf` 只接受 `.pdf`，全仓库没有 Markdown 解析器；生产 runtime 的文档目录也只收 `.pdf` 来源。 | 本文件第 3 节 P2/P2b/P3/P4；第 4 节代码证据 |
| PDF 入库链路本身是否可用？ | 已实现且在生产使用：13 份 PDF → 2178 物理页 → 4537 规范父块 → 4532 eligible → 两个双路索引（4746 / 4532 points）。本机无原始语料，未重建索引。 | 第 3 节 P5/P7、第 5 节线上只读检查 |
| 索引契约 `dense_index_contract_id` 能否离线复算？ | 能在代码层复算公式（本次用伪指纹实算成功），但不能在本机复算生产值：模型权重与索引都在 GPU 主机，本机无 `/workspace`。 | 第 3 节 P6 |
| 回滚步骤是否可执行？ | 备份路径与恢复顺序有据可依（`/opt/accelerator-rag/tmp/rag-framework-backup-20261028` + `manifest.json`，见 `reports/rag-framework-20261028.md:109`），但**本机无法读取备份内容**（只有到 `8003` 的端口转发，没有 `10.101.9.190` 的 SSH 登录权限）。回滚需具备 GPU 主机登录权限的运维执行。 | 第 5 节、手册第 7 节 |
| 自动回滚 | **未实现**。仓库内没有回滚脚本，`deploy/` 只有启动脚本。 | 手册第 7.5 节 |

一句话：**文件写进 `data/l0_raw/` 或 `docs/` 不等于已入库；Markdown 在解析入口被拒绝，属于阻塞项，不是"待配置"。**

## 1. 环境事实与一个必须注意的坑

```console
$ git rev-parse --short HEAD
0b62844
$ /home/whloong/miniconda3/envs/accelerator-rag/bin/python -V
Python 3.11.15
$ ls data/l0_raw
ls: 无法访问 'data/l0_raw': 没有那个文件或目录
$ curl --noproxy '*' -sS -m 10 -w '\nhttp_code=%{http_code}\n' http://127.0.0.1:18003/health
{"status":"ok"}
http_code=200
```

**坑：conda 环境里的 `accelerator_rag` 是 editable 安装，指向兄弟目录 `/home/whloong/projects/accelerator-rag`，不是本工作区。**

```console
$ python -c "import accelerator_rag; print(accelerator_rag.__file__)"
/home/whloong/projects/accelerator-rag/src/accelerator_rag/__init__.py     # 默认
$ PYTHONPATH=src python -c "import accelerator_rag; print(accelerator_rag.__file__)"
/home/whloong/projects/accelerator-rag-prab/src/accelerator_rag/__init__.py  # 本工作区
```

两个 checkout 的差异：`config.py` 不同（本工作区为精简版 `Settings`，生产 RAG 不走它，走 `config/rag-production.json`），其余本手册与实测涉及的文件 **逐字节相同**：

```console
$ for f in corpus/registry.py corpus/pdf_parser.py corpus/chunking.py corpus/cleaning.py \
           corpus/eligibility.py corpus/audit.py corpus/taxonomy.py ingestion.py \
           retrieval/index_contract.py domain/knowledge.py; do
    diff -q /home/whloong/projects/accelerator-rag/src/accelerator_rag/$f \
            src/accelerator_rag/$f >/dev/null && echo "SAME $f" || echo "DIFF $f"; done
SAME corpus/registry.py
SAME corpus/pdf_parser.py
SAME corpus/chunking.py
SAME corpus/cleaning.py
SAME corpus/eligibility.py
SAME corpus/audit.py
SAME corpus/taxonomy.py
SAME ingestion.py
SAME retrieval/index_contract.py
SAME domain/knowledge.py
```

因此**本记录中所有 pytest / 探针命令都显式加了 `PYTHONPATH=src`**，日志首行会打印 `accelerator_rag.__file__`。复核本记录的人如果不加，会测到兄弟目录的代码。

## 2. 执行命令与退出码总表

| # | 命令 | 退出码 | 产物 |
| --- | --- | --- | --- |
| C1 | `PYTHONPATH=src python reports/phase1-m0-20261029/ingestion-path/run_ingestion_path_probe.py` | 0（7 组探针、0 断言失败） | `probe-output.log` |
| C2 | `PYTHONPATH=src python -m pytest tests/corpus -q` | 0（93 passed in 0.32s） | `pytest-corpus.log` |
| C3 | `python scripts/corpus_inventory.py` | 1（本机无 `data/l0_raw`） | `corpus_inventory.err` |
| C4 | `PYTHONPATH=src python scripts/rag_framework_metrics.py` | 0（读已保存报告，本地可跑） | `rag_framework_metrics.out` |
| C5 | `PYTHONPATH=src python scripts/rag_framework_review.py` | 1（需原始 PDF，本机无） | `rag_framework_review.err` |
| C6 | `curl --noproxy '*' -sS http://127.0.0.1:18003/health` | 0（`{"status":"ok"}`，HTTP 200） | `health-body.json`、`health-headers.txt` |
| C7 | `curl --noproxy '*' -sS http://127.0.0.1:18003/v1/rag/documents` | 0（HTTP 200，5284 字节） | `catalog.json` |

## 3. 探针逐项结果（C1）

脚本：`run_ingestion_path_probe.py`（本目录，可重跑），完整输出：`probe-output.log`（101 行）。

### P1 registry schema 与真实 registry（只读）

```text
VALID_DOCUMENT_TYPES = ['docx', 'md', 'pdf', 'pptx', 'txt']
_DOC_ID_PATTERN      = ^[a-z0-9]+(?:-[a-z0-9]+)*$
load_registry(data/documents/registry.json) -> 13 条记录，全部通过 __post_init__ 校验
document_type 分布: {'pdf': 13}
PASS  registry schema 允许 document_type='md'（集合内注册）
PASS  真实 registry 当前 13 条全部是 pdf，无 md 记录
```

### P2 构造 Markdown 记录：registry 层接受

```text
DocumentRecord(document_type='md', source_path='data/l0_raw/docs/waveform/waveform-overview.md') -> 构造成功
  doc_id             = waveform-overview-doc
  document_type      = md
  category/topic     = beam_diagnostics / waveform
PASS  registry 元数据层接受 Markdown 登记（topic='waveform' 已存在于 taxonomy）
  reject 'data/l0_raw/docs/waveform/waveform-overview.pdf': source_path 扩展名必须与 document_type 一致
  reject '/etc/passwd': source_path 必须是 data/l0_raw 下的安全相对路径
  reject 'data/l0_raw/../escape.md': source_path 必须是 data/l0_raw 下的安全相对路径
```

要点：`data/l0_raw/docs/waveform/*.md` 的登记在**元数据层合法**（`beam_diagnostics/waveform` 话题已存在），这会让人误以为"已登记 = 可入库"。下一项证明不是。

### P2b 原地登记真实 `docs/waveform/*.md`：被路径规则拒绝（实测）

```text
实际文件: docs/waveform/waveform-storage-dataflow.md exists=True size=30214
  REJECT docs/waveform/waveform-storage-dataflow.md -> source_path 必须位于 data/l0_raw 下
  ACCEPT data/l0_raw/waveform/waveform-storage-dataflow.md
PASS  docs/waveform/*.md 不能原地登记：source_path 必须在 data/l0_raw 下（registry.py:76-77）；即使复制进去，下一步仍被 IngestionService 拒绝
```

说明：`docs/waveform/` 是并行任务在本次核验期间（13:22 / 13:28）创建的，含 `waveform-storage-dataflow.md`（30,214 B）与 `alignment-semantics-and-diagnostics.md`（59,556 B），git 未跟踪。它们是"文件已保存"，不是"已入库"。

### P3 关键证据：Markdown 走 `IngestionService`

```text
临时项目根: reports/phase1-m0-20261029/ingestion-path/tmp-probe（位于本报告目录内，不触碰 data/l0_raw）
Markdown 文件: data/l0_raw/docs/waveform/waveform-overview.md (162 字节)
IngestionService(临时根).records -> ['waveform-overview-doc']
  ingest_document('waveform-overview-doc') 抛出 ValueError: only PDF ingestion is supported
PASS  IngestionService 明确拒绝非 PDF：only PDF ingestion is supported（src/accelerator_rag/ingestion.py:55-56）
  ingest_all_registered_pdfs() -> 0 个文档（字段过滤 document_type == 'pdf'）
PASS  批量入口静默跳过已登记的 Markdown：0 个文档、0 个 chunk、无异常
```

**这是"阻塞"的核心证据**：单文档入口报错，批量入口静默返回空集合——批量路径不报错，更容易被误判为"入库完成但检索不到"。

### P4 解析层拒绝 Markdown

```text
  parse_pdf(<.md>) 抛出 ValueError: Expected a PDF file: .../waveform-overview.md
PASS  解析器只接受 PDF 后缀（src/accelerator_rag/corpus/pdf_parser.py:192-193）
  构造 ParsedPdfDocument 的源码位置: ['src/accelerator_rag/corpus/pdf_parser.py']
PASS  全仓库仅 pdf_parser 能构造 ParsedPdfDocument：没有 Markdown/HTML/纯文本解析入口
```

### P5 正对照：PDF 链路 + 切块层是否格式无关

```text
parse_pdf -> page_count=3, warnings=[]
chunk_pdf -> 2 chunks, algorithm=pdf-chunks-v3
  page_start=1 page_end=1 chars=87 chunk_id=demo-pdf:b825f8bb46cbcc6ac2c13d5af1b6340e02e8b84e16153f144f092ef67756baae
  page_start=3 page_end=3 chars=53 chunk_id=demo-pdf:2d7f4135543b991fe6ada8d588126d90a7c184679ec2d7489dfe9a076bf6f436
PASS  chunk_id 对同一输入确定性复现（sha256 前缀 + 文档 ID）
PASS  空物理页 2 不产生 chunk，也不会把第 3 页重编号

手工构造 ParsedPdfDocument(markdown) -> chunk_pdf -> 0 chunks
PASS  切块层只吃清洗后的 block（blocks 为空 -> 0 chunk）：Markdown 正文必须由适配器转成 block 才能进入
  加上一个 block 后 -> 1 chunks
  page=1 chars=49 chunk_id=waveform-overview-doc:d7192a47508b98df1da348938170cb3ff8910a78e876a63943f8738416f79cc7 text='# Waveform 采集服务概览\n\nWF 服务以 10 MS/s 采样，单次捕获 4096 点。'
PASS  chunk_pdf 本身不检查后缀：只要给 ParsedPdfDocument+PdfTextBlock，Markdown 文本可切块（但 chunk_id 仍冠以 pdf-chunks-v3）
  合成页 height=0 时 chunk_pdf 抛出 ZeroDivisionError: float division by zero
PASS  Markdown 适配器必须提供非零合成 page.width/height（cleaning.py:127 用 bbox 除以页高），否则清洗阶段崩溃
```

结论：**缺的只有一个"Markdown → ParsedPdfDocument/PdfTextBlock"适配器**（外加版本语义与 runtime 目录白名单），而不是整条链路不支持文本。最后一条是新增的工程约束：适配器造页必须给非零 `width/height`，否则 `cleaning.py:127` 除零。

### P6 索引契约语义（实算）

```text
canonical_sha256 = sha256(json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=False, allow_nan=False))
canonical_sha256({b:1,a:[2,3]}) = 2aae3bfa906be39530e7d7a4aa90a7e6d4f29c33e3ac80e1c3b05598c5953c04
PASS  字典插入顺序不影响 contract 摘要（sort_keys=True）
PASS  任一字段变化都会改变摘要（不可变身份）

canonical_passage_id 使用不同的序列化：json.dumps(..., sort_keys=True) 默认分隔符（含空格）
canonical_passage_id(passage_contract) = 2be63c66d58f4edbdd919e8db9330a56ffd832a5c30243a339e781d308b2a4de
PASS  passage 契约 ID 与 canonical_sha256 不是同一算法（保留 dense-passages-v1 历史标识，index_contract.py:84-86）

DenseIndexContract.from_fingerprint(伪指纹) ->
  contract_id      = f8b3f058397307a14f6ed696055c2a517cd480d16c27c37bf2c2c794f6c4e5e0
  passage_algorithm= dense-passages-v1
  dimension        = 768  distance = cosine  normalize_embeddings = True
  document_template= document_title + "\n" + passage.text
PASS  contract_id 为 64 位十六进制，等于 asdict(contract) 的 canonical SHA-256
PASS  维度变化即产生新 contract_id（换模型/换 passage 必须用新集合）

config/rag-production.json: intfloat/multilingual-e5-base contract_id=ccd4601d1698d3bff5b46589f11fc036e035ca57c1d8d179cd56b6b2d50e16f4 point_count=4746
  model_path=/workspace/tmp/stage-two-seven/models/intfloat--multilingual-e5-base  index_path=/workspace/tmp/stage-two-eight/e5_reused_signed_index  local_exists=False
config/rag-production.json: Qwen/Qwen3-Embedding-0.6B contract_id=6698d5531a29685c9a4002123d183e4cfa38f0e491fbeb3086448e2f0e6aa823 point_count=4532
  model_path=...  index_path=/workspace/tmp/stage-two-eight/qwen3_embedding_0_6b_fp32/qdrant  local_exists=False
PASS  两个生产索引的 contract_id 均为 64 位十六进制；本地无模型权重与索引，无法离线重算（只能比对 config 值）
```

### P7 本地 inventory

```text
  build_inventory(accelerator-rag-prab) 抛出 ValueError: raw 目录不存在: /home/whloong/projects/accelerator-rag-prab/data/l0_raw
```

（对应 C3：`corpus_inventory.py` 退出码 1，stderr 完整堆栈见 `corpus_inventory.err`。）

## 4. 代码级证据清单（Markdown 阻塞）

| 层 | 位置 | 行为 |
| --- | --- | --- |
| 元数据 | `src/accelerator_rag/corpus/registry.py:12` | `VALID_DOCUMENT_TYPES = {"docx","md","pdf","pptx","txt"}`：**只表示"可以登记"** |
| 元数据 | `registry.py:68-79` | `source_path` 必须在 `data/l0_raw` 下、相对 POSIX、无 `..`，扩展名必须等于 `.{document_type}` |
| 元数据（位置） | `registry.py:76-77` | `docs/waveform/*.md` 原地登记被拒：`source_path 必须位于 data/l0_raw 下`（P2b 实测）；须先复制到 `data/l0_raw/waveform/` |
| 单文档入口 | `src/accelerator_rag/ingestion.py:51-57` | `if record.document_type != "pdf": raise ValueError("only PDF ingestion is supported")` |
| 批量入口 | `ingestion.py:59-65` | `[... for record in self.records.values() if record.document_type == "pdf"]`：**静默跳过非 PDF** |
| 解析 | `src/accelerator_rag/corpus/pdf_parser.py:192-193` | `if pdf_path.suffix.lower() != ".pdf": raise ValueError("Expected a PDF file: ...")`；解析器基于 `pymupdf` |
| 解析产物 | `pdf_parser.py` 全文 | 全仓库唯一构造 `ParsedPdfDocument` 的位置（探针 P4 已扫描 `src/`），没有任何 Markdown/HTML/plain-text 解析器 |
| 切块 | `src/accelerator_rag/corpus/chunking.py:56-100` | 输入必须是 `ParsedPdfDocument`，`chunk_id` 前缀固定 `pdf-chunks-v3`，与真实格式解耦但语义命名绑定 PDF |
| 清洗 | `src/accelerator_rag/corpus/cleaning.py:127` | `b.bbox[1] / page.height`：合成页必须给非零页高，否则 `ZeroDivisionError` |
| 生产 runtime | `src/accelerator_rag/rag/runtime.py:126-130` | 只有 `source.is_relative_to(root) and source.suffix.lower() == ".pdf"` 的来源才进 `documents`/`catalog`；即使索引里有 Markdown chunk，也不会出现在文档目录与 PDF 查看器 |
| 文档接口 | `src/accelerator_rag/rag/api.py:47-66` | `/v1/rag/documents` 只暴露 catalog；未登记来源无法通过接口取得 |

补充：`docs/runbooks/knowledge-retrieval.md:11,112` 已声明"当前 ingestion 只支持 PDF""未实现 PPTX/DOCX 解析"；本次实测把这条声明扩展为**可执行的判定**，并定位到具体抛错行。

## 5. 线上只读检查（C6/C7）

```text
$ curl --noproxy '*' -sS -D health-headers.txt -o health-body.json http://127.0.0.1:18003/health
HTTP/1.1 200 OK
server: uvicorn
content-type: application/json
{"status":"ok"}

$ curl --noproxy '*' -sS -o catalog.json -w 'catalog_http=%{http_code} bytes=%{size_download}\n' \
    http://127.0.0.1:18003/v1/rag/documents
catalog_http=200 bytes=5284
document_count= 13 indexed_section_count= 4532
```

`catalog.json` 汇总（13 份文档）：物理页合计 **2178**、索引节合计 **4532**，与 `docs/roadmap/CURRENT.md:43` 的冻结口径（13 份 PDF、2178 页、4537 规范父块、其中 4532 eligible）一致；`indexed_section_count=4532` 与 Qwen3 索引 `point_count=4532` 对齐，说明线上加载的是同一批规范父块。全部条目 `original_available: true`，`document_url` 均指向 `/v1/rag/documents/{doc_id}`（PDF 分支）。

注意：`/v1/rag/documents` 只证明"索引已加载 + catalog 有 13 份 PDF"，不证明回答正确性。

## 6. 本机不能完成、必须在 GPU 主机完成的验证

| 命令 | 本机结果 | 原因 |
| --- | --- | --- |
| `python scripts/corpus_inventory.py` | exit 1，`raw 目录不存在` | 本机无 `data/l0_raw`（真语料在 `/workspace/data/l0_raw`） |
| `python scripts/rag_framework_review.py` | exit 1，`pymupdf.FileNotFoundError: no such file: 'data/l0_raw/EPICS/EPICS_Documentation_latest.pdf'`（完整堆栈 `rag_framework_review.err`） | 独立核对要把引文回查原始 PDF，必须有语料 |
| `python scripts/rag_framework_metrics.py` | exit 0 | 只读 `reports/rag-framework-20261028/` 已保存的 http-results + traces，不碰 PDF/网络 |
| 索引重建 / 契约复算 | 未执行 | 模型权重与索引都在 GPU 主机 `/workspace/tmp`；本机 `Path('/workspace/tmp').exists() == False` |
| 读取回滚备份内容 | 未执行 | 本机只有到 `10.101.9.190:8003` 的端口转发；`ssh waveform-zyf-oneclick 'ssh 10.101.9.190 ...'` 返回 `Permission denied (publickey...)`，无 GPU 主机登录权限 |

同目录 `regression-36-http.json` / `regression-36.log` 由 Lead 侧任务生成（20 题 HTTP 回归，`summary.statuses={"answered":20}`、0 HTTP 错误），本记录**不重复执行**、也不把它当作正确性结论——只作为"接口可用"的旁证。

## 7. 产物清单（本目录）

| 文件 | 内容 |
| --- | --- |
| `verification.md` | 本记录 |
| `run_ingestion_path_probe.py` | 可重跑探针（P1–P7） |
| `probe-output.log` | C1 完整输出（101 行，退出码 0） |
| `pytest-corpus.log` | C2 `tests/corpus` 93 passed |
| `corpus_inventory.out` / `.err` | C3 失败输出/堆栈 |
| `rag_framework_metrics.out` | C4 指标 JSON（95 行） |
| `rag_framework_review.out` / `.err` | C5 失败输出/堆栈 |
| `health-headers.txt` / `health-body.json` | C6 健康检查 |
| `catalog.json` | C7 线上文档目录（13 份） |
| `tmp-probe/` | P3/P5 的临时项目根（最小 Markdown + 生成的对照 PDF），非生产语料 |

---

## 9. 2026-10-29 14:40 后续：Markdown 入库已实现（本记录第 0–8 节保留为当时状态）

本文件第 0–8 节记录的是实现前的阻塞核验（当时结论：`IngestionService` 只收 PDF、Markdown 在
解析入口被拒）。**该结论已随方案 A 的实现过期**，仅对 TXT/HTML/DOCX 仍成立。

实现与证据：

| 项 | 内容 |
| --- | --- |
| 解析 | `src/accelerator_rag/corpus/markdown_parser.py`：front-matter 保留为证据、按标题级别切节、围栏内不切 |
| 切块 | `chunk_markdown`，算法标签 `md-chunks-v1`；PDF 的 `pdf-chunks-v3` 与既有 `chunk_id` 不变 |
| 入库 | `ingestion.py`：`pdf`+`md` 分派，`ingest_all_registered()`；`ingest_all_registered_pdfs()` 保持 PDF-only |
| 快照 | `scripts/snapshot_markdown_docs.py` → `data/l0_raw/waveform/`、`data/l0_raw/runbooks/`，记录双向 sha256 |
| 登记 | `data/documents/registry-md.json`（冻结的 `registry.json` 未改动，13 份 PDF 基线不变） |
| 干跑 | `scripts/md_corpus_report.py` → 4 份 / 40 节 / 151 chunks / 151 eligible |
| 建索引 | `scripts/build_markdown_index.py`（`--dry-run` / `--apply`，未在 GPU 主机执行） |
| 服务 | catalog 增 `document_format`；`/documents` 返回 `text/markdown`；`/view` 非 PDF 回退纯文本 |
| 测试 | `tests/corpus/test_markdown_ingestion.py` 7 项通过；全套 269 项通过 |

仍未完成：GPU 主机 `--apply` 建索引、`point_count` 更新、服务重启、生产端到端验证。
步骤见 `docs/runbooks/rag-ingestion-verification-rollback.md` §8.3。
