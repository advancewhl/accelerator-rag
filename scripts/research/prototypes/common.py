"""Shared harness for the three phase-2 single-point prototypes.

A prototype maps one dev/val question to a structured query over the fact
layers, runs deterministic operators, and assembles an answer only from
operator outputs and cited facts.  Every report embeds the operator requests
and responses so a reviewer can replay them; nothing here calls a model.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.facts.schema import UNKNOWN, Fact, FactSet  # noqa: E402,F401
from accelerator_rag.facts.corpus import (  # noqa: E402
    ALLOWED_SPLITS,
    BASE,
    QUESTIONS,
    CorpusScope,
    load_scope,
    split_family_ids,
    split_questions,
)

REPORT_SCHEMA = "phase2-prototype-v1"
DEFAULT_FACTS = ROOT / "data" / "facts" / "facts.jsonl"
EVALUATED_VERDICTS = ("deterministic",)


@lru_cache(maxsize=8)
def _facts_digest(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def facts_digest(path: Path = DEFAULT_FACTS) -> str:
    return _facts_digest(str(Path(path)))


@lru_cache(maxsize=None)
def _file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=4)
def questions_digest(split: str) -> str:
    """Hash of the question file a report was derived from."""

    if split not in ALLOWED_SPLITS:
        return ""
    return _file_sha256(str(QUESTIONS / split / "questions.json"))


@lru_cache(maxsize=4)
def corpus_digest(splits: tuple[str, ...] = ALLOWED_SPLITS) -> str:
    """Hash of the rc.3 inventory plus every chunk file in the dev/val scope.

    Reports pin this so a paragraph-level input change is visible even when no
    fact changed and ``facts_sha256`` stays the same.
    """

    digest = hashlib.sha256()
    inventories = BASE / "inventory"
    families_path = inventories / "families.json"
    for name in ("families.json", "revisions.json"):
        digest.update(name.encode())
        digest.update(bytes.fromhex(_file_sha256(str(inventories / name))))
    families = json.loads(families_path.read_text(encoding="utf-8"))
    revision_ids = sorted(
        {
            revision_id
            for family_id in split_family_ids(splits)
            for revision_id in families[family_id]["revision_ids"]
        }
    )
    for revision_id in revision_ids:
        digest.update(revision_id.encode())
        digest.update(
            bytes.fromhex(_file_sha256(str(BASE / "chunks" / f"{revision_id}.json")))
        )
    return digest.hexdigest()


def load_facts(path: Path | str = DEFAULT_FACTS) -> FactSet:
    target = Path(path)
    if not target.exists():
        raise SystemExit(
            f"facts not built: {target}\n"
            "run scripts/research/build_facts.py --splits dev,val --out data/facts"
        )
    return FactSet.read_jsonl(target)


def question_index(splits=ALLOWED_SPLITS) -> dict[str, dict]:
    for split in splits:
        if split not in ALLOWED_SPLITS:
            raise ValueError(f"split not allowed in phase 2: {split}")
    return {item["base_id"]: item for item in split_questions(splits)}


def get_question(base_id: str) -> dict:
    questions = question_index()
    if base_id not in questions:
        raise SystemExit(
            f"question not found in dev/val: {base_id} "
            "(sealed-test is never read in phase 2)"
        )
    return questions[base_id]


def guard_verdict_class(question: dict) -> str | None:
    """Return a refusal reason for rubric/human questions, else ``None``.

    Phase 1's human questions were not accepted by domain reviewers, so they
    cannot serve as a correctness basis.  The prototypes only claim results on
    deterministic gold.
    """

    verdict = question.get("gold", {}).get("verdict_class", "")
    if verdict not in EVALUATED_VERDICTS:
        return (
            f"verdict_class={verdict or 'unknown'}; phase 2 prototypes only "
            "evaluate deterministic gold, human/rubric items need semantic review"
        )
    return None


@lru_cache(maxsize=128)
def _family_revisions(family_ids: tuple[str, ...]) -> tuple[str, ...]:
    path = ROOT / "tmp" / "research-rc3" / "inventory" / "families.json"
    families = json.loads(path.read_text(encoding="utf-8"))
    revision_ids: set[str] = set()
    for family_id in family_ids:
        revision_ids.update(families[family_id]["revision_ids"])
    return tuple(sorted(revision_ids))


def question_revision_ids(question: dict) -> tuple[str, ...]:
    """Revisions belonging to the question's families, from the inventory."""

    return _family_revisions(tuple(question["family_ids"]))


@lru_cache(maxsize=128)
def scope_for_revisions(revision_ids: tuple[str, ...]) -> CorpusScope:
    """Read-only corpus scope for a question's revisions, cached per process."""

    return load_scope(revision_ids=list(revision_ids))


def scope_for_question(question: dict) -> CorpusScope:
    return scope_for_revisions(question_revision_ids(question))


