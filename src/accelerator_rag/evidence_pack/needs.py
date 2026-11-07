"""Rule-based question parsing: entities, relation needs, route and scope.

Only the question text, its ``scope`` and its family metadata are read.  The
benchmark's ``task_type``/``gold`` fields are never consulted, so routing and
budgets are not oracle labels.
"""

from __future__ import annotations

import re
import unicodedata

from .schema import EntityNeed, Needs, RelationNeed, normalize_key

_VERSION = re.compile(
    r"版本|修订|第[一二三四五六七八九十0-9]+版|[一二三四五六七八九十0-9]+版|"
    r"初版|上一版|新版|旧版|归档副本|归档版|两版|各版|历代|历史版本"
)
_DESIGN = re.compile(r"设计要求|设计值|设计报告|设计目标|指标|要求|规定|应满足|目标值")
_TEST = re.compile(r"测试结果|实测|测试|测量|试验|自测|研制总结|检验")
_ACCEPT = re.compile(r"验收|评审|结论|申请书|验收书")
_TEST_SCOPE = re.compile(r"测量范围|测量端点|测试范围|测试条件|端点|量程|适用条件|适用模式")
_CONNECTION = re.compile(
    r"端口|线缆|电缆|归属|连接|VLAN|另一端|两端|配平|分配|交换机"
)
_ENUMERATION = re.compile(
    r"全部|所有|清单|哪些|分别|逐一|逐项|多少|几个|几条|共.*个|"
    r"完整列出|完整清单|完整集合|完整枚举|完整划分|完整对应|完整覆盖"
)
_COMPARISON = re.compile(
    r"对比|比较|差异|变化|相同|一致|新增|删除|保留|仍然|是否仍|"
    r"分别|两者|对应|分别对应|是否满足"
)
# DESIGN §5.1 lists only these phrases as cross-source cues.  Broader wording
# such as "相同/一致" is kept for conflict/comparison semantics but must not
# upgrade a single-table identifier lookup to cross_source.
_CROSS_SOURCE = re.compile(r"对比|分别|两者|对应|是否满足")
_BOUNDARY = re.compile(r"是否满足|满足|小于|大于|不超过|不低于|范围|边界|端点|0%|100%")
_EXPLAIN = re.compile(r"说明|介绍|功能|作用|如何|怎么|步骤|界面|路径|流程|是什么|什么")

_CABINET = re.compile(r"(?:[A-Z][A-Z0-9]*(?:[-:][A-Z0-9]+)+)(?=柜)")
_CABINET_BARE = re.compile(r"\b(?:EXT-)?L\d[-:]CN[-:]?\d{1,3}\b")
_DEVICE = re.compile(r"[A-Z][A-Z0-9]*(?:[-:][A-Z0-9]+)*SW[A-Z0-9]*")
_PV = re.compile(r"\b[A-Z][A-Z0-9]*(?::[A-Z0-9][A-Z0-9_.-]*)+\b")
_PORT_RANGE = re.compile(r"\d+\s*[-~～至—]\s*\d+")
_CABLE_ID = re.compile(r"\bE\d{2,4}\b")
_PORT_SINGLE = re.compile(r"\d+\s*(?:号)?端口")
_NUMBER = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|μs|µs|us|ns|ms|s|V|A|mA|Hz|kHz|MHz|GHz|℃|°C|mm|cm|kg|kW|W|dB)"
)
_PAREN = re.compile(r"[（(]([^）)]{2,40})[）)]")


