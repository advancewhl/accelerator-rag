"""Add registered Markdown documents into the two frozen dense collections.

This script mutates an existing local Qdrant index, so it refuses to run unless
`--apply` is given, and it never edits `config/rag-production.json` for you: the
runtime pins `point_count` and `dense_index_contract_id` per collection, so those
values must be reviewed and updated together with the deployment.

Must run on the GPU host (needs CUDA models and the index directories).

Dry run (safe, no GPU, no index access):
    python scripts/build_markdown_index.py --dry-run \
        --registry data/documents/registry-md.json

Apply (GPU host, after a backup of both index directories):
    python scripts/build_markdown_index.py --apply \
        --config config/rag-production.json --registry data/documents/registry-md.json
"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.corpus.eligibility import eligibility_audit  # noqa: E402
from accelerator_rag.ingestion import IngestionService  # noqa: E402


def collect(registry):
    service = IngestionService(ROOT, registry_path=registry)
    documents = service.ingest_all_registered()
    chunks = [chunk for document in documents for chunk in document.chunks]
    eligible, policy = eligibility_audit(chunks)
    by_document = {}
    for document in documents:
        by_document[document.record.doc_id] = [
            chunk for chunk in eligible if chunk.document_id == document.record.doc_id
        ]
        if not by_document[document.record.doc_id]:
            raise ValueError(
                f"no eligible chunks for {document.record.doc_id}; "
                "refusing to retain its previous indexed version silently"
            )
    return documents, chunks, eligible, by_document, policy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/documents/registry-md.json")
    parser.add_argument("--config", default="config/rag-production.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.apply:
        raise SystemExit("choose exactly one of --dry-run / --apply")

    documents, chunks, eligible, by_document, policy = collect(args.registry)
    summary = {
        "documents": len(documents),
        "chunks": len(chunks),
        "eligible_chunks": len(eligible),
        "per_document": {
            doc_id: {"chunks": len(own)} for doc_id, own in by_document.items()
        },
        "eligibility": {k: v for k, v in policy.items() if k != "examples"},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.dry_run:
        print("dry run: no index was opened, no vector was written")
        return 0

    # Imports stay inside the apply path so --dry-run works without CUDA/torch.
    from qdrant_client import QdrantClient

    from accelerator_rag.embedding import EmbeddingModel
    from accelerator_rag.retrieval.dense import DenseRetriever
    from accelerator_rag.retrieval.index_contract import DenseIndexContract
    from accelerator_rag.retrieval.passages import PassageBuilder
    from accelerator_rag.storage.qdrant_passages import QdrantPassageStore

    config = json.loads((ROOT / args.config).read_text())
    applied = []
    for entry in config["indexes"]:
        path = Path(entry["index_path"])
        if not (path / "meta.json").is_file():
            raise SystemExit(f"existing local index required: {path}")
        embedder = EmbeddingModel(
            entry["model_name"],
            model_path=entry["model_path"],
            device=entry["device"],
            dtype=entry.get("dtype", "float32"),
            batch_size=8,
        )
        builder = PassageBuilder(embedder)
        contract = DenseIndexContract.from_fingerprint(
            embedder.fingerprint(), builder.contract
        )
        if contract.contract_id != entry["dense_index_contract_id"]:
            raise SystemExit(f"model/passage contract differs from frozen index: {path}")
        with closing(QdrantClient(path=str(path))) as client:
            if not client.collection_exists(entry["collection"]):
                raise ValueError(f"existing collection required: {entry['collection']}")
            store = QdrantPassageStore(client, entry["collection"], contract)
            dense = DenseRetriever(embedder, store, passage_builder=builder)
            before = store.point_count()
            for doc_id, own in by_document.items():
                dense.index_document(doc_id, own)
            after = store.point_count()
        applied.append(
            {
                "collection": entry["collection"],
                "index_path": str(path),
                "points_before": before,
                "points_after": after,
                "configured_point_count": entry["point_count"],
            }
        )
    print(json.dumps({"applied": applied}, ensure_ascii=False, indent=2))
    print(
        "next: update config point_count values, then restart the standalone RAG "
        "container and run the ingestion verification steps"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
