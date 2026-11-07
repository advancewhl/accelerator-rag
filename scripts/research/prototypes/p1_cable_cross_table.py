"""W5a: cable/switch cross-table single-point prototype (§4.3, §6 P0).

把一道 S1 连通性题映射到 W2 连接与归属事实层上的结构化查询：解析题干锚点
（机柜+设备、端口区间、电缆编号、E 编号），按 citation 的
``(chunk_id, table_block_id, row_number)`` 还原表格行，用确定性算子
（``port_range_membership``、``set_enumeration``）计算端口归属、跨表配平、
缺号边界与区间重叠，答案只由算子输出和事实原文拼接。不调用模型，不读语料，
不写事实层。

槽位模型（本原型唯一的表内推演，逐条在报告中列出依据）：

* 电缆表的行按 ``citation.row_number`` 顺序排列；
* 电缆行的 E 编号就是它占用的端口槽位号；
* 预留行的 ``raw_value`` 尾部数字就是它声明的槽位数（``束测预留4`` → 4）；
* 因此"下一槽位"是可逐行累加的整数。电缆编号跳号而槽位计数不跳号，
  说明缺号已由中间的预留行覆盖；槽位计数跳过而电缆编号没跳，说明表内
  有未声明的空槽——两种情况原型都会标出。

复算：
  python3 scripts/research/prototypes/p1_cable_cross_table.py \\
      --question S1-DEV-001 --out report.json
  python3 scripts/research/prototypes/p1_cable_cross_table.py --all --split dev
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import unicodedata

import common

SCENARIO = "s1_connectivity"
FACT_LAYER = "connectivity"

# Benchmark items whose gold contradicts the cited source.  The answer still
# follows the source facts; the note only tells a reviewer what to check.
# Tracked in docs/research/phase2/known-benchmark-issues.md.
KNOWN_BENCHMARK_ISSUES = {
    "S1-DEV-006": (
        "原文 33-48=预留；gold 疑将 29-32 写成 33-36。"
        "本报告按原文事实给出，未对齐 gold。"
    ),
}

CABLE_COLUMNS = (
    "序号",
    "电缆编号",
    "所属机柜名称",
    "所属设备",
    "电缆功能",
    "电缆类型",
    "始端设备位置或机柜编号",
    "安装路径、通过地沟、桥架等编号",
    "终端设备位置或机柜编号",
    "设备用途",
    "电缆长度",
    "工艺铺设/厂家铺设",
    "类别",
    "备注",
    "分组",
)
SWITCH_COLUMNS = ("设备", "端口", "系统", "网络分配")

PORT_ATTRIBUTES = (
    "port_span",
    "port_system",
    "port_assignment",
    "port_system_label",
)
# R2 moved table titles from ``table_header`` to ``table_title``; both are
# accepted so the prototype keeps working across the two fact builds.
TITLE_LOCATORS = ("table_title", "table_header")
# A switch row may print a system name ("预留") without a system entity; W2
# carries such labels either as ``port_system_label`` or, for "预留", as a
# ``reserved_slot`` attribute whose extra records the port column.
PORT_ROW_ATTRIBUTES = set(PORT_ATTRIBUTES) | {"reserved_slot"}
_PORT_SPEC = re.compile(r"^\s*\d{1,3}\s*(?:[-–—~～至]\s*\d{1,3})?\s*$")
CABLE_ATTRIBUTES = (
    "cable_function",
    "cable_type",
    "network_category",
    "remark",
    "device_use",
)
RESERVED_ATTRIBUTE = "reserved_slot"
NOTE_ATTRIBUTE = "cable_number_note"
CABLE_RELATIONS = (
    "cable_membership",
    "cable_endpoint_start",
    "cable_endpoint_end",
)
RELATION_LABELS = {
    "cable_membership": "所属机柜名称",
    "cable_endpoint_start": "始端设备位置或机柜编号",
    "cable_endpoint_end": "终端设备位置或机柜编号",
}
ATTRIBUTE_LABELS = {
    "cable_function": "电缆功能",
    "cable_type": "电缆类型",
    "network_category": "类别",
    "remark": "备注",
    "device_use": "设备用途",
}

# ---------------------------------------------------------------------------
# question text parsing (pure strings, unit-tested without the corpus)
# ---------------------------------------------------------------------------

_CABINET_DEVICE_PAREN = re.compile(
    r"(?P<cabinet>[^\s（()，。；;、？?「」]+?)\s*[（(]\s*"
    r"(?P<device>[A-Za-z][A-Za-z0-9_.\-]*(?::[A-Za-z0-9_.\-]+)*\d)\s*[）)]"
)
_CABINET_DEVICE_BARE = re.compile(
    r"(?P<cabinet>[A-Z][A-Za-z0-9_.:\-]*?CN[-_]?\d+)\s*柜?\s*"
    r"(?:段|中|的)?\s*"
    r"(?P<device>[A-Za-z][A-Za-z0-9_.\-]*(?::[A-Za-z0-9_.\-]+)*\d)"
)
_CABLE_ID = re.compile(
    r"(?<![A-Za-z0-9_.\-])"
    r"[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+:[A-Za-z0-9_.\-]+-E\d+"
)
_DEVICE_ONLY = re.compile(
    r"(?<![A-Za-z0-9_.\-])"
    r"(?P<device>[A-Za-z][A-Za-z0-9_.\-]*(?::[A-Za-z0-9_.\-]+)*\d)"
    r"(?![A-Za-z0-9_.\-])"
)
_PORT_RANGE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<low>\d{1,3})\s*[-–—~～至]\s*(?P<high>\d{1,3})"
    r"(?![A-Za-z0-9])"
)
_PORT_ONE = re.compile(r"端口\s*(?P<port>\d{1,3})(?!\d)")
_E_RANGE = re.compile(
    r"(?<![A-Za-z0-9])E(?P<low>\d{1,4})\s*[-–—~～至]\s*E(?P<high>\d{1,4})"
)
_E_TOKEN = re.compile(r"(?<![A-Za-z0-9])E(?P<num>\d{1,4})(?![0-9])")
_QUOTED = re.compile(r"「([^」]+)」")
_ENDPOINT_HINT = re.compile(
    r"(?<![A-Za-z0-9\-])(?P<hint>[A-Z]{2,5}[-_]?\d+)(?![A-Za-z0-9\-])"
)
_FIRST_MARKERS = (
    "段首",
    "第一条",
    "首条",
    "第一根",
    "第一行",
    "序号 1",
    "序号1",
    "唯一的电缆",
    "只有一根",
)
_CELL_SPLIT = re.compile(r"\s*\|\s*")
_CABLE_E_SUFFIX = re.compile(r"-E(?P<num>\d+)$")
_TRAILING_COUNT = re.compile(r"(?P<count>\d+)\s*$")


@dataclasses.dataclass(frozen=True)
class QueryAnchors:
    """Structured anchors read from a question stem; nothing is inferred."""

    pairs: tuple[tuple[str, str], ...] = ()
    devices: tuple[str, ...] = ()
    ports: tuple[str, ...] = ()
    cable_ids: tuple[str, ...] = ()
    e_ranges: tuple[tuple[int, int], ...] = ()
    e_numbers: tuple[int, ...] = ()
    systems: tuple[str, ...] = ()
    hints: tuple[str, ...] = ()

    @property
    def pair(self) -> tuple[str, str] | None:
        return self.pairs[0] if self.pairs else None

    @property
    def boundary_e(self) -> int | None:
        return self.e_numbers[0] if self.e_numbers else None

    def target_e_numbers(self) -> tuple[int, ...]:
        """E numbers the question asks to record (ranges expanded, deduped)."""

        numbers: list[int] = []
        for low, high in self.e_ranges:
            numbers.extend(range(min(low, high), max(low, high) + 1))
        numbers.extend(self.e_numbers)
        return tuple(dict.fromkeys(numbers))


def _mask_spans(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for index in range(start, end):
            chars[index] = " "
    return "".join(chars)


def parse_query(text: str) -> QueryAnchors:
    """Read cabinet/device pairs, ports, cable ids and E numbers from a stem."""

    text = text or ""
    pairs: list[tuple[str, str]] = []
    cable_ids: list[str] = []
    spans: list[tuple[int, int]] = []
    for match in _CABLE_ID.finditer(text):
        cable_ids.append(match.group(0))
        spans.append((match.start(), match.end()))
    masked = _mask_spans(text, spans)

    e_ranges: list[tuple[int, int]] = []
    range_spans: list[tuple[int, int]] = []
    for match in _E_RANGE.finditer(masked):
        e_ranges.append((int(match.group("low")), int(match.group("high"))))
        range_spans.append((match.start(), match.end()))
    masked = _mask_spans(masked, range_spans)
    e_numbers = tuple(int(match.group("num")) for match in _E_TOKEN.finditer(masked))

    for match in _CABINET_DEVICE_PAREN.finditer(text):
        pair = (match.group("cabinet").strip(), match.group("device").strip())
        if pair not in pairs:
            pairs.append(pair)
    for match in _CABINET_DEVICE_BARE.finditer(text):
        pair = (match.group("cabinet").strip(), match.group("device").strip())
        if pair not in pairs:
            pairs.append(pair)

    devices: list[str] = []
    known = {device for _, device in pairs}
    for match in _DEVICE_ONLY.finditer(masked):
        token = match.group("device").strip()
        if "SW" in token and token not in known and token not in devices:
            devices.append(token)

    ports: list[str] = []
    for match in _PORT_RANGE.finditer(text):
        low, high = int(match.group("low")), int(match.group("high"))
        spec = f"{min(low, high)}-{max(low, high)}"
        if spec not in ports:
            ports.append(spec)
    if not ports:
        for match in _PORT_ONE.finditer(text):
            ports.append(match.group("port"))

    hints = tuple(
        dict.fromkeys(
            match.group("hint")
            for match in _ENDPOINT_HINT.finditer(masked)
            if not match.group("hint").startswith("VLAN")
            and match.group("hint") not in devices
            and match.group("hint") not in {device for _, device in pairs}
        )
    )

    return QueryAnchors(
        pairs=tuple(pairs),
        devices=tuple(devices),
        ports=tuple(ports),
        cable_ids=tuple(cable_ids),
        e_ranges=tuple(e_ranges),
        e_numbers=e_numbers,
        systems=tuple(_QUOTED.findall(text)),
        hints=hints,
    )


# ---------------------------------------------------------------------------
# fact rows and table blocks
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").strip()


def _cabinet_key(text: str) -> str:
    """Comparison key; the printed form is never rewritten in any output."""

    value = _normalise(text).replace(" ", "")
    if value.endswith("柜"):
        value = value[:-1]
    return value.casefold()


def _device_key(text: str) -> str:
    return _normalise(text).casefold()


def _device_matches(query: str, printed: str, *, allow_short: bool = True) -> bool:
    """Full identifiers compare exactly; with a cabinet, ``:``-short forms match.

    A question may print ``LA-EXT-L4-CN:DEVSW005`` while the config row prints
    ``DEVSW005`` under the same cabinet; the cabinet check is what keeps that
    alias safe, so ``allow_short`` is only set when a cabinet is supplied.
    """

    wanted = _device_key(query)
    other = _device_key(printed)
    if other == wanted:
        return True
    if not allow_short:
        return False
    return other.rsplit(":", 1)[-1] == wanted.rsplit(":", 1)[-1]


def _cells(excerpt: str) -> tuple[str, ...]:
    parts = [part.strip() for part in _CELL_SPLIT.split(excerpt or "")]
    while parts and not parts[-1]:
        parts.pop()
    return tuple(parts)


@dataclasses.dataclass(frozen=True)
class Row:
    """One restored table line: its facts plus the verbatim source cells."""

    revision_id: str
    block_id: str
    row_number: int
    locator_kind: str
    excerpt: str
    facts: tuple
    kind: str

    @property
    def cells(self) -> tuple[str, ...]:
        return _cells(self.excerpt)

    def attribute_fact(self, name: str):
        for fact in self.facts:
            if fact.attribute == name:
                return fact
        return None

    def relation_fact(self, name: str):
        for fact in self.facts:
            if fact.attribute == name:
                return fact
        return None

    @property
    def _port_fact(self):
        """The fact that names this switch row's port span, if any."""

        for name in ("port_system", "port_system_label"):
            fact = self.attribute_fact(name)
            if fact is not None:
                return fact
        for fact in self.facts:
            if (
                fact.attribute == RESERVED_ATTRIBUTE
                and fact.subject.kind == "device"
            ):
                return fact
        return None

    @property
    def port_span(self) -> str | None:
        """The printed port span of this switch row.

        ``port_system``/``port_assignment`` carry it in ``raw_value``; the
        R2 ``port_system_label`` fact carries only the system label, so the
        span comes from the sibling ``reserved_slot`` fact's ``port`` extra.
        """

        dedicated = self.attribute_fact("port_span")
        if dedicated is not None and _PORT_SPEC.match(dedicated.raw_value):
            return dedicated.raw_value.strip()
        for fact in self.facts:
            if fact.subject.kind != "device":
                continue
            if fact.attribute not in PORT_ROW_ATTRIBUTES:
                continue
            extra = dict(fact.extra)
            for candidate in (extra.get("port"), fact.raw_value):
                if isinstance(candidate, str) and _PORT_SPEC.match(candidate):
                    return candidate.strip()
        return None

    @property
    def system(self) -> str | None:
        fact = self.attribute_fact("port_system")
        if fact is not None:
            return getattr(fact.object_ref, "raw_id", None)
        label = self.attribute_fact("port_system_label")
        if label is not None:
            return label.raw_value
        reserved = self._port_fact
        if reserved is not None and reserved.attribute == RESERVED_ATTRIBUTE:
            return reserved.raw_value
        return None

    @property
    def vlan(self) -> str | None:
        fact = self.attribute_fact("port_assignment")
        if fact is not None:
            return getattr(fact.object_ref, "raw_id", None)
        name = self.attribute_fact("vlan_name")
        return None if name is None else name.raw_value

    @property
    def cable_id(self) -> str | None:
        for fact in self.facts:
            if fact.subject.kind == "cable":
                return fact.subject.raw_id
        return None

    @property
    def e_number(self) -> int | None:
        match = _CABLE_E_SUFFIX.search(self.cable_id or "")
        return int(match.group("num")) if match else None

    @property
    def reserved_label(self) -> str | None:
        fact = self.attribute_fact(RESERVED_ATTRIBUTE)
        return None if fact is None else fact.raw_value

    @property
    def reserved_count(self) -> int | None:
        label = self.reserved_label
        if label is None:
            return None
        match = _TRAILING_COUNT.search(label)
        return int(match.group("count")) if match else None

    @property
    def device_scope(self) -> str | None:
        for fact in self.facts:
            if fact.subject.kind == "device":
                scope = fact.subject.scope
                if isinstance(scope, str) and scope:
                    return scope
        return None

    @property
    def device_id(self) -> str | None:
        for fact in self.facts:
            if fact.subject.kind == "device":
                return fact.subject.key("device_id")
        return None


