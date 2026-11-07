"""Independent audit of phase-3 evidence-pack reports (0 blockers required)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.evidence_pack.fingerprints import (  # noqa: E402
    corpus_digest,
    facts_digest,
    questions_digest,
)
from accelerator_rag.evidence_pack.index import (  # noqa: E402
    load_index,
    merge_port_intervals,
    port_intervals,
)
from accelerator_rag.evidence_pack.schema import (  # noqa: E402
    entity_in_text,
    normalize_key,
)
from accelerator_rag.facts.schema import excerpt_in_text  # noqa: E402
from accelerator_rag.verify.operators import run_operator  # noqa: E402

DEFAULT_REPORTS = [
    ROOT / "reports" / "phase3" / "dev.json",
    ROOT / "reports" / "phase3" / "val.json",
    ROOT / "reports" / "phase3" / "dev-rule.json",
    ROOT / "reports" / "phase3" / "val-rule.json",
    ROOT / "reports" / "phase3" / "dev-learned.json",
    ROOT / "reports" / "phase3" / "val-learned.json",
]
FULL_TEXT_OVERHEAD = 24


def _canonical(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _check_atoms(atoms, *, qid, chunk_text, facts, problems, label):
    for atom in atoms:
        if atom["locator_kind"] == "external_observation":
            if atom.get("chunk_id"):
                problems.append(f"{qid}: {label} external atom has chunk_id")
            external = atom.get("external") or {}
            for field in ("pv", "start", "end", "strategy", "limitations"):
                if field not in external:
                    problems.append(f"{qid}: {label} external atom missing {field}")
            continue
        text = chunk_text.get(atom["chunk_id"])
        if text is None:
            problems.append(f"{qid}: {label} atom cites unknown chunk")
            continue
        if not excerpt_in_text(atom["excerpt"], text):
            problems.append(f"{qid}: {label} atom excerpt is not verbatim")
        if atom.get("chars") != len(atom["excerpt"]):
            problems.append(f"{qid}: {label} atom char count mismatch")
        for fact_id in atom.get("fact_ids", ()):
            fact = facts.get(fact_id)
            if fact is None:
                problems.append(f"{qid}: {label} atom cites unknown fact")
                continue
            if fact.citation.chunk_id != atom["chunk_id"]:
                problems.append(f"{qid}: {label} fact cites another chunk")
            if not (
                excerpt_in_text(fact.citation.excerpt, atom["excerpt"])
                or excerpt_in_text(atom["excerpt"], fact.citation.excerpt)
            ):
                problems.append(f"{qid}: {label} fact excerpt mismatch")


def audit_report(report, *, index, chunk_text, problems, expected_hashes):
    qid = report["question_id"]
    split = report["split"]
    if split not in {"dev", "val"}:
        problems.append(f"{qid}: split is not dev/val")
    if "sealed-test" in json.dumps(report, ensure_ascii=False):
        problems.append(f"{qid}: report mentions sealed-test")
    recompute = report.get("recompute", {})
    if recompute.get("facts_sha256") != expected_hashes["facts"]:
        problems.append(f"{qid}: facts_sha256 is stale")
    if recompute.get("questions_sha256") != expected_hashes[split]:
        problems.append(f"{qid}: questions_sha256 is stale")
    if recompute.get("corpus_snapshot") != expected_hashes[f"corpus_{split}"]:
        problems.append(f"{qid}: corpus_snapshot is stale")
    if report.get("reranker", {}).get("name") in {"rule", "learned"}:
        if not report.get("rerank", {}).get("atoms"):
            problems.append(f"{qid}: rerank score_breakdown is missing")

    budget = report["budget"]
    required = sum(
        1 for item in report["needs"]["relations"] if item["required"]
    )
    cap = min(6000, budget["base_tokens"] + max(0, required - 3) * 150)
    if budget["tokens"] != cap:
        problems.append(f"{qid}: budget tokens do not follow required-only cap")
    pack = report["pack"]
    if pack["tokens"] > cap:
        problems.append(f"{qid}: pack tokens exceed required-only cap")
    referenced = {
        atom["chunk_id"] for atom in pack["atoms"] if atom.get("chunk_id")
    }
    parent_ids = {parent["chunk_id"] for parent in pack["parents"]}
    if parent_ids != referenced:
        problems.append(f"{qid}: parents do not list every referenced chunk")
    if len(parent_ids) != len(pack["parents"]):
        problems.append(f"{qid}: parents contain duplicate chunk entries")
    full_text = [parent for parent in pack["parents"] if parent.get("full_text")]
    if len(full_text) > budget["max_parents"]:
        problems.append(f"{qid}: full-text parent cap exceeded")
    expected_flags = [True] * min(budget["max_parents"], len(pack["parents"]))
    expected_flags += [False] * (len(pack["parents"]) - len(expected_flags))
    if [bool(parent.get("full_text")) for parent in pack["parents"]] != expected_flags:
        problems.append(f"{qid}: full-text parents are not the leading entries")
    expected_tokens = (
        sum(atom["tokens"] for atom in pack["atoms"])
        + FULL_TEXT_OVERHEAD * len(referenced)
    )
    if pack["tokens"] != expected_tokens:
        problems.append(f"{qid}: pack tokens do not match atom/parent cost")
    if pack.get("chars") != sum(len(atom["excerpt"]) for atom in pack["atoms"]):
        problems.append(f"{qid}: pack char count mismatch")

    atoms = {atom["atom_id"]: atom for atom in pack["atoms"]}
    _check_atoms(
        pack["atoms"], qid=qid, chunk_text=chunk_text, facts=index.facts.facts,
        problems=problems, label="pack",
    )
    for round_row in report.get("rounds", ()):
        _check_atoms(
            round_row["pack"]["atoms"], qid=qid, chunk_text=chunk_text,
            facts=index.facts.facts, problems=problems,
            label=f"round{round_row['round']}",
        )
    baseline = report.get("baseline") or {}
    _check_atoms(
        baseline.get("atoms", ()), qid=qid, chunk_text=chunk_text,
        facts=index.facts.facts, problems=problems, label="baseline",
    )
    if baseline.get("conflicts"):
        problems.append(f"{qid}: baseline carries conflict records")
    if baseline:
        baseline_parents = baseline.get("parents", ())
        baseline_ids = {parent["chunk_id"] for parent in baseline_parents}
        if len(baseline_parents) > 5:
            problems.append(f"{qid}: baseline has more than five parents")
        if len(baseline_ids) != len(baseline_parents):
            problems.append(f"{qid}: baseline parent duplicates")
        if any(not parent.get("full_text") for parent in baseline_parents):
            problems.append(f"{qid}: baseline parent is not full text")
        if baseline.get("tokens", 0) > report["budget"]["tokens"]:
            problems.append(f"{qid}: baseline tokens exceed budget")
        if baseline.get("tokens", 0) != sum(
            parent.get("tokens", 0) for parent in baseline_parents
        ):
            problems.append(f"{qid}: baseline token sum mismatch")

    selected = set(atoms)
    coverage = {item["name"]: item for item in pack["coverage"]}
    core_entities = {
        item["normalized"]: item["kind"]
        for item in report["needs"]["entities"]
        if item["kind"] in {"cabinet", "device"}
    }
    port_entities = [
        item["normalized"]
        for item in report["needs"]["entities"]
        if item["kind"] == "port"
    ]

    def _core_ok(atom, *, any_only=False):
        text = normalize_key(" ".join([atom["excerpt"], atom["locator_label"]]))
        cabinets = [
            entity
            for entity, kind in core_entities.items()
            if kind == "cabinet"
        ]
        devices = [
            entity
            for entity, kind in core_entities.items()
            if kind == "device"
        ]
        checks = []
        if cabinets:
            checks.append(
                any(entity_in_text(entity, text, "cabinet") for entity in cabinets)
            )
        if devices:
            checks.append(
                any(entity_in_text(entity, text, "device") for entity in devices)
            )
        if not checks:
            return True
        return any(checks) if any_only else all(checks)

    def _intervals(atom):
        values = []
        for cell in atom["excerpt"].strip().strip("|").split("|"):
            values.extend(port_intervals(cell))
        return values

    for name in ("value", "scope", "counterpart"):
        item = coverage.get(name)
        if not item or not item["satisfied"]:
            continue
        witnesses = []
        for atom_id in item["atom_ids"]:
            atom = atoms.get(atom_id)
            if atom is None:
                problems.append(f"{qid}: coverage cites unselected atom")
                continue
            witnesses.append(atom)
            if not _core_ok(atom):
                problems.append(
                    f"{qid}: {name} coverage atom does not match core objects"
                )
        if name in {"value", "scope"} and port_entities:
            for atom in witnesses:
                probes = [
                    interval
                    for port in port_entities
                    for interval in port_intervals(port)
                ]
                if not any(
                    not (a_high < b_low or b_high < a_low)
                    for a_low, a_high in _intervals(atom)
                    for b_low, b_high in probes
                ):
                    problems.append(
                        f"{qid}: {name} coverage lists a disjoint port atom"
                    )
            intervals = merge_port_intervals(
                interval for atom in witnesses for interval in _intervals(atom)
            )
            for port in port_entities:
                for low, high in port_intervals(port):
                    if not any(
                        s_low <= low and high <= s_high
                        for s_low, s_high in intervals
                    ):
                        problems.append(
                            f"{qid}: {name} coverage does not cover the asked port range"
                        )
    for name in ("unit", "condition", "boundary"):
        item = coverage.get(name)
        if not item or not item["satisfied"]:
            continue
        for atom_id in item["atom_ids"]:
            atom = atoms.get(atom_id)
            if atom is None:
                continue
            if not _core_ok(atom, any_only=True):
                problems.append(
                    f"{qid}: {name} coverage atom does not match any core object"
                )

    enumeration = coverage.get("enumeration")
    if enumeration and enumeration["satisfied"]:
        if not set(enumeration["atom_ids"]) <= selected:
            problems.append(f"{qid}: enumeration coverage cites unselected row")
        blocks = {
            atoms[atom_id]["table_block_id"]
            for atom_id in enumeration["atom_ids"]
            if atom_id in atoms and atoms[atom_id].get("table_block_id")
        }
        for block in blocks:
            expected_rows = {
                row.row_number for row in index.rows if row.table_block_id == block
            }
            selected_rows = {
                atoms[atom_id]["row_number"]
                for atom_id in enumeration["atom_ids"]
                if atom_id in atoms and atoms[atom_id].get("table_block_id") == block
            }
            if expected_rows != selected_rows:
                problems.append(f"{qid}: enumeration block is not complete")

    for conflict in pack.get("conflicts", ()):
        sides = set(conflict["atom_ids"])
        if sides & selected and not sides <= selected:
            if conflict["resolution"] != "unresolved":
                problems.append(f"{qid}: conflict kept one-sided")
        elif not (sides & selected):
            if conflict["resolution"] != "unresolved":
                problems.append(f"{qid}: conflict kept neither side without unresolved")
        elif sides <= selected and conflict["resolution"] == "unresolved":
            problems.append(f"{qid}: conflict marked unresolved but both sides selected")
    unresolved_ids = {
        message.split(":", 1)[0]
        for message in pack.get("unresolved", ())
        if ":" in message
    }
    declared = {
        conflict["conflict_id"]
        for conflict in pack.get("conflicts", ())
        if conflict["resolution"] == "unresolved"
    }
    if unresolved_ids != declared:
        problems.append(f"{qid}: unresolved messages and conflict resolutions differ")

    verification = report["verification"]
    if report["verdict_class"] != "deterministic":
        if verification["status"] != "not_evaluated":
            problems.append(f"{qid}: rubric/human item is not not_evaluated")
        if verification["claims"]:
            problems.append(f"{qid}: rubric/human item has claims")
    if verification["status"] == "not_evaluated" and verification["claims"]:
        problems.append(f"{qid}: not_evaluated item has claims")
    for claim in verification.get("claims", ()):
        if not claim.get("atom_ids") and not claim.get("fact_ids"):
            problems.append(f"{qid}: claim lacks atom/fact trace")
    for record in verification.get("operators", ()):
        if set(record) != {"op", "request", "response"}:
            problems.append(f"{qid}: operator record shape")
            continue
        replay = run_operator(record["op"], record["request"])
        if replay != record["response"]:
            problems.append(f"{qid}: operator {record['op']} does not replay")
    recompute = dict(report.get("recompute", {}))
    recorded_hash = recompute.pop("report_sha256", "")
    clone = {key: value for key, value in report.items() if key != "evaluation"}
    clone["recompute"] = recompute
    fresh_hash = hashlib.sha256(_canonical(clone).encode("utf-8")).hexdigest()
    if recorded_hash != fresh_hash:
        problems.append(f"{qid}: report_sha256 mismatch")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", nargs="*", default=[str(path) for path in DEFAULT_REPORTS])
    parser.add_argument("--facts", default=str(ROOT / "data" / "facts" / "facts.jsonl"))
    parser.add_argument("--out", default=str(ROOT / "reports" / "phase3" / "audit.json"))
    args = parser.parse_args(argv)

    index = load_index(splits=("dev", "val"), facts_path=args.facts)
    chunk_text = {chunk_id: chunk.text for chunk_id, chunk in index.chunks.items()}
    expected_hashes = {
        "facts": facts_digest(args.facts),
        "dev": questions_digest("dev"),
        "val": questions_digest("val"),
        "corpus_dev": corpus_digest(("dev",)),
        "corpus_val": corpus_digest(("val",)),
    }
    problems: list[str] = []
    bundles = 0
    reports = 0
    for path in args.reports:
        target = Path(path)
        if not target.exists():
            problems.append(f"missing report: {target}")
            continue
        bundle = json.loads(target.read_text(encoding="utf-8"))
        bundles += 1
        for report in bundle.get("reports", ()):
            reports += 1
            audit_report(
                report,
                index=index,
                chunk_text=chunk_text,
                problems=problems,
                expected_hashes=expected_hashes,
            )

    diff = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "src/accelerator_rag/rag"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if diff.stdout.strip():
        problems.append("production rag/ files differ from HEAD: " + diff.stdout.strip())
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "src/accelerator_rag/rag"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if status.stdout.strip():
        problems.append("production rag/ working tree is dirty: " + status.stdout.strip())
    for path in [
        ROOT / "src" / "accelerator_rag" / "evidence_pack",
        ROOT / "scripts" / "research" / "run_evidence_pack.py",
        ROOT / "scripts" / "research" / "train_pack_reranker.py",
        ROOT / "scripts" / "research" / "ingest_archiver.py",
        ROOT / "scripts" / "research" / "build_dense_vectors.py",
        ROOT / "scripts" / "research" / "ablate_pack_selection.py",
        ROOT / "scripts" / "research" / "audit_revision_chunks.py",
        ROOT / "tests" / "evidence_pack",
    ]:
        targets = path.rglob("*.py") if path.is_dir() else [path]
        for target in targets:
            if "sealed-test" in target.read_text(encoding="utf-8"):
                problems.append(f"phase-3 code references sealed-test: {target.name}")

    payload = {
        "schema_version": "phase3-audit-v1",
        "bundles": bundles,
        "reports": reports,
        "blockers": len(problems),
        "problems": problems,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"bundles={bundles} reports={reports} blockers={len(problems)}")
    for problem in problems[:40]:
        print(f"  {problem}")
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
