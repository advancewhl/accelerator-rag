"""Query the frozen rc.3 corpus locally (read-only).

Usage:
  rc3_query.py search "<regex>" [--family F] [--revision R] [--kind paragraph|cell_range|pdf_page|slide|section]
                                 [--limit 40] [--width 160]
  rc3_query.py chunk <chunk_id>
  rc3_query.py revision <revision_id> [--width 80]
  rc3_query.py family <family_id>
  rc3_query.py families [--roles role1,role2]
  rc3_query.py stats
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "tmp" / "research-rc3"
INDEX = BASE / "index" / "chunks.jsonl"
INVENTORY = BASE / "inventory"


def load_chunks():
    with INDEX.open(encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def cmd_search(args):
    pattern = re.compile(args.regex, re.IGNORECASE)
    hits = 0
    for rec in load_chunks():
        if args.family and rec["family_id"] != args.family:
            continue
        if args.revision and rec["revision_id"] != args.revision:
            continue
        if args.kind and rec["position_kind"] != args.kind:
            continue
        text = rec["text"]
        m = pattern.search(text)
        if not m:
            continue
        hits += 1
        start = max(0, m.start() - args.width // 2)
        snippet = text[start : start + args.width].replace("\n", " ")
        print(
            f"{rec['chunk_id']}\n  rev={rec['revision_id']} kind={rec['position_kind']}"
            f" label={rec['position_label']}\n  ...{snippet}..."
        )
        if hits >= args.limit:
            print(f"[stopped at limit {args.limit}]")
            break
    print(f"[{hits} shown]")


def iter_chunk(chunk_id):
    for rec in load_chunks():
        if rec["chunk_id"] == chunk_id:
            return rec
    return None


def cmd_chunk(args):
    rec = iter_chunk(args.chunk_id)
    if not rec:
        sys.exit(f"chunk not found: {args.chunk_id}")
    print(
        json.dumps(
            {k: rec[k] for k in rec if k != "text"}, ensure_ascii=False, indent=1
        )
    )
    print("--- text ---")
    print(rec["text"])


def cmd_revision(args):
    rows = [rec for rec in load_chunks() if rec["revision_id"] == args.revision_id]
    if not rows:
        sys.exit(f"revision not found: {args.revision_id}")
    first = rows[0]
    print(
        f"revision={first['revision_id']} family={first['family_id']} "
        f"title={first['document_title']} chunks={len(rows)}"
    )
    for rec in rows:
        head = rec["text"][: args.width].replace("\n", " ")
        print(f"{rec['chunk_id']}  [{rec['position_kind']}:{rec['position_label']}] {head}")


def cmd_family(args):
    fams = json.loads((INVENTORY / "families.json").read_text(encoding="utf-8"))
    fam = fams.get(args.family_id)
    if not fam:
        sys.exit(f"family not found: {args.family_id}")
    print(json.dumps(fam, ensure_ascii=False, indent=1))


def cmd_families(args):
    fams = json.loads((INVENTORY / "families.json").read_text(encoding="utf-8"))
    roles = set(args.roles.split(",")) if args.roles else None
    for fam in fams.values():
        if roles and not (set(fam["roles"]) & roles):
            continue
        print(
            f"{fam['family_id']} | revs={len(fam['revision_ids'])} | "
            f"{','.join(fam['roles'])} | {fam['title'][:60]}"
        )


def cmd_stats(args):
    counts = {}
    revs = set()
    for rec in load_chunks():
        counts[rec["position_kind"]] = counts.get(rec["position_kind"], 0) + 1
        revs.add(rec["revision_id"])
    digest = json.loads((INVENTORY / "corpus-digest.json").read_text(encoding="utf-8"))
    print(json.dumps({"revisions": len(revs), "by_kind": counts, "digest": digest,
                      "indexed_chunks": sum(counts.values())}, ensure_ascii=False, indent=1))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search")
    p.add_argument("regex")
    p.add_argument("--family")
    p.add_argument("--revision")
    p.add_argument("--kind")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--width", type=int, default=160)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("chunk")
    p.add_argument("chunk_id")
    p.set_defaults(func=cmd_chunk)

    p = sub.add_parser("revision")
    p.add_argument("revision_id")
    p.add_argument("--width", type=int, default=80)
    p.set_defaults(func=cmd_revision)

    p = sub.add_parser("family")
    p.add_argument("family_id")
    p.set_defaults(func=cmd_family)

    p = sub.add_parser("families")
    p.add_argument("--roles")
    p.set_defaults(func=cmd_families)

    p = sub.add_parser("stats")
    p.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
