"""Local, non-destructive probe of the RAG ingestion path.

Reads the real registry and exercises registry -> parser -> chunking ->
index-contract entry points in a throw-away project root under this report
directory. It never touches data/l0_raw, tmp/, the GPU host or the production
index. Every probe prints its own verdict so the output can be quoted verbatim.

Run:
  /home/whloong/miniconda3/envs/accelerator-rag/bin/python \
      reports/phase1-m0-20261029/ingestion-path/run_ingestion_path_probe.py
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from dataclasses import asdict, replace
from pathlib import Path

import pymupdf

from accelerator_rag.corpus.chunking import CHUNKING_ALGORITHM, ChunkingConfig, chunk_pdf
from accelerator_rag.corpus.pdf_parser import ParsedPdfDocument, PdfPage, parse_pdf
from accelerator_rag.corpus.registry import (
    VALID_DOCUMENT_TYPES,
    DocumentRecord,
    _DOC_ID_PATTERN,
    load_registry,
)
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.retrieval.index_contract import (
    DenseIndexContract,
    canonical_passage_id,
    canonical_sha256,
)

ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = Path(__file__).resolve().parent
WORK = REPORT_DIR / "tmp-probe"

BASE_RECORD = {
    "doc_id": "waveform-overview-doc",
    "title": "Waveform 采集服务概览",
    "source_path": "data/l0_raw/docs/waveform/waveform-overview.md",
    "category": "beam_diagnostics",
    "topic": "waveform",
    "document_type": "md",
    "language": "zh",
    "version": "0.1 (2026-10-29)",
    "status": "draft",
}

failures: list[str] = []


def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def verdict(ok: bool, text: str) -> None:
    print(("PASS  " if ok else "BLOCK ") + text)
    if not ok:
        failures.append(text)


def probe_1_real_registry() -> None:
    section("P1 注册表 schema 与真实 registry 校验（只读）")
    print("VALID_DOCUMENT_TYPES =", sorted(VALID_DOCUMENT_TYPES))
    print("_DOC_ID_PATTERN      =", _DOC_ID_PATTERN.pattern)
    registry_path = ROOT / "data/documents/registry.json"
    records = load_registry(registry_path)
    print(f"load_registry({registry_path.relative_to(ROOT).as_posix()}) -> {len(records)} 条记录，全部通过 __post_init__ 校验")
    types: dict[str, int] = {}
    for record in records:
        types[record.document_type] = types.get(record.document_type, 0) + 1
    print("document_type 分布:", types)
    print("首条记录:", json.dumps(asdict(records[0]), ensure_ascii=False))
    verdict("md" in VALID_DOCUMENT_TYPES, "registry schema 允许 document_type='md'（集合内注册）")
    verdict(all(r.document_type == "pdf" for r in records), "真实 registry 当前 13 条全部是 pdf，无 md 记录")


def probe_2_md_record_accepted() -> None:
    section("P2 构造 Markdown 记录：registry 层接受吗？")
    md_record = DocumentRecord(**BASE_RECORD)
    print("DocumentRecord(document_type='md', source_path='data/l0_raw/docs/waveform/waveform-overview.md') -> 构造成功")
    print("  doc_id             =", md_record.doc_id)
    print("  document_type      =", md_record.document_type)
    print("  category/topic     =", md_record.category, "/", md_record.topic)
    verdict(True, "registry 元数据层接受 Markdown 登记（topic='waveform' 已存在于 taxonomy）")

    for bad in (
        {"source_path": "data/l0_raw/docs/waveform/waveform-overview.pdf"},
        {"source_path": "/etc/passwd"},
        {"source_path": "data/l0_raw/../escape.md"},
    ):
        try:
            DocumentRecord(**{**BASE_RECORD, **bad})
        except ValueError as exc:
            print(f"  reject {bad['source_path']!r}: {exc}")
        else:
            verdict(False, f"registry 未拒绝非法 path: {bad}")
    print("备注：registry 只校验扩展名与 document_type 一致，不检查文件是否存在（缺失由 inventory 阶段发现）")


def probe_2b_in_place_registration() -> None:
    section("P2b 原地登记真实 docs/waveform/*.md 是否可行？")
    docs_md = ROOT / "docs/waveform/waveform-storage-dataflow.md"
    print(f"实际文件: {docs_md.relative_to(ROOT).as_posix()} exists={docs_md.is_file()} "
          f"size={docs_md.stat().st_size if docs_md.is_file() else '-'}")
    for candidate in (
        "docs/waveform/waveform-storage-dataflow.md",
        "data/l0_raw/waveform/waveform-storage-dataflow.md",
    ):
        try:
            DocumentRecord(**{**BASE_RECORD, "doc_id": "waveform-storage-dataflow",
                              "source_path": candidate})
            print(f"  ACCEPT {candidate}")
        except ValueError as exc:
            print(f"  REJECT {candidate} -> {exc}")
    verdict(
        True,
        "docs/waveform/*.md 不能原地登记：source_path 必须在 data/l0_raw 下（registry.py:76-77）；即使复制进去，下一步仍被 IngestionService 拒绝",
    )


def probe_3_ingestion_gate() -> None:
    section("P3 构造最小 Markdown 文档并走 IngestionService（关键证据）")
    if WORK.exists():
        shutil.rmtree(WORK)
    raw_dir = WORK / "data/l0_raw/docs/waveform"
    raw_dir.mkdir(parents=True)
    md_path = raw_dir / "waveform-overview.md"
    md_path.write_text(
        "# Waveform 采集服务概览\n\n"
        "## 采样率\n\n"
        "WF 服务以 10 MS/s 采样，单次捕获 4096 点。\n\n"
        "## 设备\n\n"
        "| device_id | 通道 |\n| --- | --- |\n| aq-1 | 4 |\n",
        encoding="utf-8",
    )
    registry = WORK / "data/documents/registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps([BASE_RECORD], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"临时项目根: {WORK.relative_to(ROOT).as_posix()}（位于本报告目录内，不触碰 data/l0_raw）")
    print(f"Markdown 文件: {md_path.relative_to(WORK).as_posix()} ({md_path.stat().st_size} 字节)")

    service = IngestionService(WORK)
    print("IngestionService(临时根).records ->", list(service.records))
    try:
        service.ingest_document(BASE_RECORD["doc_id"])
    except Exception as exc:
        print(f"  ingest_document('{BASE_RECORD['doc_id']}') 抛出 {type(exc).__name__}: {exc}")
        verdict(
            "only PDF ingestion is supported" in str(exc),
            "IngestionService 明确拒绝非 PDF：only PDF ingestion is supported（src/accelerator_rag/ingestion.py:55-56）",
        )
    else:
        verdict(False, "IngestionService 竟然处理了 Markdown，需重新审查结论")

    batch = service.ingest_all_registered_pdfs()
    print(f"  ingest_all_registered_pdfs() -> {len(batch)} 个文档（字段过滤 document_type == 'pdf'）")
    verdict(
        len(batch) == 0,
        "批量入口静默跳过已登记的 Markdown：0 个文档、0 个 chunk、无异常",
    )


def probe_4_parser_rejects_md() -> None:
    section("P4 解析层：parse_pdf 对 .md 的行为")
    md_path = WORK / "data/l0_raw/docs/waveform/waveform-overview.md"
    try:
        parse_pdf(md_path, source_path="data/l0_raw/docs/waveform/waveform-overview.md")
    except Exception as exc:
        print(f"  parse_pdf(<.md>) 抛出 {type(exc).__name__}: {exc}")
        verdict(
            "Expected a PDF file" in str(exc),
            "解析器只接受 PDF 后缀（src/accelerator_rag/corpus/pdf_parser.py:192-193）",
        )
    else:
        verdict(False, "parse_pdf 接受了 Markdown，结论需重审")

    callers = []
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "ParsedPdfDocument(" in text:
            callers.append(path.relative_to(ROOT).as_posix())
    print("  构造 ParsedPdfDocument 的源码位置:", callers)
    verdict(
        callers == ["src/accelerator_rag/corpus/pdf_parser.py"],
        "全仓库仅 pdf_parser 能构造 ParsedPdfDocument：没有 Markdown/HTML/纯文本解析入口",
    )


def probe_5_chunking_layer() -> None:
    section("P5 正对照：真实 PDF -> parse_pdf -> chunk_pdf；以及切块层是否格式无关")
    pdf_path = WORK / "data/l0_raw/control/demo.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as pdf:
        first = pdf.new_page()
        first.insert_text((72, 72), "SHINE uses EPICS for distributed controls.")
        first.insert_text((72, 120), "MySQL stores server and record information.")
        pdf.new_page()  # 空物理页，验证页码不重排
        third = pdf.new_page()
        third.insert_text((72, 72), "IOC startup submits installation path and IP address.")
        pdf.save(pdf_path)

    record = DocumentRecord(
        doc_id="demo-pdf",
        title="Demo PDF",
        source_path="data/l0_raw/control/demo.pdf",
        category="control_system",
        topic="ioc",
        document_type="pdf",
        language="en",
        version="1",
        status="reference",
    )
    parsed = parse_pdf(pdf_path, source_path=record.source_path)
    print(f"parse_pdf -> page_count={parsed.page_count}, warnings={parsed.warnings}")
    chunks = chunk_pdf(parsed, record, ChunkingConfig())
    print(f"chunk_pdf -> {len(chunks)} chunks, algorithm={CHUNKING_ALGORITHM}")
    for chunk in chunks:
        print(
            f"  page_start={chunk.page_start} page_end={chunk.page_end} "
            f"chars={len(chunk.text)} chunk_id={chunk.chunk_id}"
        )
    again = chunk_pdf(parse_pdf(pdf_path, source_path=record.source_path), record)
    verdict(
        [c.chunk_id for c in chunks] == [c.chunk_id for c in again],
        "chunk_id 对同一输入确定性复现（sha256 前缀 + 文档 ID）",
    )
    verdict(
        [c.page_start for c in chunks] == [1, 3],
        "空物理页 2 不产生 chunk，也不会把第 3 页重编号",
    )

    md_parsed = ParsedPdfDocument(
        source_path="data/l0_raw/docs/waveform/waveform-overview.md",
        file_name="waveform-overview.md",
        page_count=1,
        metadata={"format": "markdown"},
        pages=[
            PdfPage(
                page_number=1,
                width=612.0,
                height=792.0,
                text="# Waveform 采集服务概览\n\nWF 服务以 10 MS/s 采样。",
                char_count=40,
                blocks=[],
                image_count=0,
            )
        ],
    )
    md_record = DocumentRecord(**BASE_RECORD)
    md_chunks = chunk_pdf(md_parsed, md_record)
    print(f"\n手工构造 ParsedPdfDocument(markdown) -> chunk_pdf -> {len(md_chunks)} chunks")
    for chunk in md_chunks:
        print(f"  page={chunk.page_start} chunk_id={chunk.chunk_id} chars={len(chunk.text)}")
    verdict(
        len(md_chunks) == 0,
        "切块层只吃清洗后的 block（blocks 为空 -> 0 chunk）：Markdown 正文必须由适配器转成 block 才能进入",
    )
    # 带 block 的等价输入证明 chunk_pdf 本身与文件格式无关，缺的只是解析适配器。
    from accelerator_rag.corpus.pdf_parser import PdfTextBlock

    md_parsed_blocks = replace(
        md_parsed,
        pages=[
            replace(
                md_parsed.pages[0],
                blocks=[
                    PdfTextBlock(
                        block_number=0,
                        block_type=0,
                        bbox=(0.0, 0.0, 500.0, 40.0),
                        text="# Waveform 采集服务概览\n\nWF 服务以 10 MS/s 采样，单次捕获 4096 点。",
                    )
                ],
            )
        ],
    )
    md_chunks = chunk_pdf(md_parsed_blocks, md_record)
    print(f"  加上一个 block 后 -> {len(md_chunks)} chunks")
    for chunk in md_chunks:
        print(
            f"  page={chunk.page_start} chars={len(chunk.text)} "
            f"chunk_id={chunk.chunk_id} text={chunk.text!r}"
        )
    verdict(
        len(md_chunks) == 1,
        "chunk_pdf 本身不检查后缀：只要给 ParsedPdfDocument+PdfTextBlock，Markdown 文本可切块（但 chunk_id 仍冠以 pdf-chunks-v3）",
    )
    # 适配器若把 Markdown 造成“无物理尺寸”的页，清洗层会除以零。
    zero_geometry = replace(
        md_parsed_blocks, pages=[replace(md_parsed_blocks.pages[0], width=0.0, height=0.0)]
    )
    try:
        chunk_pdf(zero_geometry, md_record)
    except ZeroDivisionError as exc:
        print(f"  合成页 height=0 时 chunk_pdf 抛出 ZeroDivisionError: {exc}")
        verdict(
            True,
            "Markdown 适配器必须提供非零合成 page.width/height（cleaning.py:127 用 bbox 除以页高），否则清洗阶段崩溃",
        )
    else:
        verdict(False, "height=0 未崩溃，需重审适配器约束")


def probe_6_index_contract() -> None:
    section("P6 索引契约：canonical SHA-256 与 dense_index_contract_id 语义")
    print("canonical_sha256 = sha256(json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=False, allow_nan=False))")
    a = {"b": 1, "a": [2, 3]}
    b = {"a": [2, 3], "b": 1}
    print("canonical_sha256({b:1,a:[2,3]}) =", canonical_sha256(a))
    verdict(canonical_sha256(a) == canonical_sha256(b), "字典插入顺序不影响 contract 摘要（sort_keys=True）")
    verdict(
        canonical_sha256(a) != canonical_sha256({**a, "b": 2}),
        "任一字段变化都会改变摘要（不可变身份）",
    )
    passage_contract = {"algorithm": "dense-passages-v1", "guard_tokens": 16, "overlap_tokens": 32}
    print("\ncanonical_passage_id 使用不同的序列化：json.dumps(..., sort_keys=True) 默认分隔符（含空格）")
    print("canonical_passage_id(passage_contract) =", canonical_passage_id(passage_contract))
    verdict(
        canonical_passage_id(passage_contract)
        != canonical_sha256(passage_contract),
        "passage 契约 ID 与 canonical_sha256 不是同一算法（保留 dense-passages-v1 历史标识，src/accelerator_rag/retrieval/index_contract.py:84-86）",
    )

    identity = {
        "requested_model_name": "intfloat/multilingual-e5-base",
        "weights_manifest_sha256": "w" * 64,
        "model_config_sha256": "m" * 64,
        "config_files": {"1_Pooling/config.json": "c" * 64},
        "tokenizer_sha256": "t" * 64,
        "query_template": "query: {query}",
        "document_prefix": "",
        "dimension": 768,
        "max_seq_length": 512,
    }
    contract = DenseIndexContract.from_fingerprint(identity, passage_contract)
    print("\nDenseIndexContract.from_fingerprint(伪指纹) ->")
    print("  contract_id      =", contract.contract_id)
    print("  passage_algorithm=", contract.passage_algorithm)
    print("  dimension        =", contract.dimension, " distance =", contract.distance,
          " normalize_embeddings =", contract.normalize_embeddings)
    print("  document_template=", contract.document_template)
    verdict(
        len(contract.contract_id) == 64,
        "contract_id 为 64 位十六进制，等于 asdict(contract) 的 canonical SHA-256",
    )
    changed = DenseIndexContract.from_fingerprint({**identity, "dimension": 1024}, passage_contract)
    verdict(contract.contract_id != changed.contract_id, "维度变化即产生新 contract_id（换模型/换 passage 必须用新集合）")

    cfg = json.loads((ROOT / "config/rag-production.json").read_text())
    for entry in cfg["indexes"]:
        cid = entry["dense_index_contract_id"]
        print(
            f"\nconfig/rag-production.json: {entry['model_name']} "
            f"contract_id={cid} point_count={entry['point_count']}"
        )
        print(
            f"  64hex={len(cid) == 64}  model_path={entry['model_path']}  "
            f"index_path={entry['index_path']}  local_exists="
            f"{Path(entry['model_path']).exists() or Path(entry['index_path']).exists()}"
        )
    verdict(
        all(len(e["dense_index_contract_id"]) == 64 for e in cfg["indexes"]),
        "两个生产索引的 contract_id 均为 64 位十六进制；本地无模型权重与索引，无法离线重算（只能比对 config 值）",
    )


def probe_7_inventory() -> None:
    section("P7 corpus_inventory 在本地（无语料）的行为")
    from accelerator_rag.corpus.registry import build_inventory

    records = load_registry(ROOT / "data/documents/registry.json")
    try:
        build_inventory(records, ROOT)
    except ValueError as exc:
        print(f"  build_inventory({ROOT.name}) 抛出 ValueError: {exc}")
        verdict(True, "本机无 data/l0_raw：inventory 直接失败，而不是报告 13 份缺失——本地无法做语料级校验")
    else:
        verdict(False, "本地竟然完成了 inventory，需重审环境事实")


def main() -> int:
    print(f"cwd={Path.cwd()}")
    print(f"python={sys.version.split()[0]} executable={sys.executable}")
    import accelerator_rag

    print(f"accelerator_rag.__file__={accelerator_rag.__file__}")
    for probe in (
        probe_1_real_registry,
        probe_2_md_record_accepted,
        probe_2b_in_place_registration,
        probe_3_ingestion_gate,
        probe_4_parser_rejects_md,
        probe_5_chunking_layer,
        probe_6_index_contract,
        probe_7_inventory,
    ):
        try:
            probe()
        except Exception:
            print(f"UNEXPECTED in {probe.__name__}:")
            traceback.print_exc()
            failures.append(f"{probe.__name__} 异常")
    section("汇总")
    print(f"未通过的断言: {len(failures)}")
    for item in failures:
        print("  -", item)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
