"""Process and dependency facts for phase 2 (research plan §4.1).

W3 turns the frozen rc.3 snapshot into four kinds of sourced facts:

* ``step`` – one operator action quoted verbatim from an operation manual;
  a sequence number is recorded only when the source printed one;
* ``prerequisite`` – an explicit ``先…/需要…/确保…/在…之前/只有…才能`` style
  statement.  The fact points at a step when that step can be located verbatim
  in the same document and stays unlocated otherwise;
* ``test_scope`` – one row of a test plan, self-test report, test report or
  acceptance review table: test object, test item, stated condition and the
  result exactly as printed;
* ``requirement_link`` – a requirement/test binding that the source states by
  naming the requirement and putting requirement and result in one table row.

Nothing is inferred across revisions or documents: a field the source does not
carry stays ``UNKNOWN`` and is listed in ``unknown_fields``.
"""

from __future__ import annotations

import re

from accelerator_rag.corpus.table_records import TableRecord

from .corpus import (
    CorpusScope,
    block_locator_kind,
    markdown_tables,
    revision_source_role,
    verbatim_row_line,
)
from .schema import (
    UNKNOWN,
    Citation,
    Condition,
    EntityRef,
    Fact,
    make_fact_id,
)

LAYER = "process"
EXTRACTOR = "W3:process"

OPERATION_MANUAL = "operation_manual"
TEST_SCOPE_KINDS = frozenset(
    {"test_plan", "test_report", "review_opinion", "acceptance_report"}
)
def _raw_value_role(cell_role: str, document_kind: str) -> str:
    if cell_role == "conclusion":
        return "acceptance_conclusion"
    if cell_role == "test_result":
        if document_kind in {"review_opinion", "acceptance_report"}:
            return "acceptance_result"
        if document_kind == "test_plan":
            return "test_plan_result"
    return cell_role

# ---------------------------------------------------------------------------
# Verbatim text selection
# ---------------------------------------------------------------------------

_ACTION = (
    "通过|点击|单击|双击|右键|按下|输入|选中|勾选|选择|打开|关闭|启动|重启|"
    "执行|设置|修改|删除|添加|保存|导出|切换|连接|登录|进入|刷新|应用|"
    "提交|停止|将|把|使用|根据|检查|查看|确认|清除|复位|安装|配置|进行|"
    "ping|caput|caget|camonitor"
)
_MODAL = "可|可以|则|请|需|需要|必须|再|然后|将|把"
_UI_OBJECT = (
    "按钮|按键|输入框|对话框|单元格|图标|下拉框|菜单|界面|页面|窗口|"
    "表格|曲线|状态灯|指示灯|阈值|参数|通道|框|区域|PV|plot|Plot|APPLY|"
    "Enable|Disable|Bypass|BYPASS|Trigger|Add|Export|Search"
)

_ACTION_RE = re.compile(_ACTION)
# ``输入状态`` / ``设置区域`` / ``导出过程`` are nouns, not instructions.
_ACTION_NOUN = re.compile(
    r"^(?:状态|信号|值|范围|方式|过程|结果|信息|参数|条件|项|区域|界面|"
    r"功能|模式|说明|记录|列表|时间)"
)

_STEP_START = re.compile(rf"^(?:{_ACTION})")
_SEQUENCE_FRAME = re.compile(
    rf"^(?:首先|其次|然后|再|最后|此时|这时|之后|具体地|此外|同时|另外|"
    rf"或者|其中|第一种|第二种|完成[^，。；]{{0,20}}后|"
    rf"设定[^，。；]{{0,20}}后|选择[^，。；]{{0,20}}后)"
    rf"[：:，,]?\s*(?:{_MODAL}|在|用|以|{_ACTION})"
)
_CONDITIONAL_FRAME = re.compile(
    rf"^(?:如果|若|如需|当|需要|需|必须)[^，。；]{{0,50}}[，,]\s*"
    rf"(?:{_MODAL})?\s*(?:{_ACTION})"
)
_LOCATIVE_FRAME = re.compile(
    rf"^(?:在|对|从)[^，。；]{{0,50}}(?:{_UI_OBJECT})[^，。；]{{0,30}}"
    rf"(?:[，,]\s*(?:{_MODAL})?|[^，。；]{{0,10}})(?:{_ACTION})"
)
_INLINE_ACTION = re.compile(
    r"(?:可以通过|可通过|可点击|需点击|需要点击|需设置|需要设置|可设置|"
    r"可输入|需输入|需要输入|可查看|需查看|可单击|可双击|可按下|"
    r"可切换|需切换|需选择|需要选择)"
)

