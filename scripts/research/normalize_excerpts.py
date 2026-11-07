"""Rewrite evidence excerpts as exact continuous substrings of the chunk text.

The benchmark spec requires each excerpt segment to appear verbatim in the
parent chunk. Some authors normalised whitespace (newlines / multiple spaces)
before joining rows, which the structural validator tolerated but R2 does not.
This script preserves the excerpt's content and only restores the original
whitespace by locating each '……'-separated segment in the chunk with a
whitespace-flexible match and taking the exact span.

Usage:
  python3 scripts/research/normalize_excerpts.py <questions.jsonl> [--write]
  python3 scripts/research/normalize_excerpts.py --split-files [--write]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "tmp" / "research-rc3" / "index" / "chunks.jsonl"


def load_chunks():
    out = {}
    with INDEX.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            out[rec["chunk_id"]] = rec["text"]
    return out


def flexible_pattern(part: str) -> re.Pattern:
    tokens = [t for t in re.split(r"\s+", part.strip()) if t]
    if not tokens:
        return re.compile(r"")
    return re.compile(r"\s+".join(re.escape(t) for t in tokens))


def exact_span(part: str, text: str, start: int) -> tuple[str, int] | None:
    m = flexible_pattern(part).search(text, start)
    if not m:
        return None
    return text[m.start() : m.end()], m.end()


def rewrite_excerpt(excerpt: str, text: str) -> tuple[str, bool]:
    if excerpt in text:
        return excerpt, True
    parts = [p for p in re.split(r"……", excerpt)]
    spans = []
    pos = 0
    ok = True
    for part in parts:
        if not part.strip():
            continue
        found = exact_span(part, text, pos)
        if not found:
            ok = False
            break
        span, pos = found
        spans.append(span)
    if not ok or not spans:
        return excerpt, False
    return "……".join(spans), True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*")
    parser.add_argument("--split-files", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    files = [Path(f) for f in args.files]
    if args.split_files or not files:
        base = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"
        files = [base / "w2-scenario1.jsonl", base / "w3-scenario2.jsonl",
                 base / "w4-scenario3.jsonl"]

    chunks = load_chunks()
    total = changed = failed = 0
    failures = []
    for path in files:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        new_lines = []
        file_changed = 0
        for line in lines:
            if not line.strip():
                new_lines.append(line)
                continue
            item = json.loads(line)
            for ev in item.get("gold", {}).get("evidence_minimal", []):
                total += 1
                cid = ev.get("chunk_id")
                text = chunks.get(cid)
                if text is None:
                    continue
                fixed, ok = rewrite_excerpt(ev.get("excerpt", ""), text)
                if not ok:
                    failed += 1
                    failures.append((path.name, item.get("base_id"), cid))
                elif fixed != ev.get("excerpt"):
                    ev["excerpt"] = fixed
                    changed += 1
                    file_changed += 1
            new_lines.append(json.dumps(item, ensure_ascii=False))
        if args.write and file_changed:
            path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            print(f"{path.name}: rewrote {file_changed} excerpts")
    print(f"evidence={total} rewritten={changed} failed={failed}")
    for f in failures[:20]:
        print("FAILED", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