def facts_for_question(
    facts: FactSet, question: dict, *, layer: str | None = None
) -> list[Fact]:
    return select(
        facts,
        layer=layer,
        revision_ids=question_revision_ids(question),
    )


def select(
    facts: FactSet,
    *,
    layer: str | None = None,
    fact_type: str | None = None,
    revision_ids=None,
    family_roles=None,
) -> list[Fact]:
    revision_filter = set(revision_ids) if revision_ids else None
    role_filter = set(family_roles) if family_roles else None
    return [
        fact
        for fact in facts.sorted()
        if (layer is None or fact.layer == layer)
        and (fact_type is None or fact.fact_type == fact_type)
        and (revision_filter is None or fact.revision_id in revision_filter)
        and (role_filter is None or fact.source_role in role_filter)
    ]


def operator(name: str, request: dict) -> dict:
    """Run one deterministic operator; failures are programming errors."""

    from accelerator_rag.verify.operators import run_operator

    response = run_operator(name, request)
    if not isinstance(response, dict) or response.get("op") != name:
        raise ValueError(f"operator {name} returned an invalid response")
    return response


def evidence_of(facts) -> list[dict]:
    seen, rows = set(), []
    for fact in facts:
        key = (fact.citation.chunk_id, fact.citation.excerpt)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "chunk_id": fact.citation.chunk_id,
                "revision_id": fact.citation.revision_id,
                "locator_kind": fact.citation.locator_kind,
                "locator_label": fact.citation.locator_label,
                "excerpt": fact.citation.excerpt,
                "role": fact.evidence_role,
                "fact_id": fact.fact_id,
            }
        )
    return rows


def claim(claim_id: str, text: str, value: str, facts) -> dict:
    return {
        "claim_id": claim_id,
        "text": text,
        "value": value,
        "facts": [fact.fact_id for fact in facts],
        "support": sorted({fact.citation.chunk_id for fact in facts}),
    }


def gold_alignment(claims: list[dict], question: dict) -> dict:
    """String-level alignment with gold; never a semantic correctness verdict."""

    answer = question["gold"].get("answer", "")
    statements = " ".join(
        item.get("statement", "") if isinstance(item, dict) else str(item)
        for item in question["gold"].get("required_facts", ())
    )
    haystack = answer + " " + statements
    present = [item["value"] for item in claims if item["value"] in haystack]
    absent = [item["value"] for item in claims if item["value"] not in haystack]
    return {
        "present_in_gold": present,
        "absent_from_gold": absent,
        "note": (
            "仅做字符串级对齐，用于定位；不构成语义正确性判定，"
            "语义仍需人工复核。"
        ),
    }


def build_report(
    question: dict,
    *,
    status: str,
    answer: str,
    claims: list[dict] | None = None,
    operators: list[dict] | None = None,
    facts=None,
    unresolved: list[str] | None = None,
    notes: str = "",
    facts_path: Path | str = DEFAULT_FACTS,
    command: str = "",
) -> dict:
    claims = claims or []
    operators = operators or []
    facts = facts or []
    return {
        "schema_version": REPORT_SCHEMA,
        "question_id": question["base_id"],
        "split": question.get("split", ""),
        "scenario": question.get("scenario", ""),
        "task_type": question.get("task_type", ""),
        "verdict_class": question.get("gold", {}).get("verdict_class", ""),
        "status": status,
        "answer": answer,
        "claims": claims,
        "operators": operators,
        "evidence": evidence_of(facts),
        "unresolved_conditions": unresolved or [],
        "recompute": {
            "command": command,
            "question_id": question["base_id"],
            "facts_sha256": facts_digest(facts_path),
            "facts_path": str(Path(facts_path)),
            "questions_sha256": questions_digest(question.get("split", "")),
            "corpus_snapshot": corpus_digest(),
        },
        "gold_alignment": gold_alignment(claims, question),
        "notes": notes,
    }


def unsupported_report(question: dict, reason: str, **kwargs) -> dict:
    return build_report(
        question,
        status="unsupported",
        answer="",
        unresolved=[reason],
        notes=reason,
        **kwargs,
    )


def not_evaluated_report(question: dict, reason: str, **kwargs) -> dict:
    return build_report(
        question,
        status="not_evaluated",
        answer="",
        unresolved=[reason],
        notes=reason,
        **kwargs,
    )


def write_report(path: str | Path, report: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )


def add_common_arguments(parser) -> None:
    parser.add_argument("--question", required=True, help="dev/val base_id")
    parser.add_argument("--facts", default=str(DEFAULT_FACTS))
    parser.add_argument("--out", default="", help="report path; empty prints JSON")
    parser.add_argument("--json", action="store_true", help="print the report")


def emit(report: dict, out: str) -> None:
    if out:
        write_report(out, report)
    print(json.dumps(report, ensure_ascii=False, indent=1))