@dataclasses.dataclass(frozen=True)
class Block:
    """A table block of one revision, restored from its cited rows."""

    revision_id: str
    block_id: str
    kind: str
    title: str
    cabinet: str | None
    device: str | None
    owner_device: str | None
    rows: tuple[Row, ...]

    @property
    def data_rows(self) -> tuple[Row, ...]:
        return tuple(
            row for row in self.rows if row.kind in {"cable", "reserved"}
        )

    @property
    def cable_rows(self) -> tuple[Row, ...]:
        return tuple(row for row in self.rows if row.kind == "cable")

    @property
    def reserved_rows(self) -> tuple[Row, ...]:
        return tuple(row for row in self.rows if row.kind == "reserved")

    @property
    def switch_rows(self) -> tuple[Row, ...]:
        return tuple(row for row in self.rows if row.kind == "switch")


def _row_kind(facts) -> str:
    attributes = {fact.attribute for fact in facts}
    if any(fact.citation.locator_kind in TITLE_LOCATORS for fact in facts):
        return "title"
    if any(fact.subject.kind == "cable" for fact in facts):
        return "cable"
    if NOTE_ATTRIBUTE in attributes:
        return "note"
    if RESERVED_ATTRIBUTE in attributes and any(
        fact.subject.kind == "cabinet" for fact in facts
    ):
        return "reserved"
    if any(
        fact.subject.kind == "device" and fact.attribute in PORT_ROW_ATTRIBUTES
        for fact in facts
    ):
        return "switch"
    return "other"


def _block_identity(rows: tuple[Row, ...]) -> tuple[str, str | None, str | None]:
    """Title text plus (cabinet, device) when the table prints one."""

    title = next(
        (row.excerpt for row in rows if row.kind == "title"), ""
    ).strip()
    cabinet = device = None
    if title:
        match = _CABINET_DEVICE_PAREN.search(title)
        if match:
            cabinet = match.group("cabinet").strip()
            device = match.group("device").strip()
    return title, cabinet, device


