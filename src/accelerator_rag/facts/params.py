"""W1: parameter and condition facts (§4.1).

Records only what the source prints: numbers, units, comparison words, bounds,
measurement endpoints and stated conditions.  Values in tables are bound to
their column header, which is a structural assignment rather than an inference;
everything else is quoted verbatim from a paragraph, list item, footnote,
figure caption, table row or table header.

Nothing is filled from world knowledge, file names, neighbouring rows or another
revision.  A facet the source does not support stays ``UNKNOWN`` and is named in
``unknown_fields``.  Units are kept exactly as printed (``μ`` and ``µ`` differ)
and no conversion happens in this layer.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace

from accelerator_rag.corpus.table_records import GROUP_COLUMN, TableRecord

from .corpus import (
    CorpusScope,
    MarkdownTable,
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

LAYER = "parameter"
EXTRACTOR = "W1"
_FACT_TYPE = "attribute"

# --------------------------------------------------------------------------
# Vocabulary printed by the documents.  Units are matched verbatim and are
# never normalised: "μs" and "µs" are two different source spellings here.
# --------------------------------------------------------------------------

_RAW_UNITS = (
    "GSa/s",
    "MSa/s",
    "kSa/s",
    "GS/s",
    "MS/s",
    "Sa/s",
    "μs",
    "µs",
    "us",
    "ms",
    "ns",
    "fs",
    "ps",
    "GHz",
    "MHz",
    "kHz",
    "Hz",
    "kV",
    "mV",
    "μV",
    "µV",
    "uV",
    "mA",
    "μA",
    "µA",
    "uA",
    "MW",
    "kW",
    "mW",
    "mbar",
    "kPa",
    "hPa",
    "Torr",
    "psi",
    "mm",
    "cm",
    "nm",
    "μm",
    "µm",
    "um",
    "km",
    "dBm",
    "dB",
    "℃",
    "°C",
    "小时",
    "分钟",
    "秒",
    "%",
    "V",
    "A",
    "W",
    "K",
    "Pa",
    "bar",
    "m",
    "s",
    "min",
    "h",
)
_UNITS = tuple(sorted(_RAW_UNITS, key=len, reverse=True))
_UNIT = "|".join(re.escape(unit) for unit in _UNITS)
_NUM = r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"

_TEXT_COMPARATORS = (
    ("小于等于", "le"),
    ("大于等于", "ge"),
    ("不小于", "ge"),
    ("不大于", "le"),
    ("不超过", "le"),
    ("不低于", "ge"),
    ("少于", "lt"),
    ("多于", "gt"),
    ("小于", "lt"),
    ("大于", "gt"),
    ("低于", "lt"),
    ("高于", "gt"),
)
_SYMBOL_COMPARATORS = (("≤", "le"), ("≥", "ge"), ("<", "lt"), (">", "gt"))
_SUFFIX_COMPARATORS = (
    ("及以上", "ge"),
    ("以上", "ge"),
    ("以下", "le"),
    ("以内", "le"),
    ("以外", "gt"),
)
_COMPARATOR_ALTERNATION = "|".join(
    re.escape(text)
    for text, _ in sorted(
        _TEXT_COMPARATORS + _SYMBOL_COMPARATORS, key=lambda item: -len(item[0])
    )
)
_COMPARATOR_MAP = dict(_TEXT_COMPARATORS + _SYMBOL_COMPARATORS)

_PM_RE = re.compile(
    rf"(?<![\d.])(?P<center>{_NUM})\s*±\s*(?P<tolerance>{_NUM})\s*"
    rf"(?P<unit>{_UNIT})(?![A-Za-z0-9])"
)
_RANGE_RE = re.compile(
    rf"(?<![\d.])(?P<low>{_NUM})\s*(?:-|~|～|—|至)\s*(?P<high>{_NUM})\s*"
    rf"(?P<unit>{_UNIT})(?![A-Za-z0-9])"
)
_MIXED_RANGE_RE = re.compile(
    rf"(?<![\d.])(?P<low>{_NUM})\s*(?P<low_unit>{_UNIT})\s*"
    rf"(?:-|~|～|—|至)\s*(?P<high>{_NUM})\s*(?P<high_unit>{_UNIT})"
    rf"(?![A-Za-z0-9])"
)
_VERSION_SUFFIX_RE = re.compile(
    r"(?<![\d.])(?P<version>\d+(?:\.\d+)+)\s*(?P<suffix>及以上|以上)"
)
_VERSION_CELL_RE = re.compile(r"\d+(?:\.\d+)+")
_ATOM_RE = re.compile(
    rf"(?P<comparator>{_COMPARATOR_ALTERNATION})?\s*"
    rf"(?<![\d.])(?P<number>{_NUM})(?![\d.])\s*(?P<unit>{_UNIT})"
    rf"(?![A-Za-z0-9])(?:\s*(?P<suffix>及以上|以上|以下|以内|以外))?"
)
_PLAIN_NUMBER_RE = re.compile(r"[+-]?\d+(?:\.\d+)?")
_HEADER_UNIT_RE = re.compile(rf"[（(]\s*(?P<unit>{_UNIT})\s*[)）]")

# A parameter name in running text must end in one of these nouns; otherwise
# the number is a descriptive value ("1kW恒温机柜") and is not recorded.
_ATTRIBUTE_CUES = (
    "时间",
    "延时",
    "延迟",
    "频率",
    "速率",
    "采样率",
    "刷新率",
    "带宽",
    "抖动",
    "精度",
    "误差",
    "分辨率",
    "稳定度",
    "漂移",
    "温度",
    "湿度",
    "电压",
    "电流",
    "功率",
    "容量",
    "压力",
    "真空度",
    "流量",
    "液位",
    "转速",
    "速度",
    "阈值",
    "范围",
    "量程",
    "开度",
    "长度",
    "距离",
    "高度",
    "直径",
    "角度",
    "数量",
    "数目",
    "个数",
    "点数",
    "路数",
    "台数",
    "条数",
    "套数",
    "周期",
    "响应",
    "增益",
    "衰减",
    "阻抗",
    "信号",
    "电平",
    "幅度",
    "版本",
    "寿命",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[。；;！!？?])\s*|\n+")
_ATTRIBUTE_DELIMITERS = "、，,；;。！!？?\n：:（）()【】[]"
_ATTRIBUTE_LEAD = re.compile(
    r"^(?:其中|且|并|而|则|即|其|该|此|在|当|对于|如果|若|另外|同时|"
    r"需要|研制|实现|保证|确保|具有|提供|采用|通过|可以|能够|应能)\s*"
)
_ATTRIBUTE_TAIL = re.compile(
    r"(?:约为|为|是|达到|达|等于|约|大约|应|需|要求|可|能)\s*$"
)
_LABEL_PREFIX = re.compile(
    r"^(?:[üÜ•·▪◦]+\s*|[A-Za-zⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]{1,4}[：:]\s*"
    r"|\d{1,3}[.、)）]\s*)"
)

_IDENTITY_HEADERS = (
    "电缆编号",
    "设备名称",
    "器件名称",
    "模块名称",
    "系统名称",
    "信号源",
    "传感器",
    "测试项",
    "组件内容",
    "控制对象",
    "名称",
    "编号",
    "项目",
    "项",
    "序号",
)
_SCAFFOLD_MARKERS = (
    "填写",
    "目录",
    "审查意见",
    "签字",
    "日期",
    "完成情况",
    "简要说明",
)
_RESERVED_HEADERS = ("序号", "备注", "分组", "结论", "说明", "描述", "验收功能")
_VERSION_HEADER_HINTS = ("版本",)
_COUNT_HEADER_HINTS = (
    "数量",
    "数目",
    "个数",
    "点数",
    "台数",
    "路数",
    "条数",
    "套数",
    "总计",
    "合计",
)
_CONDITION_HEADERS = (
    (("测试条件", "试验条件", "条件"), "test_condition"),
    (("运行模式", "模式", "工况"), "operating_mode"),
    (("适用范围", "应用范围", "适用"), "applicability"),
    (("测量端点", "测点", "端点"), "measurement_endpoint"),
)
_KIND_BY_HEADER = (
    ("电缆", "cable"),
    ("机柜", "cabinet"),
    ("端口", "port"),
    ("网口", "port"),
    ("交换机", "switch"),
    ("开关", "switch"),
    ("模块", "module"),
    ("板卡", "module"),
    ("系统", "system"),
    ("设备", "device"),
    ("器件", "device"),
    ("传感器", "device"),
    ("探头", "device"),
    ("电机", "device"),
    ("电源", "device"),
    ("控制器", "device"),
    ("测试", "test_item"),
    ("组件", "test_item"),
    ("项目", "test_item"),
    ("指标", "requirement"),
    ("要求", "requirement"),
    ("项", "test_item"),
)
_SPACED_CJK = re.compile(r"[一-鿿] [一-鿿]")


@dataclass(frozen=True)
class _Value:
    """One value expression lifted from a source string."""

    start: int
    end: int
    raw: str
    comparator: str
    value_kind: str
    unit: object = UNKNOWN
    number: object = UNKNOWN
    low: object = UNKNOWN
    high: object = UNKNOWN
    extra: tuple[tuple[str, str], ...] = ()


# --------------------------------------------------------------------------
# Value parsing
# --------------------------------------------------------------------------


def _garbled(text: str) -> bool:
    """OCR of a rendered screen often spaces every CJK character."""

    if "�" in text:
        return True
    cjk = len(re.findall(r"[一-鿿]", text))
    if cjk < 4:
        return False
    spaced = len(_SPACED_CJK.findall(text))
    return spaced >= 2 and spaced * 4 >= cjk


_OCR_HINTS = ("ocr", "manual_review_required")


def _looks_ocr(*values) -> bool:
    blob = " ".join(str(value) for value in values if value).lower()
    return any(hint in blob for hint in _OCR_HINTS)


def _block_is_ocr(block) -> bool:
    return any(_looks_ocr(key, value) for key, value in block.metadata)


def _chunk_is_ocr(chunk) -> bool:
    """True only when the whole chunk is an OCR product.

    A ``review_status=required`` chunk is usually *mixed*: one rendered screen
    was OCR'd next to native text and captions.  Dropping the whole chunk
    silently lost native facts (R1 复审 R1-R2), so the chunk-level test looks
    only at extraction metadata; individual OCR blocks are still filtered by
    ``_block_is_ocr`` wherever facts are built.
    """

    return _looks_ocr(
        chunk.extraction_method,
        chunk.content_role,
        chunk.tags,
        chunk.formula_status,
    )


def _num(text: str) -> float:
    return float(text.replace("+", ""))


def _trimmed_span(match) -> tuple[int, int, str]:
    """Match span and text with outer whitespace removed."""

    raw = match.group(0)
    start = match.start() + (len(raw) - len(raw.lstrip()))
    end = match.end() - (len(raw) - len(raw.rstrip()))
    return start, end, raw.strip()


def _scan_values(text: str) -> list[_Value]:
    """Every explicitly printed value expression in ``text``.

    Longer shapes are consumed first (range, centre±tolerance, version), so an
    atom match never re-cuts a number that is part of a larger expression.
    """

    values: list[_Value] = []
    consumed: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(not (end <= low or start >= high) for low, high in consumed)

    for match in _RANGE_RE.finditer(text):
        start, end, raw = _trimmed_span(match)
        if overlaps(start, end):
            continue
        low, high = sorted((_num(match.group("low")), _num(match.group("high"))))
        values.append(
            _Value(
                start=start,
                end=end,
                raw=raw,
                comparator="range",
                value_kind="range",
                unit=match.group("unit"),
                low=low,
                high=high,
                extra=(("derivation", "explicit_range"),),
            )
        )
        consumed.append((start, end))

    for match in _MIXED_RANGE_RE.finditer(text):
        start, end, raw = _trimmed_span(match)
        if overlaps(start, end):
            continue
        low, high = sorted((_num(match.group("low")), _num(match.group("high"))))
        low_unit = match.group("low_unit")
        high_unit = match.group("high_unit")
        if low_unit == high_unit:
            unit = low_unit
            extra = (("derivation", "explicit_range"),)
        else:
            unit = UNKNOWN
            extra = (
                ("derivation", "explicit_range"),
                ("unit_low", low_unit),
                ("unit_high", high_unit),
            )
        values.append(
            _Value(
                start=start,
                end=end,
                raw=raw,
                comparator="range",
                value_kind="range",
                unit=unit,
                low=low,
                high=high,
                extra=extra,
            )
        )
        consumed.append((start, end))

    for match in _PM_RE.finditer(text):
        start, end, raw = _trimmed_span(match)
        if overlaps(start, end):
            continue
        center = _num(match.group("center"))
        tolerance = _num(match.group("tolerance"))
        values.append(
            _Value(
                start=start,
                end=end,
                raw=raw,
                comparator="range",
                value_kind="range",
                unit=match.group("unit"),
                number=center,
                low=center - tolerance,
                high=center + tolerance,
                extra=(
                    ("derivation", "center±tolerance"),
                    ("tolerance", match.group("tolerance")),
                ),
            )
        )
        consumed.append((start, end))

    for match in _VERSION_SUFFIX_RE.finditer(text):
        start, end, raw = _trimmed_span(match)
        if overlaps(start, end):
            continue
        values.append(
            _Value(
                start=start,
                end=end,
                raw=raw,
                comparator=dict(_SUFFIX_COMPARATORS)[match.group("suffix")],
                value_kind="version",
                extra=(("comparator_basis", "explicit_text"),),
            )
        )
        consumed.append((start, end))

    for match in _ATOM_RE.finditer(text):
        start, end, raw = _trimmed_span(match)
        if overlaps(start, end):
            continue
        comparator = "unknown"
        extra: tuple[tuple[str, str], ...] = ()
        prefix = match.group("comparator")
        suffix = match.group("suffix")
        if prefix:
            comparator = _COMPARATOR_MAP[prefix]
            extra = (("comparator_basis", "explicit_text"),)
        elif suffix:
            comparator = dict(_SUFFIX_COMPARATORS)[suffix]
            extra = (("comparator_basis", "explicit_text"),)
        values.append(
            _Value(
                start=start,
                end=end,
                raw=raw,
                comparator=comparator,
                value_kind="quantity",
                unit=match.group("unit"),
                number=_num(match.group("number")),
                extra=extra,
            )
        )
        consumed.append((start, end))

    return values


def _plain_number(text: str) -> float | None:
    text = text.strip()
    if not _PLAIN_NUMBER_RE.fullmatch(text):
        return None
    try:
        return float(text)
    except ValueError:  # pragma: no cover - regex already guarantees shape
        return None


# --------------------------------------------------------------------------
# Attribute names
# --------------------------------------------------------------------------


def _strip_attribute(text: str) -> str:
    value = text.strip()
    previous = None
    while value and value != previous:
        previous = value
        value = _LABEL_PREFIX.sub("", value).strip()
        if value.endswith(_ATTRIBUTE_CUES):
            break
        value = _ATTRIBUTE_LEAD.sub("", value).strip()
        if value.endswith(_ATTRIBUTE_CUES):
            break
        value = _ATTRIBUTE_TAIL.sub("", value).strip()
    return value


def _valid_attribute(text: str) -> bool:
    if not text or len(text) > 40:
        return False
    if not re.search(r"[一-鿿]", text):
        return False
    if re.search(r"\d", text):
        return False
    if any(char in text for char in "\n|。；;：:"):
        return False
    return text.endswith(_ATTRIBUTE_CUES)


def _last_delimiter(text: str, end: int) -> int:
    return max((text.rfind(char, 0, end) for char in _ATTRIBUTE_DELIMITERS), default=-1)


def _attribute_before(text: str, start: int) -> str:
    """The parameter name printed immediately before ``start``, or UNKNOWN."""

    cut = _last_delimiter(text, start)
    candidate = _strip_attribute(text[cut + 1 : start])
    if _valid_attribute(candidate):
        return candidate
    prefix = text[:start]
    paren = max(prefix.rfind("（"), prefix.rfind("("))
    if paren != -1:
        cut = _last_delimiter(prefix, paren)
        inside = _strip_attribute(prefix[cut + 1 : paren])
        if _valid_attribute(inside):
            return inside
    return UNKNOWN


def _header_unit(header: str) -> object:
    match = _HEADER_UNIT_RE.search(header)
    return match.group("unit") if match else UNKNOWN


def _clean_header(header: str) -> bool:
    text = header.strip()
    if not text or len(text) > 40 or "\n" in text or "|" in text:
        return False
    if _garbled(text):
        return False
    if text in _RESERVED_HEADERS:
        return False
    if re.match(r"^[一二三四五六七八九十]+[、.．]", text):
        return False
    if any(marker in text for marker in _SCAFFOLD_MARKERS):
        return False
    if not re.search(r"[一-鿿]", text):
        # Screenshot captions such as "Keysight Infiniium : Saturday," and
        # OCR fragments such as "ao" are values of a screenshot, not column
        # names; only Chinese headers are treated as parameter names here.
        return False
    return True


def _has_hint(header: str, hints: tuple[str, ...]) -> bool:
    return any(hint in header for hint in hints)


def _is_identity_header(header: str) -> bool:
    return any(hint in header for hint in _IDENTITY_HEADERS)


def _condition_kind(header: str) -> str | None:
    for hints, kind in _CONDITION_HEADERS:
        if _has_hint(header, hints):
            return kind
    return None


def _subject_kind(header: str) -> str:
    for hint, kind in _KIND_BY_HEADER:
        if hint in header:
            return kind
    return "test_item"


# --------------------------------------------------------------------------
# Conditions
# --------------------------------------------------------------------------

_CONDITION_PATTERNS = (
    ("test_condition", re.compile(r"在[^，。；,;\n]{1,30}?条件下")),
    ("test_condition", re.compile(r"当[^，。；,;\n]{1,30}?时")),
    (
        "operating_mode",
        re.compile(r"在[^，。；,;\n]{1,24}?(?:模式|工况)(?:下|中|时)?"),
    ),
    ("operating_mode", re.compile(r"当[^，。；,;\n]{1,24}?(?:模式|工况)")),
    ("applicability", re.compile(r"适用于[^，。；,;\n]{1,30}")),
    ("applicability", re.compile(r"对于[^，。；,;\n]{1,30}")),
    (
        "measurement_endpoint",
        re.compile(r"[^，。；,;\n]{1,16}?(?:测量端点|测点|端点)"),
    ),
)


def _conditions_in_text(
    text: str, make_citation
) -> tuple[Condition, ...]:
    found: list[Condition] = []
    seen: set[tuple[str, str]] = set()
    for kind, pattern in _CONDITION_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(0)
            key = (kind, raw)
            if key in seen:
                continue
            citation = make_citation(raw)
            if citation is None:
                continue
            seen.add(key)
            found.append(Condition(kind=kind, raw=raw, citation=citation))
    return tuple(found)


# --------------------------------------------------------------------------
# Citations and facts
# --------------------------------------------------------------------------


def _pages(chunk) -> tuple[int | None, int | None]:
    if getattr(chunk, "effective_position_kind", "") == "pdf_page":
        return chunk.page_start, chunk.page_end
    return None, None


def _make_fact(
    *,
    subject: EntityRef,
    attribute,
    raw_value: str,
    value_kind: str,
    comparator: str,
    revision_id: str,
    source_role: str,
    evidence_role: str,
    citation: Citation,
    number=UNKNOWN,
    low=UNKNOWN,
    high=UNKNOWN,
    unit=UNKNOWN,
    conditions: tuple[Condition, ...] = (),
    extra: tuple[tuple[str, str], ...] = (),
    locator_key: str = "",
) -> Fact:
    unknown = []
    if attribute is UNKNOWN:
        unknown.append("attribute")
    if unit is UNKNOWN:
        unknown.append("unit")
    if not conditions:
        unknown.append("conditions")
    fact_id = make_fact_id(
        layer=LAYER,
        fact_type=_FACT_TYPE,
        subject_raw=subject.raw_id,
        attribute="" if attribute is UNKNOWN else attribute,
        object_raw="",
        raw_value=raw_value,
        revision_id=revision_id,
        locator_label=locator_key or citation.locator_label,
        excerpt=citation.excerpt,
    )
    return Fact(
        fact_id=fact_id,
        layer=LAYER,
        fact_type=_FACT_TYPE,
        subject=subject,
        attribute=attribute,
        raw_value=raw_value,
        value_kind=value_kind,
        comparator=comparator,
        revision_id=revision_id,
        source_role=source_role,
        evidence_role=evidence_role,
        citation=citation,
        conditions=conditions,
        number=number,
        low=low,
        high=high,
        unit=unit,
        unknown_fields=tuple(sorted(set(unknown))),
        extra=extra,
        extracted_by=EXTRACTOR,
    )


def _document_subject(parsed) -> EntityRef:
    return EntityRef(kind="document", raw_id=parsed.title)


# --------------------------------------------------------------------------
# Paragraph, list item, footnote and figure caption facts
# --------------------------------------------------------------------------


def _block_citation(
    block,
    chunk,
    source_role: str,
    excerpt: str,
    *,
    locator_kind: str | None = None,
    table_block_id: str = "",
    row_number: int | None = None,
) -> Citation | None:
    kind = locator_kind or block_locator_kind(block.block_type)
    if kind is None:
        return None
    page_start, page_end = _pages(chunk)
    return Citation(
        chunk_id=chunk.chunk_id,
        revision_id=chunk.document_id,
        locator_kind=kind,
        locator_label=block.position.label or block.block_id,
        excerpt=excerpt,
        source_role=source_role,
        page_start=page_start,
        page_end=page_end,
        table_block_id=table_block_id,
        row_number=row_number,
    )


def _masked_text(block, table_lines: set[str]) -> str:
    text = block.effective_text
    if not table_lines:
        return text
    kept = [
        line
        for line in text.splitlines()
        if line.strip() and line.strip() not in table_lines
    ]
    return "\n".join(kept)


def _sentence_ok(sentence: str) -> bool:
    if len(sentence) > 600 or not sentence.strip():
        return False
    if len(re.findall(r"[一-鿿]", sentence)) < 2:
        return False
    return not _garbled(sentence)


def _paragraph_facts(
    *,
    parsed,
    revision_id: str,
    source_role: str,
    chunk_by_block: dict[str, object],
    chunks: dict[str, object],
    table_lines_by_chunk: dict[str, set[str]],
    valid_table_lines_by_chunk: dict[str, set[str]],
    subject: EntityRef,
) -> list[Fact]:
    facts: list[Fact] = []
    for block in parsed.blocks:
        if block.block_type not in {
            "paragraph",
            "list_item",
            "note",
            "caption",
            "heading",
            "table",
        }:
            continue
        if _block_is_ocr(block):
            continue
        if block.block_type == "caption" and block.text.strip().startswith("表"):
            continue
        chunk_id = chunk_by_block.get(block.block_id)
        if not chunk_id:
            continue
        chunk = chunks.get(chunk_id)
        if chunk is None:
            continue
        # A table block is scanned as prose only for lines that no valid
        # markdown table already turned into structured facts.
        if block.block_type == "table":
            mask = valid_table_lines_by_chunk.get(chunk_id, set())
        else:
            mask = table_lines_by_chunk.get(chunk_id, set())
        text = _masked_text(block, mask)
        if not text.strip() or _garbled(text):
            continue

        def make_citation(raw: str, _chunk=chunk, _block=block):
            if raw not in _chunk.text:
                return None
            return _block_citation(
                _block,
                _chunk,
                source_role,
                raw,
                locator_kind="paragraph"
                if _block.block_type == "table"
                else None,
            )

        for sentence in _SENTENCE_SPLIT.split(text):
            if not _sentence_ok(sentence):
                continue
            conditions = _conditions_in_text(sentence, make_citation)
            for value in _scan_values(sentence):
                attribute = _attribute_before(sentence, value.start)
                if (
                    attribute is UNKNOWN
                    and value.comparator == "unknown"
                    and value.value_kind != "version"
                ):
                    continue
                end = value.end
                excerpt = sentence[value.start : end]
                if attribute is not UNKNOWN:
                    found = sentence.rfind(attribute, 0, value.start)
                    if found != -1:
                        excerpt = sentence[found:end]
                excerpt = excerpt.strip()
                if len(excerpt) > 200:
                    excerpt = value.raw
                if excerpt not in chunk.text:
                    continue
                citation = _block_citation(
                    block,
                    chunk,
                    source_role,
                    excerpt,
                    locator_kind="paragraph"
                    if block.block_type == "table"
                    else None,
                )
                if citation is None:
                    continue
                facts.append(
                    _make_fact(
                        subject=subject,
                        attribute=attribute,
                        raw_value=value.raw,
                        value_kind=value.value_kind,
                        comparator=value.comparator,
                        revision_id=revision_id,
                        source_role=source_role,
                        evidence_role="fact_support",
                        citation=citation,
                        number=value.number,
                        low=value.low,
                        high=value.high,
                        unit=value.unit,
                        conditions=conditions,
                        extra=value.extra,
                    )
                )
    return facts


def _context_facts(
    *,
    parsed,
    revision_id: str,
    source_role: str,
    chunk_by_block: dict[str, object],
    chunks: dict[str, object],
    subject: EntityRef,
) -> list[Fact]:
    """One provenance fact per caption/note block, keeping its locator kind."""

    facts: list[Fact] = []
    blocks = parsed.blocks
    for index, block in enumerate(blocks):
        if block.block_type not in {"caption", "note"}:
            continue
        if _block_is_ocr(block):
            continue
        chunk_id = chunk_by_block.get(block.block_id)
        chunk = chunks.get(chunk_id) if chunk_id else None
        if chunk is None:
            continue
        text = block.effective_text
        if not text.strip() or text not in chunk.text or _garbled(text):
            continue
        previous = blocks[index - 1] if index > 0 else None
        following = blocks[index + 1] if index + 1 < len(blocks) else None
        table_id = ""
        if block.block_type == "caption":
            attribute = "caption"
            is_table_title = text.lstrip().startswith("表")
            if is_table_title and following is not None:
                if following.block_type == "table":
                    table_id = following.block_id
            elif is_table_title and previous is not None:
                if previous.block_type == "table":
                    table_id = previous.block_id
            locator_kind = "table_title" if is_table_title else "figure_caption"
            extra = (
                (
                    "caption_role",
                    "table_title" if is_table_title else "figure_caption",
                ),
            )
        else:
            attribute = "footnote"
            is_table_note = previous is not None and previous.block_type == "table"
            # A note printed under a table is a footnote (DESIGN §4.3), not a
            # table title; the table it annotates travels in ``extra``.
            locator_kind = "footnote"
            extra = (
                (("table_note_of", previous.block_id),) if is_table_note else ()
            )
        if locator_kind == "table_title" and not table_id:
            table_id = (
                chunk.source_block_id_list[0]
                if chunk.source_block_id_list
                else chunk.chunk_id
            )
        citation = _block_citation(
            block,
            chunk,
            source_role,
            text,
            locator_kind=locator_kind,
            table_block_id=table_id,
            row_number=1 if locator_kind == "table_title" else None,
        )
        if citation is None:
            continue
        facts.append(
            _make_fact(
                subject=subject,
                attribute=attribute,
                raw_value=text,
                value_kind="text",
                comparator="unknown",
                revision_id=revision_id,
                source_role=source_role,
                evidence_role="provenance",
                citation=citation,
                extra=extra,
            )
        )
    return facts


# --------------------------------------------------------------------------
# Table facts
# --------------------------------------------------------------------------


def _markdown_line_index(
    chunks,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Markdown-table lines; the second map only carries valid tables."""

    every: dict[str, set[str]] = {}
    valid: dict[str, set[str]] = {}
    for chunk in chunks:
        all_lines: set[str] = set()
        valid_lines: set[str] = set()
        for table in markdown_tables(chunk, chunk.document_id):
            lines = {table.header_line} | {row.line for row in table.rows}
            all_lines |= lines
            if _valid_markdown_table(table):
                valid_lines |= lines
        every[chunk.chunk_id] = all_lines
        valid[chunk.chunk_id] = valid_lines
    return every, valid