_NOUN_STEP_PREFIX = re.compile(
    r"^(?:选择项有|设置项|设置区域|导出过程|启动过程|连接状态|配置信息|"
    r"操作说明|导出数据过程中|导出过程中|导出历史数据的时间范围)"
)
_HEADING_TAIL = re.compile(r"[：:]\s*$")
_SENTENCE = re.compile(r"[。！？；\n]+")
_CJK = re.compile(r"[一-鿿]")
_NUMBERING = re.compile(
    r"^\s*(?:(?P<arabic>\d+)[、.．)）]|[（(](?P<paren>\d+)[)）]|(?P<circled>[①-⑳]))\s*"
)
_CIRCLED = {
    character: str(index)
    for index, character in enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳", 1)
}
_SPACED_CJK = re.compile(r"[一-鿿]\s+[一-鿿]")


def _is_ocr_block(block) -> bool:
    """OCR-derived blocks are never fact sources (noisy, review-required)."""

    for key, _value in block.metadata:
        lowered = key.lower()
        if (
            lowered == "ocr"
            or lowered.startswith("ocr_")
            or lowered == "manual_review_required"
        ):
            return True
    return False


def _looks_garbled(text: str) -> bool:
    """OCR text that splits Chinese characters with spaces is not quotable."""

    cjk = len(_CJK.findall(text))
    if cjk < 8:
        return False
    spaced = len(_SPACED_CJK.findall(text))
    return spaced >= 4 and spaced * 3 >= cjk


def _split_units(text: str) -> list[str]:
    """Sentence-sized pieces; each is a verbatim substring of ``text``."""

    return [piece.strip() for piece in _SENTENCE.split(text) if piece.strip()]


def _strip_numbering(text: str) -> tuple[str, str | None]:
    match = _NUMBERING.match(text)
    if not match:
        return text, None
    if match.group("arabic"):
        sequence = match.group("arabic")
    elif match.group("paren"):
        sequence = match.group("paren")
    else:
        sequence = _CIRCLED.get(match.group("circled") or "")
    return text[match.end() :].strip(), sequence


def _real_action(text: str) -> bool:
    """True when an action verb is used as a predicate, not inside a noun."""

    for match in _ACTION_RE.finditer(text):
        if _ACTION_NOUN.match(text[match.end() :]):
            continue
        return True
    return False


def _starts_with_action(text: str) -> bool:
    match = _STEP_START.match(text)
    if not match:
        return False
    return not _ACTION_NOUN.match(text[match.end() :])


def _looks_like_step(text: str) -> bool:
    if _NOUN_STEP_PREFIX.match(text):
        return False
    if _starts_with_action(text):
        return True
    if _SEQUENCE_FRAME.match(text) and _real_action(text):
        return True
    if _CONDITIONAL_FRAME.match(text) and _real_action(text):
        return True
    if _LOCATIVE_FRAME.match(text) and _real_action(text):
        return True
    return bool(_INLINE_ACTION.search(text) and re.search(_UI_OBJECT, text))


def _step_candidates(text: str) -> list[tuple[str, str | None]]:
    results: list[tuple[str, str | None]] = []
    for unit in _split_units(text):
        body, sequence = _strip_numbering(unit)
        if len(body) < 6 or len(body) > 400:
            continue
        if _HEADING_TAIL.search(body):
            continue
        if not _CJK.search(body):
            continue
        if not _looks_like_step(body):
            continue
        results.append((body, sequence))
    return results


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