def _contains(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


def _entities(query: str) -> tuple[EntityNeed, ...]:
    found: dict[tuple[str, str], EntityNeed] = {}

    def add(raw: str, kind: str) -> None:
        raw = raw.strip().strip("（）(),，。；;：:")
        if not raw:
            return
        key = (normalize_key(raw), kind)
        found.setdefault(key, EntityNeed(raw=raw, normalized=key[0], kind=kind))

    for match in _CABINET.finditer(query):
        add(match.group(0), "cabinet")
    for match in _CABINET_BARE.finditer(query):
        add(match.group(0), "cabinet")
    for group in _PAREN.findall(query):
        if _DEVICE.search(group):
            for match in _DEVICE.finditer(group):
                add(match.group(0), "device")
        elif re.fullmatch(r"[A-Z0-9:._-]{4,}", group) and ":" in group:
            add(group, "pv")
    for match in _DEVICE.finditer(query):
        add(match.group(0), "device")
    for match in _PV.finditer(query):
        text = match.group(0)
        if _DEVICE.search(text) or "CN" in text:
            continue
        add(text, "pv")
    if re.search(r"电缆|线缆", query):
        for match in _CABLE_ID.finditer(query):
            add(match.group(0), "cable")
    for match in _PORT_RANGE.finditer(query):
        add(match.group(0), "port")
    for match in _NUMBER.finditer(query):
        add(match.group(0), "number")

    ordered = sorted(
        found.values(),
        key=lambda item: (item.kind, item.normalized, item.raw),
    )
    return tuple(ordered)


def _relations(query: str, entities: tuple[EntityNeed, ...]) -> tuple[RelationNeed, ...]:
    text = unicodedata.normalize("NFKC", query)
    version = _contains(_VERSION, text)
    design = _contains(_DESIGN, text)
    test = _contains(_TEST, text)
    accept = _contains(_ACCEPT, text)
    test_scope = _contains(_TEST_SCOPE, text)
    connection = _contains(_CONNECTION, text)
    enumeration = _contains(_ENUMERATION, text)
    boundary = _contains(_BOUNDARY, text)
    has_number = any(item.kind == "number" for item in entities)
    has_port = any(item.kind == "port" for item in entities)
    has_pv = any(item.kind == "pv" for item in entities)

    items: list[RelationNeed] = []

    def add(name: str, required: bool, reason: str) -> None:
        if any(item.name == name for item in items):
            return
        items.append(RelationNeed(name, required, reason))

    if version:
        add("version_left", True, "问题要求对照较早版本")
        add("version_right", True, "问题要求对照较晚版本或归档副本")
        add(
            "enumeration",
            False,
            "版本对照的对齐完整性由两侧版本侧覆盖，不按表格枚举判定",
        )
        if has_number:
            add("value", False, "版本题可含具体参数值")
            add("unit", False, "版本参数值需保留单位")
        return tuple(items)
    if design:
        add("requirement", True, "问题引用了设计要求或指标")
    if test:
        add("test_result", True, "问题要求测试或实测证据")
    if accept:
        add("acceptance", True, "问题引用了验收或评审结论")
    if test_scope:
        add("test_scope", True, "问题要求测量范围/端点/条件")
    if connection:
        add("scope", True, "连接与归属必须保留机柜/表范围")
        add("counterpart", True, "连接问题必须取回另一端身份或同表对应列")
    if enumeration and connection:
        add("enumeration", True, "问题要求完整端口块或电缆清单")
    if candidate_value_needed(text, has_number, has_port, connection, design, test):
        add("value", True, "问题要求具体数值或分配值")
    if has_number or boundary or test_scope:
        add("unit", True, "数值必须保留原文单位")
    boundary_cue = _contains(_BOUNDARY, text)
    overlap_cue = bool(re.search(r"重叠|包含|属于|在.*范围|落.*范围", text))
    if boundary_cue or (has_port and overlap_cue):
        add("boundary", True, "问题要求区间/边界判断")
    if test_scope:
        add("condition", True, "测量条件必须与结果同时保留")
    if has_pv:
        add("external_observation", False, "问题含 PV 标识，可接纳只读归档观测")
    return tuple(items)


def candidate_value_needed(
    text: str,
    has_number: bool,
    has_port: bool,
    connection: bool,
    design: bool,
    test: bool,
) -> bool:
    if has_number or has_port:
        return True
    if connection and re.search(r"哪个|什么|多少|编号|名称|类型|VLAN|系统|用途", text):
        return True
    return bool(design or test)


def route_for(query: str, relations: tuple[RelationNeed, ...], entities: tuple[EntityNeed, ...]) -> str:
    text = unicodedata.normalize("NFKC", query)
    if _contains(_VERSION, text):
        return "document_explanation"
    roles = sum(
        1 for pattern in (_DESIGN, _TEST, _ACCEPT) if _contains(pattern, text)
    )
    if roles >= 2:
        return "cross_source"
    if _contains(_CROSS_SOURCE, text) and not _contains(_VERSION, text):
        return "cross_source"
    if _contains(_ENUMERATION, text) and _contains(_CONNECTION, text):
        return "cross_source"
    identifiers = any(
        item.kind in {"device", "cabinet", "cable", "port"} for item in entities
    )
    attribute_cue = bool(
        re.search(r"端口|系统|VLAN|归属|位置|编号|型号|用途|连接|线缆|电缆|表", text)
    )
    if identifiers and attribute_cue:
        return "exact_record"
    if _contains(_EXPLAIN, text):
        return "document_explanation"
    return "cross_source"


def parse_needs(
    question: dict, *, revision_ids: tuple[str, ...] = ()
) -> Needs:
    """Parse one question record; ``gold`` and ``task_type`` stay unread."""

    query = question["query"]
    entities = _entities(query)
    relations = _relations(query, entities)
    route = route_for(query, relations, entities)
    comparison = _contains(_COMPARISON, query)
    scope_ids = tuple(question.get("scope", {}).get("revision_ids", ()))
    version_pair = scope_ids if len(scope_ids) == 2 else ()
    return Needs(
        question_id=question["base_id"],
        route=route,
        entities=entities,
        relations=relations,
        revision_ids=tuple(revision_ids) or scope_ids,
        version_pair=version_pair,
        comparison=comparison,
        reason=(
            f"route={route}; entities={len(entities)}; "
            f"relations={','.join(item.name for item in relations)}"
        ),
    )