def _valid_markdown_table(table: MarkdownTable) -> bool:
    if len(table.header) < 2 or len(table.rows) == 0:
        return False
    if any(len(cell) > 40 for cell in table.header):
        return False
    nonempty = [cell for cell in table.header if cell.strip()]
    if not nonempty:
        return False
    if len(set(nonempty)) == 1 and len(table.header) >= 3:
        # A merged form cell repeated across every column is not a header row.
        return False
    if not any(_clean_header(cell) for cell in nonempty):
        return False
    if _garbled(table.header_line):
        return False
    return any(
        sum(1 for cell in row.cells if cell.strip()) >= 2 for row in table.rows
    )


_SERIAL_VALUE_RE = re.compile(r"\d+(?:[.、)）]\d*)?|[—\-–]+")


def _is_serial_value(value: str) -> bool:
    text = value.strip()
    return (
        not text
        or bool(_SERIAL_VALUE_RE.fullmatch(text))
        or text in _IDENTITY_HEADERS
        or text in _RESERVED_HEADERS
    )


def _looks_like_value(value: str) -> bool:
    return bool(_scan_values(value)) or _plain_number(value) is not None


def _row_identity(
    headers: tuple[str, ...], cells: tuple[str, ...]
) -> tuple[str, str] | None:
    """First cell that names the row object, skipping serial-number columns."""

    for index, cell in enumerate(cells):
        value = cell.strip()
        if not value or len(value) > 80:
            continue
        if _is_serial_value(value) or _looks_like_value(value):
            continue
        header = headers[index].strip() if index < len(headers) else ""
        return header, value
    return None


