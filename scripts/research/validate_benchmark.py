"""Structural and provenance validator for the 300-question benchmark.

Usage:
  python3 scripts/research/validate_benchmark.py <file.jsonl> [<file2.jsonl> ...]
  python3 scripts/research/validate_benchmark.py --all

Checks (hard errors):
  - schema v1 fields and enum values
  - chunk existence, revision match, locator match
  - excerpt is an exact substring of the chunk text (whitespace-normalised,
    allowing '……' separated segments)
  - fact support <- evidence consistency; every fact_support evidence referenced
  - intervention ids, operations, pair roles, target chunks
  - cluster/split/quota compliance with split-policy.json
  - explicit-scope count (30) and allocation (dev/val/test 10 each)
  - no restricted revisions in evidence or intervention targets
Warnings:
  - evidence item with role fact_support not referenced by any fact
  - duplicate normalised query within one split
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "tmp" / "research-rc3"
POLICY = ROOT / "docs" / "research" / "benchmark-300" / "split-policy.json"
REGISTRY = ROOT / "data" / "documents" / "v2" / "registry-v2.json"
_BASE = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"
DEFAULT_FILES = [
    (_BASE / name if (_BASE / name).exists()
     else _BASE / "sealed-test" / "_work" / name)
    for name in ("w2-scenario1.jsonl", "w3-scenario2.jsonl", "w4-scenario3.jsonl")
]

SCENARIOS = {"s1_connectivity", "s2_revision", "s3_verification"}
SPLITS = {"dev", "val", "test"}
TASK_TYPES = {
    "exact_record", "cross_table_join", "set_enumeration", "negative_boundary",
    "version_diff", "version_added", "version_removed", "version_same", "version_boundary",
    "requirement_test_match", "acceptance_gap", "design_test_conflict", "scope_mismatch",
    "verdict_check",
}
STATUSES = {"answered", "partial", "insufficient"}
VERDICT = {"deterministic", "rubric", "human"}
ROLES = {"fact_support", "condition", "unit", "header", "provenance"}
PAIR = {"should_change", "should_hold"}
OPS_CHANGE = {
    "delete_condition", "delete_row", "swap_adjacent_ports", "change_value",
    "replace_revision", "substitute_design_for_test", "remove_link_edge", "change_unit",
}
OPS_HOLD = {"paraphrase_query", "reorder_paragraphs", "add_irrelevant_similar",
            "convert_unit", "translate_query"}
SCOPE_MODES = {"global", "explicit_revisions"}
REQUIRED = ("base_id", "scenario", "split", "cluster_id", "family_ids", "task_type",
            "query", "query_lang", "scope", "gold", "interventions", "provenance")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_chunks():
    chunks = {}
    with (BASE / "index" / "chunks.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            chunks[rec["chunk_id"]] = rec
    return chunks


def excerpt_in_text(excerpt: str, text: str) -> bool:
    parts = [p for p in re.split(r"……|\.\.\.", excerpt) if p.strip()]
    hay = norm(text)
    return all(norm(p) in hay for p in parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--partial", action="store_true",
                        help="skip global split/scenario/explicit totals (single-workflow validation)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args()

    files = [Path(f) for f in args.files]
    if args.all or not files:
        files = [p for p in DEFAULT_FILES if p.exists()]

    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    clusters = {}
    for scen in policy["scenarios"].values():
        for cl in scen["clusters"]:
            clusters[cl["cluster_id"]] = cl
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rev_meta = {r["revision_id"]: r for r in registry["revisions"]}
    restricted = {r["revision_id"] for r in registry["revisions"]
                  if r.get("access_scope") == "restricted"}
    chunks = load_chunks()

    errors: list[str] = []
    warnings: list[str] = []
    items = []
    seen_ids = {}
    query_seen = collections.defaultdict(list)

    for path in files:
        if not path.exists():
            errors.append(f"{path}: file not found")
            continue
        with path.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"{path.name}:{lineno}: JSON error: {exc}")
                    continue
                item["_file"] = path.name
                item["_line"] = lineno
                items.append(item)

    for item in items:
        tag = f"{item['_file']}:{item['_line']} [{item.get('base_id', '?')}]"
        missing = [k for k in REQUIRED if k not in item]
        if missing:
            errors.append(f"{tag}: missing fields {missing}")
            continue
        if item["scenario"] not in SCENARIOS:
            errors.append(f"{tag}: bad scenario {item['scenario']}")
        if item["split"] not in SPLITS:
            errors.append(f"{tag}: bad split {item['split']}")
        if item["task_type"] not in TASK_TYPES:
            errors.append(f"{tag}: bad task_type {item['task_type']}")
        cl = clusters.get(item["cluster_id"])
        if not cl:
            errors.append(f"{tag}: unknown cluster {item['cluster_id']}")
        else:
            if item["split"] != cl["split"]:
                errors.append(f"{tag}: split {item['split']} != cluster split {cl['split']}")
            bad_fams = [f for f in item["family_ids"] if f not in cl["families"]]
            if bad_fams:
                errors.append(f"{tag}: families outside cluster: {bad_fams}")

        if item["base_id"] in seen_ids:
            errors.append(f"{tag}: duplicate base_id (also {seen_ids[item['base_id']]})")
        else:
            seen_ids[item["base_id"]] = tag
        query_seen[(item["split"], norm(item["query"]))].append(tag)

        scope = item["scope"]
        if scope.get("mode") not in SCOPE_MODES:
            errors.append(f"{tag}: bad scope.mode {scope.get('mode')}")
        if scope.get("mode") == "explicit_revisions":
            if not scope.get("revision_ids"):
                errors.append(f"{tag}: explicit scope without revision_ids")
            unknown = [r for r in scope.get("revision_ids", []) if r not in rev_meta]
            if unknown:
                errors.append(f"{tag}: unknown revisions in scope {unknown}")

        gold = item["gold"]
        if gold.get("status") not in STATUSES:
            errors.append(f"{tag}: bad status {gold.get('status')}")
        if gold.get("verdict_class") not in VERDICT:
            errors.append(f"{tag}: bad verdict_class {gold.get('verdict_class')}")
        if not gold.get("answer"):
            errors.append(f"{tag}: empty answer")
        if not gold.get("recompute_note"):
            errors.append(f"{tag}: missing recompute_note")

        evidence = gold.get("evidence_minimal") or []
        if not evidence:
            errors.append(f"{tag}: empty evidence_minimal")
        ev_ids = set()
        for ev in evidence:
            cid = ev.get("chunk_id")
            if cid not in chunks:
                errors.append(f"{tag}: evidence chunk not found {cid}")
                continue
            ev_ids.add(cid)
            rec = chunks[cid]
            if ev.get("revision_id") != rec["revision_id"]:
                errors.append(f"{tag}: evidence revision mismatch {cid}")
            if ev.get("locator_kind") != rec["position_kind"]:
                errors.append(f"{tag}: locator_kind mismatch {cid}: "
                              f"{ev.get('locator_kind')} != {rec['position_kind']}")
            if ev.get("locator_label") != rec.get("position_label"):
                errors.append(f"{tag}: locator_label mismatch {cid}")
            if ev.get("role") not in ROLES:
                errors.append(f"{tag}: bad evidence role {ev.get('role')}")
            if not ev.get("excerpt"):
                errors.append(f"{tag}: empty excerpt {cid}")
            elif not excerpt_in_text(ev["excerpt"], rec["text"]):
                errors.append(f"{tag}: excerpt not found verbatim in {cid}")
            elif ev["excerpt"] not in rec["text"] and not any(
                sep in ev["excerpt"] for sep in ("……", "...")
            ):
                warnings.append(
                    f"{tag}: excerpt requires whitespace normalisation in {cid}"
                )
            if rec["revision_id"] in restricted:
                errors.append(f"{tag}: evidence uses restricted revision {rec['revision_id']}")
            if rec.get("family_id") and rec["family_id"] not in item["family_ids"]:
                errors.append(
                    f"{tag}: evidence family {rec['family_id']} not in item family_ids"
                )

        facts = gold.get("required_facts") or []
        if not facts:
            errors.append(f"{tag}: empty required_facts")
        referenced = set()
        role_of = {ev.get("chunk_id"): ev.get("role") for ev in evidence}
        for fact in facts:
            support = fact.get("support") or []
            if not support:
                errors.append(f"{tag}: fact {fact.get('fact_id')} without support")
            for cid in support:
                if cid not in ev_ids:
                    errors.append(f"{tag}: fact support {cid} not in evidence_minimal")
                referenced.add(cid)
            if support and not any(role_of.get(cid) == "fact_support" for cid in support):
                errors.append(
                    f"{tag}: fact {fact.get('fact_id')} has no fact_support evidence"
                )
        for ev in evidence:
            if ev.get("role") == "fact_support" and ev.get("chunk_id") not in referenced:
                warnings.append(f"{tag}: fact_support evidence unreferenced {ev.get('chunk_id')}")

        ivs = item.get("interventions") or []
        if not ivs:
            errors.append(f"{tag}: no interventions")
        roles = collections.Counter(iv.get("pair_role") for iv in ivs)
        if roles.get("should_change", 0) < 1:
            errors.append(f"{tag}: no should_change intervention")
        if roles.get("should_hold", 0) < 1:
            errors.append(f"{tag}: no should_hold intervention")
        iv_ids = set()
        for iv in ivs:
            iid = iv.get("intervention_id")
            if not iid:
                errors.append(f"{tag}: intervention without id")
            elif iid in iv_ids:
                errors.append(f"{tag}: duplicate intervention id {iid}")
            iv_ids.add(iid)
            pr = iv.get("pair_role")
            op = iv.get("operation")
            if pr not in PAIR:
                errors.append(f"{tag}: bad pair_role {pr}")
            elif pr == "should_change" and op not in OPS_CHANGE:
                errors.append(f"{tag}: bad should_change op {op}")
            elif pr == "should_hold" and op not in OPS_HOLD:
                errors.append(f"{tag}: bad should_hold op {op}")
            for cid in iv.get("target_chunk_ids") or []:
                if cid not in chunks:
                    errors.append(f"{tag}: intervention target chunk missing {cid}")
                elif chunks[cid]["revision_id"] in restricted:
                    errors.append(f"{tag}: intervention targets restricted revision {cid}")
                elif chunks[cid].get("family_id") and chunks[cid]["family_id"] not in item["family_ids"]:
                    errors.append(
                        f"{tag}: intervention target family {chunks[cid]['family_id']} not in item family_ids"
                    )
            if pr == "should_change":
                exp = iv.get("expected_gold_after") or {}
                if exp.get("status") not in STATUSES:
                    errors.append(f"{tag}: should_change missing expected_gold_after.status")
                if not exp.get("answer_summary"):
                    errors.append(f"{tag}: should_change missing answer_summary")
            if pr == "should_hold":
                exp = iv.get("expected_gold_after") or {}
                if exp.get("changed_fact_ids"):
                    errors.append(f"{tag}: should_hold must not change facts")

        if item.get("query_lang") not in {"zh", "en"}:
            errors.append(f"{tag}: bad query_lang {item.get('query_lang')}")

        # prior-exposure rules from the split policy
        exposure = policy.get("prior_exposure", {})
        if item["split"] == "test":
            if item["scenario"] == "s1_connectivity":
                text = json.dumps(item, ensure_ascii=False)
                for cab in exposure.get("exposed_cabinets", []):
                    # full-token match: L2-CN03 must not match inside FEL2-CN03
                    pattern = r"(?<![A-Za-z0-9#\-])" + re.escape(cab) + r"(?![0-9A-Za-z#\-])"
                    if re.search(pattern, text):
                        errors.append(f"{tag}: test item references exposed cabinet {cab}")
            if item["scenario"] == "s2_revision":
                bad = set(item["family_ids"]) & set(exposure.get("exposed_manual_families", []))
                if bad:
                    errors.append(f"{tag}: test uses previously exposed manual families {sorted(bad)}")
            if item["scenario"] == "s3_verification":
                if "shine-prototype-fast-interlock-acceptance" in item["family_ids"]:
                    errors.append(f"{tag}: test uses fast-interlock family exposed by prior benchmark")

    for (split, q), tags in query_seen.items():
        if len(tags) > 1:
            warnings.append(f"duplicate query in {split}: {q[:60]} -> {tags}")

    # global accounting
    by_split = collections.Counter(i["split"] for i in items if "split" in i)
    by_scen = collections.Counter(i["scenario"] for i in items if "scenario" in i)
    by_cluster = collections.Counter(i["cluster_id"] for i in items if "cluster_id" in i)
    explicit = [i for i in items if i.get("scope", {}).get("mode") == "explicit_revisions"]

    # cross-split evidence / family isolation
    chunk_splits = collections.defaultdict(set)
    fam_splits = collections.defaultdict(set)
    for item in items:
        if "split" not in item:
            continue
        for ev in item.get("gold", {}).get("evidence_minimal", []) or []:
            chunk_splits[ev.get("chunk_id")].add(item["split"])
        for f in item.get("family_ids", []) or []:
            fam_splits[f].add(item["split"])
    for cid, splits in chunk_splits.items():
        if len(splits) > 1:
            errors.append(f"evidence chunk {cid} used across splits {sorted(splits)}")
    for fam, splits in fam_splits.items():
        if len(splits) > 1:
            errors.append(f"family {fam} used across splits {sorted(splits)}")

    if items:
        for cid, cl in clusters.items():
            if args.partial and cid not in by_cluster:
                continue
            if by_cluster.get(cid, 0) != cl["quota"]:
                errors.append(f"cluster {cid} count={by_cluster.get(cid,0)} != quota {cl['quota']}")
        if not args.partial:
            for split, target in policy["global_split_targets"].items():
                if by_split.get(split, 0) != target:
                    errors.append(f"split count {split}={by_split.get(split,0)} != {target}")
            for key, scen in policy["scenarios"].items():
                if by_scen.get(key, 0) != scen["target_count"]:
                    errors.append(f"scenario count {key}={by_scen.get(key,0)} != {scen['target_count']}")
            rule = policy["explicit_scope_rule"]
            if len(explicit) != rule["count"]:
                errors.append(f"explicit scope count={len(explicit)} != {rule['count']}")
            exp_by_split = collections.Counter(i["split"] for i in explicit)
            for split, target in rule["allocation"].items():
                if exp_by_split.get(split, 0) != target:
                    errors.append(f"explicit scope {split}={exp_by_split.get(split,0)} != {target}")
            bad_scen = {i["scenario"] for i in explicit} - {rule["scenario"]}
            if bad_scen:
                errors.append(f"explicit scope outside {rule['scenario']}: {bad_scen}")

    report = {
        "files": [str(p) for p in files],
        "items": len(items),
        "by_split": dict(by_split),
        "by_scenario": dict(by_scen),
        "by_cluster": dict(by_cluster),
        "explicit_scope": len(explicit),
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f"items={len(items)} splits={dict(by_split)} scenarios={dict(by_scen)}")
        print(f"explicit_scope={len(explicit)}")
        for e in errors:
            print(f"ERROR {e}")
        for w in warnings:
            print(f"WARN  {w}")
        print(f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
