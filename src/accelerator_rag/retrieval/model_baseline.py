"""Stage 2.7 controlled, local-only embedding comparison; download separately."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
import gc
import platform
from datetime import datetime, timezone
from importlib.metadata import version

import numpy as np
from qdrant_client import QdrantClient

from accelerator_rag.corpus.chunking import CHUNKING_ALGORITHM
from accelerator_rag.corpus.eligibility import eligibility_audit
from accelerator_rag.embedding import EmbeddingModel
from accelerator_rag.evaluation.model_comparison import (
    complementarity,
    pairwise,
    markdown,
)
from accelerator_rag.evaluation.retrieval import evaluate, load_queries, target_matches
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.retrieval.bm25 import BM25Retriever
from accelerator_rag.retrieval.corpus_baseline import _write, _git
from accelerator_rag.retrieval.index_contract import DenseIndexContract
from accelerator_rag.retrieval.dense import DenseRetriever
from accelerator_rag.retrieval.passage_baseline import _same_rankings
from accelerator_rag.retrieval.passages import PassageBuilder, passage_statistics
from accelerator_rag.storage.qdrant_passages import QdrantPassageStore

CONTROL = "BAAI/bge-small-zh-v1.5"
CANDIDATES = [CONTROL, "BAAI/bge-base-zh-v1.5", "intfloat/multilingual-e5-base"]
KNOWN = {
    "xfel-rf",
    "xfel-normal-energy",
    "shine-ioc-management",
    "shine-ioc-startup",
    "shine-main-linac",
    "shine-compressors",
    "cryo-interlock",
}


def copy_control(root, history, store, expected):
    """Read-only historical vectors; validate every passage before new writes."""
    client = QdrantClient(path=str(root / history["index"]["qdrant_path"]))
    try:
        source = QdrantPassageStore(
            client, history["index"]["collection"], store.contract
        )
        if {p.passage_id: p for p in source.all_passages()} != expected:
            raise ValueError("control passage IDs/content/parents changed")
        offset = None
        while True:
            rows, offset = client.scroll(
                history["index"]["collection"],
                offset=offset,
                limit=128,
                with_vectors=True,
                with_payload=True,
            )
            store.upsert_passages(
                [source.decode(r.payload) for r in rows],
                np.asarray([r.vector for r in rows]),
            )
            if offset is None:
                break
    finally:
        client.close()


class Traced:
    def __init__(self, dense):
        self.dense, self.traces = dense, {}

    def search(self, query, *, top_k):
        results = self.dense.search(query, top_k)
        self.traces[query] = list(self.dense.last_passage_trace)
        return results


def run(args):
    root = args.project_root.resolve()
    history_path = root / "reports/rag-stage-two-six-dense-passage.json"
    history = json.loads(history_path.read_text())
    frozen_modules = [
        "corpus/chunking.py",
        "corpus/cleaning.py",
        "corpus/eligibility.py",
        "domain/knowledge.py",
        "evaluation/retrieval.py",
        "retrieval/passages.py",
        "retrieval/bm25.py",
    ]
    # Fixture projects use the installed implementation, just like real runs.
    source_root = Path(__file__).resolve().parents[1]
    frozen_hashes = {
        "src/accelerator_rag/" + rel: sha256(
            (source_root / rel).read_bytes()
        ).hexdigest()
        for rel in frozen_modules
    }
    if any(
        history["metadata"]["code_sha256"].get(k) != v for k, v in frozen_hashes.items()
    ):
        raise ValueError(
            "frozen Stage 2.6 evaluation/representation implementation changed"
        )
    query_path = root / "data/evaluation/retrieval_baseline.json"
    query_hash = sha256(query_path.read_bytes()).hexdigest()
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
        query_hash != history["metadata"]["query_set_sha256"]
        or sources != history["metadata"]["source_sha256"]
        or CHUNKING_ALGORITHM != "pdf-chunks-v3"
        or json.loads(json.dumps(policy)) != history["retrieval_eligibility"]
    ):
        raise ValueError("frozen corpus/query/eligibility controls changed")
    queries = load_queries(query_path, documents, eligible_chunks=eligible)
    bm25 = evaluate(BM25Retriever(eligible), queries)
    _same_rankings(bm25, history["bm25"], scores=True)
    work = root / "tmp/stage-two-seven"
    work.mkdir(parents=True, exist_ok=True)
    result = {
        "metadata": {
            "stage": "2.7",
            "run_started_at_utc": datetime.now(timezone.utc).isoformat(),
            "software_versions": {
                name: version(name)
                for name in [
                    "torch",
                    "sentence-transformers",
                    "transformers",
                    "tokenizers",
                    "qdrant-client",
                    "numpy",
                    "PyMuPDF",
                    "jieba",
                ]
            },
            "cpu": next(
                (
                    line.split(":", 1)[1].strip()
                    for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name")
                ),
                platform.processor(),
            ),
            "query_set_sha256": query_hash,
            "source_sha256": sources,
            "chunking_algorithm": CHUNKING_ALGORITHM,
            "judgment_revision": "evidence-contract-v1",
            "canonical_parent_sha256": sha256(
                json.dumps([asdict(c) for c in eligible], sort_keys=True).encode()
            ).hexdigest(),
            "historical_stage26_report_sha256": sha256(
                history_path.read_bytes()
            ).hexdigest(),
            "git": _git(root),
            "local_files_only": True,
            "device": "cpu",
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "batch_size": args.batch_size,
            "torch_threads": args.threads,
            "candidate_selection": "BGE-small control; larger Chinese BGE-base; multilingual E5-base. Online download explicitly authorized; all formal encoding offline.",
            "code_sha256": {
                p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
                for p in sorted((root / "src/accelerator_rag").rglob("*.py"))
                if "agent" not in p.relative_to(root / "src/accelerator_rag").parts
            },
        },
        "controls": {
            "sources_queries_eligibility_identical": True,
            "bm25_rankings_scores_identical": True,
            "distance": "cosine",
            "parent_aggregation": "max-child",
            "passage_guard_tokens": 16,
            "overlap_tokens": 32,
            "threshold": None,
        },
        "retrieval_eligibility": policy,
        "bm25": bm25,
        "models": {},
        "excluded": [],
    }
    for name in args.models:
        slug = name.replace("/", "--").lower()
        local = work / "models" / name.replace("/", "--")
        print(f"Loading {name}", flush=True)
        before = perf_counter()
        try:
            embedder = EmbeddingModel(
                name,
                model_path=str(local) if local.is_dir() else None,
                batch_size=args.batch_size,
            )
            load_seconds = perf_counter() - before
            before = perf_counter()
            fingerprint = embedder.fingerprint()
            fingerprint_seconds = perf_counter() - before
        except Exception as exc:
            result["excluded"].append(
                {"model": name, "error_type": type(exc).__name__, "reason": str(exc)}
            )
            print(f"Excluded {name}: {exc}", flush=True)
            continue
        before = perf_counter()
        builder = PassageBuilder(embedder)
        passages = builder.build(eligible)
        stats = passage_statistics(passages, builder)
        prep_seconds = perf_counter() - before
        contract = DenseIndexContract.from_fingerprint(fingerprint, builder.contract)
        expected = {p.passage_id: p for p in passages}
        print(
            f"{name}: {len(passages)} passages; zero-truncation={stats['passages_exceeding_limit'] == 0}",
            flush=True,
        )
        path = work / slug
        path.mkdir(parents=True, exist_ok=True)
        identity_path = path / "model-identity.json"
        identity = {
            "fingerprint": fingerprint,
            "passage_contract": builder.contract,
            "canonical_parent_sha256": result["metadata"]["canonical_parent_sha256"],
        }
        collection = "knowledge_stage27_" + slug.replace("-", "_")
        client = QdrantClient(path=str(path / "qdrant"))
        try:
            store = QdrantPassageStore(client, collection, contract)
            dense = DenseRetriever(embedder, store, passage_builder=builder)
            existing = {p.passage_id: p for p in store.all_passages()}
            before = perf_counter()
            reused = False
            if identity_path.exists():
                if json.loads(identity_path.read_text()) != identity:
                    raise ValueError(
                        "existing model index fingerprint/contract mismatch"
                    )
                if existing != expected:
                    raise ValueError("existing model index passage integrity mismatch")
                indexed = {
                    "embedding_seconds": 0,
                    "qdrant_indexing_seconds": 0,
                    "point_count": store.point_count(),
                    "embedded_passage_count": 0,
                    "unique_parent_count": len(eligible),
                }
                reused = True
            elif name == CONTROL:
                if existing:
                    raise ValueError("unidentified nonempty control index")
                if stats["contract_id"] != history["passage_statistics"]["contract_id"]:
                    raise ValueError("Stage 2.6 passage contract changed")
                copy_control(root, history, store, expected)
                indexed = {
                    "embedding_seconds": 0,
                    "qdrant_indexing_seconds": perf_counter() - before,
                    "point_count": store.point_count(),
                    "embedded_passage_count": 0,
                    "unique_parent_count": len(eligible),
                }
                reused = True
            else:
                indexed = dense.index_corpus(
                    eligible,
                    document_ids=[d.record.doc_id for d in documents],
                    batch_size=args.batch_size,
                    passages=passages,
                )
            if {p.passage_id: p for p in store.all_passages()} != expected:
                raise ValueError("stored passage parent integrity mismatch")
            _write(identity_path, identity)
        finally:
            client.close()
        # Evaluate only after a real persistent reopen.
        client = QdrantClient(path=str(path / "qdrant"))
        try:
            store = QdrantPassageStore(client, collection, contract)
            dense = DenseRetriever(embedder, store, passage_builder=builder)
            traced = Traced(dense)
            before = perf_counter()
            evaluation = evaluate(traced, queries)
            evaluation_seconds = perf_counter() - before
            by_id = {q.id: q for q in queries}
            for c in evaluation["cases"]:
                c["passage_trace"] = traced.traces[c["query"]]
                satisfied = set()
                c["first_complete_passage_rank"] = None
                q = by_id[c["id"]]
                for r, t in zip(c["results"], c["passage_trace"], strict=True):
                    from dataclasses import replace
                    from accelerator_rag.domain.knowledge import KnowledgeChunk

                    matched = replace(
                        KnowledgeChunk(**r["chunk"]), text=t["passage_excerpt"]
                    )
                    groups = [
                        i
                        for i, g in enumerate(q.evidence_groups)
                        if any(
                            target_matches(matched, target) for target in g.alternatives
                        )
                    ]
                    t["matched_evidence"] = bool(groups)
                    t["matched_evidence_groups"] = groups
                    satisfied.update(groups)
                    complete = (
                        bool(satisfied)
                        if q.judgment_mode == "any"
                        else bool(q.evidence_groups)
                        and len(satisfied) == len(q.evidence_groups)
                    )
                    if complete and c["first_complete_passage_rank"] is None:
                        c["first_complete_passage_rank"] = r["rank"]
            if name == CONTROL:
                _same_rankings(evaluation, history["dense_b"])
        finally:
            client.close()
        row = {
            "fingerprint": fingerprint,
            "passage_statistics": stats,
            "collection": collection,
            "qdrant_path": str((path / "qdrant").relative_to(root)),
            "timing": {
                "model_load_seconds": load_seconds,
                "fingerprint_seconds": fingerprint_seconds,
                "passage_preparation_seconds": prep_seconds,
                **indexed,
                "evaluation_seconds": evaluation_seconds,
            },
            "vectors_reused": reused,
            "historical_control_embedding_seconds": history["index"][
                "embedding_seconds"
            ]
            if name == CONTROL
            else None,
            "control_reuse_note": "Identical passage IDs/content/canonical parents verified against Stage 2.6; query rankings/metrics revalidated. Current local weights fingerprint recorded now; historical report had no weights fingerprint, so byte identity at the historical run cannot be proved retrospectively."
            if name == CONTROL
            else None,
            "evaluation": evaluation,
            "complementarity": complementarity(bm25, evaluation),
            "known_failures": [c for c in evaluation["cases"] if c["id"] in KNOWN],
            "cross_language": [
                {
                    "id": c["id"],
                    "query_language": c["language"],
                    "target_languages": sorted(
                        {
                            d.record.language
                            for d in documents
                            for g in c["evidence_groups"]
                            for t in g["alternatives"]
                            if d.record.doc_id == t["document_id"]
                        }
                    ),
                    "first_complete_rank": c["first_complete_rank"],
                    "top5_parent_ids": [r["chunk"]["chunk_id"] for r in c["results"]],
                }
                for c in evaluation["cases"]
                if c["answerable"] and c["language_relation"] == "cross_language"
            ],
        }
        checkpoint = path / "measurement.json"
        # Preserve measured first-build costs when explicitly reusing an index.
        if reused and checkpoint.exists():
            previous = json.loads(checkpoint.read_text())
            row["first_build_timing"] = previous.get(
                "first_build_timing", previous["timing"]
            )
        _write(checkpoint, row)
        result["models"][name] = row
        result["pairwise"] = pairwise(
            {k: v["evaluation"] for k, v in result["models"].items()}
        )
        _write(work / "comparison-progress.json", result)
        print(
            f"{name}: {evaluation['metrics']}; embedding={indexed['embedding_seconds']:.2f}s",
            flush=True,
        )
        del embedder, dense, builder, traced, passages
        gc.collect()
    for rel in frozen_modules:
        if (
            sha256((source_root / rel).read_bytes()).hexdigest()
            != frozen_hashes["src/accelerator_rag/" + rel]
        ):
            raise ValueError("frozen implementation changed during model comparison")
    result["metadata"]["frozen_implementation_sha256"] = frozen_hashes
    trial = work / "interrupted-trial.json"
    if trial.exists():
        result["metadata"]["interrupted_trial"] = json.loads(trial.read_text())
    for name, row in result["models"].items():
        local = Path(row["fingerprint"]["resolved_local_model_path"])
        card = local / "README.md"
        if card.is_file():
            row["encoding_contract_source"] = {
                "local_path": str(card),
                "sha256": sha256(card.read_bytes()).hexdigest(),
                "publisher_url": "https://huggingface.co/"
                + name
                + "/blob/main/README.md",
            }
        receipt = local / ".cache/huggingface/download/config.json.metadata"
        if receipt.is_file():
            row["download_provenance"] = {
                "source": "local huggingface_hub download metadata file",
                "path": str(receipt),
                "downloaded_commit": receipt.read_text().splitlines()[0],
            }
    if CONTROL not in result["models"]:
        raise RuntimeError("BGE-small control unavailable; comparison invalid")
    result["metadata"]["run_completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    review_path = root / "data/evaluation/stage27-manual-review.json"
    if review_path.exists():
        from accelerator_rag.evaluation.manual_review import (
            apply_manual_review,
            load_manual_review,
        )

        result = apply_manual_review(result, load_manual_review(review_path))
    _write(root / "reports/rag-stage-two-seven-embedding-comparison.json", result)
    (root / "reports/rag-stage-two-seven-embedding-comparison.md").write_text(
        markdown(result)
    )
    return result


def main():
    import torch

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--models", nargs="+", choices=CANDIDATES, default=CANDIDATES)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--threads", type=int, default=6)
    args = parser.parse_args()
    if (
        args.batch_size <= 0
        or args.threads <= 0
        or len(set(args.models)) != len(args.models)
    ):
        parser.error("positive batch size/threads and unique models required")
    torch.set_num_threads(args.threads)
    run(args)


if __name__ == "__main__":
    main()