def _row_subject(
    headers: tuple[str, ...], cells: tuple[str, ...], parsed
) -> EntityRef:
    identity = _row_identity(headers, cells)
    if identity is None:
        return _document_subject(parsed)
    header, raw_id = identity
    return EntityRef(kind=_subject_kind(header), raw_id=raw_id)


def _row_unit(headers: tuple[str, ...], cells: tuple[str, ...]) -> object:
    """The row's own unit column, when the table prints one."""

    for index, header in enumerate(headers):
        if "单位" not in header or index >= len(cells):
            continue
        value = cells[index].strip()
        if value and len(value) <= 8 and not re.search(r"\d", value):
            return value
    return UNKNOWN


def _row_conditions(
    headers: tuple[str, ...],
    cells: tuple[str, ...],
    make_citation,
) -> tuple[Condition, ...]:
    conditions: list[Condition] = []
    for index, header in enumerate(headers):
        if index >= len(cells):
            continue
        kind = _condition_kind(header)
        if kind is None:
            continue
        raw = cells[index].strip()
        if not raw:
            continue
        citation = make_citation(raw)
        if citation is None:
            continue
        conditions.append(Condition(kind=kind, raw=raw, citation=citation))
    return tuple(conditions)


def _cell_values(value: str, header: str) -> list[_Value]:
    values = _scan_values(value)
    if values:
        return values
    stripped = value.strip()
    if _has_hint(header, _VERSION_HEADER_HINTS) and _VERSION_CELL_RE.fullmatch(
        stripped
    ):
        return [
            _Value(
                start=value.find(stripped),
                end=value.find(stripped) + len(stripped),
                raw=stripped,
                comparator="eq",
                value_kind="version",
                extra=(("comparator_basis", "table_cell_assignment"),),
            )
        ]
    number = _plain_number(stripped)
    if number is None:
        return []
    unit = _header_unit(header)
    if unit is UNKNOWN and not _has_hint(header, _COUNT_HEADER_HINTS):
        return []
    start = value.find(stripped)
    extra: tuple[tuple[str, str], ...] = (
        ("comparator_basis", "table_cell_assignment"),
    )
    if unit is not UNKNOWN:
        extra += (("unit_source", "table_header"),)
    return [
        _Value(
            start=start,
            end=start + len(stripped),
            raw=stripped,
            comparator="eq",
            value_kind="number",
            unit=unit,
            number=number,
            extra=extra,
        )
    ]


