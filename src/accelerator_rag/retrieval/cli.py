"""Run registered PDF ingestion and retrieval without answer generation."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from qdrant_client import QdrantClient

from accelerator_rag.embedding import EmbeddingModel
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.retrieval.bm25 import BM25Retriever
from accelerator_rag.retrieval.index_contract import DenseIndexContract
from accelerator_rag.retrieval.passages import PassageBuilder
from accelerator_rag.retrieval.dense import DenseRetriever
from accelerator_rag.storage.qdrant_passages import QdrantPassageStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--retriever", choices=("bm25", "dense"), default="bm25")
    parser.add_argument("--model", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument("--model-path", help="Downloaded local model directory")
    parser.add_argument(
        "--qdrant-path",
        type=Path,
        help="Local persistent Qdrant directory; default is memory",
    )
    parser.add_argument("--collection", default="knowledge_passages")
    args = parser.parse_args()
    if not args.query.strip() or args.top_k <= 0:
        parser.error("query must be nonempty and top-k must be positive")
    chunks = IngestionService(args.project_root).ingest_document(args.document_id)
    if not chunks:
        raise ValueError("PDF contains no extractable text chunks")
    if args.retriever == "bm25":
        results = BM25Retriever(chunks).search(args.query, top_k=args.top_k)
    else:
        # Loading is local-only. This entry point never downloads model weights.
        embedder = EmbeddingModel(
            args.model, model_path=args.model_path, local_files_only=True
        )
        builder = PassageBuilder(embedder)
        contract = DenseIndexContract.from_fingerprint(
            embedder.fingerprint(), builder.contract
        )
        if args.qdrant_path:
            source_root = (args.project_root / "data/l0_raw").resolve()
            if args.qdrant_path.resolve().is_relative_to(source_root):
                parser.error("qdrant-path must be outside the raw source directory")
        client = (
            QdrantClient(path=str(args.qdrant_path))
            if args.qdrant_path
            else QdrantClient(":memory:")
        )
        try:
            retriever = DenseRetriever(
                embedder,
                QdrantPassageStore(
                    client,
                    args.collection,
                    contract,
                ),
                passage_builder=builder,
            )
            retriever.index_document(args.document_id, chunks)
            results = retriever.search(args.query, args.top_k)
        finally:
            client.close()
    print(
        json.dumps(
            {
                "document_id": args.document_id,
                "chunk_count": len(chunks),
                "physical_pages": sorted({c.page_start for c in chunks}),
                "results": [asdict(result) for result in results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
