"""Build local E5/Qwen3 passage and query vectors for the phase-3 dev/val pack.

The production frozen indexes live on the GPU host.  This script uses the
production-identical local model files (fingerprints are checked against
``baseline-freeze.json``) and the production ``PassageBuilder`` contract to
compute the same dense representation offline.  It never writes an index and
never reads the held-out test split.

Outputs are local-only under ``data/evidence-pack/dense/`` and are gitignored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.embedding import EmbeddingModel, document_embedding_text  # noqa: E402
from accelerator_rag.evidence_pack.index import load_index  # noqa: E402
from accelerator_rag.retrieval.passages import PassageBuilder  # noqa: E402

MODELS = {
    "e5": (
        "intfloat/multilingual-e5-base",
        ROOT.parent
        / "accelerator-rag"
        / "tmp"
        / "stage-two-seven"
        / "models"
        / "intfloat--multilingual-e5-base",
    ),
    "qwen3": (
        "Qwen/Qwen3-Embedding-0.6B",
        ROOT.parent
        / "accelerator-rag"
        / "tmp"
        / "stage-two-eight"
        / "models"
        / "Qwen--Qwen3-Embedding-0.6B",
    ),
}
FACTS = ROOT / "data" / "facts" / "facts.jsonl"
QUESTIONS = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"
FREEZE = QUESTIONS / "baseline" / "baseline-freeze.json"


def _questions() -> list[dict]:
    rows = []
    for split in ("dev", "val"):
        payload = json.loads(
            (QUESTIONS / split / "questions.json").read_text(encoding="utf-8")
        )
        rows.extend(payload["items"])
    return rows


def _production_fingerprint(model_name: str) -> dict:
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    for item in payload["indexes"]:
        if item["model_name"] == model_name:
            return item["model_fingerprint"]
    raise SystemExit(f"model not in baseline freeze: {model_name}")


def _load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {}
    data = np.load(path, allow_pickle=False)
    return {key: data[key] for key in data.files}


def _save(path: Path, arrays: dict, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: np.asarray(value) for key, value in arrays.items()}
    payload["meta"] = np.asarray(json.dumps(meta, ensure_ascii=False, sort_keys=True))
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as handle:
        np.savez(handle, **payload)
    tmp.replace(path)


def build(model_key: str, *, batch_size: int, threads: int, limit: int | None):
    import torch

    torch.set_num_threads(threads)
    model_name, model_path = MODELS[model_key]
    if not model_path.exists():
        raise SystemExit(f"model path missing: {model_path}")
    out = ROOT / "data" / "evidence-pack" / "dense" / f"{model_key}.npz"
    checkpoint = _load_checkpoint(out)
    index = load_index(splits=("dev", "val"), facts_path=str(FACTS))
    chunks = sorted(index.chunks.values(), key=lambda item: item.chunk_id)
    if limit is not None:
        chunks = chunks[:limit]
    model = EmbeddingModel(
        model_name,
        device="cpu",
        batch_size=batch_size,
        model_path=str(model_path),
        dtype="float32",
    )
    fingerprint = model.fingerprint()
    expected = _production_fingerprint(model_name)
    checks = {
        key: fingerprint[key] == expected[key]
        for key in (
            "weights_manifest_sha256",
            "model_config_sha256",
            "tokenizer_sha256",
            "dimension",
            "max_seq_length",
        )
    }
    if not all(checks.values()):
        raise SystemExit(f"local model differs from production fingerprint: {checks}")
    builder = PassageBuilder(model)
    passages = builder.build(chunks)
    print(
        f"{model_key}: chunks={len(chunks)} passages={len(passages)} "
        f"contract={builder.contract_id}",
        flush=True,
    )

    ordered_ids = [str(value) for value in checkpoint.get("passage_ids", ())]
    ordered_parents = [str(value) for value in checkpoint.get("parent_chunk_ids", ())]
    ordered_vectors = [
        np.asarray(row, dtype=np.float32)
        for row in checkpoint.get("passage_vectors", ())
    ]
    if len(ordered_ids) != len(ordered_vectors):
        raise SystemExit("checkpoint passage ids and vectors differ in length")
    done = set(ordered_ids)
    remaining = [p for p in passages if p.passage_id not in done]
    print(
        f"{model_key}: resume done={len(done)} remaining={len(remaining)}",
        flush=True,
    )

    meta = {
        "model_key": model_key,
        "model_name": model_name,
        "model_path": str(model_path),
        "fingerprint": fingerprint,
        "production_fingerprint": expected,
        "fingerprint_match": checks,
        "passage_contract_id": builder.contract_id,
        "passage_contract": builder.contract,
        "device": "cpu",
        "dtype": "float32",
        "batch_size": batch_size,
        "threads": threads,
        "note": (
            "CPU inference with production-identical weights and PassageBuilder; "
            "not the production CUDA index. Query vectors use the same model contract."
        ),
    }
    start = time.time()

    def checkpoint_save(query_ids=(), query_vectors=()):
        _save(
            out,
            {
                "passage_ids": ordered_ids,
                "parent_chunk_ids": ordered_parents,
                "passage_vectors": np.vstack(ordered_vectors)
                if ordered_vectors
                else np.zeros((0, model.dimension), np.float32),
                "query_ids": list(query_ids),
                "query_vectors": np.vstack(query_vectors)
                if len(query_vectors)
                else np.zeros((0, model.dimension), np.float32),
            },
            meta,
        )

    for offset in range(0, len(remaining), batch_size):
        batch = remaining[offset : offset + batch_size]
        vectors = model.embed_token_safe_documents(
            [document_embedding_text(p) for p in batch]
        )
        ordered_ids.extend(p.passage_id for p in batch)
        ordered_parents.extend(p.parent_chunk_id for p in batch)
        ordered_vectors.extend(np.asarray(row, dtype=np.float32) for row in vectors)
        if (offset // batch_size) % 10 == 9 or offset + batch_size >= len(remaining):
            checkpoint_save()
            print(
                f"{model_key}: encoded {len(ordered_vectors)}/{len(passages)} "
                f"elapsed={time.time() - start:.0f}s",
                flush=True,
            )

    by_id = {
        pid: vector for pid, vector in zip(ordered_ids, ordered_vectors, strict=True)
    }
    final_ids = [p.passage_id for p in passages]
    final_parents = [p.parent_chunk_id for p in passages]
    final_vectors = np.vstack([by_id[pid] for pid in final_ids]).astype(np.float32)

    done_queries = {
        str(qid): np.asarray(vector, dtype=np.float32)
        for qid, vector in zip(
            checkpoint.get("query_ids", ()),
            checkpoint.get("query_vectors", ()),
            strict=False,
        )
    }
    query_ids = [question["base_id"] for question in _questions()]
    query_vectors = []
    for question in _questions():
        vector = done_queries.get(question["base_id"])
        if vector is None:
            vector = model.embed_query(question["query"])
        query_vectors.append(vector)
    _save(
        out,
        {
            "passage_ids": final_ids,
            "parent_chunk_ids": final_parents,
            "passage_vectors": final_vectors,
            "query_ids": query_ids,
            "query_vectors": np.vstack(query_vectors).astype(np.float32),
        },
        meta,
    )
    print(
        f"{model_key}: done passages={len(final_ids)} queries={len(query_ids)} "
        f"total={time.time() - start:.0f}s -> {out}",
        flush=True,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=sorted(MODELS))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None, help="debug only")
    args = parser.parse_args(argv)
    build(args.model, batch_size=args.batch_size, threads=args.threads, limit=args.limit)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