def _cell_attribute(value: str, parsed_value: _Value, header: str) -> tuple:
    prefix = value[: parsed_value.start]
    stripped = prefix.rstrip()
    if stripped.endswith(("（", "(")):
        # A value in its own parenthesis belongs to the phrase before it; if
        # that phrase is not a parameter name the binding stays unknown rather
        # than being attached to an unrelated column.  An empty phrase before
        # the parenthesis leaves the column header as the only candidate.
        paren = max(stripped.rfind("（"), stripped.rfind("("))
        head = stripped[:paren]
        if head.strip():
            cut = _last_delimiter(head, len(head))
            inside = _strip_attribute(_LABEL_PREFIX.sub("", head[cut + 1 :]))
            if _valid_attribute(inside):
                return inside, "cell_text"
            return UNKNOWN, "table_header"
    candidate = _strip_attribute(_LABEL_PREFIX.sub("", prefix.strip()))
    if _valid_attribute(candidate):
        return candidate, "cell_text"
    if _clean_header(header):
        return header, "table_header"
    return UNKNOWN, "table_header"


@dataclass(frozen=True)
class _ColumnHeader:
    """Column identity shared by a markdown table and a cell-range table."""

    key: tuple[str, str, int]
    header_line: str
    locator_label: str
    row_number: int
    chunk_id: str
    revision_id: str
    table_block_id: str


