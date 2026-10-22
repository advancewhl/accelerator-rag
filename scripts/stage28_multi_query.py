"""Use identical cached plans with existing E5 and Qwen3 dense indexes offline."""

from pathlib import Path
from dataclasses import asdict
from hashlib import sha256
from datetime import datetime, timezone
from time import perf_counter
import gc
import json
import shutil
import numpy as np
from accelerator_rag.retrieval.multilingual_baseline import (
    render,
    diagnose,
    REPORT,
)
from accelerator_rag.retrieval.multi_query import MultiQueryRetriever, QueryPlan
from accelerator_rag.embedding import EmbeddingModel
from accelerator_rag.retrieval.dense import DenseRetriever
from accelerator_rag.retrieval.passages import PassageBuilder
from accelerator_rag.retrieval.index_contract import DenseIndexContract
from accelerator_rag.storage.qdrant_passages import QdrantPassageStore
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.corpus.eligibility import eligibility_audit
from accelerator_rag.evaluation.retrieval import evaluate, load_queries, target_matches
from qdrant_client import QdrantClient
import torch

torch.set_num_threads(6)
root = Path.cwd()
result = json.loads((root / "reports" / f"{REPORT}.json").read_text())
history = json.loads(
    (root / "reports/rag-stage-two-seven-embedding-comparison.json").read_text()
)
query_path = root / "data/evaluation/retrieval_baseline.json"
assert (
    sha256(query_path.read_bytes()).hexdigest()
    == result["frozen_sha256"]["data/evaluation/retrieval_baseline.json"]
)
docs = IngestionService(root).ingest_all_registered_pdfs()
eligible, _ = eligibility_audit([c for d in docs for c in d.chunks])
assert (
    sha256(
        json.dumps([asdict(c) for c in eligible], sort_keys=True).encode()
    ).hexdigest()
    == result["canonical_parent_sha256"]
)
parents = {c.chunk_id: c for c in eligible}
queries = load_queries(query_path, docs, eligible_chunks=eligible)
plan_path = root / "tmp/stage-two-eight/query-plans.json"
cached = json.loads(plan_path.read_text())
assert set(cached["plans"]) == {q.query for q in queries}
plans = {
    text: QueryPlan(v["original_query"], tuple(v["subqueries"]))
    for text, v in cached["plans"].items()
}
assert all(
    text == p.original_query and len(p.subqueries) <= 3 for text, p in plans.items()
)
plan_hash = sha256(plan_path.read_bytes()).hexdigest()
result["query_planning"] = cached
result["status"] = "RUNNING_SHARED_PLAN_MULTI_QUERY"
result["multi_query"] = {
    "status": "RUNNING",
    "provider": cached["provider"],
    "destination": cached["base_url"],
    "query_plan_file_sha256": plan_hash,
    "user_explicit_authorization": True,
    "same_plans_for_both_models": True,
    "scope": "Only original query strings, fixed system prompt and fixed schema sent; no ground truth or retrieval results.",
    "fusion": {
        "method": "RRF",
        "k": 60,
        "per_query_parent_depth": 10,
        "max_subqueries": 3,
        "original_query_included": True,
        "same_dense_model_only": True,
    },
}
for name in ["intfloat/multilingual-e5-base", "Qwen/Qwen3-Embedding-0.6B"]:
    single = result["models"][name]
    identity = history["models"][name] if name.startswith("intfloat/") else single
    local = identity["fingerprint"]["resolved_local_model_path"]
    index_path = (
        str(root / identity["qdrant_path"])
        if "qdrant_path" in identity
        else identity["index_path"]
    )
    print("LOAD EXISTING INDEX", name, index_path, flush=True)
    embedder = EmbeddingModel(name, model_path=local, batch_size=8)
    fp = embedder.fingerprint()
    builder = PassageBuilder(embedder)
    contract = DenseIndexContract.from_fingerprint(fp, builder.contract)
    index_reuse = {"source_index_path": index_path, "signature_copy_required": False}
    if name.startswith("intfloat/"):
        audit = json.loads(
            (root / "reports/rag-stage-two-seven-one-evidence-audit.json").read_text()
        )
        assert (
            contract.contract_id
            == audit["dense_index_contracts"][name]["dense_index_contract_id"]
        )
        expected = {p.passage_id: p for p in builder.build(eligible)}
        source = QdrantClient(path=index_path)
        try:
            records = []
            offset = None
            while True:
                batch, offset = source.scroll(
                    identity["collection"],
                    offset=offset,
                    limit=128,
                    with_payload=True,
                    with_vectors=True,
                )
                records.extend(batch)
                if offset is None:
                    break
            decoded = {
                QdrantPassageStore.decode(
                    r.payload
                ).passage_id: QdrantPassageStore.decode(r.payload)
                for r in records
            }
            assert decoded == expected
            assert all(
                str(r.id)
                == QdrantPassageStore._point_id(
                    QdrantPassageStore.decode(r.payload).passage_id
                )
                for r in records
            )

            def vector_digest(rows):
                digest = sha256()
                for record in sorted(rows, key=lambda r: str(r.id)):
                    digest.update(str(record.id).encode())
                    digest.update(np.asarray(record.vector, dtype="<f4").tobytes())
                return digest.hexdigest()

            original_digest = vector_digest(records)
        finally:
            source.close()
        clone_path = root / "tmp/stage-two-eight/e5_reused_signed_index"
        if not clone_path.exists():
            shutil.copytree(
                index_path, clone_path, ignore=shutil.ignore_patterns(".lock")
            )
        clone = QdrantClient(path=str(clone_path))
        try:
            copied = []
            offset = None
            while True:
                batch, offset = clone.scroll(
                    identity["collection"],
                    offset=offset,
                    limit=128,
                    with_payload=True,
                    with_vectors=True,
                )
                copied.extend(batch)
                if offset is None:
                    break
            assert vector_digest(copied) == original_digest
            assert {
                QdrantPassageStore.decode(
                    r.payload
                ).passage_id: QdrantPassageStore.decode(r.payload)
                for r in copied
            } == expected
            assert all(
                r.payload.get("dense_index_contract_id") in (None, contract.contract_id)
                for r in copied
            )
            for start in range(0, len(copied), 128):
                clone.set_payload(
                    identity["collection"],
                    points=[r.id for r in copied[start : start + 128]],
                    payload={
                        "dense_index_contract_id": contract.contract_id,
                        "dense_index_contract": asdict(contract),
                    },
                    wait=True,
                )
            after = []
            offset = None
            while True:
                batch, offset = clone.scroll(
                    identity["collection"],
                    offset=offset,
                    limit=128,
                    with_vectors=True,
                    with_payload=False,
                )
                after.extend(batch)
                if offset is None:
                    break
            assert vector_digest(after) == original_digest
            QdrantPassageStore(
                clone, identity["collection"], contract
            ).verify_contract()
        finally:
            clone.close()
        index_reuse.update(
            signature_copy_required=True,
            vectors_bit_identical=True,
            vector_sha256=original_digest,
            reused_copy_path=str(clone_path),
            passages_verified=len(expected),
        )
        index_path = str(clone_path)
        print("E5 REUSED SIGNED COPY; VECTORS BIT IDENTICAL", len(expected), flush=True)
        del records, copied, after, expected, decoded
    else:
        assert fp == identity["fingerprint"]
    client = QdrantClient(path=index_path)
    try:
        store = QdrantPassageStore(client, identity["collection"], contract)
        before_count = store.point_count()
        dense = DenseRetriever(embedder, store, passage_builder=builder)
        mq = MultiQueryRetriever(dense, plans)
        started = perf_counter()
        evaluation = evaluate(mq, queries)
        diagnosis = diagnose(mq, queries)
        elapsed = perf_counter() - started
        assert store.point_count() == before_count
        originals = {c["query"]: c for c in single["evaluation"]["cases"]}
        consistency = {
            text: [h["parent_id"] for h in rows[0]["results"][:5]]
            == [r["chunk"]["chunk_id"] for r in originals[text]["results"]]
            for text, rows in mq.candidates.items()
        }
        for d in diagnosis:
            q = next(q for q in queries if q.id == d["id"])
            union = set()
            per_query = []
            for entry in mq.candidates[q.query]:
                groups = set()
                for hit in entry["results"]:
                    matched = [
                        i + 1
                        for i, g in enumerate(q.evidence_groups)
                        if any(
                            target_matches(parents[hit["parent_id"]], t)
                            for t in g.alternatives
                        )
                    ]
                    hit["matched_evidence_groups"] = matched
                    groups.update(matched)
                union.update(groups)
                per_query.append(
                    {
                        "query_index": entry["query_index"],
                        "query": entry["query"],
                        "groups_retrieved": sorted(groups),
                    }
                )
            d["candidate_union_groups"] = sorted(union)
            d["per_query_group_coverage"] = per_query
        row = {
            "evaluation": evaluation,
            "cross_language_diagnosis": diagnosis,
            "base_model": name,
            "fusion_trace": mq.traces,
            "query_candidates": mq.candidates,
            "query_plan_file_sha256": plan_hash,
            "evaluation_seconds": elapsed,
            "corpus_vectors_reused": True,
            "document_embeddings_computed": 0,
            "index_path": index_path,
            "collection": identity["collection"],
            "dense_index_contract_id": contract.contract_id,
            "point_count_before": before_count,
            "point_count_after": store.point_count(),
            "original_top5_parent_ids_match_saved_single": consistency,
            "fingerprint_used": fp,
            "index_reuse": index_reuse,
        }
        result["models"][name + " + multi-query"] = row
        render(result, root)
        print(
            "RESULT",
            name,
            evaluation["metrics"],
            [
                (
                    d["id"],
                    d["groups_at5"],
                    d["groups_at10"],
                    d["candidate_union_groups"],
                )
                for d in diagnosis
            ],
            flush=True,
        )
    finally:
        client.close()
    del mq, dense, store, embedder, builder
    gc.collect()
assert sha256(plan_path.read_bytes()).hexdigest() == plan_hash
for path, digest in result["frozen_sha256"].items():
    assert sha256((root / path).read_bytes()).hexdigest() == digest
result["multi_query"]["status"] = "EXECUTED"
result["status"] = "EXECUTED"
result["finished_at"] = datetime.now(timezone.utc).isoformat()
result.pop("answers", None)
result.pop("decision", None)
render(result, root)
