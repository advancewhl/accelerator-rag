"""Serial ingestion, corpus audit and independent full-corpus retrieval baselines."""

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from time import perf_counter
from zoneinfo import ZoneInfo

from qdrant_client import QdrantClient

from accelerator_rag.corpus.audit import AuditConfig, audit_corpus
from accelerator_rag.corpus.eligibility import eligibility_audit
from accelerator_rag.embedding import EmbeddingModel, audit_embedding_inputs
from accelerator_rag.evaluation.reporting import audit_markdown, baseline_markdown
from accelerator_rag.evaluation.retrieval import evaluate, load_queries
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.retrieval.bm25 import BM25Retriever
from accelerator_rag.retrieval.dense import DirectChunkDenseRetriever as DenseRetriever
from accelerator_rag.storage import QdrantVectorStore


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _git(root: Path) -> dict:
    try:
        return {
            "head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "dirty": bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=root, text=True
                )
            ),
            "identity_note": "HEAD is a base commit, not the identity of this dirty run; see code hashes.",
        }
    except subprocess.CalledProcessError:
        return {"head": None, "dirty": None}


def run(args: argparse.Namespace) -> dict:
    root = args.project_root.resolve()
    qpath = (root / args.qdrant_path).resolve()
    source_root = (root / "data/l0_raw").resolve()
    if (
        qpath == root
        or qpath.is_relative_to(source_root)
        or source_root.is_relative_to(qpath)
    ):
        raise ValueError(
            "Qdrant path must be separate from the project and raw sources"
        )
    if not args.collection.startswith("knowledge_stage25"):
        raise ValueError(
            "this baseline only owns knowledge_stage25-prefixed collections"
        )
    if args.batch_size <= 0:
        raise ValueError("batch_size must be positive")
    reports = root / "reports"
    service = IngestionService(root)
    durations = {}
    before = perf_counter()
    documents = service.ingest_all_registered_pdfs()
    durations["parse_clean_chunk"] = perf_counter() - before
    print(
        f"Ingested {len(documents)} PDFs in {durations['parse_clean_chunk']:.2f}s",
        flush=True,
    )
    chunks = [c for d in documents for c in d.chunks]
    eligible, eligibility = eligibility_audit(chunks)
    before = perf_counter()
    audit = audit_corpus(
        documents,
        sum(r.document_type == "pdf" for r in service.records.values()),
        service.chunking,
        generated_on=args.generated_on,
        config=AuditConfig(many_chunks_per_page=args.many_chunks_per_page),
    ).to_dict()
    durations["corpus_audit"] = perf_counter() - before
    audit["retrieval_eligibility"] = eligibility
    audit["cleaning_effects"] = {
        "null_before": sum(
            p.text.count("\x00") for d in documents for p in d.parsed.pages
        ),
        "null_after": sum(c.text.count("\x00") for c in chunks),
        "replacement_before": sum(
            p.text.count("\ufffd") for d in documents for p in d.parsed.pages
        ),
        "replacement_after": sum(c.text.count("\ufffd") for c in chunks),
        "replacement_chunks": sum("\ufffd" in c.text for c in chunks),
        "pua_policy": "Unexplained PUA preserved; insufficient multi-document evidence for safe bullet mapping.",
    }
    metadata = audit["metadata"]
    metadata["git"] = _git(root)
    metadata["source_sha256"] = {
        d.record.source_path: sha256(
            (root / d.record.source_path).read_bytes()
        ).hexdigest()
        for d in documents
    }
    metadata["code_sha256"] = {
        p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / "src/accelerator_rag").rglob("*.py"))
        if "agent" not in p.relative_to(root / "src/accelerator_rag").parts
    }
    _write(reports / "rag-stage-two-five-corpus-audit.json", audit)
    (reports / "rag-stage-two-five-corpus-audit.md").write_text(
        audit_markdown(audit), encoding="utf-8"
    )
    # Freeze and validate ground truth against raw pages before any ranking.
    query_path = root / args.queries
    queries = load_queries(query_path, documents, eligible_chunks=eligible)
    metadata["query_set_sha256"] = sha256(query_path.read_bytes()).hexdigest()
    query_metadata = json.loads(query_path.read_text())
    metadata["query_schema_version"] = query_metadata["schema_version"]
    metadata["judgment_revision"] = query_metadata["judgment_revision"]
    # Re-write audit with the same complete metadata as retrieval report.
    _write(reports / "rag-stage-two-five-corpus-audit.json", audit)
    (reports / "rag-stage-two-five-corpus-audit.md").write_text(
        audit_markdown(audit), encoding="utf-8"
    )
    print(f"Audit: {len(chunks)} chunks; queries validated: {len(queries)}", flush=True)
    before = perf_counter()
    bm25 = BM25Retriever(eligible)
    durations["bm25_build"] = perf_counter() - before
    before = perf_counter()
    bm25_report = evaluate(bm25, queries)
    durations["bm25_evaluation"] = perf_counter() - before
    before = perf_counter()
    # A missing local model is fatal, never substituted or downloaded.
    embedder = EmbeddingModel(
        args.model, local_files_only=True, batch_size=args.batch_size
    )
    durations["model_load"] = perf_counter() - before
    input_audit = audit_embedding_inputs(embedder, eligible)
    qpath.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(qpath))
    try:
        store = QdrantVectorStore(client, args.collection, embedder.dimension)
        dense = DenseRetriever(embedder, store)
        print(
            f"Embedding {len(eligible)} eligible chunks, batch size {args.batch_size}",
            flush=True,
        )
        indexed = dense.index_corpus(
            eligible,
            document_ids=[d.record.doc_id for d in documents],
            batch_size=args.batch_size,
        )
        durations.update(
            {k: indexed[k] for k in ["embedding_seconds", "qdrant_indexing_seconds"]}
        )
        print(
            f"Qdrant count: {indexed['point_count']}; embedding: {indexed['embedding_seconds']:.2f}s",
            flush=True,
        )
        before = perf_counter()
        dense_report = evaluate(dense, queries)
        durations["dense_evaluation"] = perf_counter() - before
        index = {
            "embedding_model": args.model,
            "dimension": embedder.dimension,
            "query_template": embedder.QUERY_TEMPLATE,
            "local_files_only": True,
            "collection": args.collection,
            "qdrant_path": qpath.relative_to(root).as_posix()
            if qpath.is_relative_to(root)
            else str(qpath),
            "chunk_count": len(eligible),
            "unique_chunk_count": len({c.chunk_id for c in eligible}),
            "point_count": indexed["point_count"],
            "duplicate_count": 0,
            "embedded_chunk_count": indexed["embedded_chunk_count"],
            "batch_size": args.batch_size,
        }
    finally:
        client.close()
    durations["evaluation_total"] = (
        durations["bm25_evaluation"] + durations["dense_evaluation"]
    )
    report = {
        "metadata": metadata,
        "index": index,
        "durations_seconds": durations,
        "retrieval_eligibility": eligibility,
        "embedding_input_audit": input_audit,
        "cleaning_effects": audit["cleaning_effects"],
        "ground_truth_validation": {
            "queries": len(queries),
            "answerable": sum(q.answerable for q in queries),
            "all_declared_alternatives_in_raw_and_eligible_chunks": True,
        },
        "bm25": bm25_report,
        "dense": dense_report,
    }
    from accelerator_rag.evaluation.comparison import compare_stage_two

    history = reports / "rag-stage-two-retrieval-baseline.json"
    if history.exists():
        report["stage_two_comparison"] = compare_stage_two(
            json.loads(history.read_text()), report, queries
        )
    _write(reports / "rag-stage-two-five-retrieval-baseline.json", report)
    (reports / "rag-stage-two-five-retrieval-baseline.md").write_text(
        baseline_markdown(report), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "corpus": audit["overview"],
                "index": index,
                "bm25": bm25_report["metrics"],
                "dense": dense_report["metrics"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--collection", default="knowledge_stage25")
    parser.add_argument(
        "--qdrant-path", type=Path, default=Path("tmp/stage-two-five-qdrant")
    )
    parser.add_argument("--model", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--many-chunks-per-page", type=int, default=10)
    parser.add_argument(
        "--queries", type=Path, default=Path("data/evaluation/retrieval_baseline.json")
    )
    parser.add_argument(
        "--generated-on",
        default=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