def _owner_device(block_rows: tuple[Row, ...]) -> str | None:
    """The 所属设备 column value the table prints for this block.

    W2 emits ``cabinet_membership`` for that column only on the first data row,
    so the value is read from that fact and cross-checked against the row text
    by the caller before it is used in an answer.
    """

    for row in block_rows:
        if row.kind != "cable":
            continue
        for fact in row.facts:
            if (
                fact.attribute in {"device_membership", "cabinet_membership"}
                and fact.subject.kind == "cable"
            ):
                return fact.raw_value
            if (
                fact.attribute == "cabinet_membership"
                and fact.subject.kind == "device"
            ):
                return fact.subject.raw_id
    for row in block_rows:
        if row.kind != "cable":
            continue
        cells = row.cells
        if len(cells) > 3 and cells[3]:
            return cells[3]
    return None


class FactIndex:
    """Connectivity facts regrouped into rows and table blocks."""

    def __init__(self, facts):
        grouped: dict[tuple[str, str, int], list] = {}
        for fact in facts:
            if fact.layer != FACT_LAYER:
                continue
            if not fact.citation.table_block_id:
                continue
            key = (
                fact.revision_id,
                fact.citation.table_block_id,
                fact.citation.row_number,
            )
            grouped.setdefault(key, []).append(fact)
        rows: list[Row] = []
        for (revision, block_id, row_number), items in grouped.items():
            items.sort(
                key=lambda fact: (
                    fact.citation.locator_kind,
                    fact.fact_id,
                )
            )
            rows.append(
                Row(
                    revision_id=revision,
                    block_id=block_id,
                    row_number=row_number,
                    locator_kind=items[0].citation.locator_kind,
                    excerpt=items[0].citation.excerpt,
                    facts=tuple(items),
                    kind=_row_kind(items),
                )
            )
        per_block: dict[tuple[str, str], list[Row]] = {}
        for row in rows:
            per_block.setdefault((row.revision_id, row.block_id), []).append(row)
        blocks: list[Block] = []
        for (revision, block_id), block_rows in per_block.items():
            block_rows.sort(key=lambda row: row.row_number)
            title, cabinet, device = _block_identity(tuple(block_rows))
            kinds = {row.kind for row in block_rows}
            if kinds & {"cable", "reserved"}:
                kind = "cable"
            elif "switch" in kinds:
                kind = "switch"
            else:
                kind = "other"
            blocks.append(
                Block(
                    revision_id=revision,
                    block_id=block_id,
                    kind=kind,
                    title=title,
                    cabinet=cabinet,
                    device=device,
                    owner_device=_owner_device(tuple(block_rows)),
                    rows=tuple(block_rows),
                )
            )
        blocks.sort(key=lambda block: (block.revision_id, block.block_id))
        self.rows = tuple(rows)
        self.blocks = tuple(blocks)

    # -- lookups -------------------------------------------------------

    def switch_rows(self, cabinet: str, device: str) -> tuple[Row, ...]:
        wanted_cabinet = _cabinet_key(cabinet)
        found = []
        for row in self.rows:
            if row.kind != "switch":
                continue
            scope = row.device_scope
            printed = row.device_id
            if scope is None or printed is None:
                continue
            if _cabinet_key(scope) != wanted_cabinet:
                continue
            if _device_matches(device, printed):
                found.append(row)
        found.sort(key=lambda row: (row.revision_id, row.block_id, row.row_number))
        return tuple(found)

    def cable_blocks(
        self, cabinet: str | None = None, device: str | None = None
    ) -> tuple[Block, ...]:
        found = []
        for block in self.blocks:
            if block.kind != "cable":
                continue
            if cabinet is not None:
                if block.cabinet is None:
                    continue
                if _cabinet_key(block.cabinet) != _cabinet_key(cabinet):
                    continue
            if device is not None:
                candidates = [
                    value
                    for value in (block.device, block.owner_device)
                    if value
                ]
                if not any(
                    _device_matches(
                        device, value, allow_short=cabinet is not None
                    )
                    for value in candidates
                ):
                    continue
            found.append(block)
        return tuple(found)

    def cable_rows_by_id(self, cable_id: str) -> tuple[Row, ...]:
        wanted = _device_key(cable_id)
        return tuple(
            row
            for row in self.rows
            if row.kind == "cable"
            and row.cable_id is not None
            and _device_key(row.cable_id) == wanted
        )


# ---------------------------------------------------------------------------
# slot walk (cables + reserved declarations, in printed row order)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Slot:
    index: int
    kind: str
    label: str
    row: Row


@dataclasses.dataclass
class SlotWalk:
    block: Block
    slots: list[Slot] = dataclasses.field(default_factory=list)
    gaps: list[int] = dataclasses.field(default_factory=list)
    overlaps: list[Row] = dataclasses.field(default_factory=list)
    unknown: list[Row] = dataclasses.field(default_factory=list)
    leading_reserved: bool = False

    @property
    def covered(self) -> list[int]:
        return sorted({slot.index for slot in self.slots})

    @property
    def start(self) -> int | None:
        return self.slots[0].index if self.slots else None

    @property
    def end(self) -> int | None:
        return self.slots[-1].index if self.slots else None

    @property
    def cable_slots(self) -> list[Slot]:
        return [slot for slot in self.slots if slot.kind == "cable"]

    @property
    def reserved_slots(self) -> list[Slot]:
        return [slot for slot in self.slots if slot.kind == "reserved"]


def walk_slots(block: Block) -> SlotWalk:
    """Assign port slots to cable rows and reserved declarations."""

    walk = SlotWalk(block=block)
    cursor: int | None = None
    for row in block.data_rows:
        if row.kind == "cable":
            number = row.e_number
            if number is None:
                walk.unknown.append(row)
                continue
            if cursor is None:
                cursor = number
            if number < cursor:
                walk.overlaps.append(row)
            elif number > cursor:
                walk.gaps.extend(range(cursor, number))
                cursor = number
            walk.slots.append(
                Slot(index=number, kind="cable", label=row.cable_id or "", row=row)
            )
            cursor = number + 1
        else:
            count = row.reserved_count
            if cursor is None:
                walk.leading_reserved = True
                cursor = 1
            if count is None:
                walk.unknown.append(row)
                continue
            for offset in range(count):
                walk.slots.append(
                    Slot(
                        index=cursor + offset,
                        kind="reserved",
                        label=row.reserved_label or "",
                        row=row,
                    )
                )
            cursor += count
    return walk


# ---------------------------------------------------------------------------
# evaluation context
# ---------------------------------------------------------------------------


class Evaluator:
    """Collects operator calls, claims and evidence for one report."""

    def __init__(self, question: dict, index: FactIndex, facts_path):
        self.question = question
        self.query = question.get("query", "") or ""
        self.index = index
        self.facts_path = facts_path
        self.anchors = parse_query(self.query)
        self.operators: list[dict] = []
        self.claims: list[dict] = []
        self.evidence: list = []
        self.unresolved: list[str] = []
        self.notes: list[str] = []
        self._claim_counter = 0

    def operator(self, name: str, request: dict) -> dict:
        response = common.operator(name, request)
        self.operators.append(
            {"op": name, "request": request, "response": response}
        )
        return response

    def claim(self, text: str, value: str, facts) -> None:
        facts = list(facts)
        self._claim_counter += 1
        self.claims.append(
            common.claim(f"c{self._claim_counter:02d}", text, value, facts)
        )
        self.evidence.extend(facts)

    def note(self, message: str) -> None:
        self.notes.append(message)

    def unresolved_add(self, message: str) -> None:
        if message not in self.unresolved:
            self.unresolved.append(message)

    def command(self, facts_path) -> str:
        return (
            "python3 scripts/research/prototypes/p1_cable_cross_table.py "
            f"--question {self.question['base_id']} --facts {facts_path}"
        )

    def build(self, status: str, answer: str, facts_path) -> dict:
        return common.build_report(
            self.question,
            status=status,
            answer=answer,
            claims=self.claims,
            operators=self.operators,
            facts=self.evidence,
            unresolved=self.unresolved,
            notes=" ".join(self.notes),
            facts_path=facts_path,
            command=self.command(facts_path),
        )


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------


def _expand_spec(spec: str | None) -> tuple[int, ...]:
    """Expand a printed port span ("9-16", "45") into its port numbers."""

    if not spec:
        return ()
    text = unicodedata.normalize("NFKC", spec).strip()
    parts = [part.strip() for part in re.split(r"[-–—~～至]", text)]
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        low, high = sorted(int(part) for part in parts)
        return tuple(range(low, high + 1))
    if len(parts) == 1 and parts[0].isdigit():
        return (int(parts[0]),)
    return ()


def _expand_ports(row: Row) -> tuple[int, ...]:
    return _expand_spec(row.port_span)


def _span_row_facts(row: Row) -> list:
    return [fact for fact in row.facts if fact.attribute in PORT_ATTRIBUTES]


def _e_label(number: int) -> str:
    return f"E{number:03d}"