_PREREQUISITE_TRIGGERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "require",
        re.compile(r"需要(?:先|获取|具备|确认|检查|满足|按照|保证|设置|输入|处于|操作员)"),
    ),
    ("must", re.compile(r"必须[^。；]{2,60}")),
    ("ensure", re.compile(r"(?:^|[，,；;。]|需|必须|应|要)(确保[^。；]{2,40})")),
    ("before", re.compile(r"在[^，。；]{1,40}之前")),
    ("first", re.compile(r"^先[^，。；]{2,30}[，,]?\s*(?:再|然后|之后|后才)[^。；]{2,40}")),
    ("only_if", re.compile(r"只有[^，。；]{1,50}(?:才能|才可|才可以|方可)[^。；]{0,40}")),
    (
        "precondition",
        re.compile(r"(?:前置条件|前提条件|前提是|先决条件)[^。；]{0,60}"),
    ),
    (
        "constraint",
        re.compile(r"(?:应小于|应大于|不得超过|不能超过|不应超过)[^。；]{0,30}"),
    ),
)

_SUBJECT_FOR = re.compile(r"(?:对于|对)([^，。；]{2,20}?)(?:需要|必须|需|应)")
_SUBJECT_WHEN = re.compile(r"^([^，。；：:]{2,16}?)(?:时|的时候)(?:[，,]|要|应|需|必须|注意)")
_SUBJECT_COLON = re.compile(r"^([^：:，,]{2,12})[：:]")
_CLAUSE_LEFT = "，,；;：:。！？!?"
_LEADING_CONNECTIVE = re.compile(r"^(?:但是|但|则|且|并且|因此|所以|此时|这时|同时|另外)")


def _clause(unit: str, match: re.Match[str], basis: str) -> str:
    """The stance itself, verbatim: trigger-first, or subject+trigger."""

    if basis in {"constraint", "must"}:
        start = match.start()
        for index in range(start - 1, -1, -1):
            if unit[index] in _CLAUSE_LEFT:
                start = index + 1
                break
        else:
            start = 0
    elif match.lastindex:
        start = match.start(1)
    else:
        start = match.start()
    clause = unit[start:].strip().strip("。；")
    return _LEADING_CONNECTIVE.sub("", clause).strip()


def _subject_phrase(unit: str) -> str | None:
    for pattern in (_SUBJECT_FOR, _SUBJECT_WHEN, _SUBJECT_COLON):
        match = pattern.search(unit)
        if not match:
            continue
        phrase = match.group(1).strip()
        if not phrase or len(phrase) > 16:
            continue
        if any(mark in phrase for mark in "，,：:"):
            continue
        if phrase.endswith("色") or phrase[:1] in "图表":
            continue
        if _LEADING_CONNECTIVE.match(phrase) or phrase.startswith("注意"):
            continue
        return phrase
    return None


def _prerequisite_candidates(text: str) -> list[tuple[str, str, str]]:
    """``(raw_value, basis, subject_phrase_or_empty)`` for explicit text."""

    results: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for unit in _split_units(text):
        body, _ = _strip_numbering(unit)
        if len(body) < 6 or not _CJK.search(body):
            continue
        for basis, pattern in _PREREQUISITE_TRIGGERS:
            match = pattern.search(body)
            if not match:
                continue
            clause = _clause(body, match, basis)
            if len(clause) < 4:
                continue
            subject = _subject_phrase(body) or ""
            key = f"{basis}\x1f{clause}"
            if key in seen:
                continue
            seen.add(key)
            results.append((clause, basis, subject))
            break
    return results


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------


def _block_locator_kind(block) -> str:
    if block.position.kind in {"slide", "pdf_page", "section"}:
        return block.position.kind
    return block_locator_kind(block.block_type) or "paragraph"