def _raw_line_index(text: str) -> dict[str, str]:
    """Stripped line -> the line exactly as the chunk prints it."""

    return {
        line.strip(): line for line in text.splitlines() if line.strip()
    }


def _markdown_header_info(
    table: MarkdownTable, chunk, raw_lines: dict[str, str]
) -> _ColumnHeader:
    return _ColumnHeader(
        key=("markdown", chunk.chunk_id, table.table_index),
        header_line=raw_lines.get(table.header_line, table.header_line),
        locator_label=table.header_label,
        row_number=0,
        chunk_id=chunk.chunk_id,
        revision_id=chunk.document_id,
        table_block_id=table.block_id,
    )


def _record_header_info(
    record: TableRecord, block, header_line: str
) -> _ColumnHeader:
    row_number = 0
    if block is not None and block.table is not None and block.table.row_numbers:
        row_number = block.table.row_numbers[0]
    elif block is not None:
        row_number = block.position.start
    return _ColumnHeader(
        key=("record", record.chunk_id, 0),
        header_line=header_line,
        locator_label=f"{record.table_block_id}:h{row_number}",
        row_number=row_number,
        chunk_id=record.chunk_id,
        revision_id=record.revision_id,
        table_block_id=record.table_block_id,
    )


def _header_fact(
    *,
    header_info: _ColumnHeader,
    header_label: str,
    subject: EntityRef,
    source_role: str,
    unit=UNKNOWN,
) -> Fact:
    page_start = page_end = None
    citation = Citation(
        chunk_id=header_info.chunk_id,
        revision_id=header_info.revision_id,
        locator_kind="table_header",
        locator_label=header_info.locator_label,
        excerpt=header_info.header_line,
        source_role=source_role,
        page_start=page_start,
        page_end=page_end,
        table_block_id=header_info.table_block_id,
        row_number=header_info.row_number,
    )
    extra: list[tuple[str, str]] = [("attribute_source", "table_header")]
    if header_info.key[0] == "markdown":
        extra.append(("table_index", str(header_info.key[2])))
    return _make_fact(
        subject=subject,
        attribute=header_label,
        raw_value=header_label,
        value_kind="text",
        comparator="unknown",
        revision_id=header_info.revision_id,
        source_role=source_role,
        evidence_role="header",
        citation=citation,
        unit=unit,
        extra=tuple(extra),
    )