def _runs(values: list[tuple[int, str]]) -> list[tuple[str, list[int]]]:
    """Group consecutive slot numbers that share the same label."""

    runs: list[tuple[str, list[int]]] = []
    for number, label in values:
        if runs and runs[-1][0] == label and runs[-1][1][-1] + 1 == number:
            runs[-1][1].append(number)
        else:
            runs.append((label, [number]))
    return runs


def _number_span(numbers: list[int]) -> str:
    if not numbers:
        return ""
    if len(numbers) == 1:
        return _e_label(numbers[0])
    return f"{_e_label(numbers[0])}–{_e_label(numbers[-1])}"


def _row_fact_list(row: Row) -> list:
    return list(row.facts)


def _cable_columns(row: Row, block: Block) -> list[tuple[str, str, list]]:
    """(column, verbatim value, backing facts) for one cable row."""

    facts = _row_fact_list(row)
    output: list[tuple[str, str, list]] = []
    cells = row.cells
    if cells and cells[0]:
        output.append(("序号", cells[0], facts))
    if row.cable_id:
        # The short form is what the tables call the cable; the full id is the
        # value printed in the 电缆编号 cell.  Both are claim values so a
        # string-level gold alignment can match either.
        if row.e_number is not None:
            output.append(("电缆编号（短号）", _e_label(row.e_number), facts))
        output.append(("电缆编号", row.cable_id, facts))
    for relation in CABLE_RELATIONS:
        fact = row.relation_fact(relation)
        if fact is not None and fact.raw_value:
            output.append((RELATION_LABELS[relation], fact.raw_value, [fact]))
    device_fact = row.relation_fact("device_membership")
    owner = device_fact.raw_value if device_fact is not None else block.owner_device
    if owner and owner in row.excerpt:
        backing = [device_fact] if device_fact is not None else facts
        output.append(("所属设备", owner, backing))
    for attribute in CABLE_ATTRIBUTES:
        fact = row.attribute_fact(attribute)
        if fact is not None and fact.raw_value:
            output.append((ATTRIBUTE_LABELS[attribute], fact.raw_value, [fact]))
    return output


def _row_summary(row: Row, block: Block) -> tuple[str, list[dict]]:
    columns = _cable_columns(row, block)
    text = "；".join(f"{name} {value}" for name, value, _ in columns)
    return text, columns


def _describe_cables(rows: tuple[Row, ...]) -> str:
    if not rows:
        return "线缆表没有电缆行"
    entries: list[tuple[int, str]] = []
    for row in rows:
        end = row.relation_fact("cable_endpoint_end")
        use = row.attribute_fact("device_use")
        label = "→".join(
            part
            for part in (
                getattr(end.object_ref, "raw_id", "") if end else "",
                use.raw_value if use else "",
            )
            if part
        )
        entries.append((row.e_number or 0, label or "（无终端）"))
    pieces = []
    for label, numbers in _runs(entries):
        pieces.append(f"{_number_span(numbers)}→{label}")
    return "；".join(pieces)


def _describe_reserved(rows: tuple[Row, ...]) -> str:
    labels = [row.reserved_label or "" for row in rows]
    return "、".join(label for label in labels if label)


def _describe_notes(block: Block) -> str:
    labels = [
        fact.raw_value
        for row in block.rows
        if row.kind == "note"
        for fact in row.facts
        if fact.attribute == NOTE_ATTRIBUTE and fact.raw_value
    ]
    return "、".join(labels)


def _slot_summary(walk: SlotWalk) -> str:
    """Compact, reviewable rendering of the slot walk (ranges, not rows)."""

    pieces: list[str] = []
    for kind, numbers in _runs(
        [(slot.index, slot.kind) for slot in walk.slots]
    ):
        label = "实接电缆" if kind == "cable" else "预留槽位"
        pieces.append(f"{_number_span(numbers)} {label}")
    for label, numbers in _runs(
        [(slot.index, slot.label) for slot in walk.reserved_slots]
    ):
        pieces.append(f"{_number_span(numbers)}={label}")
    return "；".join(pieces)


# ---------------------------------------------------------------------------
# handler: exact_record
# ---------------------------------------------------------------------------


def _exact_switch_ports(ev: Evaluator, cabinet: str, device: str, probe: str):
    rows = ev.index.switch_rows(cabinet, device)
    if not rows:
        ev.unresolved_add(
            f"配置表中找不到机柜 {cabinet} / 设备 {device} 的端口事实"
        )
        return None
    hits: list[tuple[Row, dict]] = []
    overlaps: list[tuple[Row, dict]] = []
    for row in rows:
        span = row.port_span
        if not span:
            continue
        response = ev.operator(
            "port_range_membership", {"spec": span, "probe": probe}
        )
        value = response["value"] if response["status"] == "ok" else {}
        if value.get("contained"):
            hits.append((row, response))
        elif value.get("overlap"):
            overlaps.append((row, response))
    if not hits and overlaps:
        # A range probe that spans several config rows: report every row it
        # touches instead of refusing.
        hits = overlaps
        ev.note(f"端口区间 {probe} 跨多行，按 overlap 命中 {len(hits)} 行")
    if not hits:
        ev.unresolved_add(
            f"端口 {probe} 没有落在 {cabinet}（{device}）的任何端口区间内"
        )
        return None

    parts: list[str] = []
    for row, _ in hits:
        cells = row.cells
        allocation = cells[3] if len(cells) > 3 else ""
        facts = _span_row_facts(row)
        system = row.system
        if system:
            ev.claim(
                f"{cabinet}（{device}）端口 {row.port_span} 的系统：{system}",
                system,
                facts,
            )
        if row.vlan:
            ev.claim(
                f"端口 {row.port_span} 的网络分配：{row.vlan}",
                row.vlan,
                facts,
            )
            parts.append(f"{row.port_span} 端口分配给「{system}」，网络分配为 {row.vlan}")
        elif allocation == "":
            ev.claim(
                f"端口 {row.port_span} 的网络分配列为空（行内无 VLAN 事实）",
                "网络分配列为空",
                facts,
            )
            parts.append(
                f"{row.port_span} 的系统为「{system}」，网络分配列为空"
            )
        else:
            ev.claim(
                f"端口 {row.port_span} 的网络分配原文：{allocation}",
                allocation,
                facts,
            )
            parts.append(f"{row.port_span} 的网络分配原文为「{allocation}」")
        ev.evidence.extend(facts)
        ev.note(f"命中行：{row.excerpt}")
        if row.port_span and row.port_span != probe:
            ev.note(f"题干端口 {probe} 落在更宽的配置行 {row.port_span} 内")
        for index, candidate in enumerate(rows):
            if candidate is row and index > 0:
                previous = rows[index - 1]
                ev.note(
                    f"相邻行 {previous.port_span} 为 {previous.system} "
                    f"{previous.vlan or '网络分配列为空'}"
                )
                break
    if len(hits) > 1:
        ev.unresolved_add(
            f"端口 {probe} 同时落在 {len(hits)} 个区间内，区间存在重叠"
        )
    return ev.build(
        "answered" if len(hits) == 1 else "partial",
        "；".join(parts) + "。",
        ev.facts_path,
    )


def _exact_cable_rows(
    ev: Evaluator, blocks: tuple[Block, ...], targets: tuple[int, ...]
):
    if not blocks:
        ev.unresolved_add("找不到对应的线缆表块")
        return None
    if len(blocks) > 1:
        ev.unresolved_add(
            "同一机柜/设备匹配到 2 张以上线缆表："
            + "、".join(block.title for block in blocks)
        )
        return None
    block = blocks[0]
    wanted = set(targets)
    rows = [row for row in block.cable_rows if row.e_number in wanted]
    if not rows:
        ev.unresolved_add(
            f"线缆表 {block.title} 中没有编号 {sorted(wanted)} 的电缆行"
        )
        return None
    presence = ev.operator(
        "set_enumeration",
        {
            "observed": [_e_label(row.e_number) for row in rows],
            "expected": [_e_label(number) for number in targets],
        },
    )
    missing = [
        int(label[1:])
        for label in presence["value"].get("missing", [])
        if label.startswith("E")
    ]
    parts: list[str] = []
    if len(rows) > 1:
        counts: dict[int, int] = {}
        for row in rows:
            counts[row.e_number] = counts.get(row.e_number, 0) + 1
        for number, count in sorted(counts.items()):
            if count > 1:
                response = ev.operator(
                    "set_enumeration",
                    {
                        "observed": [_e_label(row.e_number) for row in rows],
                        "expected": [_e_label(number)],
                    },
                )
                ev.claim(
                    f"编号 {_e_label(number)} 在表内出现 {count} 次",
                    str(count),
                    [fact for row in rows for fact in row.facts],
                )
                parts.append(
                    f"编号 {_e_label(number)} 在表内出现 {count} 次"
                    f"（算子 duplicates：{response['value'].get('duplicates')}）"
                )
    for row in rows:
        text, columns = _row_summary(row, block)
        for name, value, facts in columns:
            ev.claim(f"{_e_label(row.e_number or 0)} 的{name}：{value}", value, facts)
        parts.append(f"{_e_label(row.e_number or 0)}：{text}")
    if missing:
        ev.unresolved_add(f"表中缺少编号 {[_e_label(n) for n in missing]}")
    status = "answered" if not missing else "partial"
    return ev.build(status, "。".join(parts) + "。", ev.facts_path)


