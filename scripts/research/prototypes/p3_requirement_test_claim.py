"""Phase-2 W5c prototype: requirement--test claim verification.

One dev/val S3 question becomes a reviewable report built from sourced facts,
the frozen rc.3 tables and the six deterministic operators.  The prototype
never calls a model and never fills a number from general knowledge: every
reported value is bound to a ``fact_id`` plus a chunk, or (where the fact
layer has a documented gap) to a verbatim corpus chunk and an explicit note.

Usage:
  python3 scripts/research/prototypes/p3_requirement_test_claim.py \
      --question S3-DEV-VAC-009 --out /tmp/p3.json
  python3 scripts/research/prototypes/p3_requirement_test_claim.py \
      --all --split dev
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[3]
for _entry in (ROOT / "src", ROOT / "scripts" / "research" / "prototypes"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

import common  # noqa: E402
from accelerator_rag.facts.corpus import (  # noqa: E402
    markdown_tables,
    verbatim_row_line,
)
from accelerator_rag.facts.schema import UNKNOWN  # noqa: E402

DEFAULT_FACTS = common.DEFAULT_FACTS
SPLITS = ("dev", "val")

STATUS_BY_VERDICT = {
    "成立": "answered",
    "不成立": "answered",
    "有条件成立": "partial",
    "当前证据无法判断": "insufficient",
    "超出能力": "unsupported",
}

TASK_TYPES = (
    "requirement_test_match",
    "scope_mismatch",
    "design_test_conflict",
    "acceptance_gap",
    "verdict_check",
)

# Characters that end a clause in the benchmark questions.
_CLAUSE_END = "，。；;!?？、"


# ---------------------------------------------------------------------------
# research verdict -> report status (pure, unit-tested)
# ---------------------------------------------------------------------------


def verdict_to_status(verdict: str) -> str:
    """Map a research verdict label to the DESIGN §6 report status."""

    try:
        return STATUS_BY_VERDICT[verdict]
    except KeyError:
        raise ValueError(f"unknown research verdict: {verdict!r}") from None


# ---------------------------------------------------------------------------
# text and fact helpers
# ---------------------------------------------------------------------------


def normalize_text(value: str | None) -> str:
    return unicodedata.normalize("NFKC", value or "").casefold().strip()


def compact_text(value: str | None) -> str:
    return re.sub(r"\s+", "", normalize_text(value))


def fact_text(fact, name: str) -> str:
    value = getattr(fact, name)
    return "" if value is UNKNOWN else str(value)


def fact_extra(fact) -> dict[str, str]:
    return dict(fact.extra)


def fact_conditions(fact) -> dict[str, str]:
    return {condition.kind: condition.raw for condition in fact.conditions}


def dedupe_facts(facts) -> list:
    seen: set[str] = set()
    rows = []
    for fact in facts:
        if fact.fact_id in seen:
            continue
        seen.add(fact.fact_id)
        rows.append(fact)
    return rows


_QUANTITY = re.compile(
    r"(小于等于|大于等于|不小于|不大于|小于|大于|不超过|不低于|以上|以下|以内"
    r"|≤|≥|<|>|=)?\s*"
    r"(\d+(?:\.\d+)?)\s*"
    r"(μs|us|ns|ms|s|Hz|kHz|MHz|GHz|V|mV|A|mA|%|℃|°C|Pa)?"
)
_OP_WORDS = {
    "小于等于": "le",
    "≤": "le",
    "不大于": "le",
    "不超过": "le",
    "以下": "le",
    "以内": "le",
    "大于等于": "ge",
    "≥": "ge",
    "不小于": "ge",
    "不低于": "ge",
    "以上": "ge",
    "小于": "lt",
    "<": "lt",
    "大于": "gt",
    ">": "gt",
    "=": "eq",
}


def parse_quantity(text: str):
    """Parse a printed quantity into ``(comparator, Decimal, unit)``.

    Only explicit printed comparisons survive; a bare table assignment stays
    ``eq``.  This parser never invents a unit.
    """

    normalized = unicodedata.normalize("NFKC", text or "")
    match = _QUANTITY.search(normalized)
    if match is None:
        return None
    op = _OP_WORDS.get(match.group(1) or "", "eq")
    tail = normalized[match.end() :]
    if "以上" in normalized[match.start() :] and re.search(
        r"\d+(?:\.\d+)?\s*\S*以上", normalized
    ):
        op = "ge"
    if "以下" in normalized and re.search(r"\d+(?:\.\d+)?\s*\S*以下", normalized):
        op = "le"
    if "以内" in normalized and re.search(r"\d+(?:\.\d+)?\s*\S*以内", normalized):
        op = "le"
    del tail
    return op, Decimal(match.group(2)), match.group(3) or ""


def fact_quantity(fact):
    """The numeric quantity a fact records, or ``None``."""

    if fact.number is UNKNOWN:
        return None
    unit = fact_text(fact, "unit")
    if not unit:
        return None
    return fact.comparator, Decimal(str(fact.number)), unit


_MINIMUM_WORDS = ("不低于", "不小于", "达到", "以上", "至少", "满足", ">=")
_MAXIMUM_WORDS = ("不超过", "不大于", "最多", "以下", "以内", "<=")
_UPPER_WORDS = ("小于", "低于")
_LOWER_WORDS = ("大于", "高于")


def requirement_op(fact) -> tuple[str, str]:
    """Infer the comparison direction of a requirement fact.

    ``eq`` on a table cell means "the cell assigns the target value", not
    "the measurement must equal it".  Such a bare number is a minimum
    requirement (``ge``) and the basis is recorded explicitly.
    """

    comparator = fact.comparator
    if comparator in ("lt", "le", "gt", "ge"):
        return comparator, "explicit_comparator"
    raw = fact_text(fact, "raw_value")
    extra = fact_extra(fact)
    if extra.get("comparator_basis") == "table_cell_assignment":
        return "ge", "minimum_requirement"
    if any(word in raw for word in _MINIMUM_WORDS):
        return "ge", "explicit_text"
    if any(word in raw for word in _MAXIMUM_WORDS):
        return "le", "explicit_text"
    if any(word in raw for word in _UPPER_WORDS):
        return "lt", "explicit_text"
    if any(word in raw for word in _LOWER_WORDS):
        return "gt", "explicit_text"
    if comparator == "eq":
        return "ge", "minimum_requirement"
    if comparator == "range":
        return "range", "explicit_range"
    return "ge", "minimum_requirement"


def bind_value(
    value: str,
    fact=None,
    *,
    chunk=None,
    chunk_id: str = "",
    locator_label: str = "",
    note: str = "",
) -> dict:
    """Bind one reported value to a fact id and a chunk (or a chunk gap)."""

    binding = {"value": str(value)}
    if fact is not None:
        binding.update(
            fact_id=fact.fact_id,
            chunk_id=fact.citation.chunk_id,
            locator_label=fact.citation.locator_label,
        )
    else:
        binding.update(
            fact_id="",
            chunk_id=chunk_id or (chunk.chunk_id if chunk else ""),
            locator_label=locator_label
            or (chunk.position_label if chunk else ""),
        )
    if note:
        binding["note"] = note
    return binding


def claim_with_bindings(
    claim_id: str,
    text: str,
    value: str,
    facts=(),
    *,
    bindings=(),
    table_rows=(),
) -> dict:
    item = common.claim(claim_id, text, value, list(facts))
    if bindings:
        item["value_bindings"] = list(bindings)
    if table_rows:
        item["table_rows"] = list(table_rows)
    return item


# ---------------------------------------------------------------------------
# deterministic operator wrappers
# ---------------------------------------------------------------------------


def run_op(name: str, request: dict, records: list[dict]) -> dict:
    response = common.operator(name, request)
    records.append({"op": name, "request": request, "response": response})
    return response


def converted_number(
    number: Decimal, from_unit: str, to_unit: str, records: list[dict]
) -> Decimal | None:
    response = run_op(
        "unit_convert",
        {"value": str(number), "from": from_unit, "to": to_unit},
        records,
    )
    if response["status"] != "ok":
        return None
    return Decimal(response["value"]["value"])


def compare_boundary(
    number: Decimal,
    unit: str,
    op: str,
    bound: Decimal,
    bound_unit: str,
    records: list[dict],
):
    response = run_op(
        "boundary_compare",
        {
            "value": str(number),
            "unit": unit,
            "op": op,
            "bound": str(bound),
            "bound_unit": bound_unit,
        },
        records,
    )
    if response["status"] != "ok":
        return None
    return bool(response["value"]["result"])


def bound_implies(
    test_number: Decimal,
    test_op: str,
    test_unit: str,
    req_number: Decimal,
    req_op: str,
    req_unit: str,
    records: list[dict],
):
    """True when the test statement guarantees the requirement statement.

    ``test_op``/``req_op`` may be ``lt/le/gt/ge/eq``.  The numeric boundary is
    compared with ``unit_convert`` + ``boundary_compare``; equality strictness
    follows interval inclusion (a ``<= C`` test cannot imply ``< C`` when the
    boundaries coincide).
    """

    converted = converted_number(test_number, test_unit, req_unit, records)
    if converted is None:
        return None, None
    bound = Decimal(str(req_number))
    if req_op in ("lt", "le"):
        if test_op not in ("lt", "le", "eq"):
            return None, converted
        strict = req_op == "lt" and test_op in ("le", "eq")
    elif req_op in ("gt", "ge"):
        if test_op not in ("gt", "ge", "eq"):
            return None, converted
        strict = req_op == "gt" and test_op in ("ge", "eq")
    elif req_op == "eq":
        if test_op != "eq":
            return None, converted
        strict = False
        result = compare_boundary(
            converted, req_unit, "eq", bound, req_unit, records
        )
        return result, converted
    else:
        return None, converted

    if req_op in ("lt", "le"):
        op = "lt" if strict else "le"
    else:
        op = "gt" if strict else "ge"
    result = compare_boundary(converted, req_unit, op, bound, req_unit, records)
    return result, converted


def same_bound(first, second, records: list[dict]) -> bool:
    """Whether two ``(op, Decimal, unit)`` quantities state the same bound."""

    if first is None or second is None or first[0] != second[0]:
        return False
    converted = converted_number(first[1], first[2], second[2], records)
    if converted is None:
        return False
    return converted == Decimal(str(second[1]))


# ---------------------------------------------------------------------------
# table views over the frozen corpus
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RowView:
    number: int
    cells: tuple[str, ...]
    line: str


@dataclass(frozen=True)
class TableView:
    revision_id: str
    chunk_id: str
    block_id: str
    label_prefix: str
    header: tuple[str, ...]
    rows: tuple[RowView, ...]


def scope_tables(scope, revision_ids=None) -> list[TableView]:
    """All markdown / TableRecord tables of the selected revisions."""

    wanted = set(revision_ids) if revision_ids else None
    texts = scope.chunk_text()
    tables: list[TableView] = []
    for revision_id in sorted(scope.revisions):
        if wanted is not None and revision_id not in wanted:
            continue
        for chunk in scope.chunks_by_revision.get(revision_id, ()):
            for table in markdown_tables(chunk, revision_id):
                rows = tuple(
                    RowView(row.row_number, tuple(row.cells), row.line)
                    for row in table.rows
                )
                tables.append(
                    TableView(
                        revision_id,
                        chunk.chunk_id,
                        table.block_id,
                        table.label_prefix,
                        tuple(table.header),
                        rows,
                    )
                )
        by_block: dict[str, list] = {}
        for record in scope.records_by_revision.get(revision_id, ()):
            by_block.setdefault(record.table_block_id, []).append(record)
        block_to_chunk = scope.block_to_chunk(revision_id)
        for block_id, records in sorted(by_block.items()):
            records = sorted(records, key=lambda item: item.row_number)
            chunk_id = records[0].chunk_id or block_to_chunk.get(block_id, "")
            rows = tuple(
                RowView(
                    record.row_number,
                    tuple(value for _, value in record.cells),
                    verbatim_row_line(record, texts.get(chunk_id, ""))
                    or record.row_text,
                )
                for record in records
            )
            tables.append(
                TableView(
                    revision_id,
                    chunk_id,
                    block_id,
                    block_id,
                    tuple(records[0].headers),
                    rows,
                )
            )
    return tables


def normalize_rows(table: TableView) -> tuple[RowView, ...]:
    """Pad merged first-column cells without inventing values.

    A docx/pptx row that repeats the group column only in its first line loses
    that cell in the markdown parser.  The group is inherited from the previous
    row **only** when the first cell is not itself a repeated group value.
    """

    width = len(table.header)
    if width == 0:
        return ()
    first_column = [row.cells[0] if row.cells else "" for row in table.rows]
    counts: dict[str, int] = {}
    for value in first_column:
        counts[value] = counts.get(value, 0) + 1
    group_values = {value for value, count in counts.items() if value and count > 1}
    normalized: list[RowView] = []
    previous_group = ""
    for row in table.rows:
        cells = tuple(row.cells)
        if len(cells) == width - 1:
            first = cells[0] if cells else ""
            if first and first in group_values:
                previous_group = first
            elif previous_group:
                cells = (previous_group,) + cells
        elif len(cells) == width and cells:
            previous_group = cells[0]
        normalized.append(RowView(row.number, cells, row.line))
    return tuple(normalized)


def column_indexes(header: tuple[str, ...], tokens: tuple[str, ...]) -> tuple[int, ...]:
    return tuple(
        index
        for index, name in enumerate(header)
        if any(token in name for token in tokens)
    )


RESULT_TOKENS = ("测试结果", "实测结果", "实测值", "实测指标", "结果")
CONCLUSION_TOKENS = ("结论", "符合性")


def result_columns(table: TableView) -> tuple[tuple[int, ...], tuple[int, ...]]:
    return (
        column_indexes(table.header, RESULT_TOKENS),
        column_indexes(table.header, CONCLUSION_TOKENS),
    )


def table_gaps(table: TableView) -> tuple[dict, ...]:
    result_idx, conclusion_idx = result_columns(table)
    if not result_idx and not conclusion_idx:
        return ()
    gaps: list[dict] = []
    for row in normalize_rows(table):
        for index in result_idx + conclusion_idx:
            if index >= len(row.cells):
                gaps.append(
                    {
                        "row": row,
                        "column": index,
                        "header": table.header[index]
                        if index < len(table.header)
                        else "",
                        "reason": "missing_column",
                    }
                )
                continue
            if not row.cells[index].strip():
                gaps.append(
                    {
                        "row": row,
                        "column": index,
                        "header": table.header[index],
                        "reason": "empty_cell",
                    }
                )
    return tuple(gaps)


def table_ref(table: TableView, row: RowView) -> dict:
    return {
        "table_block_id": table.block_id,
        "row_number": row.number,
        "chunk_id": table.chunk_id,
        "locator_label": f"{table.label_prefix}r{row.number}",
    }


def row_evidence(
    table: TableView, row: RowView, role: str = "fact_support"
) -> dict:
    return {
        "chunk_id": table.chunk_id,
        "revision_id": table.revision_id,
        "locator_kind": "table_row",
        "locator_label": f"{table.label_prefix}r{row.number}",
        "excerpt": row.line,
        "role": role,
        "fact_id": "",
        "table_block_id": table.block_id,
        "row_number": row.number,
    }


def header_evidence(table: TableView, role: str = "header") -> dict:
    return {
        "chunk_id": table.chunk_id,
        "revision_id": table.revision_id,
        "locator_kind": "table_header",
        "locator_label": f"{table.label_prefix}h",
        "excerpt": " | ".join(table.header),
        "role": role,
        "fact_id": "",
        "table_block_id": table.block_id,
        "row_number": 0,
    }


def _best_line(chunks, needle: str):
    """``(chunk, line)`` for ``needle``; a line starting with it wins."""

    fallback = (None, "")
    for chunk in chunks:
        for line in chunk.text.splitlines():
            text = line.strip()
            if not text or needle not in text:
                continue
            if text.startswith(needle):
                return chunk, text
            if fallback[0] is None:
                fallback = (chunk, text)
    return fallback


def _set_line(chunks, items):
    """The sentence that states a whole mode set, preferring "支持…切换"."""

    fallback = (None, "")
    for chunk in chunks:
        for line in chunk.text.splitlines():
            text = line.strip()
            if not text or not all(item in text for item in items):
                continue
            if "7种" in text:
                if fallback[0] is None:
                    fallback = (chunk, text)
                continue
            if "支持" in text and "切换" in text:
                return chunk, text
            if fallback[0] is None or "7种" in fallback[1]:
                fallback = (chunk, text)
    return fallback


def _verbatim_line(chunk, needle: str) -> str:
    """The exact printed line that carries ``needle`` (empty when absent).

    A line that *starts* with the needle wins: mode names open their own
    paragraph ("运行模式。装置各段…"), while a passing mention elsewhere must
    not stand in for that paragraph.
    """

    fallback = ""
    for line in chunk.text.splitlines():
        text = line.strip()
        if not text or needle not in text:
            continue
        if text.startswith(needle):
            return text
        if not fallback:
            fallback = text
    return fallback


def chunk_evidence(chunk, excerpt: str, role: str = "fact_support") -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "revision_id": chunk.document_id,
        "locator_kind": chunk.position_kind or "paragraph",
        "locator_label": chunk.position_label,
        "excerpt": excerpt,
        "role": role,
        "fact_id": "",
    }


_MEASURE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|μs|us|ns|ms|s|Hz|kHz|MHz|GHz|V|mV|A|mA"
    r"|℃|°C|Pa|kPa|MPa|m|cm|mm|km)\b",
    re.IGNORECASE,
)


def unique_cell_text(cells) -> str:
    seen: list[str] = []
    for cell in cells:
        text = cell.strip()
        if text and text not in seen:
            seen.append(text)
    return " ".join(seen)


def has_measured_content(text: str) -> bool:
    cleaned = text
    for phrase in ("主要技术指标", "实测结果", "实测值", "符合性", "结论"):
        cleaned = cleaned.replace(phrase, "")
    if _MEASURE.search(cleaned):
        return True
    return any(
        word in cleaned for word in ("合格", "符合", "通过", "满足")
    )


# ---------------------------------------------------------------------------
# revision selection by document title
# ---------------------------------------------------------------------------


def title_of(scope, revision_id: str) -> str:
    return scope.revisions.get(revision_id, {}).get("title", "")


def revisions_with_title(
    scope, keywords: tuple[str, ...], exclude: tuple[str, ...] = ()
) -> list[str]:
    return [
        revision_id
        for revision_id, meta in scope.revisions.items()
        if all(key in meta.get("title", "") for key in keywords)
        and not any(item in meta.get("title", "") for item in exclude)
    ]


def chunks_for(scope, revision_ids):
    for revision_id in revision_ids:
        for chunk in scope.chunks_by_revision.get(revision_id, ()):
            yield chunk


# ---------------------------------------------------------------------------
# task 1: requirement -- test match
# ---------------------------------------------------------------------------

_ENDPOINTS = (
    ("节点间", "节点间"),
    ("站点间", "节点间"),
    ("单节点", "单节点"),
    ("站点内", "单节点"),
)

_PLATFORM_STOPWORDS = {
    "s",
    "us",
    "ns",
    "ms",
    "hz",
    "khz",
    "mhz",
    "ghz",
    "kw",
    "v",
    "mv",
    "a",
    "ma",
    "pa",
}


def endpoint_of(text: str) -> str:
    for token, canonical in _ENDPOINTS:
        if token in text:
            return canonical
    return ""


def platform_tokens(query: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9\-]*", query):
        if len(raw) < 2 or raw.casefold() in _PLATFORM_STOPWORDS:
            continue
        if raw not in tokens:
            tokens.append(raw)
    return tuple(tokens)


def fact_platform_text(fact) -> str:
    section = fact_extra(fact).get("section_path", "")
    innermost = section.split(">")[-1] if section else ""
    return f"{fact.subject.raw_id} {innermost}"


def matches_platform(fact, tokens: tuple[str, ...]) -> bool:
    if not tokens:
        return True
    haystack = normalize_text(fact_platform_text(fact))
    return all(normalize_text(token) in haystack for token in tokens)


def summary_averages(scope, item_names, family=()) -> list[dict]:
    """Item-bound averages written in the development summary.

    The fact layer records many of these as document-level ``平均响应时间``
    facts without an object, so the prototype also reads the verbatim sentence
    and marks the missing fact binding explicitly.
    """

    revision_ids = revisions_with_title(scope, ("研制总结",))
    found: list[dict] = []
    for chunk in chunks_for(scope, revision_ids):
        for name in item_names:
            parts = [part for part in re.split(r"[\s\-]+", name) if part]
            if not parts:
                continue
            pattern = r"[\s\-]*".join(re.escape(part) for part in parts)
            match = re.search(
                pattern
                + r"平均响应时间为\s*(\d+(?:\.\d+)?)\s*"
                r"(ns|μs|us|ms|s)",
                chunk.text,
            )
            if match is None:
                continue
            line = next(
                (
                    line
                    for line in chunk.text.splitlines()
                    if match.group(0) in line
                ),
                match.group(0),
            )
            number = Decimal(match.group(1))
            unit = match.group(2)
            corroborating = [
                fact
                for fact in family
                if fact.number is not UNKNOWN
                and Decimal(str(fact.number)) == number
                and normalize_text(fact_text(fact, "unit"))
                == normalize_text(unit)
                and fact_text(fact, "attribute") == "平均响应时间"
            ]
            found.append(
                {
                    "item": name,
                    "value": match.group(1),
                    "unit": unit,
                    "chunk": chunk,
                    "excerpt": line.strip(),
                    "facts": corroborating,
                }
            )
    return found


def requirement_test_match(question, facts, scope) -> dict:
    query = question["query"]
    family = common.facts_for_question(facts, question)
    endpoint = endpoint_of(query)
    records: list[dict] = []
    unresolved: list[str] = []

    requirements = [
        fact
        for fact in family
        if fact.layer == "parameter"
        and fact.source_role == "design_target"
        and endpoint
        and endpoint in fact_text(fact, "attribute")
        and fact_quantity(fact) is not None
    ]
    if not requirements:
        requirements = [
            fact
            for fact in family
            if fact.layer == "parameter"
            and fact.source_role == "historical_record"
            and "设计报告" in title_of(scope, fact.revision_id)
            and endpoint
            and endpoint in fact_text(fact, "attribute")
            and fact_quantity(fact) is not None
        ]
    requirements = dedupe_facts(requirements)
    if not requirements:
        return {
            "status": verdict_to_status("当前证据无法判断"),
            "research_label": "当前证据无法判断",
            "task_kind": "requirement_test_match.no_requirement",
            "answer": "未在事实层找到与题干测量端点一致的设计要求数值，无法核验。",
            "unresolved": [f"测量端点={endpoint or '未识别'}"],
            "notes": "要求侧事实缺失；不据常识补数值。",
        }

    requirements.sort(key=lambda fact: 0 if fact.subject.kind == "test_item" else 1)
    primary = requirements[0]
    requirement_quantity = fact_quantity(primary)

    tests = []
    for fact in family:
        if fact.layer != "process" or fact.fact_type != "test_scope":
            continue
        if "conclusion" not in fact_extra(fact):
            continue
        quantity = fact_quantity(fact)
        if quantity is None or not matches_platform(fact, platform_tokens(query)):
            continue
        criterion = parse_quantity(fact_extra(fact).get("acceptance_criterion", ""))
        if same_bound(criterion, requirement_quantity, records):
            tests.append(fact)
    if not tests:
        tests = [
            fact
            for fact in family
            if fact.layer == "parameter"
            and fact.source_role == "test_result"
            and fact.subject.kind == "test_item"
            and fact_quantity(fact) is not None
            and matches_platform(fact, platform_tokens(query))
            and endpoint in fact_text(fact, "attribute")
        ]
    tests = dedupe_facts(tests)
    if not tests:
        return {
            "status": verdict_to_status("当前证据无法判断"),
            "research_label": "当前证据无法判断",
            "task_kind": "requirement_test_match.no_test",
            "answer": "找到设计要求，但没有找到同测量端点的测试结果事实。",
            "unresolved": [
                f"要求对象={primary.subject.raw_id}",
                f"测量端点={endpoint}",
                "测试侧对象/条件未对齐",
            ],
            "notes": "缺口是测试侧事实，不是设备不合格。",
            "facts": requirements,
        }

    summaries = summary_averages(
        scope, [test.subject.raw_id for test in tests], family
    )
    summary_text = "；".join(
        f"{item['item']} 平均 {item['value']}{item['unit']}"
        for item in summaries
    )
    if summary_text:
        summary_text = f"研制总结给出 {summary_text}。"

    condition_conflicts: list[str] = []
    for requirement in requirements:
        requirement_conditions = fact_conditions(requirement)
        if not requirement_conditions:
            unresolved.append(
                f"要求侧 {requirement.fact_id} 未声明测试条件"
                "（conditions 为空并计入 unknown）"
            )
            continue
        for test in tests:
            test_conditions = fact_conditions(test)
            for kind, raw in requirement_conditions.items():
                if test_conditions.get(kind) != raw:
                    condition_conflicts.append(
                        f"条件 {kind}: 要求={raw!r} 测试={test_conditions.get(kind)!r}"
                    )

    comparisons: list[dict] = []
    failed = False
    bound_bindings = []
    for requirement in requirements:
        req_op, req_number, req_unit = fact_quantity(requirement)
        bound_bindings.append(bind_value(f"{req_number}{req_unit}", requirement))
        for test in tests:
            test_op, test_number, test_unit = fact_quantity(test)
            result, converted = bound_implies(
                test_number,
                test_op,
                test_unit,
                req_number,
                req_op,
                req_unit,
                records,
            )
            comparisons.append(
                {
                    "requirement": requirement.fact_id,
                    "test": test.fact_id,
                    "test_value": f"{test_number}{test_unit}",
                    "result": result,
                    "converted": str(converted) if converted is not None else "",
                }
            )
            if result is False:
                failed = True
            if result is None:
                unresolved.append(
                    f"数值不可比较：要求 {req_number}{req_unit} / "
                    f"测试 {test_number}{test_unit}"
                )

    conditional = bool(condition_conflicts)
    if conditional:
        verdict = "有条件成立"
    elif failed:
        verdict = "不成立"
    elif any(item["result"] is True for item in comparisons):
        verdict = "成立"
    else:
        verdict = "当前证据无法判断"

    test_bindings = []
    for test in tests:
        test_bindings.append(
            bind_value(
                fact_text(test, "raw_value"),
                test,
                note=f"条件={fact_conditions(test)}",
            )
        )

    if verdict == "成立":
        answer = (
            "满足。要求："
            + "、".join(
                f"{fact_text(item, 'attribute')} "
                f"{fact_text(item, 'raw_value')}"
                for item in requirements
            )
            + "。测试结果："
            + "；".join(
                f"{item.subject.raw_id} {fact_text(item, 'raw_value')}"
                for item in tests
            )
            + "。"
            + summary_text
            + "按单位换算后比较，测试上界不超过要求上界，数值上满足。"
        )
    elif verdict == "不成立":
        answer = (
            "不满足。要求："
            + "、".join(
                f"{fact_text(item, 'attribute')} "
                f"{fact_text(item, 'raw_value')}"
                for item in requirements
            )
            + "；测试结果："
            + "；".join(
                f"{item.subject.raw_id} {fact_text(item, 'raw_value')}"
                for item in tests
            )
            + "。测试上界未落在要求边界内。"
        )
    elif verdict == "有条件成立":
        answer = (
            "有条件成立。数值比较可执行，但两侧条件不一致："
            + "；".join(condition_conflicts)
            + "。"
        )
    else:
        answer = "当前证据无法判断：测试值或单位不足以完成边界比较。"

    unresolved.extend(
        [
            f"要求对象={requirements[0].subject.kind}:"
            f"{requirements[0].subject.raw_id}，测试对象="
            + "、".join(item.subject.raw_id for item in tests)
            + "；对象级别未逐字对齐",
            f"测量端点={endpoint}；按指标名称与验收指标对齐",
        ]
    )

    symbols = {"lt": "<", "le": "≤", "gt": ">", "ge": "≥", "eq": "="}
    requirement_value = (
        f"{symbols.get(requirement_quantity[0], '')}"
        f"{_format_number(requirement_quantity[1])}"
        f"{requirement_quantity[2]}"
    )
    claims = [
        claim_with_bindings(
            "requirement",
            "设计要求数值",
            requirement_value,
            requirements,
            bindings=bound_bindings,
        ),
        claim_with_bindings(
            "test_result",
            "同端点测试结果",
            re.sub(r"\s+", "", fact_text(tests[0], "raw_value")),
            tests,
            bindings=test_bindings,
        ),
        claim_with_bindings(
            "verdict",
            "数值比较结论",
            "满足" if verdict == "成立" else "不满足",
            dedupe_facts(list(requirements) + list(tests)),
        ),
    ]
    summary_facts = dedupe_facts(
        [fact for item in summaries for fact in item["facts"]]
    )
    for item in summaries:
        value = f"{item['value']}{item['unit']}"
        bindings = [
            bind_value(value, None, chunk=item["chunk"],
                       note="研制总结逐字原文")
        ]
        bindings.extend(
            bind_value(value, fact, note="同值文档级事实（验收评审报告）")
            for fact in item["facts"]
        )
        claims.append(
            claim_with_bindings(
                f"summary_{item['item']}",
                "研制总结平均值",
                value,
                item["facts"],
                bindings=bindings,
            )
        )
    if summaries:
        unresolved.append(
            "研制总结平均值未建对象级事实；同值事实为文档级平均响应时间"
        )

    return {
        "status": verdict_to_status(verdict),
        "research_label": verdict,
        "task_kind": "requirement_test_match",
        "answer": answer,
        "claims": claims,
        "operators": records,
        "facts": dedupe_facts(
            list(requirements) + list(tests) + summary_facts
        ),
        "evidence": [
            chunk_evidence(item["chunk"], item["excerpt"])
            for item in summaries
        ],
        "unresolved": unresolved,
        "notes": (
            "数值比较由 unit_convert + boundary_compare 完成；条件逐字比较。"
            "要求侧条件和对象级别仍需语义复核。"
        ),
    }


# ---------------------------------------------------------------------------
# task 2: scope mismatch
# ---------------------------------------------------------------------------

_CAPUT = re.compile(r"\bcaput\s+(\S+)\s+(-?\d+(?:\.\d+)?)\s*$", re.IGNORECASE)


def _format_number(value: float | Decimal) -> str:
    decimal = Decimal(str(value))
    if decimal == decimal.to_integral_value():
        return str(int(decimal))
    return format(decimal.normalize(), "f")


def caput_settings(scope, revision_ids):
    groups: dict[str, dict] = {}
    for chunk in chunks_for(scope, revision_ids):
        for line in chunk.text.splitlines():
            match = _CAPUT.search(line.strip())
            if match is None:
                continue
            pv = match.group(1)
            entry = groups.setdefault(
                pv, {"values": [], "lines": [], "chunk": chunk}
            )
            entry["values"].append(match.group(2))
            entry["lines"].append(line.strip()[match.start() :].strip())
    if not groups:
        return None

    def span(item) -> Decimal:
        values = [Decimal(value) for value in item[1]["values"]]
        return max(values) - min(values)

    pv, entry = max(
        groups.items(), key=lambda item: (len(item[1]["values"]), span(item))
    )
    return pv, tuple(entry["values"]), entry["chunk"], tuple(entry["lines"])


def _range_facts(family, attribute: str):
    return [
        fact
        for fact in family
        if fact.layer == "parameter"
        and attribute
        and attribute in fact_text(fact, "attribute")
        and fact.low is not UNKNOWN
        and fact.high is not UNKNOWN
    ]


def _mode_items_from_design(scope, revision_ids) -> list[str]:
    items: list[str] = []
    collecting = False
    for chunk in chunks_for(scope, revision_ids):
        for line in chunk.text.splitlines():
            text = line.strip()
            if not text:
                continue
            if "7种运行模式" in text or "7 种运行模式" in text:
                collecting = True
                continue
            if not collecting:
                continue
            match = re.match(r"^([^。]{2,40}?模式)[。.]", text)
            if match:
                items.append(match.group(1))
            if len(items) >= 7:
                return items
    return items


def _mode_items_from_inline(scope, revision_ids) -> list[str]:
    for chunk in chunks_for(scope, revision_ids):
        normalized = chunk.text
        for marker in ("分别为：", "分别为:", "分别为："):
            if marker not in normalized:
                continue
            tail = normalized.split(marker, 1)[1]
            clause = re.split(r"[。\n]", tail, 1)[0]
            if "、" not in clause:
                continue
            return [part.strip() for part in clause.split("、") if part.strip()]
    return []


MODE_KEY_ALIASES = {
    # One explicit domain synonym used for alignment only; the original names
    # stay in the report and the mapping is listed as a review condition.
    "主加速器调试": "直线加速器调试",
    "正常运行": "运行",
}


def _clean_mode_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", name)
    text = re.sub(r"（[^）]*）|\([^)]*\)", "", text)
    text = text.replace("模式", "").strip()
    return compact_text(text)


def _clean_mode_description(name: str) -> str:
    match = re.search(r"[（(]([^）)]+)[）)]", name)
    if match:
        return _clean_mode_name(match.group(1))
    return _clean_mode_name(name)


def mode_key(name: str, *, description: bool = False) -> str:
    clean = (
        _clean_mode_description(name) if description else _clean_mode_name(name)
    )
    return MODE_KEY_ALIASES.get(clean, clean)


def _scope_mismatch_lists(question, scope) -> dict | None:
    del question
    design_ids = revisions_with_title(scope, ("设计报告",), exclude=("评审",))
    outline_ids = revisions_with_title(scope, ("测试大纲",))
    if not design_ids or not outline_ids:
        return None
    design_items = _mode_items_from_design(scope, design_ids)
    test_items = _mode_items_from_inline(scope, outline_ids)
    if len(design_items) < 2 or len(test_items) < 2:
        return None
    design_clean = [(mode_key(item), item) for item in design_items]
    test_clean = [
        (mode_key(item, description=True), item) for item in test_items
    ]
    design_names = [item[0] for item in design_clean]
    test_names = [item[0] for item in test_clean]
    missing = [name for name in design_names if name not in test_names]
    extra = [name for name in test_names if name not in design_names]
    missing_originals = [
        original for key, original in design_clean if key in missing
    ]
    extra_originals = [
        original for key, original in test_clean if key in extra
    ]
    matched = len(set(design_names) & set(test_names))
    records: list[dict] = []
    run_op(
        "set_enumeration",
        {
            "observed": test_names,
            "expected": design_names,
            "assumptions": [
                "模式名称按原文括号内中文描述规范化后比较",
                "显式记录一条对齐假设：主加速器调试 ↔ 直线加速器调试；"
                "正常运行 ↔ 运行",
                "语义等价仅用于对齐，不影响 answered 判定；仍需人工复核",
            ],
        },
        records,
    )
    chunks = list(chunks_for(scope, design_ids)) + list(
        chunks_for(scope, outline_ids)
    )
    evidence = []
    seen_evidence: set[tuple[str, str]] = set()
    for item in design_items:
        chunk, line = _best_line(chunks, item)
        if chunk is None or (chunk.chunk_id, line) in seen_evidence:
            continue
        seen_evidence.add((chunk.chunk_id, line))
        evidence.append(chunk_evidence(chunk, line))
    chunk, test_line = _set_line(chunks, test_items)
    if chunk is not None and (chunk.chunk_id, test_line) not in seen_evidence:
        seen_evidence.add((chunk.chunk_id, test_line))
        evidence.append(chunk_evidence(chunk, test_line))
    verdict = "成立" if not missing and not extra else "不成立"
    answer = (
        ("完全对应。" if verdict == "成立" else "不完全对应。")
        + f"{matched} 项可对应；"
        + (
            f"设计侧 {'、'.join(missing_originals)} 无同名测试项；"
            if missing_originals
            else "设计侧无缺失；"
        )
        + (
            f"测试侧多出 {'、'.join(extra_originals)}；"
            if extra_originals
            else "测试侧无多余；"
        )
        + f"设计报告：{'、'.join(design_items)}；"
        + f"测试大纲：{'、'.join(test_items)}。"
        + (
            "语义对应（主加速器调试↔直线加速器调试、正常运行↔运行；"
            "波荡器调试↔FEL 放大器调试）需人工复核，不影响本判定。"
            if verdict != "成立"
            else ""
        )
    )
    return {
        "status": verdict_to_status(verdict),
        "research_label": verdict,
        "task_kind": "scope_mismatch.mode_lists",
        "answer": answer,
        "claims": [
            claim_with_bindings(
                "design_modes", "设计报告模式清单", "、".join(design_items)
            ),
            claim_with_bindings(
                "test_modes", "测试大纲模式清单", "、".join(test_items)
            ),
            claim_with_bindings(
                "missing_modes",
                "设计侧无同名测试项",
                "、".join(missing_originals) if missing_originals else "无",
            ),
            claim_with_bindings(
                "extra_modes",
                "测试侧多出模式",
                "、".join(extra_originals) if extra_originals else "无",
            ),
        ],
        "operators": records,
        "evidence": evidence,
        "unresolved": [
            "对象：设计报告 vs 测试大纲模式清单",
            "端点：7 种运行模式名称",
            "条件：无",
            f"设计侧无同名项：{missing_originals}",
            f"测试侧多出：{extra_originals}",
            "语义等价（主加速器调试↔直线加速器调试、波荡器调试↔"
            "FEL 放大器调试）需人工复核，不影响 answered",
        ],
        "notes": (
            "集合比较完成并给出 missing/extra，因此 status=answered；"
            "语义等价映射仅用于对齐，不改变缺项事实。"
        ),
    }


def scope_mismatch(question, facts, scope) -> dict:
    query = question["query"]
    family = common.facts_for_question(facts, question)
    records: list[dict] = []

    attribute = ""
    for candidate in ("风扇开度", "开度", "区间", "范围"):
        if candidate in query:
            attribute = candidate
            break
    ranges = _range_facts(family, attribute) if attribute else []
    if ranges:
        outline = [
            fact
            for fact in ranges
            if "测试大纲" in title_of(scope, fact.revision_id)
            or "设计报告" in title_of(scope, fact.revision_id)
        ]
        self_test = [
            fact
            for fact in ranges
            if "自测报告" in title_of(scope, fact.revision_id)
        ]
        requirement = (outline or ranges)[0]
        low = Decimal(str(requirement.low))
        high = Decimal(str(requirement.high))
        declared = (self_test or ranges)[0]
        if (Decimal(str(declared.low)), Decimal(str(declared.high))) != (
            low,
            high,
        ):
            return {
                "status": verdict_to_status("有条件成立"),
                "research_label": "有条件成立",
                "task_kind": "scope_mismatch.range_conflict",
                "answer": (
                    f"要求侧区间 {_format_number(low)}-{_format_number(high)}"
                    f" 与测试侧声明区间 {_format_number(declared.low)}-"
                    f"{_format_number(declared.high)} 不一致，无法据此判定覆盖。"
                ),
                "facts": [requirement, declared],
                "unresolved": ["两侧区间不一致"],
                "notes": "区间差异需回到原件复核。",
            }

        self_test_ids = [
            revision_id
            for revision_id in revisions_with_title(scope, ("自测报告",))
        ] or list(scope.revisions)
        settings = caput_settings(scope, self_test_ids)
        if settings is None:
            return {
                "status": verdict_to_status("当前证据无法判断"),
                "research_label": "当前证据无法判断",
                "task_kind": "scope_mismatch.no_observed",
                "answer": "找到要求区间，但未在自测报告原文中定位到设置序列。",
                "facts": [requirement, declared],
                "unresolved": ["实测设置序列未定位"],
                "notes": "不据常识补设置值。",
            }
        pv, values, chunk, lines = settings
        expected = [_format_number(low), _format_number(high)]
        if low == low.to_integral_value() and high == high.to_integral_value():
            universe = [str(value) for value in range(int(low), int(high) + 1)]
            assumptions = [
                "区间按整数端点离散化：0%-100% 视作整数百分比 0..100",
                "区间为闭区间；设置值均为整数百分比",
                "实测设置值来自自测报告 caput 行原文，事实层尚无对应事实",
            ]
        else:
            universe = None
            assumptions = [
                "端点非整数，未枚举 universe；仅检查端点成员关系",
            ]
        request = {
            "observed": list(values),
            "expected": expected,
            "assumptions": assumptions,
        }
        if universe is not None:
            request["universe"] = universe
        response = run_op("set_enumeration", request, records)
        missing = response["value"]["missing"] if response["status"] == "ok" else []
        out_of_universe = (
            response["value"]["out_of_universe"]
            if response["status"] == "ok"
            else None
        )
        endpoint_gap = bool(missing)
        verdict = "有条件成立" if endpoint_gap else "成立"
        answer = (
            ("有条件成立。" if endpoint_gap else "成立。")
            + f"要求区间 {_format_number(low)}%-{_format_number(high)}%；"
            + f"自测报告对 {pv} 执行了 {'、'.join(values)} 共 "
            + f"{len(values)} 次设置；"
            + (
                f"缺少端点 {'、'.join(missing)}，"
                "该端点没有实测证据，只能判定区间内部分取值可用。"
                if endpoint_gap
                else "两个端点均有设置记录；但“任意取值均可”仍需穷尽测试。"
            )
        )
        if out_of_universe and (
            out_of_universe["observed"] or out_of_universe["expected"]
        ):
            answer += f" 越界值：{out_of_universe}。"
        claims = [
            claim_with_bindings(
                "requirement_range",
                "要求区间",
                f"{_format_number(low)}%-{_format_number(high)}%",
                [requirement, declared],
                bindings=[
                    bind_value(f"{_format_number(low)}", requirement),
                    bind_value(f"{_format_number(high)}", requirement),
                ],
            ),
            claim_with_bindings(
                "observed_settings",
                "自测报告设置序列",
                "、".join(f"{value}%" for value in values),
                [],
                bindings=[
                    bind_value(value, None, chunk=chunk, note="caput 原文解析")
                    for value in values
                ],
            ),
            claim_with_bindings(
                "endpoint_gap",
                "端点覆盖检查",
                "、".join(missing) if missing else "端点齐全",
                [],
                bindings=[
                    bind_value(
                        value,
                        None,
                        chunk=chunk,
                        note="set_enumeration missing",
                    )
                    for value in missing
                ],
            ),
        ]
        return {
            "status": verdict_to_status(verdict),
            "research_label": verdict,
            "task_kind": "scope_mismatch.endpoint_coverage",
            "answer": answer,
            "claims": claims,
            "operators": records,
            "facts": [requirement, declared],
            "evidence": [
                chunk_evidence(chunk, line) for line in lines if line.strip()
            ],
            "unresolved": [
                "对象：要求侧事实为文档级，未与“盈凡1kW恒温机柜”逐字绑定",
                f"端点：{attribute} 百分比；端点 {', '.join(missing) or '齐'}",
                "条件：要求侧未声明测试条件（conditions 为空，计入 unknown）",
                f"设置值 {'、'.join(values)} 来自 chunk 原文 caput 行，"
                "事实层未建对应事实",
                "caput 记录未绑定对象：按自测报告章节顺序归入盈凡段"
                "（chunk 末尾出现下一节“威图”标题）",
                "离散化假设：0%-100% 按整数百分比处理",
            ],
            "notes": (
                "集合比较由 set_enumeration 完成；caput 行逐字可复核。"
                "端点缺失是证据缺口，不等于设备不合格。"
            ),
        }

    list_result = _scope_mismatch_lists(question, scope)
    if list_result is not None:
        return list_result

    return {
        "status": verdict_to_status("当前证据无法判断"),
        "research_label": "当前证据无法判断",
        "task_kind": "scope_mismatch.unsupported_shape",
        "answer": "未识别出可枚举的区间或清单，当前证据无法完成范围比较。",
        "unresolved": ["题型为范围比较，但事实层缺少区间/清单端点"],
        "notes": "需回到原件确认范围声明。",
    }


# ---------------------------------------------------------------------------
# task 3: design -- test conflict
# ---------------------------------------------------------------------------

_MODE_SET = re.compile(
    r"(?:只)?支持([^，。]*?)(两|三|四|五|六|七|八|九|十|\d)种"
)


def _split_mode_set(text: str) -> list[str]:
    parts = re.split(r"、|和|,|，|及", text)
    return [part.strip() for part in parts if part.strip()]


def design_test_conflict(question, facts, scope) -> dict:
    query = question["query"]
    family = common.facts_for_question(facts, question)
    records: list[dict] = []

    # Numeric design/test conflict: both values are preserved.
    by_attribute: dict[str, dict[str, list]] = {}
    for fact in family:
        if fact.layer != "parameter" or fact_quantity(fact) is None:
            continue
        attribute = fact_text(fact, "attribute")
        if not attribute or attribute in ("验收指标", "测试结果", "测试条件"):
            continue
        by_attribute.setdefault(attribute, {"design": [], "test": []})
        if fact.source_role == "design_target":
            by_attribute[attribute]["design"].append(fact)
        elif fact.source_role == "test_result" and fact.subject.kind == "test_item":
            by_attribute[attribute]["test"].append(fact)
    for attribute, sides in sorted(by_attribute.items()):
        if not sides["design"] or not sides["test"]:
            continue
        design = sides["design"][0]
        test = sides["test"][0]
        design_op, design_number, design_unit = fact_quantity(design)
        test_op, test_number, test_unit = fact_quantity(test)
        converted = converted_number(test_number, test_unit, design_unit, records)
        same = converted is not None and converted == Decimal(str(design_number))
        verdict = "成立" if same else "不成立"
        return {
            "status": verdict_to_status(verdict),
            "research_label": verdict,
            "task_kind": "design_test_conflict.numeric",
            "answer": (
                f"{'一致' if same else '不一致'}。设计要求 {attribute}="
                f"{design_number}{design_unit}（{design.fact_id}）；"
                f"测试值={test_number}{test_unit}（{test.fact_id}）。"
                "两侧数值并列保留，不互相替代。"
            ),
            "claims": [
                claim_with_bindings(
                    "design_value",
                    "设计要求值",
                    f"{design_number}{design_unit}",
                    [design],
                ),
                claim_with_bindings(
                    "test_value",
                    "测试值",
                    f"{test_number}{test_unit}",
                    [test],
                ),
            ],
            "operators": records,
            "facts": [design, test],
            "unresolved": [] if same else ["设计要求与测试值不同"],
            "notes": "数值差异已并列保留；是否为版本差异需语义复核。",
        }

    matches = list(_MODE_SET.finditer(query))
    if len(matches) >= 2:
        sides: list[tuple[str, list[str], str]] = []
        for match in matches:
            context = query[max(0, match.start() - 40) : match.start()]
            side = ""
            if any(token in context for token in ("测试大纲", "自测报告")):
                side = "test"
            elif any(token in context for token in ("研制总结", "验收评审")):
                side = "design"
            sides.append((side, _split_mode_set(match.group(1)), context))
        test_sets = [item[1] for item in sides if item[0] == "test"]
        design_sets = [item[1] for item in sides if item[0] == "design"]
        if test_sets and design_sets:
            observed = test_sets[0]
            expected = design_sets[0]
            response = run_op(
                "set_enumeration",
                {
                    "observed": observed,
                    "expected": expected,
                    "assumptions": [
                        "集合来自题干明确列出的模式清单",
                        "模式名称逐字比较；不把相似名称自动等同",
                    ],
                },
                records,
            )
            missing = (
                response["value"]["missing"] if response["status"] == "ok" else []
            )
            extra = (
                response["value"]["extra"] if response["status"] == "ok" else []
            )
            verdict = "成立" if not missing and not extra else "不成立"
            evidence = []
            seen_evidence: set[str] = set()
            for side, items in (("测试记录", observed), ("验收陈述", expected)):
                keywords = ("测试大纲", "自测报告") if side == "测试记录" else (
                    "研制总结",
                    "验收评审",
                )
                revision_ids = revisions_with_title(scope, (keywords[0],)) + (
                    revisions_with_title(scope, (keywords[1],))
                )
                side_chunks = chunks_for(scope, revision_ids)
                # Prefer the one printed sentence that states the whole set.
                chunk, whole = _set_line(side_chunks, items)
                if whole:
                    if whole not in seen_evidence:
                        seen_evidence.add(whole)
                        evidence.append(
                            chunk_evidence(chunk, whole, role="fact_support")
                        )
                    continue
                for item in items:
                    for chunk in side_chunks:
                        line = _verbatim_line(chunk, item)
                        if not line or line in seen_evidence:
                            continue
                        seen_evidence.add(line)
                        evidence.append(
                            chunk_evidence(chunk, line, role="fact_support")
                        )
                        break
            answer = (
                ("不一致。" if verdict == "不成立" else "一致。")
                + f"测试记录模式集合：{{{'、'.join(observed)}}}；"
                + f"研制总结/验收评审陈述：{{{'、'.join(expected)}}}"
                + (
                    f"；差集 {{{'、'.join(missing)}}} 没有测试记录，"
                    "验收陈述超出测试记录。"
                    if missing
                    else "。"
                )
            )
            return {
                # Both mode sets are read from the question wording; no test
                # record line enumerates them, so the answer stays partial and
                # the provenance is stated in ``unresolved`` (R4 I3).
                "status": "partial",
                "research_label": verdict,
                "task_kind": "design_test_conflict.mode_sets",
                "answer": answer,
                "claims": [
                    claim_with_bindings(
                        "test_modes", "测试记录模式集合", "、".join(observed)
                    ),
                    claim_with_bindings(
                        "design_modes", "验收陈述模式集合", "、".join(expected)
                    ),
                    claim_with_bindings(
                        "missing_modes", "无测试记录的模式", "、".join(missing)
                    ),
                ],
                "operators": records,
                "evidence": evidence,
                "unresolved": [
                    "对象：测试大纲/自测报告 vs 研制总结/验收评审",
                    "端点：运行模式集合",
                    "条件：无",
                    "模式集合来自题干；事实层未建模式清单事实",
                    "原文 chunk 仅用于定位，不替代逐条测试记录；"
                    "集合前提未绑定原文行，故状态为 partial",
                ],
                "notes": "两侧集合并列保留；差异由 set_enumeration 报告。",
            }

    return {
        "status": verdict_to_status("当前证据无法判断"),
        "research_label": "当前证据无法判断",
        "task_kind": "design_test_conflict.unsupported_shape",
        "answer": "未识别出可并列比较的设计值与测试值，当前证据无法判断冲突。",
        "unresolved": ["设计要求/测试值未对齐"],
        "notes": "需回到原件确认两侧口径。",
    }


# ---------------------------------------------------------------------------
# task 4: acceptance gap (structural checks)
# ---------------------------------------------------------------------------


def _document_revisions(scope, query: str, keywords: tuple[str, ...]):
    ids = revisions_with_title(scope, keywords)
    if not ids:
        ids = [
            revision_id
            for revision_id in scope.revisions
            if keywords[0] in title_of(scope, revision_id)
        ]
    del query
    return ids


def _acceptance_book_gap(question, scope) -> dict:
    revision_ids = revisions_with_title(scope, ("验收书",), exclude=("申请",))
    tables = scope_tables(scope, revision_ids)
    section_hits = [
        (table, row, unique_cell_text(row.cells))
        for table in tables
        for row in table.rows
        if "主要技术指标" in unique_cell_text(row.cells)
        and (
            "实测" in unique_cell_text(row.cells)
            or "符合性" in unique_cell_text(row.cells)
        )
    ]
    opinion_hits = [
        (table, row, unique_cell_text(row.cells))
        for table in tables
        for row in table.rows
        if "验收意见" in unique_cell_text(row.cells)
    ]
    if not section_hits:
        return {
            "status": verdict_to_status("当前证据无法判断"),
            "research_label": "当前证据无法判断",
            "task_kind": "acceptance_gap.section_not_found",
            "answer": "未在验收书中定位到“主要技术指标、实测结果和符合性”栏。",
            "unresolved": ["验收书结构未定位"],
            "notes": "不把栏目名存在当作结果。",
        }
    gap_rows = [
        (table, row, text)
        for table, row, text in section_hits
        if not has_measured_content(text)
    ]
    opinion_gap = [
        (table, row, text)
        for table, row, text in opinion_hits
        if "详见" in text or not has_measured_content(text)
    ]
    verdict = "不成立" if gap_rows else "成立"
    section_text = gap_rows[0][2] if gap_rows else section_hits[0][2]
    opinion_text = opinion_gap[0][2] if opinion_gap else "未定位到验收意见栏"
    answer = (
        ("不能。" if gap_rows else "可以。")
        + "验收书“主要技术指标、实测结果和符合性”栏"
        + (
            "只有栏目标题/指标名称，没有指标值、实测值或符合性判断"
            if gap_rows
            else "包含可识别的实测或符合性内容"
        )
        + f"；原文为：{section_text[:160]}。"
        + f"“验收意见”栏：{opinion_text[:120]}。"
        + (
            "验收书本身不构成可复算的验收结论，必须依赖外部报告。"
            if gap_rows
            else ""
        )
    )
    claims = [
        claim_with_bindings(
            "section",
            "主要技术指标栏",
            "无实测值" if gap_rows else "含实测内容",
            [],
            table_rows=[table_ref(table, row) for table, row, _ in section_hits],
        ),
        claim_with_bindings(
            "opinion",
            "验收意见栏",
            "详见验收意见" if opinion_gap else "已填写",
            [],
            table_rows=[table_ref(table, row) for table, row, _ in opinion_hits],
        ),
    ]
    evidence = [
        row_evidence(table, row) for table, row, _ in section_hits + opinion_hits
    ]
    return {
        "status": verdict_to_status(verdict),
        "research_label": verdict,
        "task_kind": "acceptance_gap.acceptance_book_section",
        "answer": answer,
        "claims": claims,
        "evidence": evidence,
        "unresolved": [
            "对象：验收书“主要技术指标、实测结果和符合性”栏",
            "端点：指标—实测—符合性三元组",
            "条件：无（结构检查）",
            "仅结构证据：栏目/指标名称存在不等于结果",
            "验收意见指向外部文件，未在验收书内复算",
            "指标—实测—符合性三元组缺失，需外部自测/评审报告",
        ],
        "notes": (
            "研究标签为“不成立”：该验收书不能作为可复算证据；"
            "底层“设备是否合格/验收结论是否成立”仍是当前证据无法判断，"
            "不判断设备不合格，需外部报告与语义复核。"
        ),
    }


_ITEM_GROUP_TOKENS = ("测试主项", "测试内容", "测试项")
_ITEM_SUB_TOKENS = ("测试子项",)


def _table_items(table: TableView):
    group_idx = column_indexes(table.header, _ITEM_GROUP_TOKENS)
    item_idx = column_indexes(table.header, _ITEM_SUB_TOKENS)
    if not item_idx:
        return ()
    group = group_idx[0] if group_idx else None
    item = item_idx[0]
    rows = normalize_rows(table)
    result_idx = column_indexes(table.header, RESULT_TOKENS + CONCLUSION_TOKENS)
    result_index = result_idx[0] if result_idx else None
    items = []
    for row in rows:
        group_value = (
            row.cells[group] if group is not None and group < len(row.cells) else ""
        )
        item_value = row.cells[item] if item < len(row.cells) else ""
        if not item_value:
            continue
        result_value = (
            row.cells[result_index]
            if result_index is not None and result_index < len(row.cells)
            else ""
        )
        items.append((group_value, item_value, result_value, row))
    return tuple(items)


def item_key(name: str) -> str:
    """Comparison key for a test sub-item.

    The outline and the review report use ``读取`` / ``回读`` for the same
    operation; the prototype normalises that one lexical pair and records the
    assumption.  Every reported name stays the original text.
    """

    return compact_text(name).replace("回读", "读取")


def _item_completeness(question, scope) -> dict:
    query = question["query"]
    outline_ids = revisions_with_title(scope, ("测试大纲",))
    review_ids = revisions_with_title(scope, ("验收评审报告",))
    outline_tables = scope_tables(scope, outline_ids)
    review_tables = scope_tables(scope, review_ids)
    if not outline_tables or not review_tables:
        return {
            "status": verdict_to_status("当前证据无法判断"),
            "research_label": "当前证据无法判断",
            "task_kind": "acceptance_gap.item_tables_not_found",
            "answer": "未定位到测试大纲/验收评审报告的测试项表。",
            "unresolved": ["测试项表未定位"],
            "notes": "不据栏目名推断结果。",
        }
    quotes = re.findall(r"[“\"]([^”\"]+)[”\"]", query)
    target_item = max(quotes, key=len) if quotes else ""
    outline_candidates = []
    for table in outline_tables:
        items = _table_items(table)
        if not items:
            continue
        if target_item and not any(
            item_key(target_item) == item_key(item[1]) for item in items
        ):
            continue
        outline_candidates.append((table, items))
    if not outline_candidates:
        return {
            "status": verdict_to_status("当前证据无法判断"),
            "research_label": "当前证据无法判断",
            "task_kind": "acceptance_gap.target_item_not_found",
            "answer": f"测试大纲中未定位到子项“{target_item}”。",
            "unresolved": [f"目标子项={target_item}"],
            "notes": "不据常识补子项。",
        }
    outline_table, outline_items = outline_candidates[0]
    target_group = next(
        (
            item[0]
            for item in outline_items
            if item_key(item[1]) == item_key(target_item)
        ),
        "",
    )
    outline_group = [item for item in outline_items if item[0] == target_group]
    expected = [item[1] for item in outline_group]
    expected_keys = [item_key(item) for item in expected]

    best = None
    for table in review_tables:
        items = _table_items(table)
        if not items:
            continue
        groups = {item[0] for item in items if item[0]}
        if target_group and target_group not in groups and len(groups) > 1:
            continue
        overlap = len(
            {item_key(item[1]) for item in items} & set(expected_keys)
        )
        if best is None or overlap > best[0]:
            best = (overlap, table, items)
    if best is None or best[0] == 0:
        return {
            "status": verdict_to_status("当前证据无法判断"),
            "research_label": "当前证据无法判断",
            "task_kind": "acceptance_gap.review_table_not_aligned",
            "answer": "验收评审报告中没有与目标测试组对齐的结果表。",
            "unresolved": [f"目标测试组={target_group}"],
            "notes": "表格分组需人工确认。",
        }
    _, review_table, review_items = best
    observed_items = [
        item
        for item in review_items
        if not target_group or item[0] == target_group
    ]
    observed = [item[1] for item in observed_items]
    observed_keys = [item_key(item) for item in observed]
    records: list[dict] = []
    response = run_op(
        "set_enumeration",
        {
            "observed": observed_keys,
            "expected": expected_keys,
            "assumptions": [
                "测试主项分组按表头与上一行继承",
                "“回读”与“读取”按同一操作词规范化后逐字比较",
                "其他同义改写不自动等同",
            ],
        },
        records,
    )
    missing_keys = (
        response["value"]["missing"] if response["status"] == "ok" else []
    )
    missing_rows = [
        item for item in outline_group if item_key(item[1]) in missing_keys
    ]
    missing = [item[1] for item in missing_rows]
    verdict = "成立" if not missing else "不成立"
    evidence = [row_evidence(outline_table, item[3]) for item in missing_rows]
    if missing_rows:
        first_index = outline_group.index(missing_rows[0])
        neighbour_keys = []
        if first_index > 0:
            neighbour_keys.append(item_key(outline_group[first_index - 1][1]))
        if first_index + 1 < len(outline_group):
            neighbour_keys.append(item_key(outline_group[first_index + 1][1]))
        for neighbour in neighbour_keys:
            for item in review_items:
                if item_key(item[1]) == neighbour:
                    evidence.append(row_evidence(review_table, item[3]))
                    break
    answer = (
        ("没有。" if missing else "是。")
        + f"测试大纲“{target_group}”共 {len(expected)} 项；"
        + f"验收评审报告该组 {len(observed)} 项"
        + (
            f"，缺少“{'、'.join(missing)}”一行；"
            "验收评审的功能性结论未覆盖该子项。"
            if missing
            else "，未发现缺项。"
        )
    )
    claims = [
        claim_with_bindings(
            "outline_items",
            "测试大纲子项",
            str(len(expected)),
            [],
            bindings=[
                bind_value(
                    str(len(expected)),
                    None,
                    chunk_id=outline_table.chunk_id,
                    locator_label=outline_table.label_prefix,
                    note="由表格行计数",
                )
            ],
            table_rows=[table_ref(outline_table, item[3]) for item in outline_group],
        ),
        claim_with_bindings(
            "review_items",
            "验收评审报告子项",
            str(len(observed)),
            [],
            bindings=[
                bind_value(
                    str(len(observed)),
                    None,
                    chunk_id=review_table.chunk_id,
                    locator_label=review_table.label_prefix,
                    note="由表格行计数",
                )
            ],
            table_rows=[table_ref(review_table, item[3]) for item in review_items],
        ),
        claim_with_bindings(
            "missing_items",
            "缺少的子项",
            "、".join(missing) if missing else "无",
            [],
            bindings=[
                bind_value(
                    item[1],
                    None,
                    chunk_id=outline_table.chunk_id,
                    locator_label=f"{outline_table.label_prefix}r{item[3].number}",
                    note="测试大纲有、评审报告无",
                )
                for item in missing_rows
            ],
            table_rows=[table_ref(outline_table, item[3]) for item in missing_rows],
        ),
    ]
    return {
        "status": verdict_to_status(verdict),
        "research_label": verdict,
        "task_kind": "acceptance_gap.item_completeness",
        "answer": answer,
        "claims": claims,
        "operators": records,
        "evidence": evidence,
        "unresolved": [
            "对象：测试大纲 vs 验收评审报告（逐字名称对齐）",
            "端点：真空控制功能组（测试主项）",
            "条件：无测试条件声明",
            "子项名称按“回读/读取”规范化后逐字比较，其他同义改写未纳入",
            "合并单元格分组按上一行继承，仍需人工确认",
            "换行或缩写导致的名称差异未纳入",
        ],
        "notes": (
            "集合比较由 set_enumeration 完成；"
            "缺项是评审材料的覆盖缺口，不等于功能未实现。"
        ),
    }


def _result_fill(question, scope, keywords: tuple[str, ...]) -> dict:
    del question
    revision_ids = revisions_with_title(scope, keywords)
    tables = scope_tables(scope, revision_ids)
    collected = []
    total_cells = 0
    for table in tables:
        result_idx, conclusion_idx = result_columns(table)
        if not result_idx:
            continue
        rows = normalize_rows(table)
        if not rows:
            continue
        gaps = table_gaps(table)
        cells = len(rows) * (len(result_idx) + len(conclusion_idx))
        collected.append((table, gaps, cells))
        total_cells += cells
    total_gaps = sum(len(gaps) for _, gaps, _ in collected)
    if not collected:
        return {
            "status": verdict_to_status("当前证据无法判断"),
            "research_label": "当前证据无法判断",
            "task_kind": "acceptance_gap.no_result_table",
            "answer": "未定位到带“测试结果/结论”列的表格。",
            "unresolved": ["结果表未定位"],
            "notes": "不据栏目名推断结果。",
        }
    if total_gaps == total_cells:
        verdict = "不成立"
    elif total_gaps:
        verdict = "有条件成立"
    else:
        verdict = "成立"
    rows_total = sum(len(normalize_rows(table)) for table, _, _ in collected)
    columns = sorted(
        {
            gap["header"]
            for _, gaps, _ in collected
            for gap in gaps
            if gap["header"]
        }
    )
    doc_name = keywords[0]
    answer = (
        ("没有。" if total_gaps else "有。")
        + f"{doc_name}共 {len(collected)} 张结果表、{rows_total} 行；"
        + f"检查 {total_cells} 个结果/结论单元格，"
        + f"其中 {total_gaps} 个为空或缺列"
        + (f"（涉及列：{'、'.join(columns)}）" if columns else "")
        + "。"
        + (
            "大纲只规定测试项与方法，不能当作结果证据；结果需查自测报告/"
            "验收评审报告。"
            if total_gaps
            else "结果列已填写，可作为对应结果证据。"
        )
    )
    claims = []
    for index, (table, gaps, cells) in enumerate(collected, 1):
        claims.append(
            claim_with_bindings(
                f"table_{index}",
                f"结果表 {table.block_id[-12:]}",
                f"{len(gaps)}/{cells} 空",
                [],
                bindings=[
                    bind_value(
                        f"{len(gaps)}/{cells}",
                        None,
                        chunk_id=table.chunk_id,
                        locator_label=table.label_prefix,
                        note="结构计数",
                    )
                ],
                table_rows=[table_ref(table, gap["row"]) for gap in gaps],
            )
        )
    evidence = []
    for table, gaps, _ in collected:
        evidence.append(header_evidence(table))
        for gap in gaps[:8]:
            evidence.append(row_evidence(table, gap["row"]))
    return {
        "status": verdict_to_status(verdict),
        "research_label": verdict,
        "task_kind": "acceptance_gap.result_cells",
        "answer": answer,
        "claims": claims,
        "evidence": evidence,
        "unresolved": [
            "对象：测试大纲结果表",
            "端点：测试结果/结论列",
            "条件：无（结构检查）",
            "缺列/空单元格按空值处理；合并单元格可能影响列对齐",
            "栏目标题存在不等于结果；未据标题判定通过",
            "结果缺失是文档证据缺口，不等于设备未测试",
        ],
        "notes": (
            "研究标签为“不成立”：该文档不能作为结果证据；"
            "底层“功能是否实现/测试是否通过”仍是当前证据无法判断，"
            "需外部报告与语义复核。"
        ),
    }


def acceptance_gap(question, facts, scope) -> dict:
    query = question["query"]
    del facts
    if "逐项" in query or "一一对应" in query or (
        "测试大纲" in query and "验收评审" in query
    ):
        return _item_completeness(question, scope)
    if "验收书" in query and "主要技术指标" in query:
        return _acceptance_book_gap(question, scope)
    if "测试大纲" in query:
        return _result_fill(question, scope, ("测试大纲",))
    if "自测报告" in query:
        return _result_fill(question, scope, ("自测报告",))
    if "验收评审报告" in query:
        return _result_fill(question, scope, ("验收评审报告",))
    return {
        "status": verdict_to_status("当前证据无法判断"),
        "research_label": "当前证据无法判断",
        "task_kind": "acceptance_gap.unsupported_shape",
        "answer": "未识别出可结构检查的目标文档。",
        "unresolved": ["目标文档未识别"],
        "notes": "需回到原件确认证据链路。",
    }


# ---------------------------------------------------------------------------
# task 5: verdict check
# ---------------------------------------------------------------------------


_RATE = re.compile(
    r"([A-Za-z0-9:\-]+)\s*为\s*([\d.]+)\s*Hz\s*[（(]\s*(\d+)秒(\d+)个数\s*[）)]"
)
_BOUND = re.compile(
    r"(单节点|节点间)[^。；，]*?(小于|不超过|不大于|<|≤)\s*"
    r"(\d+(?:\.\d+)?)\s*(μs|us|ns|ms|s)"
)
_NUMBER_UNIT = re.compile(
    r"(\d+(?:\.\d+)?)\s*(μs|us|ns|ms|s|Hz|%)(?![A-Za-z])"
)


def _rate_check(question, facts, scope) -> dict | None:
    matches = list(_RATE.finditer(question["query"]))
    if not matches:
        return None
    family = common.facts_for_question(facts, question)
    records: list[dict] = []
    rows = []
    claims = []
    evidence = []
    all_ok = True
    for match in matches:
        pv = match.group(1)
        reported = Decimal(match.group(2))
        seconds = Decimal(match.group(3))
        count = Decimal(match.group(4))
        result_fact = next(
            (
                fact
                for fact in family
                if fact.subject.raw_id == pv
                and "个数" in fact_text(fact, "raw_value")
            ),
            None,
        )
        criterion_fact = next(
            (
                fact
                for fact in family
                if fact.subject.raw_id == pv
                and fact_text(fact, "attribute") == "验收指标"
                and fact_quantity(fact) is not None
            ),
            None,
        )
        if result_fact is None or criterion_fact is None:
            return {
                "status": verdict_to_status("当前证据无法判断"),
                "research_label": "当前证据无法判断",
                "task_kind": "verdict_check.rate_missing_fact",
                "answer": f"{pv} 的计数结果或验收指标未进入事实层。",
                "unresolved": [f"PV={pv} 事实缺失"],
                "notes": "不据题干以外的数字补。",
            }
        with localcontext() as context:
            context.prec = 28
            ratio = count / seconds
        criterion = fact_quantity(criterion_fact)
        op, op_basis = requirement_op(criterion_fact)
        if op == "range":
            op = "ge"
            op_basis = "minimum_requirement"
        response = run_op(
            "boundary_compare",
            {
                "value": format(ratio, "f"),
                "unit": "Hz",
                "op": op,
                "bound": str(criterion[1]),
                "bound_unit": criterion[2],
            },
            records,
        )
        ok = (
            response["status"] == "ok"
            and bool(response["value"]["result"])
        )
        all_ok = all_ok and ok
        rounded = ratio.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        rows.append(
            {
                "pv": pv,
                "count": count,
                "seconds": seconds,
                "ratio": ratio,
                "reported": reported,
                "rounded": rounded,
                "ok": ok,
                "op": op,
                "op_basis": op_basis,
                "result_fact": result_fact,
                "criterion_fact": criterion_fact,
            }
        )
        claims.extend(
            [
                claim_with_bindings(
                    f"rate_{pv}",
                    f"{pv} 计数复算",
                    f"{count}/{seconds}={format(ratio, 'f')}",
                    [result_fact],
                    bindings=[
                        bind_value(str(count), result_fact),
                        bind_value(str(seconds), result_fact),
                        bind_value(
                            format(ratio, "f"),
                            result_fact,
                            note="Decimal 复算值",
                        ),
                    ],
                ),
                claim_with_bindings(
                    f"criterion_{pv}",
                    f"{pv} 验收指标",
                    f"{_format_number(criterion[1])}{criterion[2]}",
                    [criterion_fact],
                    bindings=[
                        bind_value(
                            f"{_format_number(criterion[1])}{criterion[2]}",
                            criterion_fact,
                        )
                    ],
                ),
                claim_with_bindings(
                    f"comparison_{pv}",
                    f"{pv} 边界比较",
                    f"{format(ratio, 'f')}Hz {op} "
                    f"{criterion[1]}{criterion[2]}",
                    [result_fact, criterion_fact],
                    bindings=[
                        bind_value(
                            op,
                            criterion_fact,
                            note=f"op_basis={op_basis}",
                        )
                    ],
                ),
            ]
        )
        # Fact evidence is emitted by common.evidence_of; only fact-less
        # values need a manual chunk entry.
    verdict = "成立" if all_ok else "不成立"
    criterion_number = _format_number(rows[0]["criterion_fact"].number)
    criterion_unit = fact_text(rows[0]["criterion_fact"], "unit")
    answer = (
        ("达到。" if all_ok else "未达到。")
        + "；".join(
            f"{row['pv']}：{row['count']}/{row['seconds']}="
            f"{format(row['ratio'], 'f')}Hz（报告 {row['reported']}Hz，"
            f"按一位小数 {row['rounded']}Hz）"
            for row in rows
        )
        + f"；均与验收指标 {criterion_number}{criterion_unit} 做边界比较"
        + f"（op={rows[0]['op']}，依据 {rows[0]['op_basis']}），"
        + ("均不低于指标。" if all_ok else "存在低于指标项。")
    )
    return {
        "status": verdict_to_status(verdict),
        "research_label": verdict,
        "task_kind": "verdict_check.count_rate",
        "answer": answer,
        "claims": claims,
        "operators": records,
        "facts": dedupe_facts(
            [
                row["result_fact"]
                for row in rows
            ]
            + [row["criterion_fact"] for row in rows]
        ),
        "evidence": evidence,
        "unresolved": [
            "对象：HW-IMG2:RdPrs、HW-IMG3:RdPrs（事实对象级）",
            "端点：真空数据刷新率 Hz；由计数/时间复算",
            "条件：未记录采样窗口完整性/采样方法",
            "报告值按一位小数记录；3.1Hz 对应复算值 "
            f"{format(rows[-1]['ratio'], 'f')}Hz，舍入假设需复核",
            "计数与时间取自原文事实的 raw_value，未做采样完整性判断",
        ],
        "notes": "比率为 Decimal 复算；边界比较由 boundary_compare 完成。",
    }


_MODEL = re.compile(
    r"^([一-鿿A-Za-z][一-鿿A-Za-z\s\-]*?)(?=\d|恒温|控制|监测|开关|$)"
)


def model_token(raw_id: str) -> str:
    match = _MODEL.match(raw_id.strip())
    return (match.group(1) if match else raw_id).strip()


def _object_attribution_check(question, facts, scope) -> dict | None:
    query = question["query"]
    if "结论" not in query or not ("行" in query or "对象" in query):
        return None
    family = common.facts_for_question(facts, question)
    candidates = [
        fact
        for fact in family
        if fact.layer == "process"
        and fact.fact_type == "test_scope"
        and "conclusion" in fact_extra(fact)
    ]
    if not candidates:
        return None
    tokens = sorted({model_token(fact.subject.raw_id) for fact in candidates})
    targets = [token for token in tokens if token and token in query]
    if not targets:
        return None
    target = max(targets, key=len)
    hit = next(
        (
            fact
            for fact in candidates
            if model_token(fact.subject.raw_id) == target
        ),
        None,
    )
    if hit is None:
        return None
    conclusion = fact_extra(hit)["conclusion"]
    own = target in conclusion
    others = [
        token for token in tokens if token != target and token in conclusion
    ]

    def clean_control(fact) -> bool:
        own = model_token(fact.subject.raw_id)
        text = fact_extra(fact).get("conclusion", "")
        return own in text and not any(
            token != own and token in text for token in tokens
        )

    controls = [fact for fact in candidates if clean_control(fact)]
    control = controls[0] if controls else None
    verdict = "不成立" if (not own and others) else "成立"
    answer = (
        f"该行结论写“{conclusion}”。"
        + (
            f"同时出现 {'、'.join(others)} 等对象名，而行首对象是"
            f"“{hit.subject.raw_id}”，两者字符串不一致，属于对象归属错误；"
            "不能据此把该行判为通过。"
            if verdict == "不成立"
            else "结论包含行首对象名，未发现对象归属错误。"
        )
        + (
            f" 对照：{control.subject.raw_id} 行结论为"
            f"“{fact_extra(control)['conclusion']}”，对象名一致。"
            if control is not None
            else ""
        )
    )
    facts_used = dedupe_facts([hit] + ([control] if control else []))
    records: list[dict] = []
    response = run_op(
        "set_enumeration",
        {
            "observed": others,
            "expected": [target],
            "assumptions": [
                "对象名按行首与结论列中的型号词逐字比较",
                "型号词从同一表格行首对象名中提取",
            ],
        },
        records,
    )
    del response
    return {
        "status": verdict_to_status(verdict),
        "research_label": verdict,
        "task_kind": "verdict_check.object_attribution",
        "answer": answer,
        "claims": [
            claim_with_bindings(
                "conclusion",
                "目标行结论列",
                conclusion,
                [hit],
                bindings=[
                    bind_value(conclusion, hit),
                    bind_value(hit.subject.raw_id, hit,
                               note="行首对象"),
                ],
            ),
            claim_with_bindings(
                "object_mismatch",
                "对象归属比较",
                "、".join(others) if others else target,
                facts_used,
                bindings=[
                    bind_value(token, hit, note="结论列出现的对象名")
                    for token in others
                ],
            ),
        ],
        "operators": records,
        "facts": facts_used,
        "unresolved": [
            "对象：威图1kW恒温机柜行 vs 结论列文本",
            "端点：结论列对象名（字符串比较）",
            "条件：无",
            "对象名按字符串比较；同音/缩写/上级对象名未纳入",
            "此行是否通过仍需结合同行测试结果另行确认",
        ],
        "notes": (
            "结论列对象错位是文档证据错误，不等于设备功能未实现；"
            "测试结果列仍需单独核验。"
        ),
    }


def _numeric_claim_check(question, facts, scope) -> dict | None:
    query = question["query"]
    bounds = [
        (match.group(1), match.group(2), Decimal(match.group(3)),
         match.group(4), match.span())
        for match in _BOUND.finditer(query)
    ]
    if not bounds:
        return None
    measurements = []
    for match in _NUMBER_UNIT.finditer(query):
        span = match.span()
        if any(span[0] < bound[4][1] and bound[4][0] < span[1]
               for bound in bounds):
            continue
        prefix = query[: span[0]]
        endpoint = endpoint_of(prefix[::-1][:60][::-1])
        measurements.append(
            (match.group(0), Decimal(match.group(1)), match.group(2),
             endpoint, span)
        )
    if not measurements:
        return None
    family = common.facts_for_question(facts, question)
    records: list[dict] = []
    rows = []
    all_ok = True
    for text, number, unit, endpoint, _ in measurements:
        bound = next(
            (item for item in bounds if item[0] == endpoint),
            bounds[0],
        )
        bound_op = _OP_WORDS.get(bound[1], "lt")
        fact_candidates = [
            fact
            for fact in family
            if fact_quantity(fact) is not None
            and Decimal(str(fact.number)) == number
            and normalize_text(fact_text(fact, "unit")) == normalize_text(unit)
        ]
        fact_candidates.sort(
            key=lambda fact: (
                0 if "研制总结" in title_of(scope, fact.revision_id) else 1,
                0 if fact_text(fact, "attribute") == "平均响应时间" else 1,
            )
        )
        fact = fact_candidates[0] if fact_candidates else None
        chunk = None
        if fact is None:
            for candidate in chunks_for(
                scope, revisions_with_title(scope, ("研制总结",))
            ):
                if text in candidate.text:
                    chunk = candidate
                    break
        converted = converted_number(number, unit, bound[3], records)
        if converted is None:
            ok = False
        else:
            response = run_op(
                "boundary_compare",
                {
                    "value": str(converted),
                    "unit": bound[3],
                    "op": bound_op,
                    "bound": str(bound[2]),
                    "bound_unit": bound[3],
                },
                records,
            )
            ok = (
                response["status"] == "ok"
                and bool(response["value"]["result"])
            )
        all_ok = all_ok and ok
        rows.append(
            {
                "text": text,
                "number": number,
                "unit": unit,
                "endpoint": endpoint,
                "bound": bound,
                "op": bound_op,
                "op_basis": "query_text",
                "ok": ok,
                "fact": fact,
                "chunk": chunk,
            }
        )
    verdict = "成立" if all_ok else "不成立"
    answer = (
        ("一致。" if all_ok else "矛盾。")
        + "；".join(
            f"{row['text']} 与 {row['endpoint'] or '对应端点'}"
            f"{row['bound'][1]}{row['bound'][2]}{row['bound'][3]} 比较："
            + ("满足" if row["ok"] else "不满足")
            for row in rows
        )
        + "。两种表述并列保留，不互相替代。"
    )
    bindings = []
    for row in rows:
        if row["fact"] is not None:
            bindings.append(bind_value(row["text"], row["fact"]))
        elif row["chunk"] is not None:
            bindings.append(
                bind_value(
                    row["text"], None, chunk=row["chunk"],
                    note="研制总结原文，事实层未建对应事实",
                )
            )
    claims = [
        claim_with_bindings(
            "measurements",
            "被测数值",
            "、".join(row["text"] for row in rows),
            [row["fact"] for row in rows if row["fact"] is not None],
            bindings=bindings,
        ),
        claim_with_bindings(
            "comparisons",
            "边界比较",
            "；".join(
                f"{row['text']} {row['op']} "
                f"{row['bound'][2]}{row['bound'][3]}"
                for row in rows
            ),
            [row["fact"] for row in rows if row["fact"] is not None],
            bindings=[
                bind_value(
                    row["op"],
                    None,
                    chunk_id=(
                        row["fact"].citation.chunk_id
                        if row["fact"] is not None
                        else (row["chunk"].chunk_id if row["chunk"] else "")
                    ),
                    note=f"op_basis={row['op_basis']}",
                )
                for row in rows
            ],
        ),
        claim_with_bindings(
            "verdict",
            "数值一致性",
            verdict,
            [row["fact"] for row in rows if row["fact"] is not None],
        ),
    ]
    evidence = [
        chunk_evidence(row["chunk"], row["text"])
        for row in rows
        if row["fact"] is None and row["chunk"] is not None
    ]
    return {
        "status": verdict_to_status(verdict),
        "research_label": verdict,
        "task_kind": "verdict_check.numeric_claims",
        "answer": answer,
        "claims": claims,
        "operators": records,
        "facts": [row["fact"] for row in rows if row["fact"] is not None],
        "evidence": evidence,
        "unresolved": [
            "对象：研制总结/验收评审报告的平均响应时间",
            "端点：单节点/节点间（按题干最近词判断）",
            "条件：未对测量方法、样本量和统计口径做判断",
            "数值来自题干明确列出的数值，并在事实层/研制总结原文中定位",
        ],
        "notes": (
            "边界比较由 unit_convert + boundary_compare 完成；"
            "表述差异是否构成矛盾仍需语义复核。"
        ),
    }


def verdict_check(question, facts, scope) -> dict:
    for handler in (_rate_check, _object_attribution_check, _numeric_claim_check):
        result = handler(question, facts, scope)
        if result is not None:
            return result
    return {
        "status": verdict_to_status("当前证据无法判断"),
        "research_label": "当前证据无法判断",
        "task_kind": "verdict_check.unsupported_shape",
        "answer": "未识别出可复算的计数、对象归属或数值比较。",
        "unresolved": ["题干未给出可复算数值或对象"],
        "notes": "需回到原件确认结论口径。",
    }


# ---------------------------------------------------------------------------
# report assembly and dispatch
# ---------------------------------------------------------------------------


def _command_for(question: dict, facts_path=DEFAULT_FACTS) -> str:
    return (
        "python3 scripts/research/prototypes/p3_requirement_test_claim.py "
        f"--question {question['base_id']} --facts {facts_path}"
    )


def _assemble(question, draft: dict, facts_path) -> dict:
    report = common.build_report(
        question,
        status=draft["status"],
        answer=draft.get("answer", ""),
        claims=draft.get("claims", []),
        operators=draft.get("operators", []),
        facts=draft.get("facts", []),
        unresolved=draft.get("unresolved", []),
        notes=draft.get("notes", ""),
        facts_path=facts_path,
        command=_command_for(question, facts_path),
    )
    report["research_label"] = draft.get("research_label", "")
    report["task_kind"] = draft.get("task_kind", "")
    report["evidence"].extend(draft.get("evidence", []))
    seen: set[tuple[str, str, str]] = set()
    deduped = []
    for item in report["evidence"]:
        key = (
            item["chunk_id"],
            item["excerpt"],
            item.get("locator_label", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    report["evidence"] = deduped
    return report


def evaluate(question, facts, facts_path=DEFAULT_FACTS) -> dict:
    """Evaluate one question and return a reviewable report dict."""

    reason = common.guard_verdict_class(question)
    if reason is not None:
        return common.not_evaluated_report(
            question,
            reason,
            facts_path=facts_path,
            command=_command_for(question, facts_path),
        )
    task_type = question.get("task_type", "")
    if task_type not in TASK_TYPES:
        return common.unsupported_report(
            question,
            f"task_type={task_type!r} 不在 P3 能力范围内",
            facts_path=facts_path,
            command=_command_for(question, facts_path),
        )
    scope = common.scope_for_question(question)
    if task_type == "requirement_test_match":
        draft = requirement_test_match(question, facts, scope)
    elif task_type == "scope_mismatch":
        draft = scope_mismatch(question, facts, scope)
    elif task_type == "design_test_conflict":
        draft = design_test_conflict(question, facts, scope)
    elif task_type == "acceptance_gap":
        draft = acceptance_gap(question, facts, scope)
    else:
        draft = verdict_check(question, facts, scope)
    return _assemble(question, draft, facts_path)


# ---------------------------------------------------------------------------
# split runner and CLI
# ---------------------------------------------------------------------------


def run_split(split: str, facts_path=DEFAULT_FACTS) -> dict:
    if split not in SPLITS:
        raise SystemExit(f"split not allowed: {split}")
    facts = common.load_facts(facts_path)
    questions = [
        question
        for _, question in sorted(common.question_index((split,)).items())
        if question.get("scenario") == "s3_verification"
    ]
    reports = []
    for question in questions:
        report = evaluate(question, facts, facts_path)
        report["recompute"]["command"] = (
            "python3 scripts/research/prototypes/"
            f"p3_requirement_test_claim.py --all --split {split}"
        )
        reports.append(report)
    status_counts: dict[str, int] = {}
    for report in reports:
        status_counts[report["status"]] = (
            status_counts.get(report["status"], 0) + 1
        )
    deterministic = [
        report
        for report in reports
        if report.get("verdict_class") == "deterministic"
    ]
    answered_or_partial = sum(
        1
        for report in deterministic
        if report["status"] in ("answered", "partial")
    )
    return {
        "schema_version": "phase2-p3-run-v1",
        "split": split,
        "facts_sha256": common.facts_digest(facts_path),
        "question_count": len(reports),
        "deterministic_count": len(deterministic),
        "status_counts": dict(sorted(status_counts.items())),
        "answered_or_partial": answered_or_partial,
        "per_question": [
            {
                "question_id": report["question_id"],
                "task_type": report["task_type"],
                "status": report["status"],
                "research_label": report.get("research_label", ""),
            }
            for report in reports
        ],
        "reports": reports,
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--question", help="dev/val base_id")
    group.add_argument("--all", action="store_true", help="run one split")
    parser.add_argument("--split", choices=SPLITS)
    parser.add_argument("--facts", default=str(DEFAULT_FACTS))
    parser.add_argument("--out", default="", help="report path; empty prints JSON")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.all:
        if not args.split:
            parser.error("--all requires --split")
        result = run_split(args.split, args.facts)
        if args.out:
            common.write_report(args.out, result)
        summary = {key: value for key, value in result.items() if key != "reports"}
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        return

    question = common.get_question(args.question)
    facts = common.load_facts(args.facts)
    report = evaluate(question, facts, args.facts)
    if args.out:
        common.write_report(args.out, report)
        summary = {
            "question_id": report["question_id"],
            "task_type": report["task_type"],
            "task_kind": report.get("task_kind", ""),
            "status": report["status"],
            "research_label": report.get("research_label", ""),
            "answer": report["answer"],
            "claim_count": len(report["claims"]),
            "operator_count": len(report["operators"]),
            "evidence_count": len(report["evidence"]),
            "unresolved_conditions": report["unresolved_conditions"],
            "notes": report["notes"],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        return
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":  # pragma: no cover
    main()