def _markdown_table_facts(
    *,
    table: MarkdownTable,
    chunk,
    parsed,
    revision_id: str,
    source_role: str,
    used_headers: dict[tuple[str, str, int], tuple[str, _ColumnHeader]],
    raw_lines: dict[str, str],
) -> list[Fact]:
    facts: list[Fact] = []
    header_info = _markdown_header_info(table, chunk, raw_lines)
    for row in table.rows:
        if _garbled(row.line):
            continue
        cells = row.cells
        row_line = raw_lines.get(row.line, row.line)

        def make_citation(raw: str, _table=table, _row=row):
            if raw not in _row.line:
                return None
            return Citation(
                chunk_id=_table.chunk_id,
                revision_id=_table.revision_id,
                locator_kind="table_row",
                locator_label=f"{_table.label_prefix}r{_row.row_number}",
                excerpt=raw,
                source_role=source_role,
                table_block_id=_table.block_id,
                row_number=_row.row_number,
            )

        row_subject = _row_subject(table.header, cells, parsed)
        row_unit = _row_unit(table.header, cells)
        conditions = _row_conditions(table.header, cells, make_citation)
        for index, cell in enumerate(cells):
            if index >= len(table.header):
                break
            header = table.header[index]
            value_text = cell.strip()
            if not value_text:
                continue
            if _condition_kind(header) is not None:
                used_headers.setdefault(
                    (header_info.key[0], header_info.key[1], index),
                    (header, header_info),
                )
                continue
            if not _clean_header(header) or _is_identity_header(header):
                continue
            for value in _cell_values(value_text, header):
                attribute, source = _cell_attribute(value_text, value, header)
                if attribute is UNKNOWN:
                    continue
                citation = Citation(
                    chunk_id=table.chunk_id,
                    revision_id=table.revision_id,
                    locator_kind="table_row",
                    locator_label=f"{table.label_prefix}r{row.row_number}",
                    excerpt=row_line,
                    source_role=source_role,
                    table_block_id=table.block_id,
                    row_number=row.row_number,
                )
                unit = value.unit
                comparator = value.comparator
                extra = value.extra + (
                    ("attribute_source", source),
                    ("document_context", parsed.title),
                    ("table_index", str(table.table_index)),
                )
                if comparator == "unknown":
                    comparator = "eq"
                    extra += (("comparator_basis", "table_cell_assignment"),)
                if (
                    unit is UNKNOWN
                    and value.value_kind == "number"
                    and row_unit is not UNKNOWN
                ):
                    unit = row_unit
                    extra += (("unit_source", "row_column"),)
                facts.append(
                    _make_fact(
                        subject=row_subject,
                        attribute=attribute,
                        raw_value=value.raw,
                        value_kind=value.value_kind,
                        comparator=comparator,
                        revision_id=revision_id,
                        source_role=source_role,
                        evidence_role="fact_support",
                        citation=citation,
                        number=value.number,
                        low=value.low,
                        high=value.high,
                        unit=unit,
                        conditions=conditions,
                        extra=extra,
                    )
                )
                used_headers.setdefault(
                    (header_info.key[0], header_info.key[1], index),
                    (header, header_info),
                )
    return facts