def _first_cable_record(
    ev: Evaluator, blocks: tuple[Block, ...], hints, unique: bool = False
):
    """The first cable row of a block ("段首"/"第一条线")."""

    if not blocks:
        ev.unresolved_add("找不到对应的线缆表块")
        return None
    if unique:
        with_rows = [block for block in blocks if block.cable_rows]
        if len(with_rows) != 1 or len(with_rows[0].cable_rows) != 1:
            ev.unresolved_add(
                "题干说「唯一」电缆，但匹配到的线缆表不是恰好一行："
                + "、".join(
                    f"{block.title}（{len(block.cable_rows)} 条）"
                    for block in with_rows
                )
            )
            return None
        blocks = tuple(with_rows)
    candidates = [
        (block, block.cable_rows[0]) for block in blocks if block.cable_rows
    ]
    if not candidates:
        ev.unresolved_add("线缆表块里没有电缆行")
        return None
    if hints:
        matched = []
        for block, row in candidates:
            end = row.relation_fact("cable_endpoint_end")
            target = end.raw_value if end else ""
            if any(hint in target for hint in hints):
                matched.append((block, row))
        if matched:
            candidates = matched
        elif len(candidates) > 1:
            ev.unresolved_add(
                f"端点提示 {list(hints)} 没有匹配任何线缆表首行"
            )
    if len(candidates) > 1:
        ev.unresolved_add(
            "有多张线缆表的首行都可能命中题干："
            + "、".join(block.title for block, _ in candidates)
        )
        return None
    block, row = candidates[0]
    text, columns = _row_summary(row, block)
    for name, value, facts in columns:
        ev.claim(f"{_e_label(row.e_number or 0)} 的{name}：{value}", value, facts)
    ev.evidence.extend(row.facts)
    return ev.build(
        "answered",
        f"{_e_label(row.e_number or 0)}：{text}。",
        ev.facts_path,
    )


def _wants_first(query: str) -> bool:
    return any(marker in query for marker in _FIRST_MARKERS)


def _handle_exact_record(ev: Evaluator):
    anchors = ev.anchors
    if _wants_first(ev.query) and not anchors.target_e_numbers():
        if anchors.pair is not None:
            cabinet, device = anchors.pair
            blocks = ev.index.cable_blocks(cabinet, device)
        else:
            blocks = tuple(
                block
                for device in anchors.devices
                for block in ev.index.cable_blocks(None, device)
            )
        if blocks:
            return _first_cable_record(
                ev, blocks, anchors.hints, unique="唯一" in ev.query
            )
    if anchors.cable_ids:
        blocks: list[Block] = []
        seen: set[str] = set()
        for cable_id in anchors.cable_ids:
            for row in ev.index.cable_rows_by_id(cable_id):
                if row.block_id in seen:
                    continue
                seen.add(row.block_id)
                blocks.extend(
                    block
                    for block in ev.index.blocks
                    if block.block_id == row.block_id
                )
        if not blocks:
            ev.unresolved_add(
                f"事实层没有电缆编号 {list(anchors.cable_ids)} 的行"
            )
            return None
        targets = tuple(
            row.e_number
            for cable_id in anchors.cable_ids
            for row in ev.index.cable_rows_by_id(cable_id)
            if row.e_number is not None
        )
        return _exact_cable_rows(ev, tuple(blocks), targets)

    pair = anchors.pair
    if pair is None:
        if anchors.devices:
            ev.unresolved_add(
                "题干只给出设备标识、没有机柜范围，无法按 §4.2 限定线缆表："
                + "、".join(anchors.devices)
            )
        else:
            ev.unresolved_add("题干没有可解析的机柜/设备锚点")
        return None
    cabinet, device = pair

    targets = anchors.target_e_numbers()
    if targets:
        blocks = ev.index.cable_blocks(cabinet, device)
        return _exact_cable_rows(ev, blocks, targets)
    if anchors.ports:
        return _exact_switch_ports(ev, cabinet, device, anchors.ports[0])
    ev.unresolved_add(
        "exact_record 题既没有端口区间也没有电缆编号，原型不处理该形态"
    )
    return None


# ---------------------------------------------------------------------------
# handler: set_enumeration
# ---------------------------------------------------------------------------


def _enumerate_switch_blocks(ev: Evaluator, cabinet: str, device: str):
    rows = ev.index.switch_rows(cabinet, device)
    if not rows:
        ev.unresolved_add(
            f"配置表中找不到机柜 {cabinet} / 设备 {device} 的端口事实"
        )
        return None
    observed: list[str] = []
    parts: list[str] = []
    for row in rows:
        ports = _expand_ports(row)
        if not ports:
            continue
        observed.extend(str(port) for port in ports)
        cells = row.cells
        allocation = cells[3] if len(cells) > 3 else ""
        facts = _span_row_facts(row)
        system = row.system or ""
        tail = row.vlan if row.vlan else "网络分配列为空"
        parts.append(f"{row.port_span} {system} {tail}")
        ev.claim(
            f"端口块 {row.port_span} 的系统：{system}", system, facts
        )
        if row.vlan:
            ev.claim(f"端口块 {row.port_span} 的网络分配：{row.vlan}", row.vlan, facts)
        elif allocation == "":
            ev.claim(
                f"端口块 {row.port_span} 的网络分配列为空",
                "网络分配列为空",
                facts,
            )
    top = max((max(_expand_ports(row), default=0) for row in rows), default=0)
    expected = [str(number) for number in range(1, top + 1)]
    response = ev.operator(
        "set_enumeration", {"observed": observed, "expected": expected}
    )
    value = response["value"]
    status = "answered" if value.get("exact") else "partial"
    if not value.get("complete"):
        ev.unresolved_add(f"端口枚举缺号：{value.get('missing')}")
    if value.get("duplicates"):
        ev.unresolved_add(f"端口被重复分配：{value.get('duplicates')}")
    answer = (
        f"共 {len(rows)} 个端口块：" + "；".join(parts) + "。"
        f"端口 1-{top} 枚举 complete={value.get('complete')}、"
        f"exact={value.get('exact')}，duplicates={value.get('duplicates')}。"
    )
    return ev.build(status, answer, ev.facts_path)


def _enumerate_cables(ev: Evaluator, block: Block):
    walk = walk_slots(block)
    numbers = sorted({slot.index for slot in walk.cable_slots})
    observed = [_e_label(slot.index) for slot in walk.cable_slots]
    if numbers:
        expected = [_e_label(number) for number in range(numbers[0], numbers[-1] + 1)]
        response = ev.operator(
            "set_enumeration", {"observed": observed, "expected": expected}
        )
        value = response["value"]
    else:
        value = {}
        ev.unresolved_add("线缆表没有可枚举的电缆编号")
    for row in block.cable_rows:
        end = row.relation_fact("cable_endpoint_end")
        use = row.attribute_fact("device_use")
        facts = _row_fact_list(row)
        if end is not None and end.raw_value:
            ev.claim(
                f"{_e_label(row.e_number or 0)} 的终端：{end.raw_value}",
                end.raw_value,
                [end],
            )
        if use is not None and use.raw_value:
            ev.claim(
                f"{_e_label(row.e_number or 0)} 的设备用途：{use.raw_value}",
                use.raw_value,
                [use],
            )
        ev.evidence.extend(facts)
    reserved = _describe_reserved(block.reserved_rows)
    facts = [fact for row in block.reserved_rows for fact in row.facts]
    if reserved:
        ev.claim(f"另有预留行：{reserved}", reserved, facts)
    ev.note("槽位模型：" + _slot_summary(walk))
    if walk.gaps:
        ev.unresolved_add(f"表内未声明的空槽：{walk.gaps}")
    if walk.overlaps:
        ev.unresolved_add("电缆编号回退（可能与前面的编号重复）")
    if walk.unknown:
        ev.unresolved_add("有预留行没有声明数量，槽位无法继续累加")
    if walk.leading_reserved:
        ev.unresolved_add("首行是预留行，槽位起点按 1 计（表内未直接印出）")
    status = "answered" if len(numbers) else "partial"
    if walk.gaps or walk.overlaps or walk.unknown:
        status = "partial"
    notes = _describe_notes(block)
    answer = (
        f"共 {len(block.cable_rows)} 条实际电缆：{_describe_cables(block.cable_rows)}。"
        f"另有预留行：{reserved or '无'}。"
        f"表内注记：{notes or '无'}。"
        f"编号枚举 complete={value.get('complete')}、"
        f"exact={value.get('exact')}、missing={value.get('missing')}。"
    )
    return ev.build(status, answer, ev.facts_path)


