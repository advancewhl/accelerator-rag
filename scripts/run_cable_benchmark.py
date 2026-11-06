"""Run and score the cable/switch-table benchmark against a live RAG service.

Usage::

    python scripts/run_cable_benchmark.py --base-url http://127.0.0.1:8003 \
        --output reports/<dir>/cable-benchmark.json [--lookup-only]

Standard library only; sends ``{"query": ...}`` to ``/v1/rag/answer`` and
``q=...`` to ``/v1/rag/structured/lookup``.  Gold rows stay in this client.

Automatic checks (identifier answers allow string matching; semantic quality
still needs human review):

* lookup_best_hit   - a gold row is among the near-best lookup rows
* lookup_hit_at_10  - a gold row is in the first 10 lookup rows
* status_ok         - answer status equals the expected status
* values_ok         - every required value appears in the answer text
* forbidden_ok      - no forbidden claim appears in the answer text
* citation_row_ok   - a citation from a gold document covers a gold row
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib import parse, request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUESTIONS = ROOT / "data/evaluation/cable-lookup-v1.json"
RANGE = re.compile(r"[A-Za-z]+(\d+):[A-Za-z]+(\d+)")


def norm(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or "")).casefold()


def call(url: str, payload: dict | None, timeout: float) -> tuple[int, dict, float]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/json")
    started = time.monotonic()
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body, time.monotonic() - started
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        status = getattr(exc, "code", 0)
        return status, {"error": type(exc).__name__}, time.monotonic() - started


def label_rows(label: str) -> tuple[str, list[tuple[int, int]]]:
    if "!" not in label:
        return "", []
    sheet, ranges = label.rsplit("!", 1)
    spans = [(int(a), int(b)) for a, b in RANGE.findall(ranges)]
    return sheet, spans[1:] if len(spans) > 1 else spans


def score(item: dict, lookup: dict | None, answer: dict | None) -> dict:
    gold = {(e["document_id"], e["sheet"], e["row"]) for e in item["evidence"]}
    gold_docs = {e["document_id"] for e in item["evidence"]}
    result: dict = {"id": item["id"], "category": item["category"]}
    if lookup is not None:
        hits = lookup.get("hits") or []
        keys = [(h.get("revision_id"), h.get("sheet"), h.get("row_number")) for h in hits]
        best = [k for k, h in zip(keys, hits) if h.get("near_best")]
        if gold:
            result["lookup_best_hit"] = bool(gold & set(best))
            result["lookup_hit_at_10"] = bool(gold & set(keys[:10]))
            result["lookup_all_gold_best"] = gold <= set(best)
        else:
            result["lookup_best_count"] = len(best)
    if answer is not None:
        text = answer.get("answer", "")
        status = answer.get("status")
        result["status"] = status
        result["status_ok"] = status == item["expected_status"]
        result["values_ok"] = all(norm(v) in norm(text) for v in item["required_values"])
        result["missing_values"] = [
            v for v in item["required_values"] if norm(v) not in norm(text)
        ]
        result["forbidden_ok"] = not any(
            norm(f) in norm(text) for f in item["forbidden_claims"]
        )
        covered = False
        for citation in answer.get("citations") or []:
            if citation.get("document_id") not in gold_docs:
                continue
            sheet, spans = label_rows(citation.get("position_label", ""))
            for doc, gold_sheet, row in gold:
                if doc == citation.get("document_id") and sheet == gold_sheet and any(
                    a <= row <= b for a, b in spans
                ):
                    covered = True
        result["citation_row_ok"] = covered if gold else None
        result["citation_docs"] = sorted(
            {c.get("document_id") for c in answer.get("citations") or []}
        )
    return result


def summarize(rows: list[dict]) -> dict:
    def rate(key, subset=None):
        values = [r[key] for r in (subset or rows) if isinstance(r.get(key), bool)]
        return {"pass": sum(values), "total": len(values)}

    answerable = [r for r in rows if r.get("citation_row_ok") is not None]
    summary = {
        "questions": len(rows),
        "lookup_best_hit": rate("lookup_best_hit"),
        "lookup_hit_at_10": rate("lookup_hit_at_10"),
        "lookup_all_gold_best": rate("lookup_all_gold_best"),
        "status_ok": rate("status_ok"),
        "values_ok": rate("values_ok"),
        "forbidden_ok": rate("forbidden_ok"),
        "citation_row_ok": rate("citation_row_ok", answerable),
        "status_counts": dict(Counter(r.get("status") for r in rows if "status" in r)),
    }
    strict = [
        r for r in rows
        if "status_ok" in r
        and r["status_ok"] and r["values_ok"] and r["forbidden_ok"]
        and r.get("citation_row_ok") in (True, None)
    ]
    summary["auto_strict_pass"] = {"pass": len(strict), "total": sum("status_ok" in r for r in rows)}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lookup-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=240.0)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    items = json.loads(args.questions.read_text(encoding="utf-8"))["questions"]
    records, rows = [], []
    for item in items:
        query = parse.urlencode({"q": item["question"], "limit": "60"})
        lookup_status, lookup, lookup_seconds = call(
            f"{base}/v1/rag/structured/lookup?{query}", None, 30
        )
        answer = None
        answer_status, answer_seconds = None, None
        if not args.lookup_only:
            answer_status, answer, answer_seconds = call(
                f"{base}/v1/rag/answer", {"query": item["question"]}, args.timeout
            )
        row = score(
            item,
            lookup if lookup_status == 200 else None,
            answer if answer_status == 200 else None,
        )
        row["lookup_http"] = lookup_status
        row["answer_http"] = answer_status
        row["answer_seconds"] = answer_seconds
        rows.append(row)
        records.append(
            {
                "id": item["id"],
                "question": item["question"],
                "lookup_http": lookup_status,
                "lookup_seconds": lookup_seconds,
                "lookup_top": (lookup.get("hits") or [])[:5] if lookup_status == 200 else lookup,
                "answer_http": answer_status,
                "answer_seconds": answer_seconds,
                "answer": answer,
            }
        )
        print(
            f"{item['id']}: lookup={row.get('lookup_best_hit')} "
            f"status={row.get('status')} values={row.get('values_ok')} "
            f"cite={row.get('citation_row_ok')}",
            flush=True,
        )
    payload = {
        "schema_version": "cable-benchmark-run-v1",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "base_url_host": parse.urlparse(base).netloc,
        "questions_file": str(args.questions.relative_to(ROOT)) if args.questions.is_relative_to(ROOT) else str(args.questions),
        "lookup_only": args.lookup_only,
        "summary": summarize(rows),
        "scores": rows,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