def _record_table_facts(
    *,
    record: TableRecord,
    chunk_text: str,
    block,
    parsed,
    revision_id: str,
    source_role: str,
    used_headers: dict[tuple[str, str, int], tuple[str, _ColumnHeader]],
    header_lines: dict[str, str],
) -> list[Fact]:
    row_line = verbatim_row_line(record, chunk_text)
    if row_line is None or _garbled(row_line):
        return []
    header_line = header_lines.get(record.table_block_id)
    if header_line is None:
        return []
    headers = record.headers
    cells = tuple(value for _, value in record.cells)
    header_info = _record_header_info(record, block, header_line)

    def make_citation(raw: str, _record=record):
        if raw not in row_line:
            return None
        return Citation(
            chunk_id=_record.chunk_id,
            revision_id=_record.revision_id,
            locator_kind="table_row",
            locator_label=_record.record_id,
            excerpt=raw,
            source_role=source_role,
            table_block_id=_record.table_block_id,
            row_number=_record.row_number,
        )

    row_subject = _row_subject(headers, cells, parsed)
    row_unit = _row_unit(headers, cells)
    conditions = _row_conditions(headers, cells, make_citation)
    facts: list[Fact] = []
    for index, (letter, cell) in enumerate(record.cells):
        if letter == GROUP_COLUMN or index >= len(headers):
            continue
        header = headers[index]
        value_text = cell.strip()
        if not value_text:
            continue
        if _condition_kind(header) is not None:
            used_headers.setdefault(
                ("record", record.chunk_id, index), (header, header_info)
            )
            continue
        if not _clean_header(header) or _is_identity_header(header):
            continue
        for value in _cell_values(value_text, header):
            attribute, source = _cell_attribute(value_text, value, header)
            if attribute is UNKNOWN:
                continue
            citation = Citation(
                chunk_id=record.chunk_id,
                revision_id=record.revision_id,
                locator_kind="table_row",
                locator_label=record.record_id,
                excerpt=row_line,
                source_role=source_role,
                table_block_id=record.table_block_id,
                row_number=record.row_number,
            )
            unit = value.unit
            comparator = value.comparator
            extra = value.extra + (
                ("attribute_source", source),
                ("document_context", parsed.title),
            )
            if comparator == "unknown":
                comparator = "eq"
                extra += (("comparator_basis", "table_cell_assignment"),)
            if (
                unit is UNKNOWN
                and value.value_kind == "number"
                and row_unit is not UNKNOWN
            ):
                unit = row_unit
                extra += (("unit_source", "row_column"),)
            facts.append(
                _make_fact(
                    subject=row_subject,
                    attribute=attribute,
                    raw_value=value.raw,
                    value_kind=value.value_kind,
                    comparator=comparator,
                    revision_id=revision_id,
                    source_role=source_role,
                    evidence_role="fact_support",
                    citation=citation,
                    number=value.number,
                    low=value.low,
                    high=value.high,
                    unit=unit,
                    conditions=conditions,
                    extra=extra,
                )
            )
            used_headers.setdefault(
                ("record", record.chunk_id, index), (header, header_info)
            )
    return facts


