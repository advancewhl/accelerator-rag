"""Build a local, read-only inventory of the frozen rc.3 corpus.

Inputs (local copies pulled from the release directory):
  tmp/research-rc3/chunks/*.json
  tmp/research-rc3/chunk-report.json
  data/documents/v2/registry-v2.json

Outputs:
  tmp/research-rc3/index/chunks.jsonl
  tmp/research-rc3/inventory/families.json
  tmp/research-rc3/inventory/revisions.json
  tmp/research-rc3/inventory/corpus-digest.json
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "tmp" / "research-rc3"
REGISTRY = ROOT / "data" / "documents" / "v2" / "registry-v2.json"


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    revs = {r["revision_id"]: r for r in registry["revisions"]}
    fams = {f["family_id"]: f for f in registry["families"]}
    fam_of = {}
    for fam in registry["families"]:
        for rid in fam["revision_ids"]:
            fam_of[rid] = fam["family_id"]

    chunk_report = json.loads((BASE / "chunk-report.json").read_text(encoding="utf-8"))
    chunks_meta = {r["revision_id"]: r for r in chunk_report["records"]}

    index_dir = BASE / "index"
    inventory_dir = BASE / "inventory"
    index_dir.mkdir(parents=True, exist_ok=True)
    inventory_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    total = 0
    per_rev = {}
    with (index_dir / "chunks.jsonl").open("w", encoding="utf-8") as out:
        for path in sorted((BASE / "chunks").glob("*.json")):
            raw = path.read_bytes()
            digest.update(raw)
            doc = json.loads(raw)
            rid = doc["revision_id"]
            per_rev[rid] = len(doc["chunks"])
            for chunk in doc["chunks"]:
                total += 1
                record = {
                    "chunk_id": chunk["chunk_id"],
                    "revision_id": rid,
                    "family_id": chunk.get("family_id") or fam_of.get(rid, ""),
                    "document_title": chunk.get("document_title", ""),
                    "revision_label": chunk.get("revision_label", ""),
                    "position_kind": chunk.get("position_kind", ""),
                    "position_label": chunk.get("position_label", ""),
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "language": chunk.get("language", ""),
                    "evidence_role": chunk.get("evidence_role", ""),
                    "document_kind": chunk.get("document_kind", ""),
                    "access_scope": chunk.get("access_scope", ""),
                    "usage_status": chunk.get("usage_status", ""),
                    "text": chunk["text"],
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")

    revisions = {}
    for rid, meta in chunks_meta.items():
        reg = revs.get(rid, {})
        revisions[rid] = {
            "revision_id": rid,
            "family_id": fam_of.get(rid, ""),
            "title": reg.get("title", ""),
            "revision_label": reg.get("revision_label", ""),
            "document_kind": reg.get("document_kind", ""),
            "evidence_role": reg.get("evidence_role", ""),
            "usage_status": reg.get("usage_status", ""),
            "access_scope": reg.get("access_scope", ""),
            "language": reg.get("language", ""),
            "source_path": reg.get("source_path", ""),
            "chunk_count": meta["chunk_count"],
            "indexable_chunk_count": meta["indexable_chunk_count"],
            "char_count": meta.get("char_count", 0),
        }
    (inventory_dir / "revisions.json").write_text(
        json.dumps(revisions, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    families = {}
    for fid, fam in fams.items():
        member_ids = [r for r in fam["revision_ids"] if r in revisions]
        if not member_ids:
            continue
        families[fid] = {
            "family_id": fid,
            "title": fam.get("title", ""),
            "description": fam.get("description", ""),
            "revision_ids": member_ids,
            "roles": sorted({revisions[r]["evidence_role"] for r in member_ids}),
            "kinds": sorted({revisions[r]["document_kind"] for r in member_ids}),
        }
    (inventory_dir / "families.json").write_text(
        json.dumps(families, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    corpus_digest = {
        "source": "kb-2.0.0-rc.3 build kb2-prod-20261105-v3 (release snapshot)",
        "chunk_files": len(per_rev),
        "chunks": total,
        "chunks_sha256_concat": digest.hexdigest(),
        "revision_chunk_counts_sha256": hashlib.sha256(
            json.dumps(per_rev, sort_keys=True).encode()
        ).hexdigest(),
    }
    (inventory_dir / "corpus-digest.json").write_text(
        json.dumps(corpus_digest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(corpus_digest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
