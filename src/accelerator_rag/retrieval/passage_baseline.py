"""Stage 2.6: frozen canonical corpus, historical direct vectors vs safe passages."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from qdrant_client import QdrantClient
from accelerator_rag.corpus.eligibility import eligibility_audit
from accelerator_rag.corpus.chunking import CHUNKING_ALGORITHM
from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.embedding import EmbeddingModel
from accelerator_rag.evaluation.passage_comparison import (
    comparison_markdown,
    query_comparison,
    truncation_diagnosis,
)
from accelerator_rag.evaluation.retrieval import evaluate, load_queries
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.retrieval.bm25 import BM25Retriever
from accelerator_rag.retrieval.corpus_baseline import _git, _write
from accelerator_rag.retrieval.index_contract import DenseIndexContract
from accelerator_rag.retrieval.dense import DenseRetriever, DirectChunkDenseRetriever
from accelerator_rag.retrieval.passages import (
    PassageBuilder,
    PassageConfig,
    passage_statistics,
)
from accelerator_rag.storage import QdrantVectorStore
from accelerator_rag.storage.qdrant_passages import QdrantPassageStore

MODEL = "BAAI/bge-small-zh-v1.5"


def _same_rankings(actual, historical, *, scores=False):
    if actual["metrics"] != historical["metrics"]:
        raise ValueError("historical metric control mismatch")
    old = {c["id"]: c for c in historical["cases"]}
    for c in actual["cases"]:
        prev = old[c["id"]]
        if c["first_complete_rank"] != prev["first_complete_rank"] or [
            r["chunk"]["chunk_id"] for r in c["results"]
        ] != [r["chunk"]["chunk_id"] for r in prev["results"]]:
            raise ValueError(f"historical ranking control mismatch: {c['id']}")
        if scores and any(
            abs(x["score"] - y["score"]) > 1e-8
            for x, y in zip(c["results"], prev["results"], strict=True)
        ):
            raise ValueError("BM25 score control mismatch")


def run(args):
    root = args.project_root.resolve()
    history_path = root / "reports/rag-stage-two-five-retrieval-baseline.json"
    history = json.loads(history_path.read_text())
    qpath = (root / args.qdrant_path).resolve()
    oldpath = (root / history["index"]["qdrant_path"]).resolve()
    raw = (root / "data/l0_raw").resolve()
    if (
        not args.collection.startswith("knowledge_stage26")
        or qpath == root
        or qpath.is_relative_to(raw)
        or raw.is_relative_to(qpath)
        or qpath == oldpath
        or qpath == root / "tmp/stage-two-qdrant"
    ):
        raise ValueError("Stage 2.6 requires a dedicated passage collection/path")
    if args.batch_size <= 0:
        raise ValueError("positive batch_size required")
    query_path = root / "data/evaluation/retrieval_baseline.json"
    query_hash = sha256(query_path.read_bytes()).hexdigest()
    if query_hash != history["metadata"]["query_set_sha256"]:
        raise ValueError("frozen query set SHA256 changed")
    before = perf_counter()
    documents = IngestionService(root).ingest_all_registered_pdfs()
    chunks = [c for d in documents for c in d.chunks]
    eligible, policy = eligibility_audit(chunks)
    sources = {
        d.record.source_path: sha256(
            (root / d.record.source_path).read_bytes()
        ).hexdigest()
        for d in documents
    }
    if (
        sources != history["metadata"]["source_sha256"]
        or CHUNKING_ALGORITHM != "pdf-chunks-v3"
        or json.loads(json.dumps(policy)) != history["retrieval_eligibility"]
    ):
        raise ValueError("corpus/eligibility control mismatch")
    queries = load_queries(query_path, documents, eligible_chunks=eligible)
    print(
        f"Frozen corpus: {len(chunks)} chunks, {len(eligible)} eligible; {len(queries)} queries",
        flush=True,
    )
    bm25 = evaluate(BM25Retriever(eligible), queries)
    _same_rankings(bm25, history["bm25"], scores=True)
    embedder = EmbeddingModel(MODEL, local_files_only=True, batch_size=args.batch_size)
    if (
        embedder.QUERY_TEMPLATE != history["index"]["query_template"]
        or embedder.dimension != history["index"]["dimension"]
    ):
        raise ValueError("embedding/query contract changed")
    # Reuse historical A vectors; deliberately do not re-embed oversized chunks.
    # Full payload/parent equality proves current canonical representation is A's.
    if not oldpath.is_dir():
        raise ValueError("historical Stage 2.5 index is missing")
    client_a = QdrantClient(path=str(oldpath))
    try:
        expected = {c.chunk_id: c for c in eligible}
        seen = set()
        offset = None
        while True:
            rows, offset = client_a.scroll(
                history["index"]["collection"],
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for row in rows:
                c = KnowledgeChunk(**row.payload)
                if c.chunk_id in seen or c != expected.get(c.chunk_id):
                    raise ValueError("Stage 2.5 canonical parent mismatch")
                seen.add(c.chunk_id)
            if offset is None:
                break
        if seen != expected.keys():
            raise ValueError("Stage 2.5 index parent set mismatch")
        direct = DirectChunkDenseRetriever(
            embedder,
            QdrantVectorStore(
                client_a, history["index"]["collection"], embedder.dimension
            ),
        )
        dense_a = evaluate(direct, queries)
        _same_rankings(dense_a, history["dense"])
    finally:
        client_a.close()
    builder = PassageBuilder(
        embedder,
        PassageConfig(
            guard_tokens=args.guard_tokens, overlap_tokens=args.overlap_tokens
        ),
    )
    passages = builder.build(eligible)
    stats = passage_statistics(passages, builder)
    diagnosis = truncation_diagnosis(embedder, queries, eligible, dense_a)
    metadata = {
        "embedding_model": MODEL,
        "model_max_seq_length": embedder.max_seq_length,
        "passage_algorithm": stats["algorithm"],
        "passage_config": asdict(builder.config),
        "tokenizer_contract": builder.contract,
        "query_template": embedder.QUERY_TEMPLATE,
        "query_set_sha256": query_hash,
        "source_sha256": sources,
        "chunking_algorithm": CHUNKING_ALGORITHM,
        "schema_version": 2,
        "judgment_revision": "evidence-contract-v1",
        "historical_report_sha256": sha256(history_path.read_bytes()).hexdigest(),
        "git": _git(root),
        "code_sha256": {
            p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "src/accelerator_rag").rglob("*.py"))
            if "agent" not in p.relative_to(root / "src/accelerator_rag").parts
        },
        "local_files_only": True,
    }
    print(
        f"Passages: {len(passages)}; split parents: {stats['parents_split']}; exceeding: {stats['passages_exceeding_limit']}",
        flush=True,
    )
    preparation = perf_counter() - before
    qpath.mkdir(parents=True, exist_ok=True)
    client_b = QdrantClient(path=str(qpath))
    try:
        store = QdrantPassageStore(
            client_b,
            args.collection,
            DenseIndexContract.from_fingerprint(
                embedder.fingerprint(), builder.contract
            ),
        )
        dense = DenseRetriever(
            embedder,
            store,
            passage_builder=builder,
            oversample_factor=args.oversample_factor,
        )
        indexed = dense.index_corpus(
            eligible,
            document_ids=[d.record.doc_id for d in documents],
            batch_size=args.batch_size,
            passages=passages,
        )
        print(
            f"Indexed {indexed['point_count']} passages in {indexed['embedding_seconds']:.2f}s embedding",
            flush=True,
        )

        class Traced:
            def __init__(self):
                self.traces = {}

            def search(self, query, *, top_k):
                results = dense.search(query, top_k)
                self.traces[query] = list(dense.last_passage_trace)
                return results

        traced = Traced()
        dense_b = evaluate(traced, queries)
        for c in dense_b["cases"]:
            c["passage_trace"] = traced.traces[c["query"]]
        stored = list(store.all_passages())
        if {p.passage_id: p for p in stored} != {p.passage_id: p for p in passages}:
            raise RuntimeError("passage payload round-trip mismatch")
    finally:
        client_b.close()
    result = {
        "metadata": metadata,
        "controls": {
            "query_hash_identical": True,
            "sources_identical": True,
            "canonical_parents_identical_to_stage25_index": True,
            "eligibility_identical": True,
            "bm25_metrics_rankings_scores_identical": True,
            "live_stage25_dense_metrics_rankings_match_history": True,
            "a_vectors": "Preserved Stage 2.5 direct-chunk vectors with actual historical truncation; no new A document embedding. Queries re-run locally.",
            "oversample_factor": args.oversample_factor,
            "distance": "cosine",
            "ground_truth_all_alternatives_validated": True,
        },
        "passage_statistics": stats,
        "retrieval_eligibility": policy,
        "bm25": bm25,
        "dense_a": dense_a,
        "dense_b": dense_b,
        "query_comparison": query_comparison(dense_a, dense_b),
        "truncation_diagnosis": diagnosis,
        "index": {
            "collection": args.collection,
            "qdrant_path": str(qpath.relative_to(root))
            if qpath.is_relative_to(root)
            else str(qpath),
            "preparation_seconds": preparation,
            **indexed,
            "payload_parent_integrity_verified": True,
        },
    }
    _write(root / "reports/rag-stage-two-six-dense-passage.json", result)
    (root / "reports/rag-stage-two-six-dense-passage.md").write_text(
        comparison_markdown(result)
    )
    print(
        json.dumps(
            {
                "A": dense_a["metrics"],
                "B": dense_b["metrics"],
                "changes": result["query_comparison"]["counts"],
                "diagnosis": {k: v for k, v in diagnosis.items() if k != "queries"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--qdrant-path", type=Path, default=Path("tmp/stage-two-six-qdrant")
    )
    parser.add_argument("--collection", default="knowledge_stage26")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--guard-tokens", type=int, default=16)
    parser.add_argument("--overlap-tokens", type=int, default=32)
    parser.add_argument("--oversample-factor", type=int, default=4)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