def _table_facts(
    *,
    scope: CorpusScope,
    parsed,
    revision_id: str,
    source_role: str,
    subject: EntityRef,
    chunks: tuple,
) -> list[Fact]:
    facts: list[Fact] = []
    used_headers: dict[tuple[str, str, int], tuple[str, _ColumnHeader]] = {}
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    blocks = {block.block_id: block for block in parsed.blocks}
    cell_range_blocks = {
        block.block_id
        for block in parsed.blocks
        if block.block_type == "table" and block.position.kind == "cell_range"
    }
    chunk_text = {chunk_id: chunk.text for chunk_id, chunk in by_id.items()}

    for chunk in chunks:
        raw_lines = _raw_line_index(chunk.text)
        tables = markdown_tables(chunk, revision_id)
        header_lines = {
            table.block_id: raw_lines.get(table.header_line, table.header_line)
            for table in tables
            if table.block_id in cell_range_blocks
        }
        for table in tables:
            if table.block_id in cell_range_blocks:
                continue
            block = blocks.get(table.block_id)
            if block is not None and _block_is_ocr(block):
                continue
            if not _valid_markdown_table(table):
                continue
            facts.extend(
                _markdown_table_facts(
                    table=table,
                    chunk=chunk,
                    parsed=parsed,
                    revision_id=revision_id,
                    source_role=source_role,
                    used_headers=used_headers,
                    raw_lines=raw_lines,
                )
            )
        for record in scope.records_by_revision.get(revision_id, ()):
            if record.chunk_id != chunk.chunk_id:
                continue
            block = blocks.get(record.table_block_id)
            if block is not None and _block_is_ocr(block):
                continue
            facts.extend(
                _record_table_facts(
                    record=record,
                    chunk_text=chunk_text[chunk.chunk_id],
                    block=block,
                    parsed=parsed,
                    revision_id=revision_id,
                    source_role=source_role,
                    used_headers=used_headers,
                    header_lines=header_lines,
                )
            )

    for _, (header, header_info) in sorted(used_headers.items()):
        if not _clean_header(header):
            continue
        facts.append(
            _header_fact(
                header_info=header_info,
                header_label=header,
                subject=subject,
                source_role=source_role,
                unit=_header_unit(header),
            )
        )
    return facts


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def _extract_revision(
    scope: CorpusScope, parsed, revision_id: str, source_role: str
) -> list[Fact]:
    revision_chunks = tuple(
        chunk
        for chunk in scope.chunks_by_revision.get(revision_id, ())
        if not _chunk_is_ocr(chunk) and not _garbled(chunk.text)
    )
    chunks = {chunk.chunk_id: chunk for chunk in revision_chunks}
    subject = _document_subject(parsed)
    chunk_by_block = scope.block_to_chunk(revision_id)
    table_lines_by_chunk, valid_table_lines_by_chunk = _markdown_line_index(
        revision_chunks
    )
    facts = _table_facts(
        scope=scope,
        parsed=parsed,
        revision_id=revision_id,
        source_role=source_role,
        subject=subject,
        chunks=revision_chunks,
    )
    facts.extend(
        _paragraph_facts(
            parsed=parsed,
            revision_id=revision_id,
            source_role=source_role,
            chunk_by_block=chunk_by_block,
            chunks=chunks,
            table_lines_by_chunk=table_lines_by_chunk,
            valid_table_lines_by_chunk=valid_table_lines_by_chunk,
            subject=subject,
        )
    )
    facts.extend(
        _context_facts(
            parsed=parsed,
            revision_id=revision_id,
            source_role=source_role,
            chunk_by_block=chunk_by_block,
            chunks=chunks,
            subject=subject,
        )
    )
    return facts


def extract(scope: CorpusScope) -> list[Fact]:
    """Every parameter/condition fact the scoped revisions print."""

    facts: list[Fact] = []
    seen: set[str] = set()
    for revision_id in scope.revision_ids():
        source_role = revision_source_role(scope, revision_id)
        if not source_role:
            continue
        parsed = scope.parsed_by_revision.get(revision_id)
        if parsed is None:
            continue
        for fact in _extract_revision(scope, parsed, revision_id, source_role):
            if fact.fact_id in seen:
                continue
            seen.add(fact.fact_id)
            facts.append(fact)
    return _mark_duplicates(facts)


def _mark_duplicates(facts: list[Fact]) -> list[Fact]:
    """Mark same-parameter facts repeated in one revision; keep every record."""

    groups: dict[tuple, list[int]] = {}
    for index, fact in enumerate(facts):
        if fact.evidence_role != "fact_support":
            continue
        key = (
            fact.revision_id,
            fact.subject.raw_id,
            str(fact.attribute),
            fact.value_kind,
            fact.comparator,
            str(fact.number),
            str(fact.low),
            str(fact.high),
            str(fact.unit),
        )
        groups.setdefault(key, []).append(index)
    marked = list(facts)
    for key, indexes in groups.items():
        if len(indexes) < 2:
            continue
        digest = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:10]
        for index in indexes:
            fact = marked[index]
            marked[index] = replace(
                fact, extra=fact.extra + (("duplicate_group", digest),)
            )
    return marked
