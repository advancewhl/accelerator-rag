"""W2: connectivity and membership facts (§4.1).

The layer records what the cable tables and switch configuration tables print
about devices, cabinets, cables, ports, VLANs, systems and PVs.  Two source
shapes carry it:

* spreadsheet ``cell_range`` tables, read through ``TableRecord`` and cited on
  the verbatim markdown line of the parent chunk;
* markdown tables embedded in paragraph/page/slide chunks, read through
  ``markdown_tables``.

Object identity follows design §4.2.  ``raw_id`` is always a verbatim fragment
of the source cell that names the object.  A device identifier such as
``DEVSW001`` only becomes linkable when the same reference position also prints
its cabinet or range; that cabinet goes into ``scope`` with ``scope_source``
set.  Otherwise ``scope`` stays ``UNKNOWN`` and ``extra`` carries
``("scope_status", "unresolved")``.  No scope is ever borrowed from a file
name, a neighbouring table or another cabinet's table: the same ``DEVSW001``
printed under two cabinets yields two independent entity references.  Empty
cells produce no facts, and nothing is filled from world knowledge.  The tables
in this corpus never write ``同上``; if one did, it would stay unresolved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from accelerator_rag.corpus.table_records import TableRecord

from .corpus import (
    CorpusScope,
    markdown_tables,
    revision_source_role,
    verbatim_row_line,
)
from .schema import (
    UNKNOWN,
    Citation,
    EntityRef,
    Fact,
    IdentityKey,
    make_fact_id,
)

LAYER = "connectivity"
EXTRACTOR = "W2"

_FACT_RELATION = "relation"
_FACT_ATTRIBUTE = "attribute"

# --------------------------------------------------------------------------
# Source vocabulary.  Identifiers are matched as printed, never normalised.
# --------------------------------------------------------------------------

_CABLE_HEADERS = ("电缆编号", "所属机柜名称", "所属设备")
_SWITCH_HEADERS = ("设备", "端口", "系统")

# "FEL1-CN01柜（DEVSW001）" or "LA-BRK-CN13柜（DEVSW005） 仅包含..."
_CABINET_DEVICE = re.compile(
    r"^\s*(?P<cabinet>[^（()]+?)\s*[（(]\s*(?P<device>[^（()）]+?)\s*[）)]"
)
# A device token printed in parentheses: ASCII letters/digits, '-' ':' '.' '_'.
_DEVICE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-\.:]*$")
# "LA-L2-CN01/VA01:DEVSW001-E001"; reserved labels such as "真空预留2" do not
# match and become reserved-slot facts instead of cable entities.
_CABLE_ID = re.compile(r"^\S+/\S+:\S+-E\d+$")
# Cabinet codes end with CN-01 / CN-1 (column "所属机柜名称").
_CABINET_CODE = re.compile(r"CN[-_]?\d+$")
_PORT_SPAN = re.compile(r"^\s*(\d{1,3})\s*(?:-|~|～|至|—|–)\s*(\d{1,3})\s*$")
_PORT_ONE = re.compile(r"^\s*(\d{1,3})\s*$")
_VLAN = re.compile(r"^VLAN\d+$")

# PV names carry at least two colon-separated components, e.g.
# "DEMO-FAC:PV01:SIG".  At least one component holds an uppercase
# letter so the lowercase literal "pv" is not taken for a name.
_PV_TOKEN = (
    r"(?=[A-Za-z0-9_\-]*[A-Z])[A-Za-z][A-Za-z0-9_\-]*"
    r"(?::[A-Za-z0-9][A-Za-z0-9_\-\.]*)+"
)
# Only explicit wording joins a PV to a system; naming conventions do not.
_PV_SYSTEM_PATTERNS = (
    re.compile(
        rf"(?P<pv>{_PV_TOKEN})\s*"
        r"(?:属于|隶属于|归属(?:于)?)\s*"
        r"(?P<system>[^\s，。；;、]{1,30}?系统)"
    ),
    re.compile(
        r"(?P<system>[^\s，。；;、]{1,30}?系统)\s*(?:中|内|下)?的?\s*"
        rf"(?:控制)?PV\s*(?:名称|名)?\s*(?:为|是|：|:)\s*(?P<pv>{_PV_TOKEN})"
    ),
)
_PV_HEADERS = ("pv", "变量名", "变量")
_SYSTEM_HEADERS = ("系统", "所属系统", "子系统")

_CHUNK_LOCATOR = {
    "paragraph": "paragraph",
    "list_item": "paragraph",
    "heading": "paragraph",
    "formula": "paragraph",
    "code": "paragraph",
    "slide": "slide",
    "pdf_page": "pdf_page",
    "section": "section",
    "line_range": "paragraph",
}

_CELL_ASSIGNMENT = (("comparator_basis", "table_cell_assignment"),)
_UNRESOLVED = ("scope_status", "unresolved")
# Reserved-slot labels: "电源预留3", "机械真空预留1", "空12", "备用2".
_RESERVED_LABEL = re.compile(r"预留|备用|^空\d+$")


# --------------------------------------------------------------------------
# Small value objects
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Row:
    """One data row of a connectivity table, with its verbatim source line."""

    values: dict[str, str]
    line: str
    row_number: int
    table_block_id: str
    sheet: str
    locator_label: str
    chunk_id: str
    revision_id: str
    source_role: str
    group: str = ""
    title_line: str = ""

    def value(self, header: str) -> str:
        return self.values.get(header, "").strip()


@dataclass(frozen=True)
class _Span:
    raw: str
    value_kind: str
    comparator: str
    number: float
    low: float
    high: float
    extra: tuple[tuple[str, str], ...]


class _Collector:
    """Facts keyed by deterministic id; identical evidence is kept once."""

    def __init__(self) -> None:
        self.facts: dict[str, Fact] = {}

    def add(
        self,
        *,
        fact_type: str,
        subject: EntityRef,
        attribute: str | None,
        raw_value: str,
        value_kind: str,
        comparator: str,
        citation: Citation,
        object_ref: EntityRef | None = None,
        number=UNKNOWN,
        low=UNKNOWN,
        high=UNKNOWN,
        evidence_role: str = "fact_support",
        extra: tuple[tuple[str, str], ...] = (),
    ) -> None:
        fact_attribute = UNKNOWN if attribute is None else attribute
        object_value = object_ref if object_ref is not None else UNKNOWN
        fact_id = make_fact_id(
            layer=LAYER,
            fact_type=fact_type,
            subject_raw=subject.raw_id,
            attribute="" if fact_attribute is UNKNOWN else fact_attribute,
            object_raw=(
                object_value.raw_id if isinstance(object_value, EntityRef) else ""
            ),
            raw_value=raw_value,
            revision_id=citation.revision_id,
            locator_label=citation.locator_label,
            excerpt=citation.excerpt,
        )
        if fact_id in self.facts:
            return
        unknown = []
        if fact_attribute is UNKNOWN:
            unknown.append("attribute")
        unknown.append("unit")
        unknown.append("conditions")
        self.facts[fact_id] = Fact(
            fact_id=fact_id,
            layer=LAYER,
            fact_type=fact_type,
            subject=subject,
            attribute=fact_attribute,
            raw_value=raw_value,
            value_kind=value_kind,
            comparator=comparator,
            revision_id=citation.revision_id,
            source_role=citation.source_role,
            evidence_role=evidence_role,
            citation=citation,
            object_ref=object_value,
            number=number,
            low=low,
            high=high,
            unknown_fields=tuple(sorted(set(unknown))),
            extra=extra,
            extracted_by=EXTRACTOR,
        )


# --------------------------------------------------------------------------
# Entity factories.  Every raw_id is a verbatim fragment of the source.
# --------------------------------------------------------------------------


def _cabinet(raw: str) -> EntityRef:
    return EntityRef(
        kind="cabinet",
        raw_id=raw,
        keys=(IdentityKey(name="cabinet", value=raw, basis="whole"),),
    )


def _split_cabinet_device(text: str) -> tuple[str, str] | None:
    match = _CABINET_DEVICE.match(text)
    if not match:
        return None
    cabinet = match.group("cabinet").strip()
    device = match.group("device").strip()
    if not cabinet or not device or not _DEVICE_TOKEN.match(device):
        return None
    return cabinet, device


def _device_keys(
    raw: str, whole_basis: str
) -> tuple[IdentityKey, ...]:
    """Identity components of a device reference.

    ``device_id`` is always the short name (the token after the last colon, or
    the whole value); ``device_path`` keeps the full printed path when the two
    differ, so the same raw value yields the same key values everywhere.
    """

    if ":" in raw:
        code = raw.rsplit(":", 1)[1]
        if code and code != raw and _DEVICE_TOKEN.match(code):
            return (
                IdentityKey(
                    name="device_id", value=code, basis="explicit_in_text"
                ),
                IdentityKey(name="device_path", value=raw, basis="whole"),
            )
    return (IdentityKey(name="device_id", value=raw, basis=whole_basis),)


def _device_in_cabinet(
    device: str, cabinet: str, scope_source: str, cabinet_basis: str
) -> EntityRef:
    keys = _device_keys(device, "parenthesized") + (
        IdentityKey(name="cabinet", value=cabinet, basis=cabinet_basis),
    )
    return EntityRef(
        kind="device",
        raw_id=device,
        scope=cabinet,
        scope_source=scope_source,
        keys=keys,
    )


def _device_from_path(
    raw: str, cabinet: str | None, scope_source: str | None
) -> EntityRef:
    keys = _device_keys(raw, "whole")
    if cabinet and scope_source:
        return EntityRef(
            kind="device",
            raw_id=raw,
            scope=cabinet,
            scope_source=scope_source,
            keys=keys,
        )
    return EntityRef(kind="device", raw_id=raw, keys=keys)


def _cabinet_key(raw: str) -> str:
    """Normalised comparison key for a cabinet, never used as a raw value.

    ``LA-`` is dropped, a trailing ``柜`` is dropped, case is folded and every
    separator is removed, so ``L4:CN-13柜`` and ``LA-L4:CN-13`` share a key.
    """

    text = raw.strip().casefold()
    if text.endswith("柜"):
        text = text[:-1]
    text = re.sub(r"^la[-_\s]*", "", text)
    return re.sub(r"[^0-9a-z]", "", text)


def _cabinet_extra(raw: str) -> tuple[tuple[str, str], ...]:
    key = _cabinet_key(raw)
    return (("cabinet_key", key),) if key else ()


def _cable(raw: str, cabinet: str | None, scope_source: str | None) -> EntityRef:
    key = IdentityKey(name="cable_id", value=raw, basis="whole")
    if cabinet and scope_source:
        return EntityRef(
            kind="cable",
            raw_id=raw,
            scope=cabinet,
            scope_source=scope_source,
            keys=(key,),
        )
    return EntityRef(kind="cable", raw_id=raw, keys=(key,))


def _vlan(raw: str) -> EntityRef:
    return EntityRef(
        kind="vlan",
        raw_id=raw,
        keys=(IdentityKey(name="vlan", value=raw, basis="whole"),),
    )


def _system(raw: str) -> EntityRef:
    return EntityRef(
        kind="system",
        raw_id=raw,
        keys=(IdentityKey(name="system", value=raw, basis="whole"),),
    )


def _pv(raw: str) -> EntityRef:
    return EntityRef(
        kind="pv",
        raw_id=raw,
        keys=(IdentityKey(name="pv", value=raw, basis="whole"),),
    )


# --------------------------------------------------------------------------
# Value parsing
# --------------------------------------------------------------------------


def _port_span(raw: str) -> _Span | None:
    match = _PORT_SPAN.match(raw)
    if match:
        low, high = sorted((int(match.group(1)), int(match.group(2))))
        return _Span(
            raw=raw,
            value_kind="range",
            comparator="range",
            number=UNKNOWN,
            low=float(low),
            high=float(high),
            extra=(("range_basis", "explicit_numeric_range"),),
        )
    match = _PORT_ONE.match(raw)
    if match:
        return _Span(
            raw=raw,
            value_kind="number",
            comparator="eq",
            number=float(match.group(1)),
            low=UNKNOWN,
            high=UNKNOWN,
            extra=(("number_basis", "explicit_numeric_port"),),
        )
    return None


# --------------------------------------------------------------------------
# Citations
# --------------------------------------------------------------------------


def _short(block_id: str) -> str:
    return block_id.rsplit(":", 1)[-1][:10]


def _row_citation(row: _Row, locator_kind: str = "table_row") -> Citation:
    return Citation(
        chunk_id=row.chunk_id,
        revision_id=row.revision_id,
        locator_kind=locator_kind,
        locator_label=row.locator_label,
        excerpt=row.line,
        source_role=row.source_role,
        table_block_id=row.table_block_id,
        row_number=row.row_number,
    )


def _title_citation(
    *,
    chunk_id: str,
    revision_id: str,
    source_role: str,
    table_block_id: str,
    sheet: str,
    row_number: int,
    excerpt: str,
) -> Citation:
    return Citation(
        chunk_id=chunk_id,
        revision_id=revision_id,
        locator_kind="table_title",
        locator_label=f"{sheet}!{_short(table_block_id)}!title{row_number}",
        excerpt=excerpt,
        source_role=source_role,
        table_block_id=table_block_id,
        row_number=row_number,
    )


# --------------------------------------------------------------------------
# Row extraction
# --------------------------------------------------------------------------


_RESERVED_EXTRA_NAMES = {
    "所属机柜名称": "cabinet",
    "所属设备": "device",
    "电缆功能": "cable_function",
    "电缆类型": "cable_type",
    "始端设备位置或机柜编号": "start_endpoint",
    "终端设备位置或机柜编号": "end_endpoint",
    "设备用途": "device_use",
    "类别": "category",
    "备注": "remark",
}


def _reserved_row(collector: _Collector, row: _Row) -> None:
    """A row whose cable column holds a reserved-slot label, not a cable id.

    ``raw_value`` is the first non-empty cell as printed, so it is always a
    contiguous fragment of the row's verbatim line.  Any further non-empty
    cells (and the serial number) are kept in ``extra``.  The subject is the
    cabinet range printed by the table, never a cable entity.
    """

    values = [
        (header, value.strip())
        for header, value in row.values.items()
        if header not in {"序号", "分组"} and value.strip()
    ]
    if not values:
        return
    _, label = values[0]
    cabinet_text = row.group or row.value("所属机柜名称")
    if not cabinet_text:
        return
    match = _CABINET_DEVICE.match(cabinet_text)
    if match is not None:
        # The range as printed, without the trailing note the title may add.
        range_text = match.group(0).strip()
        cabinet = match.group("cabinet").strip()
        subject = EntityRef(
            kind="cabinet",
            raw_id=range_text,
            scope=cabinet,
            scope_source="table_title",
            keys=(IdentityKey(name="cabinet", value=cabinet, basis="prefix"),),
        )
    else:
        cabinet = cabinet_text
        subject = EntityRef(
            kind="cabinet",
            raw_id=cabinet_text,
            scope=cabinet,
            scope_source="row_column",
            keys=(
                IdentityKey(name="cabinet", value=cabinet_text, basis="whole"),
            ),
        )
    extra = [
        ("comparator_basis", "table_cell_assignment"),
        ("column_header", "电缆编号"),
    ]
    for header, value in values[1:]:
        extra.append((_RESERVED_EXTRA_NAMES.get(header, "cell"), value))
    serial = row.value("序号")
    if serial:
        extra.append(("row_serial", serial))
    if row.title_line:
        # The subject comes from the table title, so keep that line with the
        # row citation for review.
        extra.append(("table_title", row.title_line))
    extra.extend(_cabinet_extra(cabinet))
    # Only reserved/empty/standby labels are slots; other text is an annotation.
    attribute = (
        "reserved_slot" if _RESERVED_LABEL.search(label) else "cable_number_note"
    )
    collector.add(
        fact_type=_FACT_ATTRIBUTE,
        subject=subject,
        attribute=attribute,
        raw_value=label,
        value_kind="text",
        comparator="eq",
        citation=_row_citation(row),
        extra=tuple(extra),
    )


def _cable_row(collector: _Collector, row: _Row) -> None:
    cable_raw = row.value("电缆编号")
    if not cable_raw:
        return
    if not _CABLE_ID.match(cable_raw):
        # Reserved labels ("真空预留2") are not cables; keep their slot text.
        _reserved_row(collector, row)
        return
    cabinet_cell = row.value("所属机柜名称")
    cabinet_raw = cabinet_cell
    scope_source = "row_column" if cabinet_cell else ""
    if not cabinet_raw and row.group:
        split = _split_cabinet_device(row.group)
        if split:
            cabinet_raw = split[0]
            scope_source = "table_title"
    subject = _cable(cable_raw, cabinet_raw or None, scope_source or None)
    start_raw = row.value("始端设备位置或机柜编号")
    end_raw = row.value("终端设备位置或机柜编号")
    if cabinet_cell:
        collector.add(
            fact_type=_FACT_RELATION,
            subject=subject,
            attribute="cable_membership",
            raw_value=cabinet_cell,
            value_kind="text",
            comparator="eq",
            citation=_row_citation(row),
            object_ref=_cabinet(cabinet_cell),
            extra=_CELL_ASSIGNMENT + _cabinet_extra(cabinet_cell),
        )
    device_raw = row.value("所属设备")
    if device_raw:
        device_extra = _CELL_ASSIGNMENT + (("column_header", "所属设备"),)
        if cabinet_cell:
            device_object = _device_from_path(
                device_raw, cabinet_cell, "row_column"
            )
            device_extra += _cabinet_extra(cabinet_cell)
        else:
            device_object = _device_from_path(device_raw, None, None)
            device_extra += (_UNRESOLVED,)
        collector.add(
            fact_type=_FACT_RELATION,
            subject=subject,
            attribute="device_membership",
            raw_value=device_raw,
            value_kind="text",
            comparator="eq",
            citation=_row_citation(row),
            object_ref=device_object,
            extra=device_extra,
        )
    start = _endpoint_entity(start_raw) if start_raw else None
    if start is not None:
        start_extra = (
            ("comparator_basis", "table_cell_assignment"),
            ("endpoint_role", "start"),
            ("column_header", "始端设备位置或机柜编号"),
        )
        if start.kind == "cabinet":
            start_extra += _cabinet_extra(start_raw)
        if cabinet_raw and _cabinet_key(cabinet_raw):
            start_extra += (("cable_cabinet_key", _cabinet_key(cabinet_raw)),)
        collector.add(
            fact_type=_FACT_RELATION,
            subject=subject,
            attribute="cable_endpoint_start",
            raw_value=start_raw,
            value_kind="text",
            comparator="eq",
            citation=_row_citation(row),
            object_ref=start,
            extra=start_extra,
        )
    end = _endpoint_entity(end_raw) if end_raw else None
    if end is not None:
        end_extra = (
            ("comparator_basis", "table_cell_assignment"),
            ("endpoint_role", "end"),
            ("column_header", "终端设备位置或机柜编号"),
        )
        if end.kind == "cabinet":
            end_extra += _cabinet_extra(end_raw)
        elif end.scope is UNKNOWN:
            end_extra += (_UNRESOLVED,)
        collector.add(
            fact_type=_FACT_RELATION,
            subject=subject,
            attribute="cable_endpoint_end",
            raw_value=end_raw,
            value_kind="text",
            comparator="eq",
            citation=_row_citation(row),
            object_ref=end,
            extra=end_extra,
        )
    for header, attribute in (
        ("电缆功能", "cable_function"),
        ("电缆类型", "cable_type"),
        ("类别", "network_category"),
        ("备注", "remark"),
    ):
        value = row.value(header)
        if not value:
            continue
        collector.add(
            fact_type=_FACT_ATTRIBUTE,
            subject=subject,
            attribute=attribute,
            raw_value=value,
            value_kind="text",
            comparator="eq",
            citation=_row_citation(row),
            extra=(
                ("comparator_basis", "table_cell_assignment"),
                ("column_header", header),
            )
            + (_cabinet_extra(cabinet_raw) if cabinet_raw else ()),
        )
    use = row.value("设备用途")
    if use and end is not None:
        use_extra = (
            ("comparator_basis", "table_cell_assignment"),
            ("column_header", "设备用途"),
        )
        if end.kind == "cabinet":
            use_extra += _cabinet_extra(end_raw)
        elif end.scope is UNKNOWN:
            use_extra = use_extra + (_UNRESOLVED,)
        collector.add(
            fact_type=_FACT_ATTRIBUTE,
            subject=end,
            attribute="device_use",
            raw_value=use,
            value_kind="text",
            comparator="eq",
            citation=_row_citation(row),
            extra=use_extra,
        )


def _endpoint_entity(raw: str) -> EntityRef:
    if _CABINET_CODE.search(raw):
        return _cabinet(raw)
    # "终端设备位置或机柜编号" does not state the device's own cabinet.
    return _device_from_path(raw, None, None)


def _switch_row(collector: _Collector, row: _Row) -> None:
    split = _split_cabinet_device(row.value("设备"))
    if split is None:
        return
    cabinet, device = split
    subject = _device_in_cabinet(device, cabinet, "row_column", "prefix")
    span = _port_span(row.value("端口")) if row.value("端口") else None
    system_raw = row.value("系统")
    vlan_raw = row.value("网络分配")
    cabinet_extra = _cabinet_extra(cabinet)
    if span is not None:
        # The port span stays available even when it is a reserved row.
        collector.add(
            fact_type=_FACT_ATTRIBUTE,
            subject=subject,
            attribute="port_span",
            raw_value=span.raw,
            value_kind=span.value_kind,
            comparator=span.comparator,
            citation=_row_citation(row),
            number=span.number,
            low=span.low,
            high=span.high,
            extra=span.extra
            + (
                ("comparator_basis", "table_cell_assignment"),
                ("column_header", "端口"),
            )
            + cabinet_extra,
        )
    # "预留" in the 系统 column is a reservation label, not a system name.
    reserved_system = system_raw == "预留"
    if system_raw:
        # Keep the printed label even when it is not a system name.
        collector.add(
            fact_type=_FACT_ATTRIBUTE,
            subject=subject,
            attribute="port_system_label",
            raw_value=system_raw,
            value_kind="text",
            comparator="eq",
            citation=_row_citation(row),
            extra=(
                ("comparator_basis", "table_cell_assignment"),
                ("column_header", "系统"),
            )
            + cabinet_extra,
        )
    if span is not None and system_raw and not reserved_system:
        collector.add(
            fact_type=_FACT_RELATION,
            subject=subject,
            attribute="port_system",
            raw_value=span.raw,
            value_kind=span.value_kind,
            comparator=span.comparator,
            citation=_row_citation(row),
            object_ref=_system(system_raw),
            number=span.number,
            low=span.low,
            high=span.high,
            extra=span.extra
            + (
                ("comparator_basis", "table_cell_assignment"),
                ("column_header", "端口"),
                ("system", system_raw),
            )
            + cabinet_extra,
        )
    if reserved_system:
        reserved_extra = [
            ("comparator_basis", "table_cell_assignment"),
            ("column_header", "系统"),
        ]
        if span is not None:
            reserved_extra.append(("port", span.raw))
        reserved_extra.extend(cabinet_extra)
        collector.add(
            fact_type=_FACT_ATTRIBUTE,
            subject=subject,
            attribute="reserved_slot",
            raw_value=system_raw,
            value_kind="text",
            comparator="eq",
            citation=_row_citation(row),
            extra=tuple(reserved_extra),
        )
    if span is not None and _VLAN.match(vlan_raw):
        collector.add(
            fact_type=_FACT_RELATION,
            subject=subject,
            attribute="port_assignment",
            raw_value=span.raw,
            value_kind=span.value_kind,
            comparator=span.comparator,
            citation=_row_citation(row),
            object_ref=_vlan(vlan_raw),
            number=span.number,
            low=span.low,
            high=span.high,
            extra=span.extra
            + (
                ("comparator_basis", "table_cell_assignment"),
                ("column_header", "网络分配"),
                ("system", system_raw),
            )
            + cabinet_extra,
        )
    if vlan_raw:
        attribute = "vlan_name" if _VLAN.match(vlan_raw) else "network_allocation"
        kind = "enum" if _VLAN.match(vlan_raw) else "text"
        extra = [
            ("comparator_basis", "table_cell_assignment"),
            ("column_header", "网络分配"),
        ]
        if system_raw:
            extra.append(("system", system_raw))
        extra.extend(cabinet_extra)
        collector.add(
            fact_type=_FACT_ATTRIBUTE,
            subject=subject,
            attribute=attribute,
            raw_value=vlan_raw,
            value_kind=kind,
            comparator="eq",
            citation=_row_citation(row),
            extra=tuple(extra),
        )


# --------------------------------------------------------------------------
# Table-level facts (cabinet membership printed in the title / first row)
# --------------------------------------------------------------------------


def _table_kind(headers: tuple[str, ...]) -> str | None:
    if all(header in headers for header in _CABLE_HEADERS):
        return "cable"
    if all(header in headers for header in _SWITCH_HEADERS):
        return "switch"
    return None


def _line_with(chunk_text: str, needle: str) -> str | None:
    """The one verbatim line of the chunk that prints ``needle``."""

    if not needle:
        return None
    matches = [
        line.strip() for line in chunk_text.splitlines() if needle in line
    ]
    if len(matches) == 1 and matches[0]:
        return matches[0]
    return None


def _title_row_number(scope: CorpusScope, revision_id: str, block_id: str) -> int:
    parsed = scope.parsed_by_revision.get(revision_id)
    if parsed is None:
        return 1
    for block in parsed.blocks:
        if block.block_id == block_id:
            metadata = dict(block.metadata)
            value = metadata.get("title_row", "")
            if value.isdigit():
                return int(value)
            return 1
    return 1


def _membership_from_title(
    collector: _Collector,
    scope: CorpusScope,
    rows: tuple[TableRecord, ...],
    texts: dict[str, str],
) -> str | None:
    """One membership fact from a cable table's printed title.

    Returns the title cabinet so callers can fall back to it for scope, or
    ``None`` when the title does not print a cabinet/device pair.
    """

    first = rows[0]
    group = ""
    for record in rows:
        values = _record_values(record)
        group = values.get("分组", "").strip()
        if group:
            break
    split = _split_cabinet_device(group) if group else None
    if split is None:
        return None
    cabinet, device = split
    text = texts.get(first.chunk_id, "")
    title_line = _line_with(text, group)
    if title_line is None:
        return None
    row_number = _title_row_number(scope, first.revision_id, first.table_block_id)
    citation = _title_citation(
        chunk_id=first.chunk_id,
        revision_id=first.revision_id,
        source_role=revision_source_role(scope, first.revision_id),
        table_block_id=first.table_block_id,
        sheet=first.sheet,
        row_number=row_number,
        excerpt=title_line,
    )
    collector.add(
        fact_type=_FACT_RELATION,
        subject=_device_in_cabinet(device, cabinet, "table_title", "prefix"),
        attribute="cabinet_membership",
        raw_value=group,
        value_kind="text",
        comparator="eq",
        citation=citation,
        object_ref=_cabinet(cabinet),
        evidence_role="header",
        extra=(
            ("comparator_basis", "table_cell_assignment"),
            ("title_source", "table_title"),
        )
        + _cabinet_extra(cabinet),
    )
    return cabinet


def _membership_from_row(
    collector: _Collector, row: _Row, kind: str
) -> None:
    if kind == "switch":
        split = _split_cabinet_device(row.value("设备"))
        if split is None:
            return
        cabinet, device = split
        collector.add(
            fact_type=_FACT_RELATION,
            subject=_device_in_cabinet(device, cabinet, "row_column", "prefix"),
            attribute="cabinet_membership",
            raw_value=row.value("设备"),
            value_kind="text",
            comparator="eq",
            citation=_row_citation(row),
            object_ref=_cabinet(cabinet),
            extra=(
                ("comparator_basis", "table_cell_assignment"),
                ("column_header", "设备"),
            )
            + _cabinet_extra(cabinet),
        )
        return
    device_raw = row.value("所属设备")
    cabinet_cell = row.value("所属机柜名称")
    if not device_raw or not cabinet_cell:
        return
    collector.add(
        fact_type=_FACT_RELATION,
        subject=_device_from_path(device_raw, cabinet_cell, "row_column"),
        attribute="cabinet_membership",
        raw_value=device_raw,
        value_kind="text",
        comparator="eq",
        citation=_row_citation(row),
        object_ref=_cabinet(cabinet_cell),
        extra=(
            ("comparator_basis", "table_cell_assignment"),
            ("column_header", "所属设备"),
        )
        + _cabinet_extra(cabinet_cell),
    )


# --------------------------------------------------------------------------
# Record and markdown adapters
# --------------------------------------------------------------------------


def _record_values(record: TableRecord) -> dict[str, str]:
    return {
        header: value
        for header, (_, value) in zip(record.headers, record.cells)
    }


def _record_row(
    record: TableRecord,
    chunk_text: str,
    source_role: str,
    title_line: str = "",
) -> _Row | None:
    line = verbatim_row_line(record, chunk_text)
    if line is None:
        return None
    values = _record_values(record)
    return _Row(
        values=values,
        line=line,
        row_number=record.row_number,
        table_block_id=record.table_block_id,
        sheet=record.sheet,
        locator_label=(
            f"{record.sheet}!{_short(record.table_block_id)}"
            f"!r{record.row_number}"
        ),
        chunk_id=record.chunk_id,
        revision_id=record.revision_id,
        source_role=source_role,
        group=values.get("分组", "").strip(),
        title_line=title_line,
    )


def _markdown_row(
    table, row, source_role: str  # noqa: ANN001 - corpus dataclasses
) -> _Row:
    values = {
        header: cell
        for header, cell in zip(table.header, row.cells)
    }
    return _Row(
        values=values,
        line=row.line,
        row_number=row.row_number,
        table_block_id=table.block_id,
        sheet=table.label_prefix.split("!", 1)[0],
        locator_label=f"{table.label_prefix}r{row.row_number}",
        chunk_id=table.chunk_id,
        revision_id=table.revision_id,
        source_role=source_role,
    )


def _record_facts(
    collector: _Collector,
    scope: CorpusScope,
    revision_id: str,
    records: tuple[TableRecord, ...],
    texts: dict[str, str],
    source_role: str,
) -> None:
    grouped: dict[str, list[TableRecord]] = {}
    for record in records:
        grouped.setdefault(record.table_block_id, []).append(record)
    for block_id in sorted(grouped):
        rows = tuple(grouped[block_id])
        kind = _table_kind(rows[0].headers)
        if kind is None:
            continue
        if kind == "cable":
            _membership_from_title(collector, scope, rows, texts)
        group = ""
        for record in rows:
            group = _record_values(record).get("分组", "").strip()
            if group:
                break
        title_line = (
            _line_with(texts.get(rows[0].chunk_id, ""), group) if group else ""
        ) or ""
        for record in rows:
            candidate = _record_row(
                record,
                texts.get(record.chunk_id, ""),
                source_role,
                title_line,
            )
            if candidate is None:
                continue
            if kind == "switch" or (
                candidate.value("所属设备")
                and candidate.value("所属机柜名称")
            ):
                _membership_from_row(collector, candidate, kind)
                break
        for record in rows:
            row = _record_row(
                record,
                texts.get(record.chunk_id, ""),
                source_role,
                title_line,
            )
            if row is None:
                continue
            if kind == "cable":
                _cable_row(collector, row)
            else:
                _switch_row(collector, row)


def _markdown_facts(
    collector: _Collector, chunk, revision_id: str, source_role: str
) -> None:  # noqa: ANN001 - KnowledgeChunk
    for table in markdown_tables(chunk, revision_id):
        kind = _table_kind(table.header)
        if kind in {"cable", "switch"}:
            for raw_row in table.rows:
                row = _markdown_row(table, raw_row, source_role)
                if kind == "cable":
                    _cable_row(collector, row)
                else:
                    _switch_row(collector, row)
            continue
        pv_index = _header_index(table.header, _PV_HEADERS)
        system_index = _header_index(table.header, _SYSTEM_HEADERS)
        if pv_index is None or system_index is None:
            continue
        for raw_row in table.rows:
            pv_raw = _cell(raw_row.cells, pv_index)
            system_raw = _cell(raw_row.cells, system_index)
            if not pv_raw or not system_raw:
                continue
            if not re.fullmatch(_PV_TOKEN, pv_raw):
                continue
            row = _markdown_row(table, raw_row, source_role)
            collector.add(
                fact_type=_FACT_RELATION,
                subject=_pv(pv_raw),
                attribute="pv_system",
                raw_value=system_raw,
                value_kind="text",
                comparator="eq",
                citation=_row_citation(row),
                object_ref=_system(system_raw),
                extra=(
                    ("comparator_basis", "table_cell_assignment"),
                    ("relation_basis", "table_columns"),
                ),
            )


def _header_index(
    headers: tuple[str, ...], names: tuple[str, ...]
) -> int | None:
    for index, header in enumerate(headers):
        text = header.strip().casefold()
        for name in names:
            if name.casefold() in text:
                return index
    return None


def _cell(cells: tuple[str, ...], index: int) -> str:
    return cells[index].strip() if index < len(cells) else ""


# --------------------------------------------------------------------------
# Paragraph PV/system facts (only when the prose says so)
# --------------------------------------------------------------------------


def _paragraph_pv_facts(
    collector: _Collector, chunk, revision_id: str, source_role: str
) -> None:  # noqa: ANN001 - KnowledgeChunk
    locator_kind = _CHUNK_LOCATOR.get(chunk.effective_position_kind)
    if locator_kind is None:
        return
    label = chunk.position_label or chunk.chunk_id
    for raw_line in chunk.text.splitlines():
        line = raw_line.strip()
        if not line or len(line) > 300:
            continue
        for pattern in _PV_SYSTEM_PATTERNS:
            for match in pattern.finditer(line):
                pv_raw = match.group("pv")
                system_raw = match.group("system")
                if not re.fullmatch(_PV_TOKEN, pv_raw):
                    continue
                citation = Citation(
                    chunk_id=chunk.chunk_id,
                    revision_id=revision_id,
                    locator_kind=locator_kind,
                    locator_label=label,
                    excerpt=line,
                    source_role=source_role,
                    page_start=(
                        chunk.page_start
                        if chunk.effective_position_kind == "pdf_page"
                        else None
                    ),
                    page_end=(
                        chunk.page_end
                        if chunk.effective_position_kind == "pdf_page"
                        else None
                    ),
                )
                collector.add(
                    fact_type=_FACT_RELATION,
                    subject=_pv(pv_raw),
                    attribute="pv_system",
                    raw_value=system_raw,
                    value_kind="text",
                    comparator="eq",
                    citation=citation,
                    object_ref=_system(system_raw),
                    extra=(
                        ("comparator_basis", "explicit_in_text"),
                        ("relation_basis", "explicit_wording"),
                    ),
                )


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def extract(scope: CorpusScope) -> list[Fact]:
    """Every connectivity/membership fact the scoped revisions print."""

    collector = _Collector()
    texts = scope.chunk_text()
    for revision_id in scope.revision_ids():
        source_role = revision_source_role(scope, revision_id)
        if not source_role:
            continue
        records = scope.records_by_revision.get(revision_id, ())
        if records:
            _record_facts(
                collector, scope, revision_id, records, texts, source_role
            )
        for chunk in scope.chunks_by_revision.get(revision_id, ()):
            if chunk.effective_position_kind == "cell_range":
                # Already covered by TableRecord; parsing its markdown again
                # would duplicate every row.
                continue
            _markdown_facts(collector, chunk, revision_id, source_role)
            _paragraph_pv_facts(collector, chunk, revision_id, source_role)
    return list(collector.facts.values())