def _handle_set_enumeration(ev: Evaluator):
    pair = ev.anchors.pair
    if pair is None:
        ev.unresolved_add("题干没有可解析的机柜/设备锚点")
        return None
    cabinet, device = pair
    blocks = ev.index.cable_blocks(cabinet, device)
    wants_cable = "线缆表" in ev.query
    switch_rows = ev.index.switch_rows(cabinet, device)
    if wants_cable and blocks:
        if len(blocks) > 1:
            ev.unresolved_add(
                "匹配到多张线缆表：" + "、".join(block.title for block in blocks)
            )
            return None
        return _enumerate_cables(ev, blocks[0])
    if switch_rows:
        return _enumerate_switch_blocks(ev, cabinet, device)
    if blocks:
        if len(blocks) > 1:
            ev.unresolved_add(
                "匹配到多张线缆表：" + "、".join(block.title for block in blocks)
            )
            return None
        return _enumerate_cables(ev, blocks[0])
    ev.unresolved_add("配置表与线缆表都没有匹配的事实")
    return None


# ---------------------------------------------------------------------------
# handler: negative_boundary
# ---------------------------------------------------------------------------


def _boundary_cable(ev: Evaluator, block: Block):
    walk = walk_slots(block)
    if not walk.slots:
        ev.unresolved_add(
            f"线缆表 {block.title} 没有可还原的电缆/预留行"
        )
        return None
    by_index = {slot.index: slot for slot in walk.slots}
    anchors = ev.anchors

    explicit = anchors.target_e_numbers()
    trailing = (
        anchors.boundary_e is not None
        and not anchors.e_ranges
        and len(anchors.e_numbers) == 1
        and any(marker in ev.query for marker in ("之后", "以后", "收尾"))
    )
    if trailing:
        boundary = anchors.boundary_e
        expected = [
            _e_label(number) for number in range(boundary + 1, (walk.end or boundary) + 1)
        ]
        observed = [
            _e_label(slot.index)
            for slot in walk.cable_slots
            if slot.index > boundary
        ]
        response = ev.operator(
            "set_enumeration", {"observed": observed, "expected": expected}
        )
        value = response["value"]
        reserved_runs = [
            (label, numbers)
            for label, numbers in _runs(
                [
                    (slot.index, slot.label)
                    for slot in walk.slots
                    if slot.index > boundary and slot.kind == "reserved"
                ]
            )
        ]
        missing = value.get("missing", [])
        numbers = [int(label[1:]) for label in missing]
        facts = [fact for row in block.data_rows for fact in row.facts]
        text = "、".join(
            f"{_number_span(item)}={label}" for label, item in reserved_runs
        )
        for label in missing:
            ev.claim(f"{label} 在表内没有电缆记录", label, facts)
        if text:
            ev.claim(f"{_e_label(boundary)} 之后的预留行：{text}", text, facts)
        answer = (
            f"{_e_label(boundary)} 之后没有 "
            f"{_number_span(numbers) if numbers else '其他编号'} 的电缆记录"
            f"（set_enumeration missing={missing}）"
            + (f"；表内以预留行收尾：{text}" if text else "")
            + "。"
        )
        ev.note("槽位模型：" + _slot_summary(walk))
        return ev.build("answered", answer, ev.facts_path)

    if explicit:
        wanted = set(explicit)
        expected = [_e_label(number) for number in explicit]
        observed = [
            _e_label(number)
            for number in sorted(by_index)
            if number in wanted and by_index[number].kind == "cable"
        ]
        response = ev.operator(
            "set_enumeration", {"observed": observed, "expected": expected}
        )
        value = response["value"]
        reserved_runs = _runs(
            [
                (number, by_index[number].label)
                for number in sorted(by_index)
                if number in wanted and by_index[number].kind == "reserved"
            ]
        )
        missing = value.get("missing", [])
        missing_numbers = [
            int(label[1:]) for label in missing if label.startswith("E")
        ]
        facts = [
            fact
            for row in block.data_rows
            for fact in row.facts
            if row.e_number in wanted
            or (row.reserved_label and row.e_number is None)
        ]
        for label in missing:
            ev.claim(f"{label} 在表内没有电缆记录", label, facts)
        text = "、".join(
            f"{_number_span(numbers)}={label}"
            for label, numbers in reserved_runs
        )
        for label, numbers in reserved_runs:
            ev.claim(
                f"预留声明 {label} 覆盖 {_number_span(numbers)}", label, facts
            )
        if text:
            ev.claim(f"该区间由预留行覆盖：{text}", text, facts)
        anchor_max = max(missing_numbers) if missing_numbers else max(wanted)
        after = sorted(
            number
            for number in by_index
            if number > anchor_max and by_index[number].kind == "cable"
        )
        if after:
            ev.claim(
                f"区间之后的下一条电缆：{_e_label(after[0])}",
                _e_label(after[0]),
                facts,
            )
        if missing_numbers:
            headline = f"没有 {_number_span(missing_numbers)} 的电缆记录"
            detail = f"（set_enumeration missing={missing}）"
        else:
            headline = "题干区间内每一号都有电缆行"
            detail = "（set_enumeration missing=[]）"
        answer = (
            headline
            + detail
            + (f"；这些槽位由预留行覆盖：{text}" if text else "")
            + (
                f"；区间之后的下一条电缆为 {_e_label(after[0])}"
                if after
                else ""
            )
            + "。"
        )
        ev.note("槽位模型：" + _slot_summary(walk))
        if missing and not text:
            ev.unresolved_add("缺号没有被同区间的预留行覆盖")
        return ev.build(
            "answered" if missing else "partial", answer, ev.facts_path
        )

    if anchors.ports:
        ports: list[int] = []
        for spec in anchors.ports:
            low, _, high = spec.partition("-")
            ports.extend(range(int(low), int(high or low) + 1))
        expected = [str(number) for number in ports]
        covered = set(walk.covered)
        observed = [str(number) for number in ports if number in covered]
        response = ev.operator(
            "set_enumeration", {"observed": observed, "expected": expected}
        )
        value = response["value"]
        facts = [fact for row in block.data_rows for fact in row.facts]
        listed = "、".join(observed) if observed else "无"
        answer = (
            f"线缆表 {block.title} 只覆盖槽位 {walk.start}-{walk.end}，"
            f"端口 {anchors.ports[0]} 中列出的电缆记录为 {listed}；"
            f"算子 missing 共 {len(value.get('missing', []))} 个。"
        )
        ev.claim(
            f"线缆表槽位范围为 {walk.start}-{walk.end}",
            f"{walk.start}-{walk.end}",
            facts,
        )
        return ev.build(
            "answered" if walk.start is not None else "partial",
            answer,
            ev.facts_path,
        )

    boundary = anchors.boundary_e
    if boundary is None:
        ev.unresolved_add("negative_boundary 题没有 E 编号或端口区间锚点")
        return None
    following = sorted(
        number
        for number in by_index
        if number > boundary and by_index[number].kind == "cable"
    )
    stop = following[0] if following else (walk.end or boundary) + 1
    expected = [_e_label(number) for number in range(boundary + 1, stop)]
    observed = [
        _e_label(number)
        for number in sorted(by_index)
        if boundary < number < stop and by_index[number].kind == "cable"
    ]
    response = ev.operator(
        "set_enumeration", {"observed": observed, "expected": expected}
    )
    value = response["value"]
    facts = [fact for row in block.data_rows for fact in row.facts]
    answer = (
        f"{_e_label(boundary)} 之后到下一根电缆之间没有电缆编号 "
        f"{value.get('missing')}（observed={observed}）；"
        f"该区间在表内是："
        + "、".join(
            f"{number}={by_index[number].label}"
            for number in range(boundary + 1, stop)
            if number in by_index
        )
        + "。"
    )
    return ev.build("answered", answer, ev.facts_path)