def _block_citation(
    scope: CorpusScope,
    revision_id: str,
    block,
    excerpt: str,
    source_role: str,
) -> Citation | None:
    chunk_id = scope.block_to_chunk(revision_id).get(block.block_id)
    if not chunk_id:
        return None
    chunk = scope.chunk_index(revision_id).get(chunk_id)
    if chunk is None or excerpt not in chunk.text:
        return None
    page_start = block.position.start if block.position.kind == "pdf_page" else None
    page_end = block.position.end if block.position.kind == "pdf_page" else None
    return Citation(
        chunk_id=chunk_id,
        revision_id=revision_id,
        locator_kind=_block_locator_kind(block),
        locator_label=block.position.label
        or f"{block.block_type}-{block.position.start}",
        excerpt=excerpt,
        source_role=source_role,
        page_start=page_start,
        page_end=page_end,
    )


def _table_citation(chunk, source_role: str, table, row, *, header: bool) -> Citation:
    page_start = chunk.page_start if chunk.position_kind == "pdf_page" else None
    page_end = chunk.page_end if chunk.position_kind == "pdf_page" else None
    label = table.header_label if header else f"{table.label_prefix}r{row.row_number}"
    return Citation(
        chunk_id=chunk.chunk_id,
        revision_id=chunk.document_id,
        locator_kind="table_header" if header else "table_row",
        locator_label=label,
        excerpt=table.header_line if header else row.line,
        source_role=source_role,
        page_start=page_start,
        page_end=page_end,
        table_block_id=table.block_id,
        row_number=0 if header else row.row_number,
    )


def _record_citation(
    record: TableRecord, chunk_text: str, source_role: str
) -> Citation | None:
    line = verbatim_row_line(record, chunk_text)
    if not line:
        return None
    return Citation(
        chunk_id=record.chunk_id,
        revision_id=record.revision_id,
        locator_kind="table_row",
        locator_label=record.record_id,
        excerpt=line,
        source_role=source_role,
        table_block_id=record.table_block_id,
        row_number=record.row_number,
    )


# ---------------------------------------------------------------------------
# Value parsing (only what the source prints)
# ---------------------------------------------------------------------------

_VALUE_PATTERN = re.compile(
    r"^(?P<cmp><=|>=|≤|≥|<|>|=)?\s*(?P<number>\d+(?:\.\d+)?)"
    r"\s*(?P<unit>[A-Za-zμµ%℃°]+(?:/[A-Za-z]+)?)?$"
)
_COMPARATORS = {
    "<=": "le",
    "≥": "ge",
    ">=": "ge",
    "≤": "le",
    "<": "lt",
    ">": "gt",
    "=": "eq",
}


class _ParsedValue:
    __slots__ = ("raw", "value_kind", "comparator", "number", "unit", "extra")

    def __init__(self, raw: str) -> None:
        text = raw.strip()
        match = _VALUE_PATTERN.match(text)
        self.raw = raw
        self.extra: tuple[tuple[str, str], ...] = ()
        if not match:
            self.value_kind = "text"
            self.comparator = "unknown"
            self.number: float | object = UNKNOWN
            self.unit: str | object = UNKNOWN
            return
        unit = match.group("unit") or ""
        self.value_kind = "quantity" if unit else "number"
        self.comparator = _COMPARATORS.get(match.group("cmp") or "=", "unknown")
        self.number = float(match.group("number"))
        self.unit = unit or UNKNOWN
        if match.group("cmp") is None:
            self.extra = (("comparator_basis", "table_cell_assignment"),)


# ---------------------------------------------------------------------------
# Fact builders
# ---------------------------------------------------------------------------


