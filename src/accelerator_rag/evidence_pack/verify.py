"""Claim assembly and deterministic operator execution over a selected pack.

Only atoms in the pack can produce a claim.  Operators run on structured
values the pack actually contains; a refusal is preserved, never downgraded.
The output is a verifiable claim set, not a natural-language proof.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import re

from accelerator_rag.facts.schema import Fact, UNKNOWN
from accelerator_rag.verify.operators import run_operator

from .index import CorpusIndex, atom_entity_match
from .relations import relevant_atom_ids
from .schema import Atom, Needs, Pack, entity_in_text, normalize_key

_ROLE_ORDER = (
    "requirement",
    "design",
    "test_scope",
    "test_result",
    "acceptance",
    "value",
)
_ROLE_LABEL = {
    "requirement": "要求",
    "design": "设计",
    "test_scope": "测试范围",
    "test_result": "测试结果",
    "acceptance": "验收",
    "value": "证据",
}
_UNIT = re.compile(r"(?:%|μs|µs|us|ns|ms|s|V|A|mA|Hz|kHz|MHz|GHz|℃|°C|mm|cm|kg|kW|W|dB)")
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    value: str
    role: str
    revision_id: str
    atom_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    support: tuple[str, ...]
    anchor_hits: int = 0

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "value": self.value,
            "role": self.role,
            "revision_id": self.revision_id,
            "atom_ids": list(self.atom_ids),
            "fact_ids": list(self.fact_ids),
            "support": list(self.support),
            "anchor_hits": self.anchor_hits,
        }


@dataclass
class Verification:
    status: str
    claims: list[Claim] = field(default_factory=list)
    operators: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    answer: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "claims": [claim.to_dict() for claim in self.claims],
            "operators": self.operators,
            "missing": list(self.missing),
            "answer": self.answer,
            "notes": self.notes,
        }


def _claim_id(payload: str) -> str:
    return "K" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _text(value: object) -> str:
    if isinstance(value, type(UNKNOWN)) or value is None:
        return ""
    return str(value).strip()


def _facts(index: CorpusIndex, atoms) -> tuple[Fact, ...]:
    seen: dict[str, Fact] = {}
    for atom in atoms:
        for fact_id in atom.fact_ids:
            fact = index.facts.facts.get(fact_id)
            if fact is not None:
                seen.setdefault(fact_id, fact)
    return tuple(seen[key] for key in sorted(seen))


def _claim_for_fact(fact: Fact, atom_ids: tuple[str, ...]) -> Claim:
    subject = _text(fact.subject.raw_id)
    attribute = _text(fact.attribute)
    value = _text(fact.raw_value)
    unit = _text(fact.unit)
    text = " ".join(
        part for part in (subject, attribute, "=", value) if part
    )
    if unit and unit not in value:
        text = f"{text} {unit}"
    payload = f"{fact.fact_id}\x1f{text}\x1f{fact.source_role}"
    return Claim(
        claim_id=_claim_id(payload),
        text=text.strip(),
        value=value,
        role=fact.source_role,
        revision_id=fact.revision_id,
        atom_ids=atom_ids,
        fact_ids=(fact.fact_id,),
        support=(fact.citation.chunk_id,),
    )


def _row_text(index: CorpusIndex, atom: Atom) -> tuple[str, str]:
    row = index.row_atoms.get(atom.atom_id)
    if row is None:
        cells = [
            cell.strip()
            for cell in atom.excerpt.strip().strip("|").split("|")
            if cell.strip()
        ]
        return " | ".join(cells), " | ".join(cells)
    pairs = [
        (header, value)
        for header, value in zip(row.headers, [value for _, value in row.cells])
        if value and value.strip()
    ]
    if not pairs:
        return atom.excerpt.strip(), atom.excerpt.strip()
    text = "；".join(f"{header}={value}" for header, value in pairs[:8])
    return text, "；".join(value for _, value in pairs[:8])


def _role_claims(
    index: CorpusIndex, pack: Pack, needs: Needs
) -> list[Claim]:
    claims: list[Claim] = []
    for atom in pack.atoms:
        if atom.locator_kind == "table_row" and not atom.fact_ids:
            if not atom.source_role:
                continue
            text, value = _row_text(index, atom)
            role = atom.source_role
            if role not in {
                "design_target",
                "test_plan",
                "test_result",
                "acceptance_conclusion",
            }:
                continue
            claims.append(
                Claim(
                    claim_id=_claim_id(f"{atom.atom_id}\x1f{text}"),
                    text=text,
                    value=value,
                    role=role,
                    revision_id=atom.revision_id,
                    atom_ids=(atom.atom_id,),
                    fact_ids=(),
                    support=(atom.chunk_id,),
                )
            )
    for fact in _facts(index, pack.atoms):
        role = fact.source_role
        if role in {
            "design_target",
            "test_plan",
            "test_result",
            "acceptance_conclusion",
        }:
            atom_ids = tuple(
                atom.atom_id
                for atom in pack.atoms
                if fact.fact_id in atom.fact_ids
            )
            claims.append(_claim_for_fact(fact, atom_ids))
    return claims


def _anchor_hits(
    claim: Claim, atoms: dict[str, Atom], anchors: dict[str, str]
) -> int:
    if not anchors:
        return 0
    text = normalize_key(claim.text)
    hits = 0
    for entity, kind in anchors.items():
        if entity_in_text(entity, text, kind):
            hits += 1
            continue
        if any(
            atom_entity_match(atoms[atom_id], entity, kind)
            for atom_id in claim.atom_ids
            if atom_id in atoms
        ):
            hits += 1
    return hits


def _value_claims(
    index: CorpusIndex, pack: Pack, needs: Needs, query: str
) -> list[Claim]:
    relevant = relevant_atom_ids(pack.atoms, needs, query, index)
    anchors = {
        item.normalized: item.kind
        for item in needs.entities
        if item.kind in {"device", "cabinet", "port"}
    }
    claims: list[Claim] = []
    for atom in pack.atoms:
        if atom.atom_id not in relevant:
            continue
        if anchors and not any(
            atom_entity_match(atom, entity, kind)
            for entity, kind in anchors.items()
        ):
            continue
        facts = tuple(
            index.facts.facts[fact_id]
            for fact_id in atom.fact_ids
            if fact_id in index.facts.facts
        )
        if facts:
            for fact in facts:
                if _text(fact.raw_value):
                    claims.append(
                        _claim_for_fact(fact, (atom.atom_id,))
                    )
            continue
        if atom.locator_kind == "table_row":
            text, value = _row_text(index, atom)
            if not text:
                continue
            claims.append(
                Claim(
                    claim_id=_claim_id(f"{atom.atom_id}\x1f{text}"),
                    text=text,
                    value=value,
                    role=atom.source_role or "value",
                    revision_id=atom.revision_id,
                    atom_ids=(atom.atom_id,),
                    fact_ids=(),
                    support=(atom.chunk_id,),
                )
            )
    return claims


def _version_claims(
    index: CorpusIndex,
    pack: Pack,
    needs: Needs,
    alignment: tuple[dict, ...],
    operators: list[dict],
) -> list[Claim]:
    if not needs.version_pair:
        return []
    pairs = [
        item
        for item in alignment
        if item["left_atom_id"] in {atom.atom_id for atom in pack.atoms}
        and item["right_atom_id"] in {atom.atom_id for atom in pack.atoms}
    ]
    if not pairs:
        return []
    left_items, right_items = [], []
    pair_map = {}
    for position, pair in enumerate(pairs, 1):
        left = pack.atom(pair["left_atom_id"])
        right = pack.atom(pair["right_atom_id"])
        item_id = f"P{position}"
        pair_map[item_id] = (left, right)
        left_items.append({"item_id": item_id, "text": left.excerpt})
        right_items.append({"item_id": item_id, "text": right.excerpt})
    request = {
        "left": {"revision_id": needs.version_pair[0], "items": left_items},
        "right": {"revision_id": needs.version_pair[1], "items": right_items},
        "normalizer": "whitespace",
    }
    response = run_operator("version_diff", request)
    operators.append({"op": "version_diff", "request": request, "response": response})
    if response.get("status") != "ok":
        return []
    value = response.get("value", {})
    claims: list[Claim] = []
    for item in value.get("changed", [])[:4]:
        left, right = pair_map[item["item_id"]]
        text = (
            f"第一版：{item['left_text'][:90]}；"
            f"第二版：{item['right_text'][:90]}"
        )
        claims.append(
            Claim(
                claim_id=_claim_id(f"changed\x1f{item['item_id']}\x1f{text}"),
                text=text,
                value="changed",
                role="version_diff",
                revision_id=needs.version_pair[1],
                atom_ids=(left.atom_id, right.atom_id),
                fact_ids=(),
                support=(left.chunk_id, right.chunk_id),
            )
        )
    for item in value.get("same", [])[:2]:
        left, right = pair_map[item["item_id"]]
        text = f"两版相同：{item['left_text'][:90]}"
        claims.append(
            Claim(
                claim_id=_claim_id(f"same\x1f{item['item_id']}\x1f{text}"),
                text=text,
                value="same",
                role="version_same",
                revision_id=needs.version_pair[1],
                atom_ids=(left.atom_id, right.atom_id),
                fact_ids=(),
                support=(left.chunk_id, right.chunk_id),
            )
        )
    for item in value.get("added", [])[:2]:
        left, right = pair_map[item["item_id"]]
        text = f"仅第二版：{item['text'][:100]}"
        claims.append(
            Claim(
                claim_id=_claim_id(f"added\x1f{item['item_id']}\x1f{text}"),
                text=text,
                value="added",
                role="version_added",
                revision_id=needs.version_pair[1],
                atom_ids=(right.atom_id,),
                fact_ids=(),
                support=(right.chunk_id,),
            )
        )
    for item in value.get("removed", [])[:2]:
        left, right = pair_map[item["item_id"]]
        text = f"仅第一版：{item['text'][:100]}"
        claims.append(
            Claim(
                claim_id=_claim_id(f"removed\x1f{item['item_id']}\x1f{text}"),
                text=text,
                value="removed",
                role="version_removed",
                revision_id=needs.version_pair[1],
                atom_ids=(left.atom_id,),
                fact_ids=(),
                support=(left.chunk_id,),
            )
        )
    return claims


def _attribute_related(left: str, right: str) -> bool:
    left, right = normalize_key(left), normalize_key(right)
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    grams_left = {left[index : index + 2] for index in range(max(0, len(left) - 1))}
    grams_right = {right[index : index + 2] for index in range(max(0, len(right) - 1))}
    if not grams_left or not grams_right:
        return False
    return len(grams_left & grams_right) / len(grams_left | grams_right) >= 0.25


def _subject_related(left: str, right: str) -> bool:
    first, second = normalize_key(left), normalize_key(right)
    if not first or not second:
        return False
    if first == second or first in second or second in first:
        return True
    first_grams = {
        first[index : index + 2] for index in range(max(0, len(first) - 1))
    }
    second_grams = {
        second[index : index + 2] for index in range(max(0, len(second) - 1))
    }
    if not first_grams or not second_grams:
        return False
    return len(first_grams & second_grams) / len(first_grams | second_grams) >= 0.4


def _boundary_claims(
    index: CorpusIndex,
    pack: Pack,
    needs: Needs,
    operators: list[dict],
) -> tuple[list[Claim], list[str]]:
    facts = _facts(index, pack.atoms)
    requirements = [
        fact
        for fact in facts
        if fact.source_role in {"design_target", "test_plan"}
        and fact.number is not UNKNOWN
        and _text(fact.unit)
    ]
    tests = [
        fact
        for fact in facts
        if fact.source_role == "test_result"
        and fact.number is not UNKNOWN
        and _text(fact.unit)
    ]
    claims: list[Claim] = []
    missing: list[str] = []
    used: set[str] = set()
    for requirement in requirements:
        for test in tests:
            if test.fact_id in used:
                continue
            if not _attribute_related(
                _text(requirement.attribute), _text(test.attribute)
            ):
                continue
            if not _subject_related(
                _text(requirement.subject.raw_id),
                _text(test.subject.raw_id),
            ):
                continue
            req_scope = requirement.subject.scope
            test_scope = test.subject.scope
            if (
                not isinstance(req_scope, type(UNKNOWN))
                and not isinstance(test_scope, type(UNKNOWN))
                and normalize_key(str(req_scope)) != normalize_key(str(test_scope))
            ):
                continue
            used.add(test.fact_id)
            op = {
                "le": "le",
                "lt": "le",
                "ge": "ge",
                "gt": "ge",
            }.get(requirement.comparator)
            if op is None:
                continue
            request = {
                "value": test.number,
                "unit": _text(test.unit),
                "op": op,
                "bound": requirement.number,
                "bound_unit": _text(requirement.unit),
            }
            response = run_operator("boundary_compare", request)
            operators.append(
                {"op": "boundary_compare", "request": request, "response": response}
            )
            if response.get("status") != "ok":
                missing.append(
                    "边界比较无法执行：" + response.get("refusal", {}).get("code", "")
                )
                continue
            value = response.get("value", {})
            result = value.get("result")
            text = (
                f"测试值 {test.number:g}{_text(test.unit)} "
                f"对要求 {requirement.number:g}{_text(requirement.unit)} "
                f"比较：{'满足' if result else '不满足'}"
            )
            atom_ids = tuple(
                atom.atom_id
                for atom in pack.atoms
                if requirement.fact_id in atom.fact_ids
                or test.fact_id in atom.fact_ids
            )
            claims.append(
                Claim(
                    claim_id=_claim_id(
                        f"boundary\x1f{requirement.fact_id}\x1f{test.fact_id}"
                    ),
                    text=text,
                    value=str(result).lower(),
                    role="boundary",
                    revision_id=test.revision_id,
                    atom_ids=atom_ids,
                    fact_ids=(requirement.fact_id, test.fact_id),
                    support=(
                        requirement.citation.chunk_id,
                        test.citation.chunk_id,
                    ),
                )
            )
            break
    return claims, missing


def _enumeration_claims(
    index: CorpusIndex,
    pack: Pack,
    needs: Needs,
    enumeration: dict,
    operators: list[dict],
) -> list[Claim]:
    claims: list[Claim] = []
    selected = {atom.atom_id for atom in pack.atoms}
    for block, summary in sorted(enumeration.items()):
        if not set(summary.get("atom_ids", ())) <= selected:
            continue
        rows = []
        for atom in pack.atoms:
            if atom.table_block_id == block and atom.locator_kind == "table_row":
                row = index.row_atoms.get(atom.atom_id)
                if row is not None:
                    rows.append(row)
        if not rows:
            continue
        rows.sort(key=lambda row: (row.chunk_id, row.row_number))
        keys = []
        for row in rows:
            values = [value.strip() for _, value in row.cells if value.strip()]
            if values:
                keys.append(values[0])
        target_rows = [
            row for row in index.rows if row.table_block_id == block
        ]
        target_keys = []
        for row in target_rows:
            values = [value.strip() for _, value in row.cells if value.strip()]
            if values:
                target_keys.append(values[0])
        if keys and target_keys:
            request = {
                "observed": keys,
                "expected": sorted(set(target_keys)),
                "universe": sorted(set(target_keys)),
            }
            response = run_operator("set_enumeration", request)
            operators.append(
                {"op": "set_enumeration", "request": request, "response": response}
            )
        text = "，".join(
            " | ".join(value.strip() for _, value in row.cells if value.strip())
            for row in rows[:8]
        )
        claims.append(
            Claim(
                claim_id=_claim_id(f"enumeration\x1f{block}\x1f{text}"),
                text=f"完整枚举（{len(rows)} 行）：{text}",
                value=str(len(rows)),
                role="enumeration",
                revision_id=rows[0].revision_id,
                atom_ids=tuple(
                    atom.atom_id
                    for atom in pack.atoms
                    if atom.table_block_id == block
                ),
                fact_ids=(),
                support=tuple(sorted({row.chunk_id for row in rows})),
            )
        )
    return claims


def verify(
    index: CorpusIndex,
    pack: Pack,
    needs: Needs,
    question: dict,
    *,
    alignment: tuple[dict, ...] = (),
    enumeration: dict | None = None,
    run_all: bool = False,
) -> Verification:
    """Run deterministic operators over the pack.

    ``run_all`` is the phase-4 mode: operators run without consulting the
    benchmark's ``verdict_class``, so a method never learns whether the
    question is deterministic.  The default keeps phase-3 behaviour.
    """

    verdict = question.get("gold", {}).get("verdict_class", "")
    if not run_all and verdict != "deterministic":
        return Verification(
            status="not_evaluated",
            answer="",
            notes=(
                f"verdict_class={verdict or 'unknown'}；阶段三只对 deterministic "
                "题输出主张，rubric/human 不作正确性依据"
            ),
        )
    enumeration = enumeration or {}
    operators: list[dict] = []
    claims = _role_claims(index, pack, needs)
    claims.extend(
        _value_claims(index, pack, needs, question["query"])
    )
    claims.extend(_version_claims(index, pack, needs, alignment, operators))
    boundary, boundary_missing = _boundary_claims(index, pack, needs, operators)
    claims.extend(boundary)
    claims.extend(
        _enumeration_claims(index, pack, needs, enumeration, operators)
    )
    deduped: dict[tuple, Claim] = {}
    for claim in claims:
        key = (claim.text, claim.revision_id)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = claim
        elif existing.role in {"value", ""} and claim.role not in {"value", ""}:
            deduped[key] = claim
    claims = list(deduped.values())
    atoms_by_id = {atom.atom_id: atom for atom in pack.atoms}
    anchors = {
        item.normalized: item.kind
        for item in needs.entities
        if item.kind in {"device", "cabinet", "port"}
    }
    claims = [
        replace(
            claim,
            anchor_hits=_anchor_hits(claim, atoms_by_id, anchors),
        )
        for claim in claims
    ]
    claims.sort(
        key=lambda claim: (
            -claim.anchor_hits,
            _ROLE_ORDER.index(claim.role)
            if claim.role in _ROLE_ORDER
            else 99,
            claim.claim_id,
        )
    )
    coherence = max((claim.anchor_hits for claim in claims), default=0)
    missing = [
        f"{item.name}: {item.missing}"
        for item in pack.coverage
        if item.required and not item.satisfied
    ]
    missing.extend(boundary_missing)
    if pack.unresolved:
        missing.extend(pack.unresolved)
    if anchors and needs.route == "exact_record" and coherence < len(anchors):
        missing.append(
            "没有单条证据同时覆盖全部对象与范围（当前最多覆盖 "
            f"{coherence}/{len(anchors)} 个锚点）"
        )
    limit = 5 if needs.route == "exact_record" else 10
    claims = claims[:limit]
    affecting = [
        conflict
        for conflict in pack.conflicts
        if conflict.resolution in {"affects_target", "unresolved"}
    ]
    if any(
        conflict.resolution == "unresolved" for conflict in pack.conflicts
    ):
        missing.extend(
            conflict.reason
            for conflict in pack.conflicts
            if conflict.resolution == "unresolved"
        )
    missing.extend(
        f"冲突（{conflict.kind}，{conflict.subject} / {conflict.attribute}）："
        f"{conflict.reason}"
        for conflict in affecting
    )
    if not claims and (missing or affecting):
        status = "insufficient"
    elif missing or pack.unresolved or any(
        conflict.resolution in {"affects_target", "unresolved"}
        for conflict in affecting
    ):
        status = "partial"
    elif claims:
        status = "answered"
    else:
        status = "insufficient"
    if status == "insufficient":
        answer = "当前证据无法判断：" + "；".join(
            dict.fromkeys(missing or ["没有可核查的证据"])
        )
    elif status == "partial":
        answer = "部分成立（存在未解决条件）：" + "；".join(
            claim.text for claim in claims[:8]
        )
        if missing:
            answer += "。未解决：" + "；".join(dict.fromkeys(missing))
    else:
        answer = "；".join(claim.text for claim in claims[:10]) + "。"
    return Verification(
        status=status,
        claims=claims,
        operators=operators,
        missing=list(dict.fromkeys(missing)),
        answer=answer,
        notes=(
            "主张只来自证据包内的原子与确定性算子；status 是机制状态，"
            "不是工程验收结论，也不构成语义正确性判定。"
        ),
    )