def _boundary_switch_overlap(ev: Evaluator, cabinet: str, device: str):
    rows = ev.index.switch_rows(cabinet, device)
    if not rows:
        ev.unresolved_add(
            f"配置表中找不到机柜 {cabinet} / 设备 {device} 的端口事实"
        )
        return None
    observed: list[str] = []
    for row in rows:
        observed.extend(str(port) for port in _expand_ports(row))
    top = max((max(_expand_ports(row), default=0) for row in rows), default=0)
    expected = [str(number) for number in range(1, top + 1)]
    response = ev.operator(
        "set_enumeration", {"observed": observed, "expected": expected}
    )
    value = response["value"]
    duplicates = value.get("duplicates") or []
    parts: list[str] = []
    for item in duplicates:
        port = item["value"]
        owners: list[str] = []
        for row in rows:
            span = row.port_span
            if not span:
                continue
            check = ev.operator(
                "port_range_membership", {"spec": span, "probe": int(port)}
            )
            if check["status"] == "ok" and check["value"].get("contained"):
                owners.append(f"{span}（{row.system}）")
        if owners:
            text = f"端口 {port} 同时落在 " + "、".join(owners)
            parts.append(text)
            ev.claim(text, port, [fact for row in rows for fact in row.facts])
    for row in rows:
        ev.claim(
            f"端口块 {row.port_span} 的系统：{row.system}",
            row.system or "",
            _span_row_facts(row),
        )
        if row.vlan:
            ev.claim(
                f"端口块 {row.port_span} 的网络分配：{row.vlan}",
                row.vlan,
                _span_row_facts(row),
            )
    answer = (
        f"{'存在重叠' if duplicates else '不存在重叠'}："
        + "；".join(parts)
        + f"。算子 duplicates={duplicates}，complete={value.get('complete')}。"
    )
    return ev.build("answered", answer, ev.facts_path)


def _wants_duplicates(query: str) -> bool:
    return any(
        marker in query
        for marker in ("出现了几次", "几次", "重复", "两行", "两次")
    )


def _wants_overlap(query: str) -> bool:
    return any(marker in query for marker in ("重叠", "重复分配", "覆盖"))


def _duplicate_rows(ev: Evaluator, block: Block):
    """How often one cable number is printed, and what differs per row."""

    number = ev.anchors.boundary_e
    if number is None:
        ev.unresolved_add("没有可统计的电缆短号")
        return None
    rows = [row for row in block.cable_rows if row.e_number == number]
    if not rows:
        ev.unresolved_add(
            f"线缆表 {block.title} 中没有 {_e_label(number)} 行"
        )
        return None
    label = _e_label(number)
    response = ev.operator(
        "set_enumeration",
        {"observed": [label for _ in rows], "expected": [label]},
    )
    value = response["value"]
    facts = [fact for row in rows for fact in row.facts]
    parts: list[str] = []
    for row in rows:
        serial = row.cells[0] if row.cells and row.cells[0] else "?"
        use = row.attribute_fact("device_use")
        end = row.relation_fact("cable_endpoint_end")
        text = (
            f"序号 {serial} 用途 {use.raw_value if use else '（无）'}"
            f"、终端 {end.raw_value if end else '（无）'}"
        )
        parts.append(text)
        if use is not None:
            ev.claim(
                f"{label}（序号 {serial}）的设备用途：{use.raw_value}",
                use.raw_value,
                [use],
            )
        if end is not None:
            ev.claim(
                f"{label}（序号 {serial}）的终端：{end.raw_value}",
                end.raw_value,
                [end],
            )
    ev.claim(
        f"编号 {label} 在表内出现 {len(rows)} 次",
        str(len(rows)),
        facts,
    )
    ev.evidence.extend(facts)
    answer = (
        f"编号 {label} 在表内出现 {len(rows)} 次："
        + "；".join(parts)
        + "。同一编号被两行不同用途的记录共用，编号不能唯一标识一根电缆"
        f"（set_enumeration duplicates={value.get('duplicates')}）。"
    )
    return ev.build("answered", answer, ev.facts_path)


def _switch_usage(ev: Evaluator, cabinet: str, device: str):
    """Port block usage / VLAN allocation for a negative_boundary stem."""

    if ev.anchors.ports:
        return _exact_switch_ports(ev, cabinet, device, ev.anchors.ports[0])
    return _enumerate_switch_blocks(ev, cabinet, device)


def _handle_negative_boundary(ev: Evaluator):
    pair = ev.anchors.pair
    if pair is None:
        ev.unresolved_add("题干没有可解析的机柜/设备锚点")
        return None
    cabinet, device = pair
    blocks = ev.index.cable_blocks(cabinet, device)
    wants_cable = "线缆表" in ev.query
    has_e_anchor = bool(ev.anchors.e_numbers or ev.anchors.e_ranges)
    switch_rows = ev.index.switch_rows(cabinet, device)
    if blocks and (wants_cable or has_e_anchor or not switch_rows):
        if len(blocks) > 1:
            ev.unresolved_add(
                "匹配到多张线缆表：" + "、".join(block.title for block in blocks)
            )
            return None
        if _wants_duplicates(ev.query) and ev.anchors.boundary_e is not None:
            return _duplicate_rows(ev, blocks[0])
        return _boundary_cable(ev, blocks[0])
    if _wants_overlap(ev.query):
        return _boundary_switch_overlap(ev, cabinet, device)
    return _switch_usage(ev, cabinet, device)


# ---------------------------------------------------------------------------
# handler: cross_table_join
# ---------------------------------------------------------------------------


def _balance(ev: Evaluator, cabinet: str, device: str, block: Block):
    walk = walk_slots(block)
    if walk.start is None:
        ev.unresolved_add(f"线缆表 {block.title} 没有可还原的槽位")
        return None
    rows = ev.index.switch_rows(cabinet, device)
    if not rows:
        ev.unresolved_add(
            f"配置表中找不到机柜 {cabinet} / 设备 {device} 的端口事实"
        )
        return None
    selected = list(rows)
    if ev.anchors.ports:
        selected = []
        touched = []
        for row in rows:
            span = row.port_span
            if not span:
                continue
            response = ev.operator(
                "port_range_membership",
                {"spec": span, "probe": ev.anchors.ports[0]},
            )
            value = response["value"] if response["status"] == "ok" else {}
            if value.get("contained"):
                selected.append(row)
            elif value.get("overlap"):
                touched.append(row)
        if not selected and touched:
            selected = touched
            ev.note(
                f"端口区间 {ev.anchors.ports[0]} 跨 {len(touched)} 个配置行，"
                "按 overlap 取行"
            )
        if not selected:
            ev.unresolved_add(
                f"端口 {ev.anchors.ports[0]} 没有落在任何配置行内"
            )
            return None
    expected: list[str] = []
    config_parts: list[str] = []
    for row in selected:
        expected.extend(str(port) for port in _expand_ports(row))
        config_parts.append(
            f"{row.port_span}（{row.system} {row.vlan or '无 VLAN'}）"
        )
        ev.claim(
            f"配置表端口块 {row.port_span} 的系统：{row.system}",
            row.system or "",
            _span_row_facts(row),
        )
        if row.vlan:
            ev.claim(
                f"配置表端口块 {row.port_span} 的网络分配：{row.vlan}",
                row.vlan,
                _span_row_facts(row),
            )
    # The question asks about one port block; cable rows whose slot falls
    # outside that block belong to another system and are excluded from the
    # balance, and named in the notes with the config row that owns them.
    window = {int(number) for number in expected}
    inside = [slot for slot in walk.slots if slot.index in window]
    outside = [slot for slot in walk.slots if slot.index not in window]
    observed = [str(number) for number in sorted({s.index for s in inside})]
    response = ev.operator(
        "set_enumeration", {"observed": observed, "expected": expected}
    )
    value = response["value"]
    allocated = len([slot for slot in inside if slot.kind == "cable"])
    reserved = len([slot for slot in inside if slot.kind == "reserved"])
    in_row_ids = {id(slot.row) for slot in inside}
    in_cables = tuple(
        row for row in block.cable_rows if id(row) in in_row_ids
    )
    in_reserved = tuple(
        row for row in block.reserved_rows if id(row) in in_row_ids
    )
    facts = [fact for row in block.data_rows for fact in row.facts]
    composition = _describe_cables(in_cables)
    reserved_text = _describe_reserved(in_reserved)
    outside_note = ""
    if outside:
        outside_numbers = sorted({slot.index for slot in outside})
        owners: list[str] = []
        for row in rows:
            ports = set(_expand_ports(row))
            if ports & set(outside_numbers):
                owners.append(f"配置行 {row.port_span}（{row.system}）")
        outside_note = (
            f"块外槽位 {_number_span(outside_numbers)} 属于 "
            f"{('、'.join(owners)) or '配置表未覆盖的端口'}，未计入本次配平。"
        )
        ev.note(
            "排除块外行：" + "、".join(
                _e_label(number) for number in outside_numbers
            )
        )
    answer = (
        f"{'能配平' if value.get('exact') else '不能完全配平'}："
        f"端口 {expected[0]}-{expected[-1]} 共 {len(expected)} 个，"
        f"由实接电缆 {allocated} 条 + 预留声明 {reserved} 个 = "
        f"{allocated + reserved} 覆盖；"
        f"算子 complete={value.get('complete')}、exact={value.get('exact')}、"
        f"missing={value.get('missing')}、extra={value.get('extra')}。"
        f"线缆构成：{composition}；预留行：{reserved_text or '无'}。"
        + outside_note
    )
    ev.claim(
        f"端口 {expected[0]}-{expected[-1]} 共 {len(expected)} 个",
        f"{len(expected)}",
        facts,
    )
    ev.claim(
        f"实接电缆 {allocated} 条、预留声明 {reserved} 个",
        f"{allocated}",
        facts,
    )
    ev.evidence.extend(facts)
    ev.note("配置行：" + "；".join(config_parts))
    if value.get("missing"):
        ev.unresolved_add(f"未被线缆表覆盖的端口：{value.get('missing')}")
    status = "answered" if value.get("exact") else "partial"
    return ev.build(status, answer, ev.facts_path)