def _fact(
    *,
    fact_type: str,
    subject: EntityRef,
    attribute: str | object,
    raw_value: str,
    value_kind: str,
    comparator: str,
    number: float | object,
    unit: str | object,
    citation: Citation,
    evidence_role: str,
    conditions: tuple[Condition, ...] = (),
    object_ref: EntityRef | object = UNKNOWN,
    extra: tuple[tuple[str, str], ...] = (),
) -> Fact:
    fact_id = make_fact_id(
        layer=LAYER,
        fact_type=fact_type,
        subject_raw=subject.raw_id,
        attribute=attribute if isinstance(attribute, str) else "",
        object_raw=object_ref.raw_id if isinstance(object_ref, EntityRef) else "",
        raw_value=raw_value,
        revision_id=citation.revision_id,
        locator_label=citation.locator_label,
        excerpt=citation.excerpt,
    )
    unknown: set[str] = set()
    if unit is UNKNOWN or unit == "":
        unknown.add("unit")
    if not conditions:
        unknown.add("conditions")
    return Fact(
        fact_id=fact_id,
        layer=LAYER,
        fact_type=fact_type,
        subject=subject,
        attribute=attribute,
        raw_value=raw_value,
        value_kind=value_kind,
        comparator=comparator,
        revision_id=citation.revision_id,
        source_role=citation.source_role,
        evidence_role=evidence_role,
        citation=citation,
        conditions=conditions,
        object_ref=object_ref,
        number=number,
        unit=unit,
        unknown_fields=tuple(sorted(unknown)),
        extra=extra,
        extracted_by=EXTRACTOR,
    )


# ---------------------------------------------------------------------------
# Operation manuals: steps and prerequisites
# ---------------------------------------------------------------------------

_LABEL_LIMIT = 24


_BOILERPLATE_LABEL = re.compile(r"^(?:编制|审核|审定|会签|日期|编号|申请|签字)")


def _procedure_label(block) -> str | None:
    """A heading or short label that names the current procedure."""

    text = block.text.strip()
    if not text:
        return None
    if re.match(r"^(?:图|表)\s*\d", text):
        return None
    if block.block_type == "heading":
        return text
    if block.block_type not in {"paragraph", "list_item"}:
        return None
    if len(text) > 30:
        return None
    body = text.rstrip("：: ").strip()
    if not body or _BOILERPLATE_LABEL.match(body):
        return None
    if text.endswith(("：", ":")):
        if len(body) <= 16:
            return body
        return None
    if block.block_type != "list_item":
        return None
    if len(body) > _LABEL_LIMIT or "，" in body:
        return None
    body, _ = _strip_numbering(body)
    if not body or _HEADING_TAIL.search(body) or _looks_like_step(body):
        return None
    return body


def _locate_target(phrase: str | None, unit: str, steps):
    """A distinct step whose verbatim text contains the named operation."""

    if not phrase or len(phrase) < 4:
        return None
    matches = [item for item in steps if phrase in item[0] and item[0] != unit]
    if len(matches) != 1:
        return None
    return matches[0]


