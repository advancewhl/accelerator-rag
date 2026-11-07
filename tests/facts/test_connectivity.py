"""Contract tests for the W2 connectivity/membership fact layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from accelerator_rag.corpus.table_records import TableRecord
from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.facts import connectivity
from accelerator_rag.facts.corpus import BASE, load_scope
from accelerator_rag.facts.schema import UNKNOWN, check_citations

CABLE_HEADERS = (
    "序号",
    "电缆编号",
    "所属机柜名称",
    "所属设备",
    "电缆功能",
    "电缆类型",
    "始端设备位置或机柜编号",
    "安装路径、通过地沟、桥架等编号 （由工艺填写）",
    "终端设备位置或机柜编号",
    "设备用途",
    "电缆长度 （由工艺估算）",
    "工艺铺设/厂家铺设",
    "类别",
    "备注",
)
SWITCH_HEADERS = ("设备", "端口", "系统", "网络分配")
_CABLE_TITLE = "总控集成系统（网络）电缆安装统计表"


class _Scope:
    """Minimal stand-in for ``CorpusScope`` used by the in-memory samples."""

    def __init__(self, chunks, records, revisions):
        self.revisions = {
            revision_id: {"evidence_role": "background_reference"}
            for revision_id in revisions
        }
        self.chunks_by_revision = dict(chunks)
        self.records_by_revision = dict(records)
        self.parsed_by_revision = {}

    def revision_ids(self):
        return tuple(sorted(self.revisions))

    def records(self):
        for revision_id in self.revision_ids():
            yield from self.records_by_revision.get(revision_id, ())

    def chunk_text(self):
        return {
            chunk.chunk_id: chunk.text
            for chunks in self.chunks_by_revision.values()
            for chunk in chunks
        }


def _chunk(chunk_id, text, *, position_kind="cell_range", label=""):
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=chunk_id.split(":")[0],
        document_title="sample",
        text=text,
        source_path="data/l0_raw/sample.xlsx",
        document_version="v1",
        language="zh",
        category="test",
        topic="connectivity",
        page_start=1,
        page_end=1,
        position_kind=position_kind,
        position_label=label,
    )


def _table_text(title, headers, rows):
    lines = [title, " | ".join(headers), " | ".join(["---"] * len(headers))]
    for row in rows:
        lines.append(" | ".join(row.get(header, "") for header in headers))
    return "\n".join(lines)


def _record(
    *,
    revision_id,
    block_id,
    sheet,
    row_number,
    headers,
    values,
    group="",
    chunk_id="",
):
    full_headers = headers + (("分组",) if group else ())
    cells = []
    for index, header in enumerate(headers):
        letter = chr(ord("A") + index)
        cells.append((letter, values.get(header, "")))
    if group:
        cells.append(("_group", group))
    return TableRecord(
        record_id=f"{block_id}:r{row_number}",
        revision_id=revision_id,
        table_block_id=block_id,
        sheet=sheet,
        row_number=row_number,
        headers=full_headers,
        cells=tuple(cells),
        row_text=" | ".join(value for _, value in cells if value),
        chunk_id=chunk_id,
    )


def _cable_scope(
    *,
    group="",
    cabinet="LA-L2:CN-01",
    device="LA-L2-CN:DEVSW001",
    cable="L2-CN01/VA01:DEVSW001-E001",
    start="LA-L2:CN-01",
    end="LA-L2:VA-01",
    use="真空 串口服务器",
    function="网络连接",
    cable_type="网线",
    category="设备网",
    remark="",
    revision_id="rev-a",
    block_id="rev-a:b:aaa",
    chunk_id="rev-a:cable",
    row_number=6,
):
    values = {
        "序号": "1",
        "电缆编号": cable,
        "所属机柜名称": cabinet,
        "所属设备": device,
        "电缆功能": function,
        "电缆类型": cable_type,
        "始端设备位置或机柜编号": start,
        "终端设备位置或机柜编号": end,
        "设备用途": use,
        "类别": category,
        "备注": remark,
    }
    title = f"{_CABLE_TITLE} · {group}" if group else _CABLE_TITLE
    text = _table_text(title, CABLE_HEADERS, [values])
    chunk = _chunk(chunk_id, text)
    record = _record(
        revision_id=revision_id,
        block_id=block_id,
        sheet="L2+BC2+EMIT",
        row_number=row_number,
        headers=CABLE_HEADERS,
        values=values,
        group=group,
        chunk_id=chunk_id,
    )
    scope = _Scope(
        chunks={revision_id: (chunk,)},
        records={revision_id: (record,)},
        revisions=[revision_id],
    )
    return scope, record


def _facts(scope):
    facts = connectivity.extract(scope)
    assert check_citations(facts, scope.chunk_text()) == []
    return facts


def _by_attribute(facts, attribute):
    return [fact for fact in facts if fact.attribute == attribute]


def test_title_scope_is_filled_with_source():
    scope, _ = _cable_scope(
        group="FEL1-CN01柜（DEVSW001）", cabinet="", start="UN-FEL1:CN-01"
    )
    facts = _facts(scope)

    cable = next(
        fact
        for fact in _by_attribute(facts, "cable_endpoint_start")
    )
    assert cable.subject.raw_id == "L2-CN01/VA01:DEVSW001-E001"
    assert cable.subject.scope == "FEL1-CN01柜"
    assert cable.subject.scope_source == "table_title"
    assert cable.subject.scope is not UNKNOWN


def test_table_title_is_not_reported_as_column_header():
    scope, _ = _cable_scope(group="L2-CN11柜（DEVSW012）")
    facts = _facts(scope)

    titles = [f for f in facts if f.citation.locator_kind == "table_title"]
    assert len(titles) == 1
    fact = titles[0]
    assert fact.attribute == "cabinet_membership"
    assert fact.evidence_role == "header"
    assert fact.citation.table_block_id == "rev-a:b:aaa"
    assert fact.citation.row_number == 1
    assert fact.citation.excerpt.startswith(_CABLE_TITLE)
    assert fact.subject.raw_id in fact.citation.excerpt
    # A table title is not a column header; no table_header fact is produced.
    assert not [
        item for item in facts if item.citation.locator_kind == "table_header"
    ]


def test_missing_scope_stays_unknown_and_unresolved():
    scope, _ = _cable_scope(group="", cabinet="", end="UN-X:VA-01")
    facts = _facts(scope)

    endpoint = next(iter(_by_attribute(facts, "cable_endpoint_end")))
    assert endpoint.object_ref.scope is UNKNOWN
    assert endpoint.object_ref.scope_source is UNKNOWN
    assert ("scope_status", "unresolved") in endpoint.extra
    assert endpoint.subject.scope is UNKNOWN

    membership = next(iter(_by_attribute(facts, "device_membership")))
    assert membership.object_ref.scope is UNKNOWN
    assert ("scope_status", "unresolved") in membership.extra


def test_device_membership_object_takes_the_row_cabinet():
    scope, _ = _cable_scope(cabinet="LA-L2:CN-01")
    facts = _facts(scope)

    membership = next(iter(_by_attribute(facts, "device_membership")))
    assert membership.object_ref.raw_id == "LA-L2-CN:DEVSW001"
    assert membership.object_ref.scope == "LA-L2:CN-01"
    assert membership.object_ref.scope_source == "row_column"
    assert ("cabinet_key", "l2cn01") in membership.extra
    assert ("scope_status", "unresolved") not in membership.extra


def test_same_device_in_two_cabinets_is_not_merged():
    revision_id = "rev-a"
    chunks = []
    records = []
    for index, cabinet in enumerate(("A柜", "B柜")):
        group = f"{cabinet}（DEVSW001）"
        values = {
            "序号": str(index + 1),
            "电缆编号": f"{cabinet}/VA01:DEVSW001-E00{index + 1}",
            "所属机柜名称": f"LA-A:CN-0{index + 1}",
            "所属设备": "LA-A-CN:DEVSW001",
            "电缆功能": "网络连接",
            "电缆类型": "网线",
            "始端设备位置或机柜编号": f"LA-A:CN-0{index + 1}",
            "终端设备位置或机柜编号": f"LA-A:VA-0{index + 1}",
            "设备用途": "真空 串口服务器",
            "类别": "设备网",
        }
        block_id = f"{revision_id}:b:t{index}"
        chunk_id = f"{revision_id}:t{index}"
        chunks.append(
            _chunk(
                chunk_id,
                _table_text(f"{_CABLE_TITLE} · {group}", CABLE_HEADERS, [values]),
            )
        )
        records.append(
            _record(
                revision_id=revision_id,
                block_id=block_id,
                sheet="S",
                row_number=6,
                headers=CABLE_HEADERS,
                values=values,
                group=group,
                chunk_id=chunk_id,
            )
        )
    scope = _Scope(
        chunks={revision_id: tuple(chunks)},
        records={revision_id: tuple(records)},
        revisions=[revision_id],
    )
    facts = _facts(scope)

    memberships = [
        fact
        for fact in _by_attribute(facts, "cabinet_membership")
        if fact.subject.raw_id == "DEVSW001"
        and fact.citation.locator_kind == "table_title"
    ]
    assert len(memberships) == 2
    pairs = {
        (
            fact.subject.scope,
            fact.subject.scope_source,
            fact.object_ref.raw_id,
            fact.citation.table_block_id,
        )
        for fact in memberships
    }
    assert pairs == {
        ("A柜", "table_title", "A柜", f"{revision_id}:b:t0"),
        ("B柜", "table_title", "B柜", f"{revision_id}:b:t1"),
    }
    # The two references stay separate entities; no scope leaks across tables.
    for fact in memberships:
        assert fact.subject.scope == fact.object_ref.raw_id


def test_cable_endpoints_keep_verbatim_identifiers():
    scope, _ = _cable_scope(
        start="LA-L2:CN-01",
        end="LA-L2:VA-01",
        cable="L2-CN01/VA01:DEVSW001-E001",
    )
    facts = _facts(scope)

    start = next(iter(_by_attribute(facts, "cable_endpoint_start")))
    assert start.subject.raw_id == "L2-CN01/VA01:DEVSW001-E001"
    assert start.raw_value == "LA-L2:CN-01"
    assert start.object_ref.raw_id == "LA-L2:CN-01"
    assert start.object_ref.kind == "cabinet"

    end = next(iter(_by_attribute(facts, "cable_endpoint_end")))
    assert end.subject.raw_id == "L2-CN01/VA01:DEVSW001-E001"
    assert end.raw_value == "LA-L2:VA-01"
    assert end.object_ref.raw_id == "LA-L2:VA-01"
    assert end.object_ref.kind == "device"
    assert end.citation.locator_kind == "table_row"
    assert end.citation.row_number == 6
    assert end.citation.table_block_id == "rev-a:b:aaa"
    assert end.citation.excerpt in scope.chunk_text()["rev-a:cable"]


def _row_values(cable, device, start, end, serial):
    return {
        "序号": serial,
        "电缆编号": cable,
        "所属机柜名称": "LA-L2:CN-01",
        "所属设备": device,
        "电缆功能": "网络连接",
        "电缆类型": "网线",
        "始端设备位置或机柜编号": start,
        "终端设备位置或机柜编号": end,
        "设备用途": "真空 串口服务器",
        "类别": "设备网",
    }


def test_each_cable_row_has_cable_and_device_membership():
    revision_id = "rev-a"
    rows = [
        _row_values(
            "L2-CN01/VA01:DEVSW001-E001",
            "LA-L2-CN:DEVSW001",
            "LA-L2:CN-01",
            "LA-L2:VA-01",
            "1",
        ),
        _row_values(
            "L2-CN01/VA02:DEVSW002-E001",
            "LA-L2-CN:DEVSW002",
            "LA-L2:CN-01",
            "LA-L2:VA-02",
            "2",
        ),
    ]
    chunk_id = f"{revision_id}:cable"
    chunk = _chunk(
        chunk_id, _table_text(f"{_CABLE_TITLE} · L2-CN01柜（DEVSW001）", CABLE_HEADERS, rows)
    )
    records = tuple(
        _record(
            revision_id=revision_id,
            block_id=f"{revision_id}:b:m1",
            sheet="S",
            row_number=6 + index,
            headers=CABLE_HEADERS,
            values=values,
            group="L2-CN01柜（DEVSW001）",
            chunk_id=chunk_id,
        )
        for index, values in enumerate(rows)
    )
    scope = _Scope(
        chunks={revision_id: (chunk,)},
        records={revision_id: records},
        revisions=[revision_id],
    )
    facts = _facts(scope)

    devices = [fact for fact in facts if fact.attribute == "device_membership"]
    assert len(devices) == 2
    expected = {6: "LA-L2-CN:DEVSW001", 7: "LA-L2-CN:DEVSW002"}
    for fact in devices:
        assert fact.object_ref.raw_id == expected[fact.citation.row_number]
        assert fact.raw_value == expected[fact.citation.row_number]
        assert fact.raw_value in fact.citation.excerpt
        assert fact.subject.kind == "cable"
        assert fact.subject.scope == "LA-L2:CN-01"
        assert fact.object_ref.scope == "LA-L2:CN-01"
        assert fact.object_ref.scope_source == "row_column"

    cabinets = [
        fact
        for fact in facts
        if fact.attribute == "cable_membership" and fact.subject.kind == "cable"
    ]
    assert len(cabinets) == 2
    for fact in cabinets:
        assert fact.raw_value == "LA-L2:CN-01"
        assert fact.raw_value in fact.citation.excerpt
        assert fact.object_ref.raw_id == "LA-L2:CN-01"
    assert not [
        fact
        for fact in facts
        if fact.attribute == "cabinet_membership" and fact.subject.kind == "cable"
    ]


def _switch_scope(values, *, row_number=7, revision_id="rev-s"):
    chunk_id = f"{revision_id}:switch"
    chunk = _chunk(
        chunk_id, _table_text("交换机网口配置表", SWITCH_HEADERS, [values])
    )
    record = _record(
        revision_id=revision_id,
        block_id=f"{revision_id}:b:s1",
        sheet="L3",
        row_number=row_number,
        headers=SWITCH_HEADERS,
        values=values,
        chunk_id=chunk_id,
    )
    return _Scope(
        chunks={revision_id: (chunk,)},
        records={revision_id: (record,)},
        revisions=[revision_id],
    )


def test_port_span_is_range_with_low_and_high():
    values = {
        "设备": "L3-CN01柜（DEVSW001）",
        "端口": "45-48",
        "系统": "联锁FL-net",
        "网络分配": "VLAN100",
    }
    facts = _facts(_switch_scope(values))

    assignment = next(iter(_by_attribute(facts, "port_assignment")))
    assert assignment.value_kind == "range"
    assert assignment.comparator == "range"
    assert assignment.low == 45.0
    assert assignment.high == 48.0
    assert assignment.raw_value == "45-48"
    assert assignment.object_ref.raw_id == "VLAN100"
    assert assignment.subject.raw_id == "DEVSW001"
    assert assignment.subject.scope == "L3-CN01柜"
    assert assignment.subject.scope_source == "row_column"

    system = next(iter(_by_attribute(facts, "port_system")))
    assert system.object_ref.raw_id == "联锁FL-net"
    assert system.low == 45.0 and system.high == 48.0
    assert ("system", "联锁FL-net") in assignment.extra

    vlan_name = next(iter(_by_attribute(facts, "vlan_name")))
    assert vlan_name.subject.raw_id == "DEVSW001"
    assert vlan_name.raw_value == "VLAN100"
    assert vlan_name.value_kind == "enum"

    membership = next(iter(_by_attribute(facts, "cabinet_membership")))
    assert membership.subject.raw_id == "DEVSW001"
    assert membership.object_ref.raw_id == "L3-CN01柜"


def test_reserved_system_is_not_a_system_entity():
    values = {
        "设备": "L3-CN03柜（DEVSW004）",
        "端口": "45-48",
        "系统": "预留",
        "网络分配": "",
    }
    facts = _facts(_switch_scope(values))

    assert not _by_attribute(facts, "port_system")
    assert not [
        fact
        for fact in facts
        if getattr(fact.object_ref, "raw_id", None) == "预留"
    ]
    labels = _by_attribute(facts, "port_system_label")
    assert len(labels) == 1
    assert labels[0].raw_value == "预留"
    assert labels[0].subject.raw_id == "DEVSW004"
    assert ("column_header", "系统") in labels[0].extra

    reserved = _by_attribute(facts, "reserved_slot")
    assert len(reserved) == 1
    assert reserved[0].subject.raw_id == "DEVSW004"
    assert reserved[0].raw_value == "预留"
    assert ("column_header", "系统") in reserved[0].extra
    assert ("port", "45-48") in reserved[0].extra

    span = next(iter(_by_attribute(facts, "port_span")))
    assert span.subject.raw_id == "DEVSW004"
    assert span.raw_value == "45-48"
    assert span.value_kind == "range"
    assert span.comparator == "range"
    assert span.low == 45.0 and span.high == 48.0
    assert ("column_header", "端口") in span.extra


def test_single_port_is_a_number():
    values = {
        "设备": "L3-CN03柜（DEVSW004）",
        "端口": "45",
        "系统": "预留",
        "网络分配": "",
    }
    facts = _facts(_switch_scope(values))

    span = next(iter(_by_attribute(facts, "port_span")))
    assert span.raw_value == "45"
    assert span.value_kind == "number"
    assert span.comparator == "eq"
    assert span.number == 45.0
    assert span.low is UNKNOWN and span.high is UNKNOWN


def test_device_keys_use_short_id_and_full_path():
    scope, _ = _cable_scope(
        group="LA-BRK-CN01柜（BRK:DEVSW001）",
        cabinet="LA-BRK:CN-01",
        device="LA-BRK-CN:DEVSW001",
    )
    facts = _facts(scope)

    title = next(
        fact for fact in facts if fact.citation.locator_kind == "table_title"
    )
    keys = {key.name: key.value for key in title.subject.keys}
    assert keys["device_id"] == "DEVSW001"
    assert keys["device_path"] == "BRK:DEVSW001"

    membership = next(iter(_by_attribute(facts, "device_membership")))
    keys = {key.name: key.value for key in membership.object_ref.keys}
    assert keys["device_id"] == "DEVSW001"
    assert keys["device_path"] == "LA-BRK-CN:DEVSW001"


def test_cable_number_notes_are_not_reserved_slots():
    note_scope, _ = _cable_scope(
        group="LA-BRK-CN07柜（BRK:DEVSW004）",
        cable="剩下的给联锁 19开始",
        device="",
        start="",
        end="",
        use="",
        function="",
        cable_type="",
        category="",
    )
    notes = _by_attribute(_facts(note_scope), "cable_number_note")
    assert len(notes) == 1
    assert notes[0].raw_value == "剩下的给联锁 19开始"
    assert not _by_attribute(_facts(note_scope), "reserved_slot")

    slot_scope, _ = _cable_scope(
        group="LA-BRK-CN07柜（BRK:DEVSW004）",
        cable="空12",
        device="",
        start="",
        end="",
        use="",
        function="",
        cable_type="",
        category="",
    )
    slots = _by_attribute(_facts(slot_scope), "reserved_slot")
    assert len(slots) == 1
    assert slots[0].raw_value == "空12"
    assert not _by_attribute(_facts(slot_scope), "cable_number_note")


def test_cabinet_endpoint_is_not_flagged_unresolved():
    scope, _ = _cable_scope(end="LA-L2:CN-02")
    facts = _facts(scope)

    endpoint = next(iter(_by_attribute(facts, "cable_endpoint_end")))
    assert endpoint.object_ref.kind == "cabinet"
    assert ("scope_status", "unresolved") not in endpoint.extra
    assert ("cabinet_key", "l2cn02") in endpoint.extra

    use = next(iter(_by_attribute(facts, "device_use")))
    assert ("scope_status", "unresolved") not in use.extra


def test_cabinet_key_normalises_printings():
    assert (
        connectivity._cabinet_key("L4:CN-13柜")
        == connectivity._cabinet_key("LA-L4:CN-13")
        == "l4cn13"
    )
    scope, _ = _cable_scope(
        group="L4-CN-13柜（DEVSW001）", cabinet="LA-L4:CN-13"
    )
    facts = _facts(scope)

    title = next(
        fact for fact in facts if fact.citation.locator_kind == "table_title"
    )
    assert ("cabinet_key", "l4cn13") in title.extra
    membership = next(iter(_by_attribute(facts, "cable_membership")))
    assert ("cabinet_key", "l4cn13") in membership.extra


def test_empty_row_and_unsourced_reserved_label_produce_no_facts():
    revision_id = "rev-e"
    headers = CABLE_HEADERS
    empty = {header: "" for header in headers}
    # A reserved label with no cabinet range in its table has no named
    # subject; nothing is invented for it.
    reserved = dict(empty, 电缆编号="真空预留2")
    empty_chunk = f"{revision_id}:empty"
    text = _table_text(_CABLE_TITLE, headers, [empty, reserved])
    chunk = _chunk(empty_chunk, text)
    records = tuple(
        _record(
            revision_id=revision_id,
            block_id=f"{revision_id}:b:e1",
            sheet="S",
            row_number=row,
            headers=headers,
            values=values,
            chunk_id=empty_chunk,
        )
        for row, values in ((6, empty), (7, reserved))
    )
    scope = _Scope(
        chunks={revision_id: (chunk,)},
        records={revision_id: records},
        revisions=[revision_id],
    )
    assert connectivity.extract(scope) == []


def test_reserved_row_becomes_cabinet_attribute():
    scope, _ = _cable_scope(
        group="L3-CN03柜（DEVSW004）",
        cable="工艺/PDU预留8",
        cabinet="",
        device="",
        start="",
        end="",
        use="",
        function="",
        cable_type="",
        category="",
    )
    facts = _facts(scope)

    reserved = _by_attribute(facts, "reserved_slot")
    assert len(reserved) == 1
    fact = reserved[0]
    assert fact.fact_type == "attribute"
    assert fact.subject.kind == "cabinet"
    assert fact.subject.raw_id == "L3-CN03柜（DEVSW004）"
    assert fact.subject.scope == "L3-CN03柜"
    assert fact.subject.scope_source == "table_title"
    assert fact.raw_value == "工艺/PDU预留8"
    assert fact.value_kind == "text"
    assert fact.comparator == "eq"
    assert fact.citation.locator_kind == "table_row"
    assert fact.citation.row_number == 6
    assert ("column_header", "电缆编号") in fact.extra
    assert fact.raw_value in fact.citation.excerpt
    # The subject comes from the table title; keep that line for review.
    title_line = dict(fact.extra)["table_title"]
    assert fact.subject.raw_id in title_line
    assert fact.subject.scope in title_line


def test_reserved_row_keeps_first_cell_and_moves_the_rest_to_extra():
    scope, _ = _cable_scope(
        group="EMIT-CN01柜（DEVSW001）",
        cable="真空预留2",
        cabinet="",
        device="",
        start="",
        end="",
        use="",
        function="",
        cable_type="",
        category="设备网",
    )
    facts = _facts(scope)

    reserved = _by_attribute(facts, "reserved_slot")
    assert len(reserved) == 1
    fact = reserved[0]
    assert fact.raw_value == "真空预留2"
    assert ("category", "设备网") in fact.extra
    assert " | " not in fact.raw_value
    # Every reserved label must be a contiguous fragment of its own row.
    assert all(
        item.raw_value in item.citation.excerpt for item in reserved
    )


def test_blank_attribute_cells_are_not_filled():
    scope, _ = _cable_scope(
        function="", cable_type="", category="", use="", remark=""
    )
    facts = _facts(scope)

    attributes = {fact.attribute for fact in facts}
    assert "cable_function" not in attributes
    assert "cable_type" not in attributes
    assert "network_category" not in attributes
    assert "device_use" not in attributes
    assert "remark" not in attributes
    # Endpoints and cabinet membership are still printed and recorded.
    assert "cable_endpoint_start" in attributes
    assert "cable_membership" in attributes


def test_pv_system_only_from_explicit_wording():
    revision_id = "rev-p"
    chunk_id = f"{revision_id}:p1"
    chunk = _chunk(
        chunk_id,
        "设备清单如下。\n"
        "DEMO-FAC:PV01:SIG 属于 束测系统。\n"
        "HW-IMG2:RdPrs 运行正常。",
        position_kind="paragraph",
        label="paragraph-1",
    )
    scope = _Scope(
        chunks={revision_id: (chunk,)},
        records={revision_id: ()},
        revisions=[revision_id],
    )
    facts = _facts(scope)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.attribute == "pv_system"
    assert fact.subject.raw_id == "DEMO-FAC:PV01:SIG"
    assert fact.object_ref.raw_id == "束测系统"
    assert fact.citation.locator_kind == "paragraph"
    assert fact.citation.excerpt == (
        "DEMO-FAC:PV01:SIG 属于 束测系统。"
    )


def test_markdown_switch_table_in_paragraph_chunk():
    revision_id = "rev-m"
    chunk_id = f"{revision_id}:m1"
    chunk = _chunk(
        chunk_id,
        "设备 | 端口 | 系统 | 网络分配\n"
        "--- | --- | --- | ---\n"
        "L2-CN01柜（DEVSW001） | 1-4 | 真空/机械 | VLAN40",
        position_kind="paragraph",
        label="paragraph-2",
    )
    scope = _Scope(
        chunks={revision_id: (chunk,)},
        records={revision_id: ()},
        revisions=[revision_id],
    )
    facts = _facts(scope)

    assignment = next(iter(_by_attribute(facts, "port_assignment")))
    assert assignment.low == 1.0 and assignment.high == 4.0
    assert assignment.object_ref.raw_id == "VLAN40"
    assert assignment.citation.locator_kind == "table_row"
    assert assignment.citation.row_number == 1
    assert assignment.citation.table_block_id == chunk_id
    assert assignment.citation.locator_label == "paragraph-2#t1r1"


def test_markdown_pv_table_requires_both_columns():
    revision_id = "rev-mp"
    chunk_id = f"{revision_id}:mp1"
    chunk = _chunk(
        chunk_id,
        "测试pv | 所属系统\n"
        "--- | ---\n"
        "DEMO-FAC:PV01:SIG | 束测系统",
        position_kind="paragraph",
        label="paragraph-3",
    )
    scope = _Scope(
        chunks={revision_id: (chunk,)},
        records={revision_id: ()},
        revisions=[revision_id],
    )
    facts = _facts(scope)

    assert [(f.attribute, f.subject.raw_id, f.object_ref.raw_id) for f in facts] == [
        (
            "pv_system",
            "DEMO-FAC:PV01:SIG",
            "束测系统",
        )
    ]


@pytest.mark.corpus
def test_corpus_snapshot_builds_clean_citations():
    if not Path(BASE).exists():
        pytest.skip("rc.3 snapshot is missing")
    scope = load_scope(
        revision_ids=[
            "network-cable-table-shine-l2-bc2-emit-e58a13-rev",
            "network-switch-config-l3-005513-rev",
        ]
    )
    facts = connectivity.extract(scope)
    texts = scope.chunk_text()
    assert facts
    assert check_citations(facts, texts) == []
    assert all(fact.layer == connectivity.LAYER for fact in facts)

    titles = [f for f in facts if f.citation.locator_kind == "table_title"]
    assert titles
    for fact in titles:
        assert fact.citation.table_block_id
        assert type(fact.citation.row_number) is int
        first_line = texts[fact.citation.chunk_id].splitlines()[0].strip()
        assert fact.citation.excerpt == first_line
        assert fact.subject.raw_id in fact.citation.excerpt
    assert not [
        f for f in facts if f.citation.locator_kind == "table_header"
    ]

    devices = {
        (fact.subject.scope, fact.subject.raw_id)
        for fact in facts
        if fact.subject.kind == "device" and fact.subject.raw_id == "DEVSW001"
    }
    scopes = {scope for scope, raw in devices}
    assert len(scopes) > 1  # the same DEVSW001 is printed under many cabinets
    assert any(
        ("scope_status", "unresolved") in fact.extra for fact in facts
    )
    # A reserved 系统 cell is never a system entity.
    assert not [
        fact
        for fact in facts
        if getattr(fact.object_ref, "raw_id", None) == "预留"
    ]
    # Only devices may carry the unresolved-scope marker.
    for fact in facts:
        if ("scope_status", "unresolved") not in fact.extra:
            continue
        for entity in (fact.subject, fact.object_ref):
            if getattr(entity, "kind", None) == "cabinet":
                pytest.fail("cabinet marked unresolved")
    # Cabinet comparison keys exist wherever a cabinet is printed.
    memberships = [
        fact for fact in facts if fact.attribute == "cable_membership"
    ]
    assert memberships
    assert all(dict(fact.extra).get("cabinet_key") for fact in memberships)