def _multi_block_join(ev: Evaluator, blocks: tuple[Block, ...]):
    parts: list[str] = []
    covered: list[str] = []
    for block in blocks:
        walk = walk_slots(block)
        first = walk.start
        last = walk.end
        prefixes = sorted(
            {row.cable_id.split("/", 1)[0] for row in block.cable_rows if row.cable_id}
        )
        parts.append(
            f"{block.title}：{_e_label(first)}–{_e_label(last)}"
            f"（{len(block.cable_rows)} 条电缆，"
            f"预留 {_describe_reserved(block.reserved_rows) or '无'}，"
            f"注记 {_describe_notes(block) or '无'}，"
            f"前缀 {'/'.join(prefixes)}）"
            if first is not None and last is not None
            else f"{block.title}：没有可还原的槽位"
        )
        covered.extend(_e_label(slot.index) for slot in walk.slots if slot.kind == "cable")
        ev.claim(
            f"{block.title} 覆盖 {_e_label(first)}–{_e_label(last)}"
            if first is not None and last is not None
            else f"{block.title} 没有槽位",
            f"{_e_label(first)}–{_e_label(last)}" if first is not None else "",
            [fact for row in block.data_rows for fact in row.facts],
        )
    response = ev.operator(
        "set_enumeration",
        {"observed": covered, "expected": sorted(set(covered))},
    )
    value = response["value"]
    answer = (
        "同一台交换机被拆在 " + str(len(blocks)) + " 张线缆表中："
        + "；".join(parts)
        + f"。跨表重复编号（set_enumeration duplicates）={value.get('duplicates')}。"
    )
    ev.unresolved_add(
        "多表题只汇总了每张表的编号范围与前缀，未逐条核对题干要求的边界归属"
    )
    return ev.build("partial", answer, ev.facts_path)


def _handle_cross_table_join(ev: Evaluator):
    pair = ev.anchors.pair
    if pair is not None:
        cabinet, device = pair
        blocks = ev.index.cable_blocks(cabinet, device)
        if not blocks:
            ev.unresolved_add(
                f"找不到机柜 {cabinet} / 设备 {device} 的线缆表块"
            )
            return None
        if len(blocks) == 1:
            return _balance(ev, cabinet, device, blocks[0])
        return _multi_block_join(ev, blocks)
    if ev.anchors.devices:
        blocks: list[Block] = []
        seen: set[str] = set()
        for device in ev.anchors.devices:
            for block in ev.index.cable_blocks(None, device):
                if block.block_id in seen:
                    continue
                seen.add(block.block_id)
                blocks.append(block)
        if not blocks:
            ev.unresolved_add(
                f"找不到设备 {list(ev.anchors.devices)} 的线缆表块"
            )
            return None
        if len(blocks) == 1:
            cabinet = blocks[0].cabinet or ""
            return _balance(ev, cabinet, device=blocks[0].device or ev.anchors.devices[0], block=blocks[0])
        return _multi_block_join(ev, tuple(blocks))
    ev.unresolved_add("题干没有可解析的机柜/设备锚点")
    return None


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


HANDLERS = {
    "exact_record": _handle_exact_record,
    "set_enumeration": _handle_set_enumeration,
    "negative_boundary": _handle_negative_boundary,
    "cross_table_join": _handle_cross_table_join,
}


def evaluate(
    question: dict, facts, facts_path=common.DEFAULT_FACTS
) -> dict:
    """Evaluate one S1 question against the connectivity fact layer."""

    reason = common.guard_verdict_class(question)
    if reason is not None:
        return common.not_evaluated_report(
            question,
            reason,
            facts_path=facts_path,
            command=(
                "python3 scripts/research/prototypes/p1_cable_cross_table.py "
                f"--question {question['base_id']}"
            ),
        )
    if question.get("scenario") != SCENARIO:
        return common.unsupported_report(
            question,
            f"scenario={question.get('scenario')} 不属于 S1 线缆跨表关联原型",
            facts_path=facts_path,
        )
    index = FactIndex(facts.sorted() if hasattr(facts, "sorted") else facts)
    evaluator = Evaluator(question, index, facts_path)
    handler = HANDLERS.get(question.get("task_type", ""))
    if handler is None:
        return common.unsupported_report(
            question,
            f"task_type={question.get('task_type')} 超出原型覆盖范围",
            facts_path=facts_path,
            command=evaluator.command(facts_path),
        )
    if not evaluator.query:
        return common.unsupported_report(
            question,
            "题干为空，无法解析锚点",
            facts_path=facts_path,
            command=evaluator.command(facts_path),
        )
    report = handler(evaluator)
    if report is None:
        return common.build_report(
            question,
            status="insufficient",
            answer="",
            claims=evaluator.claims,
            operators=evaluator.operators,
            facts=evaluator.evidence,
            unresolved=evaluator.unresolved
            or ["原型没有覆盖该题形态"],
            notes=" ".join(evaluator.notes),
            facts_path=facts_path,
            command=evaluator.command(facts_path),
        )
    issue = KNOWN_BENCHMARK_ISSUES.get(question["base_id"])
    if issue:
        report["notes"] = (report["notes"] + " " + issue).strip()
    return report


def _evaluate_one(base_id: str, split: str | None, facts, facts_path) -> dict:
    question = common.get_question(base_id)
    if split and question.get("split") != split:
        raise SystemExit(f"{base_id} 不在 {split} split")
    return evaluate(question, facts, facts_path)


def _all(split: str, facts, facts_path) -> dict:
    """Run every deterministic S1 question of one dev/val split."""

    questions = [
        item
        for _, item in sorted(common.question_index((split,)).items())
        if item.get("scenario") == SCENARIO
    ]
    deterministic = [
        item for item in questions if not common.guard_verdict_class(item)
    ]
    skipped = [
        {
            "question_id": item["base_id"],
            "reason": common.guard_verdict_class(item),
        }
        for item in questions
        if common.guard_verdict_class(item)
    ]
    reports = [evaluate(question, facts, facts_path) for question in deterministic]
    counts: dict[str, int] = {}
    for report in reports:
        counts[report["status"]] = counts.get(report["status"], 0) + 1
    return {
        "scenario": SCENARIO,
        "split": split,
        "facts_sha256": common.facts_digest(facts_path),
        "question_count": len(reports),
        "skipped_not_deterministic": skipped,
        "status_counts": dict(sorted(counts.items())),
        "questions": [
            {
                "question_id": report["question_id"],
                "task_type": report["task_type"],
                "status": report["status"],
                "answer": report["answer"],
                "unresolved": report["unresolved_conditions"],
            }
            for report in reports
        ],
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="", help="dev/val base_id")
    parser.add_argument("--all", action="store_true", help="run the whole split")
    parser.add_argument("--split", default="dev", choices=["dev", "val"])
    parser.add_argument("--facts", default=str(common.DEFAULT_FACTS))
    parser.add_argument("--out", default="", help="report path; empty prints JSON")
    args = parser.parse_args(argv)
    facts = common.load_facts(args.facts)
    if args.all:
        result = _all(args.split, facts, args.facts)
        if args.out:
            common.write_report(args.out, result)
        summary = {key: value for key, value in result.items() if key != "questions"}
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        for item in result["questions"]:
            print(
                f"{item['question_id']} {item['task_type']:<14} "
                f"{item['status']:<12} {item['answer'][:70]}"
            )
        return
    if not args.question:
        parser.error("either --question or --all is required")
    report = _evaluate_one(args.question, None, facts, args.facts)
    if args.out:
        common.write_report(args.out, report)
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":  # pragma: no cover
    main()