def _document_facts(
    scope: CorpusScope, revision_id: str, parsed, source_role: str
) -> list[Fact]:
    facts: list[Fact] = []
    steps: list[tuple[str, Citation]] = []
    procedure_by_block: dict[str, str] = {}
    procedure = parsed.title or revision_id
    for block in parsed.blocks:
        if _is_ocr_block(block) or _looks_garbled(block.text):
            continue
        label = _procedure_label(block)
        if label:
            procedure = label
            procedure_by_block[block.block_id] = procedure
            continue
        procedure_by_block[block.block_id] = procedure
        if block.block_type not in {"paragraph", "list_item"}:
            continue
        for body, sequence in _step_candidates(block.text):
            citation = _block_citation(scope, revision_id, block, body, source_role)
            if citation is None:
                continue
            facts.append(
                _fact(
                    fact_type="step",
                    subject=EntityRef(kind="procedure", raw_id=procedure),
                    attribute="step",
                    raw_value=body,
                    value_kind="text",
                    comparator="unknown",
                    number=UNKNOWN,
                    unit=UNKNOWN,
                    citation=citation,
                    evidence_role="fact_support",
                    extra=(("sequence", sequence or "UNKNOWN"),),
                )
            )
            steps.append((body, citation))

    for block in parsed.blocks:
        if block.block_type not in {"paragraph", "list_item"}:
            continue
        if _is_ocr_block(block) or _looks_garbled(block.text):
            continue
        current = procedure_by_block.get(block.block_id, procedure)
        for clause, basis, phrase in _prerequisite_candidates(block.text):
            citation = _block_citation(
                scope, revision_id, block, clause, source_role
            )
            if citation is None:
                continue
            subject_raw = phrase or current or parsed.title or revision_id
            subject_kind = "procedure" if phrase or current else "document"
            target = _locate_target(phrase, clause, steps)
            extra: list[tuple[str, str]] = [("basis", basis)]
            if target is None:
                extra.append(("target_status", "unlocated"))
                object_ref: EntityRef | object = UNKNOWN
            else:
                target_body, target_citation = target
                extra.append(("target_status", "located"))
                extra.append(("target_locator", target_citation.locator_label))
                object_ref = EntityRef(kind="step", raw_id=target_body)
            facts.append(
                _fact(
                    fact_type="prerequisite",
                    subject=EntityRef(kind=subject_kind, raw_id=subject_raw),
                    attribute="prerequisite",
                    raw_value=clause,
                    value_kind="text",
                    comparator="unknown",
                    number=UNKNOWN,
                    unit=UNKNOWN,
                    citation=citation,
                    evidence_role="condition",
                    object_ref=object_ref,
                    extra=tuple(extra),
                )
            )
    return facts


# ---------------------------------------------------------------------------
# Test scope tables
# ---------------------------------------------------------------------------

_RESULT_HEADERS = ("测试结果", "实测指标", "自测结论", "验收结论", "测试结论", "结论")
_ITEM_HEADERS = (
    "测试子项",
    "测试内容",
    "测试项",
    "测试项目",
    "测试pv",
    "控制对象",
    "测试对象",
    "测试主项",
    "项",
)
_CATEGORY_HEADERS = ("测试主项", "测试类别", "测试分类")
_CONDITION_HEADERS = ("测试条件", "试验条件", "测试方法", "条件")
_CRITERION_HEADERS = ("验收指标", "验收功能", "设计指标", "指标", "要求")
_CONCLUSION_HEADERS = ("结论", "自测结论", "验收结论", "测试结论")


def _column_index(headers: tuple[str, ...], names: tuple[str, ...]) -> int | None:
    for name in names:
        for index, header in enumerate(headers):
            if header == name:
                return index
    for name in names:
        if len(name) < 2:
            continue
        for index, header in enumerate(headers):
            if name in header:
                return index
    return None


def _cell(cells: tuple[str, ...], index: int | None) -> str:
    if index is None or index >= len(cells):
        return ""
    return cells[index].strip()


