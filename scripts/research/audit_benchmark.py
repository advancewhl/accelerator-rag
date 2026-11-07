"""Read-only audit helpers for the 300-question benchmark.

Computes signals the independent reviewers need:
  - near-duplicate queries (token Jaccard within scenario/split)
  - shared object anchors across base questions (cable IDs, cabinets, revisions, chunks)
  - cross-split family / cluster matrix
  - evidence chunk reuse
  - intervention target reuse across different base_ids
  - duplicate gold answers

Usage:
  python3 scripts/research/audit_benchmark.py [files...] [--json]
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_BASE = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"
DEFAULT = [
    (_BASE / n if (_BASE / n).exists() else _BASE / "sealed-test" / "_work" / n)
    for n in ("w2-scenario1.jsonl", "w3-scenario2.jsonl", "w4-scenario3.jsonl")
]

CABLE_RE = re.compile(r"[A-Za-z0-9#\-]+/[A-Za-z0-9]+:[A-Za-z0-9]+-E\d+")
CAB_RE = re.compile(r"[A-Za-z0-9#]+(?:-[A-Za-z0-9#]+)*-CN[-]?\d+")
PORT_RE = re.compile(r"\b\d{1,2}\s*[-–~]\s*\d{1,2}\b")


def norm_q(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def tokens(text: str):
    if re.search(r"[一-鿿]", text):
        return set(text)
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def jaccard(a, b) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def anchors(item):
    text = json.dumps(item, ensure_ascii=False)
    return {
        "cable": set(CABLE_RE.findall(text)),
        "cabinet": set(CAB_RE.findall(text)),
        "chunk": {ev["chunk_id"] for ev in item["gold"]["evidence_minimal"]},
        "revision": {ev["revision_id"] for ev in item["gold"]["evidence_minimal"]}
        | set(item.get("scope", {}).get("revision_ids") or []),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    files = [Path(f) for f in args.files] or [p for p in DEFAULT if p.exists()]

    items = []
    for path in files:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    items.append(json.loads(line))

    findings = []
    by_scen = collections.defaultdict(list)
    for item in items:
        by_scen[item["scenario"]].append(item)

    # near-duplicate queries within scenario
    for scen, group in by_scen.items():
        for a, b in itertools.combinations(group, 2):
            score = jaccard(tokens(a["query"]), tokens(b["query"]))
            if score >= 0.8:
                findings.append({
                    "type": "near_duplicate_query",
                    "severity": "blocking" if score >= 0.92 else "major",
                    "scenario": scen,
                    "ids": [a["base_id"], b["base_id"]],
                    "split": [a["split"], b["split"]],
                    "score": round(score, 3),
                    "queries": [a["query"][:80], b["query"][:80]],
                })

    # shared anchors across different base questions
    for scen, group in by_scen.items():
        anc = {i["base_id"]: anchors(i) for i in group}
        for a, b in itertools.combinations(group, 2):
            shared_cable = anc[a["base_id"]]["cable"] & anc[b["base_id"]]["cable"]
            shared_cab = anc[a["base_id"]]["cabinet"] & anc[b["base_id"]]["cabinet"]
            shared_ev = anc[a["base_id"]]["chunk"] & anc[b["base_id"]]["chunk"]
            qsim = jaccard(tokens(a["query"]), tokens(b["query"]))
            # a shared parent chunk is normal for short manual families; only
            # treat it as an anchor clash when the excerpts overlap as well.
            ev_a = {ev["chunk_id"]: norm_q(ev.get("excerpt", ""))
                    for ev in a["gold"]["evidence_minimal"]
                    if ev.get("role") == "fact_support"}
            ev_b = {ev["chunk_id"]: norm_q(ev.get("excerpt", ""))
                    for ev in b["gold"]["evidence_minimal"]
                    if ev.get("role") == "fact_support"}
            excerpt_clash = any(
                ev_a.get(cid) and ev_b.get(cid)
                and (ev_a[cid] == ev_b[cid]
                     or jaccard(tokens(ev_a[cid]), tokens(ev_b[cid])) > 0.95)
                for cid in shared_ev
            )
            if shared_cable or excerpt_clash or (shared_cab and qsim > 0.8):
                findings.append({
                    "type": "shared_object_anchor",
                    "severity": "blocking" if a["split"] != b["split"] else "major",
                    "scenario": scen,
                    "ids": [a["base_id"], b["base_id"]],
                    "split": [a["split"], b["split"]],
                    "shared_cables": sorted(shared_cable)[:5],
                    "shared_cabinets": sorted(shared_cab)[:5],
                    "shared_chunks": len(shared_ev),
                    "excerpt_clash": excerpt_clash,
                })
            elif shared_ev:
                findings.append({
                    "type": "shared_parent_chunk",
                    "severity": "suggestion",
                    "scenario": scen,
                    "ids": [a["base_id"], b["base_id"]],
                    "split": [a["split"], b["split"]],
                    "shared_chunks": len(shared_ev),
                })

    # cross-split family matrix
    fam_split = collections.defaultdict(set)
    cluster_split = collections.defaultdict(set)
    for item in items:
        for f in item["family_ids"]:
            fam_split[f].add(item["split"])
        cluster_split[item["cluster_id"]].add(item["split"])
    for f, splits in fam_split.items():
        if len(splits) > 1:
            findings.append({"type": "family_cross_split", "severity": "blocking",
                             "family": f, "splits": sorted(splits)})
    for c, splits in cluster_split.items():
        if len(splits) > 1:
            findings.append({"type": "cluster_cross_split", "severity": "blocking",
                             "cluster": c, "splits": sorted(splits)})

    # evidence reuse: same chunk is fine if different rows/excerpts are used;
    # flag only when the same excerpt (or near-identical text) is reused.
    chunk_users = collections.defaultdict(list)
    for item in items:
        for ev in item["gold"]["evidence_minimal"]:
            if ev.get("role") != "fact_support":
                continue
            chunk_users[ev["chunk_id"]].append(
                (item["base_id"], norm_q(ev.get("excerpt", "")))
            )
    for cid, users in chunk_users.items():
        if len(users) <= 1:
            continue
        flagged = False
        for (a_id, a_ex), (b_id, b_ex) in itertools.combinations(users, 2):
            if a_ex and b_ex and (a_ex == b_ex or jaccard(tokens(a_ex), tokens(b_ex)) > 0.9):
                flagged = True
                findings.append({"type": "evidence_excerpt_reuse", "severity": "major",
                                 "chunk_id": cid, "ids": [a_id, b_id]})
        if not flagged and len(users) > 4:
            findings.append({"type": "evidence_chunk_shared_rows", "severity": "suggestion",
                             "chunk_id": cid, "count": len(users),
                             "ids": [u[0] for u in users][:8]})

    # intervention target reuse across different base ids
    iv_users = collections.defaultdict(set)
    for item in items:
        for iv in item["interventions"]:
            for cid in iv.get("target_chunk_ids") or []:
                iv_users[cid].add(item["base_id"])
    for cid, users in iv_users.items():
        if len(users) > 4:
            findings.append({"type": "intervention_target_reuse", "severity": "suggestion",
                             "chunk_id": cid, "count": len(users), "ids": sorted(users)[:8]})

    # duplicate gold answers
    ans = collections.defaultdict(list)
    for item in items:
        ans[(item["scenario"], item["split"], re.sub(r"\s+", "", item["gold"]["answer"]))].append(item["base_id"])
    for (scen, split, _), ids in ans.items():
        if len(ids) > 2:
            findings.append({"type": "duplicate_answer", "severity": "suggestion",
                             "scenario": scen, "split": split, "ids": ids[:10]})

    by_sev = collections.Counter(f["severity"] for f in findings)
    report = {
        "items": len(items),
        "findings": findings,
        "by_severity": dict(by_sev),
        "family_split": {f: sorted(s) for f, s in sorted(fam_split.items())},
        "cluster_split": {c: sorted(s) for c, s in sorted(cluster_split.items())},
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f"items={len(items)} findings={len(findings)} {dict(by_sev)}")
        for f in findings:
            print(f"{f['severity'].upper():9} {f['type']}: {json.dumps({k: v for k, v in f.items() if k not in ('type','severity')}, ensure_ascii=False)[:220]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
