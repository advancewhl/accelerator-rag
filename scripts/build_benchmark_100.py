#!/usr/bin/env python3
"""Build the audited 100-question rc.3 validation benchmark.

Inputs (all read-only):

* ``data/evaluation/validity-pilot-v2.json`` — the 50-question regression set.
  This script emits ``validity-pilot-v3.json`` with the stem amendments that
  the 2026-10-30 rubric adjudication required. Gold answers, must-cover facts
  and evidence groups are copied unchanged; only the question stem gains the
  clarification, so this is not a post-hoc answer edit.
* ``data/evaluation/cable-lookup-v1.json`` — 20 cable/switch questions whose
  gold rows were produced by an independent openpyxl pass.
* ``data/evaluation/kb2-question-plan-v1.json`` — the 60-question draft. Only
  ``verified_from_extracted_text`` items are eligible; the 13
  ``needs_source_check``, the 8 ``derived_from_analysis`` and the two items
  that depend on a restricted document stay out.

Selection for the 100: all 50 regression items, all 20 cable items and 30
verified KB2 items (20 dev + 10 sealed). The remaining 9 verified KB2 items
are listed as reserve in the generated report.

The output is deterministic; rerunning produces byte-identical JSON except for
the ``generated_on`` field.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "data/evaluation"

# Stems to clarify, taken verbatim from
# reports/validity-pilot-online-20261030/rubric-adjudication.md §1.
STEM_AMENDMENTS = {
    "P50-004": "请明确所依据资料的年代及设计／实测口径。",
    "P50-012": "调整阈值后，用输出做统计还应读取什么信息？",
    "P50-027": "请说明归档查询的时间覆盖限制，以及能否据此解释全部问题。",
    "P50-030": "分别说明前端和服务端在何时读取或检查。",
    "P50-039": "另外，剩余两台有效数据能否继续用于分析？",
    "P50-042": "分别给出下一步排查，并说明能否只改界面或插值等待值。",
    "P50-043": "说明应比较哪些编号集合，以及与 X、Y 双零处理的区别。",
    "P50-045": "说明两路构建的事务边界，以及发布时需要保持一致的资产。",
}

# Items selected from the verified 60-question plan: 12 new-fact, 11 version,
# 5 boundary and 2 format questions, 20 dev + 10 sealed.
KB2_SELECTED = [
    "KB2-FACT-001",
    "KB2-FACT-002",
    "KB2-FACT-003",
    "KB2-FACT-004",
    "KB2-FACT-005",
    "KB2-FACT-009",
    "KB2-FACT-011",
    "KB2-FACT-013",
    "KB2-FACT-015",
    "KB2-FACT-016",
    "KB2-FACT-017",
    "KB2-FACT-018",
    "KB2-VER-001",
    "KB2-VER-002",
    "KB2-VER-003",
    "KB2-VER-004",
    "KB2-VER-005",
    "KB2-VER-006",
    "KB2-VER-007",
    "KB2-VER-010",
    "KB2-VER-008",
    "KB2-VER-009",
    "KB2-VER-015",
    "KB2-BND-004",
    "KB2-BND-006",
    "KB2-BND-007",
    "KB2-BND-008",
    "KB2-BND-010",
    "KB2-FMT-001",
    "KB2-FMT-002",
]

# Boundary questions whose correct behaviour is a refusal of the requested
# real-world state; everything else is expected to answer.
KB2_INSUFFICIENT = {"KB2-BND-007", "KB2-BND-008"}

# The default retrieval scope only admits current/reference documents.  These
# questions name an archived, pending-review or historical revision, exactly
# as a user does in the workbench when they select that document.  Without an
# explicit version scope the question is answered against a scope that cannot
# contain its source, which measures the default refusal rather than the
# answer.  Revision IDs are resolved from registry-v2.json source paths.
KB2_SCOPES = {
    "KB2-FACT-001": ["shine-control-operation-manual-series-rev-715c251d"],
    "KB2-FACT-002": ["shine-control-operation-manual-series-rev-715c251d"],
    "KB2-FACT-003": ["shine-control-operation-manual-series-rev-715c251d"],
    "KB2-FACT-004": ["shine-control-operation-manual-series-rev-300f0580"],
    "KB2-FACT-005": ["shine-control-operation-manual-series-rev-b672c917"],
    "KB2-FACT-009": ["shine-control-operation-manual-series-rev-b9bfd428"],
    "KB2-FACT-011": ["shine-control-operation-manual-series-rev-b9bfd428"],
    "KB2-FACT-013": ["shine-control-operation-manual-series-rev-b9bfd428"],
    "KB2-FACT-015": ["shine-control-operation-manual-series-rev-ec081ce3"],
    "KB2-FACT-016": ["shine-data-storage-and-archive-rev-a14b336b"],
    "KB2-FACT-017": ["shine-control-operation-manual-series-rev-b9bfd428"],
    "KB2-FACT-018": ["shine-data-storage-and-archive-rev-3e4fff6e"],
    "KB2-VER-001": [
        "shine-control-operation-manual-series-rev-715c251d",
        "shine-control-operation-manual-series-rev-73552d9f",
    ],
    "KB2-VER-002": [
        "shine-control-operation-manual-series-rev-715c251d",
        "shine-control-operation-manual-series-rev-99ecefba",
    ],
    "KB2-VER-003": [
        "shine-control-operation-manual-series-rev-99ecefba",
        "shine-control-operation-manual-series-rev-73552d9f",
    ],
    "KB2-VER-004": [
        "shine-control-operation-manual-series-rev-300f0580",
        "shine-control-operation-manual-series-rev-0e94a5e4",
    ],
    "KB2-VER-005": [
        "shine-control-operation-manual-series-rev-96ebdc19",
        "shine-control-operation-manual-series-rev-b9bfd428",
    ],
    "KB2-VER-006": [
        "shine-control-operation-manual-series-rev-fba2ad49",
        "shine-control-operation-manual-series-rev-7da26046",
    ],
    "KB2-VER-007": [
        "shine-control-operation-manual-series-rev-fba2ad49",
        "shine-control-operation-manual-series-rev-7da26046",
    ],
    "KB2-VER-008": [
        "shine-control-operation-manual-series-rev-fba2ad49",
        "shine-control-operation-manual-series-rev-7da26046",
    ],
    "KB2-VER-009": [
        "shine-control-operation-manual-series-rev-fba2ad49",
        "shine-control-operation-manual-series-rev-7da26046",
    ],
    "KB2-VER-010": [
        "shine-control-operation-manual-series-rev-f12c9ad8",
        "shine-control-operation-manual-series-rev-ec081ce3",
    ],
    "KB2-VER-015": [
        "shine-control-operation-manual-series-rev-fba2ad49",
        "shine-control-operation-manual-series-rev-f12c9ad8",
        "shine-control-operation-manual-series-rev-ec081ce3",
    ],
    "KB2-BND-004": ["shine-data-storage-and-archive-rev-3e4fff6e"],
    "KB2-BND-006": ["shine-control-operation-manual-series-rev-715c251d"],
    "KB2-BND-007": [
        "shine-control-operation-manual-series-rev-715c251d",
        "shine-control-operation-manual-series-rev-300f0580",
    ],
    "KB2-BND-008": ["shine-control-operation-manual-series-rev-b672c917"],
    "KB2-BND-010": ["shine-control-operation-manual-series-rev-7da26046"],
    "KB2-FMT-001": ["shine-data-storage-and-archive-rev-3e4fff6e"],
    "KB2-FMT-002": ["shine-data-storage-and-archive-rev-3e4fff6e"],
}


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def dump(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_validity_v3(source: dict) -> dict:
    items = []
    for item in source["items"]:
        item = dict(item)
        addition = STEM_AMENDMENTS.get(item["id"])
        if addition:
            item["query"] = item["query"].rstrip() + addition
            item["stem_amended_2026_11_05"] = True
            item["stem_amendment_reason"] = (
                "rubric-adjudication.md §1：题干未要求但 must_cover 要求的事实，"
                "下一版题干补充，答案与清单不变。"
            )
        items.append(item)
    return {
        "schema_version": "validity-pilot-v3",
        "dataset_revision": "2026-11-05-r2",
        "supersedes": "validity-pilot-v2.json",
        "purpose": source.get("purpose"),
        "independent_test_allowed": source.get("independent_test_allowed"),
        "status": "frozen_for_rc3_validation",
        "amendment_policy": (
            "只按 rubric-adjudication.md §1 补充题干范围；gold_answer、must_cover、"
            "forbidden_claims、evidence_groups 原样保留，未用于本轮提分。"
        ),
        "amended_ids": sorted(STEM_AMENDMENTS),
        "items": items,
    }


def unified_from_p50(item: dict) -> dict:
    return {
        "id": item["id"],
        "source_set": "validity-pilot-v3",
        "group": item.get("category", "regression"),
        "split": "regression",
        "query": item["query"],
        "expected_status": item["expected_status"],
        "required_facts": list(item.get("must_cover", [])),
        "forbidden_claims": list(item.get("forbidden_claims", [])),
        # Keep the original grouped evidence under its native key: the
        # regression runner resolves document/chunk IDs only from
        # ``evidence_groups``.  ``evidence`` is the flattened display copy.
        "evidence_groups": item.get("evidence_groups", []),
        "evidence": item.get("evidence_groups", []),
        "verification_level": "evidence_machine_verified",
        "notes": item.get("human_review", ""),
    }


def unified_from_cable(item: dict) -> dict:
    return {
        "id": item["id"],
        "source_set": "cable-lookup-v1",
        "group": item.get("category", "cable"),
        "split": item.get("split", "dev"),
        "query": item["question"],
        "expected_status": item.get("expected_status", "answered"),
        "required_facts": list(item.get("required_values", [])),
        "forbidden_claims": list(item.get("forbidden_claims", [])),
        "evidence": item.get("evidence", []),
        "verification_level": "gold_rows_machine_verified",
        "notes": item.get("notes", ""),
    }


def unified_from_kb2(item: dict) -> dict:
    return {
        "id": item["id"],
        "source_set": "kb2-question-plan-v1",
        "group": item["group"],
        "split": item["split"],
        "query": item["question_zh"],
        "expected_status": (
            "insufficient" if item["id"] in KB2_INSUFFICIENT else "answered"
        ),
        "required_facts": list(item.get("required_facts", [])),
        "forbidden_claims": list(item.get("forbidden_inferences", [])),
        "evidence": [
            {
                "candidate_source": item.get("candidate_source"),
                "evidence_location": item.get("evidence_location"),
            }
        ],
        "scope": (
            {"mode": "version", "revision_ids": KB2_SCOPES[item["id"]]}
            if item["id"] in KB2_SCOPES
            else None
        ),
        "verification_level": item.get("provenance_status", ""),
        "notes": item.get("notes", ""),
    }


def audit(items: list[dict]) -> dict:
    ids = [item["id"] for item in items]
    duplicates = [key for key, count in collections.Counter(ids).items() if count > 1]
    queries = [item["query"].strip().casefold() for item in items]
    duplicate_queries = [
        key for key, count in collections.Counter(queries).items() if count > 1
    ]
    missing = [
        item["id"]
        for item in items
        if not item["query"].strip()
        or item["expected_status"] not in ("answered", "partial", "insufficient")
        # Refusal/qualification items carry their judgment in forbidden_claims
        # and notes; only answered items need positive required facts.
        or (item["expected_status"] == "answered" and not item["required_facts"])
    ]
    return {
        "count": len(items),
        "by_source": dict(collections.Counter(i["source_set"] for i in items)),
        "by_group": dict(collections.Counter(i["group"] for i in items)),
        "by_split": dict(collections.Counter(i["split"] for i in items)),
        "by_status": dict(collections.Counter(i["expected_status"] for i in items)),
        "duplicate_ids": duplicates,
        "duplicate_queries": duplicate_queries,
        "items_missing_required_fields": missing,
        "kb2_items_without_scope": [
            item["id"]
            for item in items
            if item["source_set"] == "kb2-question-plan-v1" and not item.get("scope")
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-on", default="2026-11-05")
    args = parser.parse_args()

    v2 = load(EVAL / "validity-pilot-v2.json")
    cable = load(EVAL / "cable-lookup-v1.json")
    plan = load(EVAL / "kb2-question-plan-v1.json")

    v3 = build_validity_v3(v2)
    if len(v3["items"]) != 50:
        raise SystemExit(f"validity-pilot-v3 must have 50 items, got {len(v3['items'])}")
    dump(EVAL / "validity-pilot-v3.json", v3)

    registry = load(ROOT / "data/documents/v2/registry-v2.json")
    known_revisions = {item["revision_id"] for item in registry["revisions"]}
    missing_scopes = [qid for qid in KB2_SELECTED if qid not in KB2_SCOPES]
    unknown_revisions = sorted(
        {
            revision_id
            for revision_ids in KB2_SCOPES.values()
            for revision_id in revision_ids
        }
        - known_revisions
    )
    if missing_scopes or unknown_revisions:
        raise SystemExit(
            f"scope mapping incomplete: missing={missing_scopes} "
            f"unknown={unknown_revisions}"
        )

    plan_by_id = {item["id"]: item for item in plan["questions"]}
    for question_id in KB2_SELECTED:
        item = plan_by_id.get(question_id)
        if item is None:
            raise SystemExit(f"selected question missing: {question_id}")
        if item.get("provenance_status") != "verified_from_extracted_text":
            raise SystemExit(
                f"{question_id} is not verified_from_extracted_text: "
                f"{item.get('provenance_status')}"
            )

    items = []
    items.extend(unified_from_p50(item) for item in v3["items"])
    items.extend(unified_from_cable(item) for item in cable["questions"])
    items.extend(unified_from_kb2(plan_by_id[qid]) for qid in KB2_SELECTED)

    if len(items) != 100:
        raise SystemExit(f"benchmark must have 100 items, got {len(items)}")
    checks = audit(items)
    if checks["duplicate_ids"] or checks["duplicate_queries"]:
        raise SystemExit(f"duplicate ids/queries: {checks}")
    if checks["items_missing_required_fields"]:
        raise SystemExit(f"items missing fields: {checks['items_missing_required_fields']}")

    reserve = [
        item["id"]
        for item in plan["questions"]
        if item.get("provenance_status") == "verified_from_extracted_text"
        and item["id"] not in KB2_SELECTED
    ]

    payload = {
        "schema_version": "kb2-benchmark-100-v1",
        "generated_on": args.generated_on,
        "status": "frozen_for_rc3_validation",
        "release_target": "kb-2.0.0-rc.3",
        "purpose": (
            "rc.3 候选与 rc.2 生产对照的 100 题工程回归集；用于状态、引用覆盖与"
            "HTTP 稳定性比较，语义正确性仍需人工评分。"
        ),
        "composition": {
            "validity-pilot-v3": {
                "selected": 50,
                "source": "data/evaluation/validity-pilot-v3.json",
                "verification": "evidence_machine_verified",
            },
            "cable-lookup-v1": {
                "selected": 20,
                "source": "data/evaluation/cable-lookup-v1.json",
                "verification": "gold_rows_machine_verified",
            },
            "kb2-question-plan-v1": {
                "selected": len(KB2_SELECTED),
                "source": "data/evaluation/kb2-question-plan-v1.json",
                "verification": "verified_from_extracted_text",
                "reserve_verified": reserve,
            },
        },
        "exclusions": {
            "kb2-needs-source-check": (
                "13 题依赖 PPTX/XLSX/OCR/公式解析，冻结前需人工核对，未纳入。"
            ),
            "kb2-derived-from-analysis": (
                "8 题来自二手分析，未回原文核对，未纳入。"
            ),
            "restricted-dependency": (
                "KB2-FMT-015、KB2-BND-001 依赖 access_scope=restricted 的网络安全"
                "设计报告，默认检索不可见，未纳入。"
            ),
        },
        "runners": {
            "answer": (
                "python scripts/kb2_run_regression.py --questions "
                "data/evaluation/kb2-benchmark-100-v1.json --base-url <url> "
                "--output <json>"
            ),
            "cable_lookup": (
                "python scripts/run_cable_benchmark.py --base-url <url> "
                "--output <json>"
            ),
        },
        "audit": checks,
        "items": items,
    }
    dump(EVAL / "kb2-benchmark-100-v1.json", payload)

    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print(f"reserve verified: {len(reserve)} -> {', '.join(reserve)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