def _test_scope_facts(
    headers: tuple[str, ...],
    cells: tuple[str, ...],
    citation: Citation,
    *,
    section_path: str,
    document_kind: str,
) -> list[Fact]:
    result_index = _column_index(headers, _RESULT_HEADERS)
    item_index = _column_index(headers, _ITEM_HEADERS)
    if result_index is None or item_index is None:
        return []
    category_index = _column_index(headers, _CATEGORY_HEADERS)
    condition_index = _column_index(headers, _CONDITION_HEADERS)
    criterion_index = _column_index(headers, _CRITERION_HEADERS)
    conclusion_index = _column_index(headers, _CONCLUSION_HEADERS)

    item = _cell(cells, item_index)
    if not item:
        item_index = category_index
        item = _cell(cells, category_index)
    if not item:
        return []
    result = _cell(cells, result_index)
    criterion = _cell(cells, criterion_index)
    conclusion = _cell(cells, conclusion_index)
    if result:
        raw, role = result, "test_result"
    elif criterion:
        raw, role = criterion, "acceptance_criterion"
    elif conclusion:
        raw, role = conclusion, "conclusion"
    else:
        return []

    parsed = _ParsedValue(raw)
    conditions: list[Condition] = []
    condition = _cell(cells, condition_index)
    if condition:
        kind = "test_method" if "方法" in headers[condition_index] else "test_condition"
        conditions.append(Condition(kind=kind, raw=condition, citation=citation))

    extra: list[tuple[str, str]] = [
        ("raw_value_role", _raw_value_role(role, document_kind)),
        ("result_column", headers[result_index]),
    ]
    if criterion and criterion != raw:
        extra.append(("acceptance_criterion", criterion))
        extra.append(("criterion_column", headers[criterion_index]))
    if conclusion and conclusion != raw:
        extra.append(("conclusion", conclusion))
        extra.append(("conclusion_column", headers[conclusion_index]))
    category = _cell(cells, category_index)
    if category and category != item and category != headers[item_index]:
        extra.append(("test_category", category))
    if section_path:
        extra.append(("section_path", section_path))
    extra.extend(parsed.extra)

    return [
        _fact(
            fact_type="test_scope",
            subject=EntityRef(kind="test_item", raw_id=item),
            attribute=headers[item_index],
            raw_value=raw,
            value_kind=parsed.value_kind,
            comparator=parsed.comparator,
            number=parsed.number,
            unit=parsed.unit,
            citation=citation,
            evidence_role="fact_support",
            conditions=tuple(conditions),
            extra=tuple(extra),
        )
    ]


def _requirement_link_facts(
    headers: tuple[str, ...],
    cells: tuple[str, ...],
    citation: Citation,
) -> list[Fact]:
    """Only tables that name the requirement and bind it to a result row."""

    name_index = _column_index(headers, ("验收功能",))
    metric_table = all(
        _column_index(headers, (name,)) is not None
        for name in ("设计指标", "验收指标", "实测指标")
    )
    result_index = _column_index(headers, ("实测指标", "测试结果"))
    item_index = _column_index(headers, _ITEM_HEADERS)
    if name_index is not None:
        requirement = _cell(cells, name_index)
        if not requirement:
            return []
        requirement_name = requirement
        item = _cell(cells, item_index)
        if not item:
            return []
        result = _cell(cells, result_index)
        extra = [
            ("link_basis", "same_table_row"),
            ("name_basis", "acceptance_function_column"),
            ("requirement_column", headers[name_index]),
        ]
        if result:
            extra.append(("result_column", headers[result_index]))
            extra.append(("test_result", result))
    elif metric_table:
        item = _cell(cells, 0)
        if not item:
            return []
        acceptance = _cell(cells, _column_index(headers, ("验收指标",)))
        design = _cell(cells, _column_index(headers, ("设计指标",)))
        measured = _cell(cells, _column_index(headers, ("实测指标",)))
        requirement = acceptance or design or measured
        if not requirement:
            return []
        requirement_name = item
        extra = [
            ("link_basis", "same_table_row"),
            ("name_basis", "named_metric_row"),
            ("requirement_column", "验收指标"),
            ("requirement_name", item),
        ]
        if design:
            extra.append(("design_target", design))
        if measured:
            extra.append(("test_result", measured))
    else:
        return []

    parsed = _ParsedValue(requirement)
    extra.extend(parsed.extra)
    return [
        _fact(
            fact_type="requirement_link",
            subject=EntityRef(kind="test_item", raw_id=item),
            attribute="acceptance_requirement",
            raw_value=requirement,
            value_kind=parsed.value_kind,
            comparator=parsed.comparator,
            number=parsed.number,
            unit=parsed.unit,
            citation=citation,
            evidence_role="fact_support",
            object_ref=EntityRef(kind="requirement", raw_id=requirement_name),
            extra=tuple(extra),
        )
    ]


def _parsed_table_rows(parsed) -> dict[str, tuple[tuple[str, ...], ...]]:
    """Full cell rows per table block; markdown may drop leading empty cells."""

    rows: dict[str, tuple[tuple[str, ...], ...]] = {}
    if parsed is None:
        return rows
    for block in parsed.blocks:
        if block.table is None:
            continue
        rows[block.block_id] = tuple(block.table.data_rows())
    return rows


