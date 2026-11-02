"""Dry-run the Markdown ingestion path: registry -> parse -> chunk -> eligibility.

Needs no GPU and writes no index. Use it to check section counts, chunk counts,
eligibility and the page(=section) numbering before an index build on the GPU
host.

Usage:
    python scripts/md_corpus_report.py --output reports/phase1-m0-20261029/md-ingestion-report.json
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.corpus.eligibility import eligibility_audit  # noqa: E402
from accelerator_rag.ingestion import IngestionService  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/documents/registry-md.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    service = IngestionService(ROOT, registry_path=args.registry)
    documents = service.ingest_all_registered()
    chunks = [chunk for document in documents for chunk in document.chunks]
    eligible, policy = eligibility_audit(chunks)

    rows = []
    for document in documents:
        own = [c for c in chunks if c.document_id == document.record.doc_id]
        own_eligible = [c for c in eligible if c.document_id == document.record.doc_id]
        rows.append(
            {
                "document_id": document.record.doc_id,
                "source_path": document.record.source_path,
                "document_type": document.record.document_type,
                "version": document.record.version,
                "sections_pages": document.parsed.page_count,
                "chunks": len(own),
                "eligible_chunks": len(own_eligible),
                "characters": sum(len(c.text) for c in own),
                "page_numbers_from": min((c.page_start for c in own), default=None),
                "page_numbers_to": max((c.page_end for c in own), default=None),
                "warnings": document.parsed.warnings,
                "front_matter_keys": sorted(
                    k
                    for k in document.parsed.metadata
                    if k not in {"format", "section_split_level", "section_count"}
                ),
            }
        )

    report = {
        "registry": args.registry,
        "documents": rows,
        "totals": {
            "documents": len(documents),
            "sections_pages": sum(r["sections_pages"] for r in rows),
            "chunks": len(chunks),
            "eligible_chunks": len(eligible),
            "characters": sum(r["characters"] for r in rows),
        },
        "eligibility": {k: v for k, v in policy.items() if k != "examples"},
        "page_semantics": "Markdown page_start/page_end are 1-based section indexes, not PDF pages.",
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    print(f"{'document_id':<40}{'sections':>9}{'chunks':>8}{'eligible':>9}{'chars':>9}")
    for row in rows:
        print(
            f"{row['document_id']:<40}{row['sections_pages']:>9}{row['chunks']:>8}"
            f"{row['eligible_chunks']:>9}{row['characters']:>9}"
        )
    print(
        f"TOTAL documents={report['totals']['documents']} "
        f"sections={report['totals']['sections_pages']} "
        f"chunks={report['totals']['chunks']} "
        f"eligible={report['totals']['eligible_chunks']}"
    )
    print(f"wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