def _table_facts(
    scope: CorpusScope,
    revision_id: str,
    source_role: str,
    document_kind: str,
) -> list[Fact]:
    facts: list[Fact] = []
    seen: set[tuple[str, str]] = set()
    parsed = scope.parsed_by_revision.get(revision_id)
    parsed_rows = _parsed_table_rows(parsed)
    ocr_blocks = {
        block.block_id for block in parsed.blocks if _is_ocr_block(block)
    } if parsed is not None else set()
    for chunk in scope.chunks_by_revision.get(revision_id, ()):
        if chunk.position_kind == "cell_range":
            continue
        if any(item in ocr_blocks for item in chunk.source_block_id_list):
            continue
        if _looks_garbled(chunk.text):
            continue
        for table in markdown_tables(chunk, revision_id):
            if _looks_garbled(table.header_line):
                continue
            if any(_looks_garbled(row.line) for row in table.rows):
                continue
            full_rows = parsed_rows.get(table.block_id, ())
            usable = len(full_rows) == len(table.rows)
            for position, row in enumerate(table.rows):
                citation = _table_citation(
                    chunk, source_role, table, row, header=False
                )
                key = (chunk.chunk_id, citation.locator_label)
                if key in seen:
                    continue
                seen.add(key)
                cells = full_rows[position] if usable else row.cells
                facts.extend(
                    _test_scope_facts(
                        table.header,
                        cells,
                        citation,
                        section_path=chunk.section_path,
                        document_kind=document_kind,
                    )
                )
                facts.extend(
                    _requirement_link_facts(table.header, cells, citation)
                )
    return facts


def _record_table_facts(
    scope: CorpusScope,
    revision_id: str,
    source_role: str,
    document_kind: str,
) -> list[Fact]:
    facts: list[Fact] = []
    chunk_text = scope.chunk_text()
    parsed = scope.parsed_by_revision.get(revision_id)
    ocr_blocks = {
        block.block_id for block in parsed.blocks if _is_ocr_block(block)
    } if parsed is not None else set()
    for record in scope.records_by_revision.get(revision_id, ()):
        if record.table_block_id in ocr_blocks:
            continue
        citation = _record_citation(
            record, chunk_text.get(record.chunk_id, ""), source_role
        )
        if citation is None or _looks_garbled(citation.excerpt):
            continue
        headers = record.headers
        cells = tuple(value for _, value in record.cells)
        facts.extend(
            _test_scope_facts(
                headers,
                cells,
                citation,
                section_path="",
                document_kind=document_kind,
            )
        )
        facts.extend(_requirement_link_facts(headers, cells, citation))
    return facts


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _dedupe(facts: list[Fact]) -> list[Fact]:
    result: list[Fact] = []
    seen: set[str] = set()
    for fact in facts:
        if fact.fact_id in seen:
            continue
        seen.add(fact.fact_id)
        result.append(fact)
    return result


def extract(scope: CorpusScope) -> list[Fact]:
    """All process-layer facts for the loaded dev/val scope."""

    facts: list[Fact] = []
    for revision_id in scope.revision_ids():
        meta = scope.revisions.get(revision_id, {})
        document_kind = meta.get("document_kind", "")
        source_role = revision_source_role(scope, revision_id)
        if not source_role:
            continue
        parsed = scope.parsed_by_revision.get(revision_id)
        if document_kind == OPERATION_MANUAL and parsed is not None:
            facts.extend(_document_facts(scope, revision_id, parsed, source_role))
        if document_kind in TEST_SCOPE_KINDS:
            facts.extend(
                _table_facts(scope, revision_id, source_role, document_kind)
            )
            facts.extend(
                _record_table_facts(
                    scope, revision_id, source_role, document_kind
                )
            )
    return _dedupe(facts)
