"""P2: align one manual revision pair and compare the text verbatim.

The prototype answers one dev/val ``s2_revision`` question without a model:

1. **Resolve the revisions deterministically.**  ``scope.mode=
   explicit_revisions`` gives the revisions in order (N=2 is compared as a
   pair; N>2 is accepted for added/removed questions, with the question-named
   target compared against each prior).  Otherwise the question wording is
   mapped to ``revision_label``: ``第二版``/``第三版`` require the printed
   ordinal (``label_ordinal``), ``第一版`` is the unique manual with no
   ordinal and no archive marker (``only_non_archive_manual``), and
   ``2023归档副本``/``2024归档副本`` require the archive year
   (``archive_year``).  No marker falls back to the family's first two
   versions, or to version + archive when the family only holds those two.
   A marker that matches zero or several revisions, or a mapping that selects
   the same revision twice, is ``unsupported`` with the candidates.
2. **Align one paragraph per side by literal anchors** taken from the
   question: quoted phrases (``“…”`` / ``「…」``), explicit identifiers
   (``APPLY``, ``SHINE-AC``, ``CM52``, ``083C``, ``图3`` …) and a curated
   functional-keyword table (``离子泵``, ``回差``, ``状态灯`` …).  A paragraph
   must contain every anchor; exactly one hit per side is required.  When a
   paragraph-level search is ambiguous, the prototype retries with
   sentence-level co-occurrence.  When the curated anchors cannot align at
   all, a last-resort tier of clean 2–6 character Chinese noun phrases taken
   literally from the question is tried (1–3 phrases, unique hit required).
   Zero or several remaining hits are ``unsupported`` with the candidate
   paragraphs — similarity is never used.
3. **Compare** the two aligned paragraphs (``item_id=chunk_id``, which is
   unique even where ``position_label`` repeats, and ``text=chunk.text``) with
   the deterministic ``version_diff`` operator and
   ``normalizer="whitespace"``.  Only exact / whitespace-level equality is
   claimed; semantic equivalence is explicitly left for human review.

Answer policy (research plan §4.3, DESIGN §6):

* ``version_same``: whitespace-normalised texts equal -> ``answered`` (一致);
  different -> ``partial`` with both original sentences and the note
  “文本不一致，需语义复核”.
* ``version_diff``: both sides quoted sentence by sentence; a ``图号``
  question additionally reports the literal ``如图N所示`` references.  Status
  is ``answered`` once both sides are aligned; no semantic equivalence.
* ``version_added`` / ``version_removed``: an identifier probe (e.g.
  ``APPLY``) found on one side only -> ``answered`` with the source text of
  the side that carries it; found on both / neither, or no probe in the
  question -> ``partial``.
* ``version_boundary``: only ``revision_label`` / ``document_kind`` plus the
  question wording; approval status is never inferred, so the report is
  ``partial`` (``unsupported`` when a side cannot be resolved).

Every claim value is copied from the aligned chunk text; evidence keeps the
``chunk_id`` and ``position_label`` plus the full paragraph.
"""

from __future__ import annotations

import argparse
import collections
from dataclasses import dataclass
import json
import re

import common

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

TASKS = (
    "version_same",
    "version_diff",
    "version_added",
    "version_removed",
    "version_boundary",
)
PROBE_TASKS = ("version_added", "version_removed")
SUPPORTED_STATUSES = ("answered", "partial")


class Unsupported(Exception):
    """The question cannot be resolved deterministically."""

    def __init__(self, reason: str, candidates=()):
        super().__init__(reason)
        self.reason = reason
        self.candidates = list(candidates)


@dataclass(frozen=True)
class Side:
    role: str
    revision_id: str
    label: str
    document_kind: str


@dataclass(frozen=True)
class Anchor:
    kind: str
    source: str
    alternatives: tuple[str, ...]

    def holds(self, text: str) -> bool:
        return any(_contains(text, alt) for alt in self.alternatives)


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------


def _ws(text: str) -> str:
    """Collapse whitespace runs; used only for comparison and quote lookup."""

    return " ".join(text.split())


def _contains(text: str, needle: str) -> bool:
    return needle in text or _ws(needle) in _ws(text)


_SENTENCE_RE = re.compile(r"[。；;！？\n]+")


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_RE.split(text) if part.strip()]


def _is_heading_like(line: str) -> bool:
    # _sentences strips the trailing punctuation, so headings are recognised
    # by their short CJK length and by the absence of list/colon separators.
    cjk = sum(1 for ch in line if "\u4e00" <= ch <= "\u9fff")
    return (
        cjk >= 2
        and len(line) <= 20
        and not any(ch in line for ch in "，,：:、")
    )


def _focal_sentence(text: str, anchors: list[Anchor]) -> str:
    """The sentence covering most anchors, preferring the longest literal.

    A short first line without punctuation (a title) is skipped when another
    sentence matches, so claim values quote prose rather than headings.
    """

    scored = []
    for index, line in enumerate(_sentences(text)):
        matched = [anchor for anchor in anchors if anchor.holds(line)]
        if not matched:
            continue
        longest = max(
            (
                len(alt)
                for anchor in matched
                for alt in anchor.alternatives
                if _contains(line, alt)
            ),
            default=0,
        )
        skip = index == 0 and _is_heading_like(line)
        scored.append(((len(matched), longest, not skip), line))
    if not scored:
        return _sentences(text)[0] if text.strip() else ""
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


_FIGURE_NUM_RE = re.compile(r"图\s*([0-9]+)")

_DEVICE_LIST_RE = re.compile(r"包括\s*(.+?)[，,]?\s*界面")


def _figure_refs(text: str) -> list[str]:
    return list(
        dict.fromkeys(f"图{match.group(1)}" for match in _FIGURE_NUM_RE.finditer(text))
    )


def _figure_sentences(text: str, anchors: list[Anchor]) -> list[str]:
    """Sentences that carry every identifier anchor, best anchor coverage first."""

    identifier_anchors = [
        anchor for anchor in anchors if anchor.kind in {"identifier", "quoted"}
    ]
    lines = _sentences(text)
    if identifier_anchors:
        lines = [
            line for line in lines if all(a.holds(line) for a in identifier_anchors)
        ]
    scored = [
        (sum(1 for anchor in anchors if anchor.holds(line)), line) for line in lines
    ]
    if not scored:
        return []
    best = max(count for count, _ in scored)
    return [line for count, line in scored if count == best]


def _device_list(text: str) -> str:
    match = _DEVICE_LIST_RE.search(text)
    return match.group(1).strip() if match else ""


_ACTION_WORDS = ("进入", "菜单栏", "导航栏", "图标", "点击", "选择")


def _path_question(query: str, terms: QueryTerms) -> bool:
    """Only questions that ask for an entry path, not any sentence with 进入."""

    has_entry_concept = any(
        name in terms.concepts for name in ("进入", "菜单栏", "导航栏")
    )
    explicit_path = (
        "路径" in query
        or "菜单栏" in query
        or "导航栏" in query
        or ("通过" in query and "进入" in query)
    )
    return has_entry_concept and explicit_path


def _action_sentences(text: str, anchors: list[Anchor]) -> list[str]:
    """Sentences that state an entry action, kept to the best anchor coverage.

    Screenshot OCR paragraphs are allowed in, but only their clean action
    sentences; a heading and a figure caption never qualify.  Among the
    remaining sentences only those covering the most anchors are kept, so a
    generic "桌面图标进入" sentence does not dilute the menu path.
    """

    lines = [
        line
        for line in _sentences(text)
        if any(word in line for word in _ACTION_WORDS)
        and not _is_heading_like(line)
        and not re.match(r"^图\s*[0-9]", line)
    ]
    lines = list(dict.fromkeys(lines))
    if not lines:
        return []
    scored = [
        (sum(1 for anchor in anchors if anchor.holds(line)), line) for line in lines
    ]
    best = max(score for score, _ in scored)
    if best == 0:
        return lines
    return [line for score, line in scored if score == best]


def _sentence_tokens(sentences: list[str], limit: int = 6) -> list[str]:
    tokens = []
    for line in sentences:
        for match in _ASCII_RE.finditer(line):
            token = match.group(0).rstrip("_.+-/")
            if len(token) >= 2 and token.casefold() not in _STOPWORDS:
                tokens.append(token)
        for word in _ACTION_WORDS:
            if word in line:
                tokens.append(word)
    return list(dict.fromkeys(tokens))[:limit]


def _ocr_noise(line: str) -> bool:
    if len(line) < 40:
        return False
    ascii_ratio = sum(ch.isascii() for ch in line) / len(line)
    cjk = sum(1 for ch in line if "\u4e00" <= ch <= "\u9fff")
    return ascii_ratio > 0.6 and cjk < 8


def _context_sentences(
    text: str, anchors: list[Anchor], limit: int = 5
) -> list[str]:
    """Focal sentence first, then its neighbours; long OCR lines are dropped."""

    lines = _sentences(text)
    focal = _focal_sentence(text, anchors)
    if focal not in lines:
        return [focal] if focal else []
    index = lines.index(focal)
    ordered = (
        [focal]
        + lines[index + 1 : index + limit]
        + list(reversed(lines[max(0, index - 2) : index]))
    )
    return [
        line
        for line in ordered
        if not _ocr_noise(line) or any(anchor.holds(line) for anchor in anchors)
    ][:limit]


def _relevant(line: str, anchors: list[Anchor]) -> bool:
    if any(anchor.holds(line) for anchor in anchors):
        return True
    cjk = sum(1 for ch in line if "\u4e00" <= ch <= "\u9fff")
    return (
        cjk >= 8
        and line.count(" ") < 8
        and "|" not in line
        and not _ocr_noise(line)
    )


def _sentence_difference(
    left_text: str,
    right_text: str,
    anchors: list[Anchor] | None = None,
    limit: int = 4,
) -> tuple[list[str], list[str]]:
    """Sentences present on one side only, ignoring whitespace and OCR noise.

    With ``anchors`` the comparison is limited to each side's focal window, so
    unrelated parts of a long paragraph do not leak into the answer.
    """

    if anchors is None:
        left_lines = _sentences(left_text)
        right_lines = _sentences(right_text)
    else:
        left_lines = _context_sentences(left_text, anchors, limit=8)
        right_lines = _context_sentences(right_text, anchors, limit=8)
    right_set = {_ws(line) for line in right_lines}
    left_set = {_ws(line) for line in left_lines}
    def keep(line: str) -> bool:
        if _is_heading_like(line):
            return False
        if anchors is not None and any(anchor.holds(line) for anchor in anchors):
            return True
        if anchors is not None and not _relevant(line, anchors):
            return False
        return not _ocr_noise(line)

    left_only = [line for line in left_lines if _ws(line) not in right_set and keep(line)]
    right_only = [
        line for line in right_lines if _ws(line) not in left_set and keep(line)
    ]
    return left_only[:limit], right_only[:limit]


# ---------------------------------------------------------------------------
# revision resolution
# ---------------------------------------------------------------------------

_CN_DIGITS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_VERSION_RE = re.compile(r"第([一二三四五六七八九十])版")
_ARCHIVE_RE = re.compile(r"归档文档（(\d{6})）")
_MARKER_RE = re.compile(r"(20[0-9]{2})\s*归档副本|第([一二三四五六七八九十])版")


def label_ordinal(label: str) -> int | None:
    """Explicit ``第N版`` ordinal printed in ``revision_label``, if any."""

    match = _VERSION_RE.search(label)
    return _CN_DIGITS.get(match.group(1)) if match else None


def is_archive_label(label: str) -> bool:
    return "归档" in label or "202310" in label or "202410" in label


def version_number(label: str) -> int | None:
    """Version ordinal; a non-archive manual without one is the first version."""

    ordinal = label_ordinal(label)
    if ordinal is not None:
        return ordinal
    if is_archive_label(label):
        return None
    return 1


def archive_period(label: str) -> str | None:
    match = _ARCHIVE_RE.match(label)
    return match.group(1) if match else None


def _versions(revisions: dict[str, dict]) -> list[tuple[int, str]]:
    found = []
    for revision_id, meta in revisions.items():
        number = version_number(meta.get("revision_label", ""))
        if number is not None:
            found.append((number, revision_id))
    return sorted(found)


def _archives(revisions: dict[str, dict]) -> list[tuple[str, str]]:
    found = []
    for revision_id, meta in revisions.items():
        period = archive_period(meta.get("revision_label", ""))
        if period is not None:
            found.append((period, revision_id))
    return sorted(found)


_CN_NAMES = {
    1: "第一版",
    2: "第二版",
    3: "第三版",
    4: "第四版",
    5: "第五版",
    6: "第六版",
}


def role_from_label(label: str) -> str:
    """Human-readable side name derived from ``revision_label`` only."""

    ordinal = label_ordinal(label)
    if ordinal is not None:
        return _CN_NAMES.get(ordinal, f"第{ordinal}版")
    period = archive_period(label)
    if period is not None:
        return f"{period[:4]}归档副本"
    if is_archive_label(label):
        return "归档副本"
    return "第一版"


def _side(role: str, revision_id: str, revisions: dict[str, dict]) -> Side:
    meta = revisions.get(revision_id, {})
    return Side(
        role=role,
        revision_id=revision_id,
        label=meta.get("revision_label", ""),
        document_kind=meta.get("document_kind", ""),
    )


def revisions_for_marker(
    marker: str, revisions: dict[str, dict]
) -> tuple[list[str], str]:
    """Revisions whose ``revision_label`` realizes one question marker.

    Basis values are recorded in the report so R4 can replay the mapping:
    ``label_ordinal`` (label prints 第N版), ``only_non_archive_manual`` (the
    unique manual with no ordinal and no archive marker is 第一版) and
    ``archive_year`` (archive label carries 202310/202410 or its year).
    """

    match = _MARKER_RE.fullmatch(marker)
    if match is None:
        return [], "unmapped"
    if match.group(1):
        year = match.group(1)
        hits = []
        for revision_id, meta in revisions.items():
            label = meta.get("revision_label", "")
            if year in {"2023", "2024"}:
                period = f"{year}10"
            else:
                period = year
            if period in label or (year in label and is_archive_label(label)):
                hits.append(revision_id)
        return hits, "archive_year"
    number = _CN_DIGITS.get(match.group(2))
    if number == 1:
        hits = [
            revision_id
            for revision_id, meta in revisions.items()
            if label_ordinal(meta.get("revision_label", "")) is None
            and not is_archive_label(meta.get("revision_label", ""))
        ]
        return hits, "only_non_archive_manual"
    hits = [
        revision_id
        for revision_id, meta in revisions.items()
        if label_ordinal(meta.get("revision_label", "")) == number
    ]
    return hits, "label_ordinal"


def question_markers(query: str) -> list[str]:
    return [match.group(0).replace(" ", "") for match in _MARKER_RE.finditer(query)]


def _mapping_note(marker: str, revision_id: str, basis: str, revisions: dict) -> str:
    meta = revisions.get(revision_id, {})
    return (
        f"修订映射：{marker} → {revision_id}"
        f"（revision_label=「{meta.get('revision_label', '')}」；依据 {basis}）"
    )


def _ensure_distinct(sides: list[Side]) -> None:
    revision_ids = [side.revision_id for side in sides]
    if len(set(revision_ids)) != len(revision_ids):
        raise Unsupported("映射结果包含重复修订，拒绝自我比较", revision_ids)


def resolve_pair(
    question: dict, revisions: dict[str, dict]
) -> tuple[list[Side], list[str], str]:
    """Return the two sides, notes and the resolution mode."""

    notes: list[str] = []
    scope = question.get("scope") or {}
    if scope.get("mode") == "explicit_revisions":
        revision_ids = list(scope.get("revision_ids") or ())
        if len(revision_ids) < 2:
            raise Unsupported(
                "scope.mode=explicit_revisions 给出 "
                f"{len(revision_ids)} 个修订；至少需要两侧",
                revision_ids,
            )
        missing = [rid for rid in revision_ids if rid not in revisions]
        if missing:
            raise Unsupported("scope 中的修订不在本题族范围内", missing)
        sides = [
            _side(
                role_from_label(revisions[rid].get("revision_label", "")),
                rid,
                revisions,
            )
            for rid in revision_ids
        ]
        _ensure_distinct(sides)
        notes.extend(
            f"修订映射：按 scope.revision_ids 顺序取 {side.revision_id}"
            f"（revision_label=「{side.label}」）"
            for side in sides
        )
        return sides, notes, "explicit_revisions"

    markers = []
    for marker in question_markers(question.get("query", "")):
        if marker not in markers:
            markers.append(marker)
    if len(markers) > 2:
        raise Unsupported(
            f"题干点名 {len(markers)} 个修订标识；原型只比较一对修订",
            markers,
        )
    if len(markers) == 2:
        sides = []
        for marker in markers:
            hits, basis = revisions_for_marker(marker, revisions)
            if len(hits) != 1:
                raise Unsupported(
                    f"题干标识「{marker}」在题族内映射到 {len(hits)} 个修订，"
                    f"无法唯一确定（依据 {basis}）",
                    hits,
                )
            sides.append(_side(marker, hits[0], revisions))
            notes.append(_mapping_note(marker, hits[0], basis, revisions))
        _ensure_distinct(sides)
        return sides, notes, "query_markers"

    if len(markers) == 1:
        marker = markers[0]
        hits, basis = revisions_for_marker(marker, revisions)
        if len(hits) != 1:
            raise Unsupported(
                f"题干标识「{marker}」在题族内映射到 {len(hits)} 个修订，"
                f"无法唯一确定（依据 {basis}）",
                hits,
            )
        if not marker.endswith("归档副本"):
            raise Unsupported(
                f"题干只点名「{marker}」，未给出可确定的对照修订",
                hits,
            )
        versions = _versions(revisions)
        if not versions:
            raise Unsupported("题干只点名归档副本，题族内没有版本修订可对照")
        notes.append(_mapping_note(marker, hits[0], basis, revisions))
        notes.append(
            f"题干只点名「{marker}」；对照侧取版本号最大的修订（依据 archive_nearest_version）"
            f"「{revisions.get(versions[-1][1], {}).get('revision_label', '')}」"
        )
        sides = [
            _side(
                role_from_label(
                    revisions[versions[-1][1]].get("revision_label", "")
                ),
                versions[-1][1],
                revisions,
            ),
            _side(marker, hits[0], revisions),
        ]
        _ensure_distinct(sides)
        return sides, notes, "archive_nearest_version"

    versions = _versions(revisions)
    archives = _archives(revisions)
    if len(versions) == 2:
        if len(revisions) > 2:
            notes.append(
                "题干未点名修订标识；按版本号取前两个版本修订（依据 family_versions）"
            )
        sides = [
            _side(
                role_from_label(revisions[versions[0][1]].get("revision_label", "")),
                versions[0][1],
                revisions,
            ),
            _side(
                role_from_label(revisions[versions[1][1]].get("revision_label", "")),
                versions[1][1],
                revisions,
            ),
        ]
        _ensure_distinct(sides)
        return sides, notes, "family_versions"
    if len(versions) == 1 and len(archives) == 1:
        notes.append(
            "题干未点名修订标识；题族只有一对版本/归档修订（依据 family_pair）"
        )
        sides = [
            _side(
                role_from_label(revisions[versions[0][1]].get("revision_label", "")),
                versions[0][1],
                revisions,
            ),
            _side(
                role_from_label(revisions[archives[0][1]].get("revision_label", "")),
                archives[0][1],
                revisions,
            ),
        ]
        _ensure_distinct(sides)
        return sides, notes, "family_pair"
    raise Unsupported(
        "题干未点名修订标识，题族修订无法唯一确定为一对",
        sorted(revisions),
    )


# ---------------------------------------------------------------------------
# anchors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QueryTerms:
    markers: tuple[str, ...]
    quoted: tuple[str, ...]
    identifiers: tuple[str, ...]
    concepts: tuple[str, ...]
    probes: tuple[str, ...]


@dataclass(frozen=True)
class Concept:
    name: str
    query_terms: tuple[str, ...]
    alternatives: tuple[str, ...]


# Functional keywords: the question names a function point, the table lists the
# literal wordings that realize it in these operation manuals.  A concept is an
# anchor group: at least one alternative must occur verbatim in the paragraph.
CONCEPTS: tuple[Concept, ...] = (
    Concept("进入", ("进入", "路径"), ("进入",)),
    Concept("菜单栏", ("菜单栏",), ("菜单栏",)),
    Concept("导航栏", ("导航栏",), ("导航栏",)),
    Concept("分段页面", ("分段页面",), ("分段页面",)),
    Concept("台数", ("多少台", "几台", "台数"), ("台",)),
    Concept("按键", ("按键",), ("按键",)),
    Concept("开关", ("开关",), ("开关",)),
    Concept("颜色", ("颜色",), ("绿色", "红色")),
    Concept("用途", ("用途",), ("实时监测", "作用", "用于")),
    Concept("控件", ("控件",), ("输入框",)),
    Concept("回车", ("回车",), ("回车键",)),
    Concept("报警指示灯", ("报警指示灯",), ("报警指示灯",)),
    Concept("组成部分", ("组成部分",), ("部分",)),
    Concept("束测系统", ("束测系统",), ("束测系统",)),
    Concept("全局频率设置", ("全局频率设置",), ("全局频率设置",)),
    Concept("分组", ("分组",), ("分为",)),
    Concept("额外功能控制", ("额外功能控制",), ("额外功能控制",)),
    Concept("真空控制页面", ("真空控制分段页面", "真空控制页面"), ("真空控制分段页面", "真空控制页面")),
    Concept("总页面", ("总页面",), ("控制总页面", "总页面")),
    Concept("延时调节", ("延时调节",), ("延时调节",)),
    Concept("频率输入项", ("频率输入项",), ("Frequency_Prof", "Frequency (")),
    Concept("状态灯", ("状态灯",), ("状态灯",)),
    Concept("高级设置子界面", ("高级设置子界面",), ("高级设置子界面",)),
    Concept("单触发模式", ("单触发模式",), ("单触发模式",)),
    Concept("概述", ("概述",), ("概述",)),
    Concept("离子泵", ("离子泵",), ("离子泵",)),
    Concept("门阀", ("门阀",), ("门阀",)),
    Concept("温度显示", ("温度显示",), ("温度显示",)),
    Concept("分子泵机组", ("分子泵机组",), ("分子泵机组",)),
    Concept("组合", ("组合",), ("组合",)),
    Concept("分布", ("分布",), ("共有", "分布")),
    Concept("保护压强", ("保护压强",), ("保护压强",)),
    Concept("回差", ("回差",), ("回差",)),
    Concept("高压开关", ("高压开关",), ("高压开关",)),
    Concept("升压", ("升压", "升高压"), ("升高压", "升压")),
    Concept("型号", ("型号",), ("IPCMini", "4UHV", "型号")),
    Concept("图号", ("图号",), ("如图",)),
    Concept("温度报警阈值", ("温度报警阈值",), ("温度报警阈值",)),
    Concept(
        "恒温机柜控制总界面",
        ("恒温机柜控制总界面",),
        ("恒温机柜控制总界面",),
    ),
    Concept("远程控制", ("远程控制",), ("远程控制",)),
    Concept("定时控制", ("定时控制",), ("定时控制",)),
    Concept("保护电流", ("保护电流",), ("保护电流",)),
    Concept("三井", ("三井",), ("三井",)),
    Concept("联锁", ("联锁",), ("联锁",)),
    Concept("运行模式", ("运行模式",), ("运行模式",)),
    Concept("导出", ("导出",), ("导出",)),
    Concept("绘图", ("绘图",), ("绘图",)),
)

_QUOTE_RE = re.compile(r"[“「『]([^”」』]+)[”」』]")
_FIGURE_RE = re.compile(r"图\s*([0-9]+)")
_ASCII_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9_.+\-/]*|[0-9]{2,4}[A-Za-z][A-Za-z0-9]*|[0-9]{3,4}"
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
_QUOTE_SPLIT_RE = re.compile(r"[\s/、；;，,（）()]+")
_SEGMENT_RE = re.compile(r"段")


def extract_terms(query: str, *, probe_identifiers: bool) -> QueryTerms:
    """Pull quoted phrases, identifiers and functional concepts from a query."""

    quoted = []
    masked = list(query)
    for match in _QUOTE_RE.finditer(query):
        quoted.append(match.group(1).strip())
        for index in range(match.start(), match.end()):
            masked[index] = " "
    for match in _MARKER_RE.finditer(query):
        for index in range(match.start(), match.end()):
            masked[index] = " "
    working = "".join(masked)

    figures = []
    for match in _FIGURE_RE.finditer(working):
        figures.append(f"图{match.group(1)}")
        for index in range(match.start(), match.end()):
            working = working[:index] + " " + working[index + 1 :]

    identifiers: list[str] = []
    for match in _ASCII_RE.finditer(working):
        token = match.group(0).rstrip("_.+-/")
        if len(token) < 2 or token.casefold() in _STOPWORDS:
            continue
        if token.isdigit() and len(token) == 4 and token[:2] in {"19", "20"}:
            continue
        suffix = working[match.end() : match.end() + 2]
        # "InjCM 段" / "LH/BD 段": the segment word disambiguates the page.
        if suffix.lstrip().startswith("段"):
            token = token + "段"
        identifiers.append(token)
    identifiers = figures + identifiers

    concepts = []
    remaining = working
    scored_terms = sorted(
        (
            (term, concept)
            for concept in CONCEPTS
            for term in concept.query_terms
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for term, concept in scored_terms:
        if term in remaining and concept.name not in concepts:
            concepts.append(concept.name)
            remaining = remaining.replace(term, "\x00" * len(term))

    probes: tuple[str, ...] = ()
    if probe_identifiers:
        # In an added/removed question the named identifier or quoted phrase is
        # the item whose presence is being checked.  A quoted phrase stays an
        # anchor too: when it exists on one side only that drives the
        # one-sided "added/removed" report.
        probes = tuple(dict.fromkeys(list(quoted) + identifiers))
        identifiers = []

    return QueryTerms(
        markers=tuple(dict.fromkeys(question_markers(query))),
        quoted=tuple(dict.fromkeys(quoted)),
        identifiers=tuple(dict.fromkeys(identifiers)),
        concepts=tuple(concepts),
        probes=probes,
    )


_CONCEPT_BY_NAME = {concept.name: concept for concept in CONCEPTS}


def _quote_anchor_alternatives(
    phrase: str, side_texts, *, one_sided_ok: bool = False
) -> tuple[list[str], list[str]]:
    """Verbatim quote when present on both sides, else its literal fragments.

    For added/removed questions ``one_sided_ok`` keeps the phrase as an anchor
    when it exists on at least one side, so the one-sided alignment can report
    it instead of losing the only handle the question gives.
    """

    normalized = _ws(phrase)
    sides_present = [
        any(normalized in _ws(text) for text in texts) for texts in side_texts
    ]
    if all(sides_present) or (one_sided_ok and any(sides_present)):
        return [phrase], []
    fragments = [part for part in _QUOTE_SPLIT_RE.split(phrase) if len(part) >= 2]
    kept, dropped = [], []
    for fragment in fragments:
        if all(any(fragment in text for text in texts) for texts in side_texts):
            kept.append(fragment)
        else:
            dropped.append(fragment)
    return kept, dropped


def build_anchors(
    terms: QueryTerms,
    side_texts: list[list[str]],
    *,
    one_sided_quotes: bool = False,
) -> tuple[list[Anchor], list[str]]:
    """Turn extracted terms into literal anchors plus explanatory notes."""

    anchors: list[Anchor] = []
    notes: list[str] = []

    def add(anchor: Anchor) -> None:
        if anchor.alternatives and all(
            anchor.alternatives != item.alternatives for item in anchors
        ):
            anchors.append(anchor)

    for phrase in terms.quoted:
        alternatives, dropped = _quote_anchor_alternatives(
            phrase, side_texts, one_sided_ok=one_sided_quotes
        )
        if not alternatives:
            notes.append(f"引号短语「{phrase}」在两侧原文中均不可逐字定位，已忽略")
            continue
        if dropped:
            notes.append(
                f"引号短语「{phrase}」未整段出现，按片段定位；"
                f"两侧均不可定位的片段已忽略：{'、'.join(dropped)}"
            )
        for alternative in alternatives:
            add(Anchor("quoted", phrase, (alternative,)))

    for identifier in terms.identifiers:
        add(Anchor("identifier", identifier, (identifier,)))

    for name in terms.concepts:
        concept = _CONCEPT_BY_NAME[name]
        add(Anchor("concept", "、".join(concept.query_terms), concept.alternatives))

    return anchors, notes


# ---------------------------------------------------------------------------
# alignment
# ---------------------------------------------------------------------------


def _chunks(scope, revision_id: str) -> list:
    return [
        chunk
        for chunk in scope.chunks_by_revision.get(revision_id, ())
        if chunk.position_kind in {"paragraph", "section", "slide"}
    ]


@dataclass
class Alignment:
    chunk: object | None
    granularity: str
    candidates: list


def align_side(scope, side: Side, anchors: list[Anchor]) -> Alignment:
    chunks = _chunks(scope, side.revision_id)
    hits = [chunk for chunk in chunks if all(a.holds(chunk.text) for a in anchors)]
    if len(hits) == 1:
        return Alignment(hits[0], "paragraph", hits)
    if len(hits) > 1:
        refined = []
        for chunk in hits:
            if any(
                all(anchor.holds(line) for anchor in anchors)
                for line in _sentences(chunk.text)
            ):
                refined.append(chunk)
        if len(refined) == 1:
            return Alignment(refined[0], "sentence", hits)
        return Alignment(None, "ambiguous", refined or hits)
    return Alignment(None, "missing", [])


# ---------------------------------------------------------------------------
# fallback anchors (only when the curated anchors cannot align)
# ---------------------------------------------------------------------------

_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_FALLBACK_BOUNDARY = set(
    "的与在和及或对为是有无两一不中上下将把可需应此其该各每第版副本说明记载限制方面"
)


def fallback_phrases(query: str) -> list[str]:
    """Clean Chinese noun phrases from the question, longest first.

    This is a last-resort anchor source for questions the curated table does
    not cover; it only proposes literal substrings, never a paraphrase.
    """

    masked = query
    for match in _MARKER_RE.finditer(query):
        masked = masked[: match.start()] + " " * (
            match.end() - match.start()
        ) + masked[match.end() :]
    for match in _QUOTE_RE.finditer(masked):
        masked = masked[: match.start()] + " " * (
            match.end() - match.start()
        ) + masked[match.end() :]
    phrases: set[str] = set()
    for run in _CJK_RUN_RE.findall(masked):
        for length in range(2, min(6, len(run)) + 1):
            for start in range(len(run) - length + 1):
                phrase = run[start : start + length]
                if phrase[0] in _FALLBACK_BOUNDARY or phrase[-1] in _FALLBACK_BOUNDARY:
                    continue
                phrases.add(phrase)
    return sorted(phrases, key=lambda item: (-len(item), query.find(item)))


def fallback_align(scope, sides: list[Side], query: str, task: str):
    """Try 1–3 clean noun phrases; every required side must be unique."""

    side_texts = [
        [chunk.text for chunk in _chunks(scope, side.revision_id)] for side in sides
    ]
    feasible = [
        phrase
        for phrase in fallback_phrases(query)
        if any(any(phrase in text for text in texts) for texts in side_texts)
    ]
    maximal = [
        phrase
        for phrase in feasible
        if not any(phrase != other and phrase in other for other in feasible)
    ]
    if not maximal:
        return None
    for size in (1, 2, 3):
        anchors = [
            Anchor("fallback", phrase, (phrase,)) for phrase in maximal[:size]
        ]
        alignments = [align_side(scope, side, anchors) for side in sides]
        aligned = [item.chunk is not None for item in alignments]
        if all(aligned):
            return anchors, alignments
        if task in PROBE_TASKS and len(sides) == 2 and sum(aligned) == 1:
            return anchors, alignments
    return None


# ---------------------------------------------------------------------------
# report helpers
# ---------------------------------------------------------------------------


def _command(question_id: str, facts_path=common.DEFAULT_FACTS) -> str:
    return (
        "python3 scripts/research/prototypes/p2_manual_revision_align.py "
        f"--question {question_id} --facts {facts_path}"
    )


def _question_facts(facts, question: dict) -> dict[str, list]:
    by_chunk: dict[str, list] = {}
    for fact in common.facts_for_question(facts, question):
        by_chunk.setdefault(fact.citation.chunk_id, []).append(fact)
    return by_chunk


def _claim(
    claim_id: str, text: str, value: str, chunk_id: str, facts, *, role: str = "fact_support"
) -> dict:
    item = common.claim(claim_id, text, value, facts)
    if chunk_id and chunk_id not in item["support"]:
        item["support"].append(chunk_id)
    item["role"] = role
    return item


def _chunk_evidence(chunk, facts) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "revision_id": chunk.document_id,
        "locator_kind": chunk.position_kind,
        "locator_label": chunk.position_label,
        "excerpt": chunk.text,
        "role": "fact_support",
        "fact_id": ",".join(sorted(fact.fact_id for fact in facts)),
    }


def _operator_record(request: dict) -> dict:
    response = common.operator("version_diff", request)
    return {"op": "version_diff", "request": request, "response": response}


def _version_request(left: Side, left_chunk, right: Side, right_chunk) -> dict:
    return {
        "left": {
            "revision_id": left.revision_id,
            "items": [
                {
                    "item_id": left_chunk.chunk_id,
                    "text": left_chunk.text,
                }
            ],
        },
        "right": {
            "revision_id": right.revision_id,
            "items": [
                {
                    "item_id": right_chunk.chunk_id,
                    "text": right_chunk.text,
                }
            ],
        },
        "normalizer": "whitespace",
    }


def _alignment_payload(
    mode: str,
    sides: list[Side],
    anchors: list[Anchor],
    alignments: list[Alignment],
    notes: list[str],
) -> dict:
    return {
        "mode": mode,
        "sides": [
            {
                "role": side.role,
                "revision_id": side.revision_id,
                "revision_label": side.label,
                "document_kind": side.document_kind,
                "position_label": (
                    alignment.chunk.position_label if alignment.chunk else ""
                ),
                "chunk_id": alignment.chunk.chunk_id if alignment.chunk else "",
                "granularity": alignment.granularity,
                "candidate_count": len(alignment.candidates),
            }
            for side, alignment in zip(sides, alignments)
        ],
        "anchors": [
            {
                "kind": anchor.kind,
                "source": anchor.source,
                "alternatives": list(anchor.alternatives),
            }
            for anchor in anchors
        ],
        "notes": notes,
    }


def _finish(
    question: dict,
    *,
    status: str,
    answer: str,
    claims: list[dict],
    operators: list[dict],
    evidence: list[dict],
    unresolved: list[str],
    notes: str,
    alignment: dict,
    facts_path,
) -> dict:
    report = common.build_report(
        question,
        status=status,
        answer=answer,
        claims=claims,
        operators=operators,
        unresolved=unresolved,
        notes=notes,
        facts_path=facts_path,
        command=_command(question["base_id"], facts_path),
    )
    report["evidence"] = evidence
    report["alignment"] = alignment
    return report


def _unsupported(
    question: dict, reason: str, *, candidates=(), facts_path, notes: str = ""
) -> dict:
    report = common.unsupported_report(
        question,
        reason,
        facts_path=facts_path,
        command=_command(question["base_id"], facts_path),
    )
    report["notes"] = reason if not notes else f"{reason}\n{notes}"
    if candidates:
        report["alignment"] = {
            "mode": "unresolved",
            "candidates": list(candidates),
            "notes": [reason],
        }
    return report


# ---------------------------------------------------------------------------
# task handlers
# ---------------------------------------------------------------------------


def _boundary_report(
    question: dict, sides: list[Side], notes: list[str], facts_path
) -> dict:
    claims = [
        _claim(
            f"B{index}",
            f"{side.role}元数据（revision_label / document_kind）",
            side.label,
            f"metadata:{side.revision_id}",
            [],
        )
        for index, side in enumerate(sides, 1)
    ]
    for item, side in zip(claims, sides):
        item["document_kind"] = side.document_kind
        item["revision_id"] = side.revision_id
    answer = (
        "文档身份（仅 revision_label / document_kind）："
        + "；".join(
            f"{side.role} = {side.label}（document_kind={side.document_kind}）"
            for side in sides
        )
        + "。归档副本是否可当作更新的版本，原型不依据正文或目录推断批准状态，"
        "需查归档/批准记录；此处只陈述元数据。"
    )
    return _finish(
        question,
        status="partial",
        answer=answer,
        claims=claims,
        operators=[],
        evidence=[],
        unresolved=[
            "归档副本能否作为新版本涉及批准状态，元数据不足以判定",
        ],
        notes="\n".join(notes + ["version_boundary 只使用修订元数据，不比较正文"]),
        alignment=_alignment_payload("metadata_only", sides, [], [], notes),
        facts_path=facts_path,
    )



def _evaluate_multi_probe(
    question: dict,
    sides: list[Side],
    scope,
    anchors: list[Anchor],
    facts,
    notes: list[str],
    facts_path,
) -> dict:
    """N>=2 revisions: target side named by the question, one pair per prior."""

    markers = set(question_markers(question.get("query", "")))
    targets = [side for side in sides if side.role in markers]
    if len(targets) != 1:
        return _unsupported(
            question,
            "题干未在多修订中唯一点名目标修订（如 2024归档副本）",
            candidates=[
                {"revision_id": side.revision_id, "role": side.role}
                for side in sides
            ],
            facts_path=facts_path,
            notes="\n".join(notes),
        )
    target = targets[0]
    priors = [side for side in sides if side.revision_id != target.revision_id]
    results = {side.revision_id: align_side(scope, side, anchors) for side in sides}
    target_result = results[target.revision_id]
    if target_result.chunk is None:
        return _unsupported(
            question,
            f"目标修订「{target.role}」未唯一对齐（{target_result.granularity}）",
            candidates=[
                {
                    "chunk_id": chunk.chunk_id,
                    "locator_label": chunk.position_label,
                }
                for chunk in target_result.candidates
            ],
            facts_path=facts_path,
            notes="\n".join(notes),
        )

    by_chunk = _question_facts(facts, question)
    target_chunk = target_result.chunk
    target_facts = by_chunk.get(target_chunk.chunk_id, [])
    target_focal = _focal_sentence(target_chunk.text, anchors)
    claims = [
        _claim(
            "P1",
            f"{target.role}对齐段落原文",
            target_focal,
            target_chunk.chunk_id,
            target_facts,
        )
    ]
    evidence = [_chunk_evidence(target_chunk, target_facts)]
    operators = []
    rows = []
    for prior in priors:
        result = results[prior.revision_id]
        if result.chunk is None:
            state = "missing" if result.granularity == "missing" else "ambiguous"
            rows.append((prior, state, None))
            continue
        operators.append(
            _operator_record(
                _version_request(target, target_chunk, prior, result.chunk)
            )
        )
        prior_facts = by_chunk.get(result.chunk.chunk_id, [])
        prior_focal = _focal_sentence(result.chunk.text, anchors)
        claims.append(
            _claim(
                f"P{len(claims) + 1}",
                f"{prior.role}对齐段落原文",
                prior_focal,
                result.chunk.chunk_id,
                prior_facts,
            )
        )
        evidence.append(_chunk_evidence(result.chunk, prior_facts))
        rows.append((prior, "aligned", result.chunk))

    parts = [f"{target.role}（目标侧）原文：{target_focal}"]
    for prior, state, chunk in rows:
        if state == "aligned":
            parts.append(
                f"{prior.role}：有对应段落，原文：{_focal_sentence(chunk.text, anchors)}"
            )
        elif state == "missing":
            parts.append(f"{prior.role}：没有包含全部锚点的段落")
        else:
            parts.append(f"{prior.role}：候选段落不唯一，未判定")
    status = "answered" if all(state != "ambiguous" for _, state, _ in rows) else "partial"
    notes.append(
        f"显式 scope 给出 {len(sides)} 个修订；以题干点名的「{target.role}」为目标侧，"
        "其余每个修订逐一对照。"
    )
    return _finish(
        question,
        status=status,
        answer=(
            "多修订核对（仅锚点存在性与文本级比较）：" + "；".join(parts) + "。"
            "语义等价需人工复核。"
        ),
        claims=claims,
        operators=operators,
        evidence=evidence,
        unresolved=["多修订逐对比较只做 exact/whitespace 级判断，语义需复核"],
        notes="\n".join(notes),
        alignment=_alignment_payload(
            "explicit_revisions_multi",
            sides,
            anchors,
            [results[side.revision_id] for side in sides],
            notes,
        ),
        facts_path=facts_path,
    )


def evaluate(question: dict, facts, facts_path=common.DEFAULT_FACTS) -> dict:
    """Evaluate one dev/val S2 question and return a replayable report."""

    reason = common.guard_verdict_class(question)
    if reason is not None:
        return common.not_evaluated_report(
            question,
            reason,
            facts_path=facts_path,
            command=_command(question["base_id"], facts_path),
        )

    task = question.get("task_type", "")
    if task not in TASKS:
        return _unsupported(
            question,
            f"task_type={task or 'unknown'} 不在手册修订对齐原型范围内",
            facts_path=facts_path,
        )

    scope = common.scope_for_question(question)
    revisions = scope.revisions
    try:
        sides, notes, mode = resolve_pair(question, revisions)
    except Unsupported as exc:
        return _unsupported(
            question, exc.reason, candidates=exc.candidates, facts_path=facts_path
        )

    used = {side.revision_id for side in sides}
    unused = [rid for rid in sorted(revisions) if rid not in used]
    if unused:
        notes.append("题干未对齐的族内修订未参与：" + "、".join(unused))
    if re.search(r"(?<!第)三版", question.get("query", "")):
        notes.append("题干提到「三版」；原型只比较一对修订，其余修订未参与")

    if task == "version_boundary":
        return _boundary_report(question, sides, notes, facts_path)

    terms = extract_terms(question["query"], probe_identifiers=task in PROBE_TASKS)
    side_texts = [
        [chunk.text for chunk in _chunks(scope, side.revision_id)] for side in sides
    ]
    anchors, anchor_notes = build_anchors(
        terms, side_texts, one_sided_quotes=task in PROBE_TASKS
    )
    notes.extend(anchor_notes)
    if not anchors:
        fallback = fallback_align(scope, sides, question.get("query", ""), task)
        if fallback is not None:
            anchors, _ = fallback
            notes.append(
                "主锚点为空；回退到题干中文名词短语锚点："
                + "、".join(anchor.source for anchor in anchors)
            )

    if len(sides) > 2:
        if task not in PROBE_TASKS:
            return _unsupported(
                question,
                f"scope 给出 {len(sides)} 个修订；非增删题只比较一对修订",
                candidates=[side.revision_id for side in sides],
                facts_path=facts_path,
                notes="\n".join(notes),
            )
        if not anchors:
            return _unsupported(
                question,
                "题干中未提取到可逐字定位的锚点（引号短语 / 标识 / 功能关键词）",
                facts_path=facts_path,
                notes="\n".join(notes),
            )
        return _evaluate_multi_probe(
            question, sides, scope, anchors, facts, notes, facts_path
        )

    if not anchors:
        return _unsupported(
            question,
            "题干中未提取到可逐字定位的锚点（引号短语 / 标识 / 功能关键词），"
            "中文名词短语回退也无法在所需各侧唯一对齐",
            facts_path=facts_path,
            notes="\n".join(notes),
        )

    alignments = [align_side(scope, side, anchors) for side in sides]
    aligned_now = sum(1 for item in alignments if item.chunk is not None)
    if any(item.chunk is None for item in alignments) and not (
        task in PROBE_TASKS and aligned_now == 1
    ):
        fallback = fallback_align(scope, sides, question.get("query", ""), task)
        if fallback is not None:
            anchors, alignments = fallback
            notes.append(
                "主锚点无法唯一对齐；回退到题干中文名词短语锚点："
                + "、".join(anchor.source for anchor in anchors)
            )
    alignment = _alignment_payload(mode, sides, anchors, alignments, notes)
    failures = []
    for side, result in zip(sides, alignments):
        if result.chunk is not None:
            continue
        if result.granularity == "missing":
            failures.append(f"{side.role}「{side.label}」没有段落同时包含全部锚点")
        else:
            failures.append(
                f"{side.role}「{side.label}」有 {len(result.candidates)} 个候选段落，"
                "无法唯一对齐"
            )
    aligned_count = sum(1 for item in alignments if item.chunk is not None)

    if task in PROBE_TASKS and aligned_count == 1:
        present = next(item for item in alignments if item.chunk is not None)
        side_index = alignments.index(present)
        side = sides[side_index]
        missing_side = sides[1 - side_index]
        query_text = question.get("query", "")
        positions = {
            s.revision_id: query_text.find(s.role)
            for s in sides
            if s.role and s.role in query_text
        }
        if task == "version_added" and missing_side.revision_id in positions:
            if positions[missing_side.revision_id] == min(positions.values()):
                return _finish(
                    question,
                    status="partial",
                    answer=(
                        f"目标侧（{missing_side.role}）没有包含全部锚点的段落，"
                        f"只有{side.role}命中；无法确认「新增」方向，需语义复核。"
                    ),
                    claims=[],
                    operators=[],
                    evidence=[],
                    unresolved=[
                        "题干点名的新增侧未对齐，锚点可能未覆盖该侧措辞"
                    ],
                    notes="\n".join(notes),
                    alignment=alignment,
                    facts_path=facts_path,
                )
        if task == "version_removed" and side.revision_id in positions:
            if positions[side.revision_id] == max(positions.values()):
                return _finish(
                    question,
                    status="partial",
                    answer=(
                        f"标识只出现在较晚的{side.role}，与「删除」方向矛盾；"
                        "需语义复核。"
                    ),
                    claims=[],
                    operators=[],
                    evidence=[],
                    unresolved=["删除方向与锚点命中侧矛盾，未给出结论"],
                    notes="\n".join(notes),
                    alignment=alignment,
                    facts_path=facts_path,
                )
        by_chunk = _question_facts(facts, question)
        chunk = present.chunk
        chunk_facts = by_chunk.get(chunk.chunk_id, [])
        focal = _focal_sentence(chunk.text, anchors)
        claim = _claim(
            "P1",
            f"{side.role}对齐段落（另一侧未找到同锚点段落）",
            focal,
            chunk.chunk_id,
            chunk_facts,
        )
        return _finish(
            question,
            status="answered",
            answer=(
                f"该说明只出现在{side.role}的对齐段落；"
                f"原文：{focal}"
            ),
            claims=[claim],
            operators=[],
            evidence=[_chunk_evidence(chunk, chunk_facts)],
            unresolved=[
                f"另一侧（{sides[1 - side_index].role}）没有包含全部锚点的段落；"
                "该侧是否完全没有对应说明仍需语义复核"
            ],
            notes="\n".join(notes),
            alignment=alignment,
            facts_path=facts_path,
        )

    if failures:
        reason_text = "；".join(failures)
        return _unsupported(
            question,
            reason_text,
            candidates=[
                {
                    "revision_id": side.revision_id,
                    "revision_label": side.label,
                    "candidates": [
                        {
                            "chunk_id": chunk.chunk_id,
                            "locator_label": chunk.position_label,
                        }
                        for chunk in result.candidates
                    ],
                }
                for side, result in zip(sides, alignments)
                if result.chunk is None
            ],
            facts_path=facts_path,
            notes="\n".join(notes),
        )

    left, right = sides
    left_chunk = alignments[0].chunk
    right_chunk = alignments[1].chunk
    if alignments[0].granularity == "sentence" or alignments[1].granularity == "sentence":
        notes.append("段落级对齐有多条候选；改用句内共现唯一化后各侧恰好 1 条")
    by_chunk = _question_facts(facts, question)
    left_facts = by_chunk.get(left_chunk.chunk_id, [])
    right_facts = by_chunk.get(right_chunk.chunk_id, [])
    operators = [
        _operator_record(_version_request(left, left_chunk, right, right_chunk))
    ]
    same = _ws(left_chunk.text) == _ws(right_chunk.text)
    path_question = _path_question(question.get("query", ""), terms)
    left_focal = _focal_sentence(left_chunk.text, anchors)
    right_focal = _focal_sentence(right_chunk.text, anchors)
    claims: list[dict] = []
    evidence = [
        _chunk_evidence(left_chunk, left_facts),
        _chunk_evidence(right_chunk, right_facts),
    ]
    operator_note = (
        "对齐项 item_id 用 chunk_id（同一修订内 position_label 可能重复）；"
        "原型另按对齐段落的 whitespace 归一文本比较。"
    )
    notes.append(operator_note)

    claim_count = 0

    def add_claim(text: str, value: str, side, chunk, chunk_facts) -> None:
        nonlocal claim_count
        claim_count += 1
        claims.append(
            _claim(f"P{claim_count}", text, value, chunk.chunk_id, chunk_facts)
        )

    def add_path_claims() -> tuple[list[str], list[str]]:
        left_path = _action_sentences(left_chunk.text, anchors)
        right_path = _action_sentences(right_chunk.text, anchors)
        for sentence in left_path:
            add_claim(f"{left.role}路径句", sentence, left, left_chunk, left_facts)
        for sentence in right_path:
            add_claim(f"{right.role}路径句", sentence, right, right_chunk, right_facts)
        for token in _sentence_tokens(left_path):
            add_claim(
                f"{left.role}路径要素「{token}」", token, left, left_chunk, left_facts
            )
        for token in _sentence_tokens(right_path):
            add_claim(
                f"{right.role}路径要素「{token}」", token, right, right_chunk, right_facts
            )
        return left_path, right_path

    if task == "version_same":
        if path_question:
            left_path, right_path = add_path_claims()
            if not (1 <= len(left_path) <= 5 and 1 <= len(right_path) <= 5):
                status = "partial"
                answer = (
                    "无法确定具体进入路径："
                    f"{left.role}命中 {len(left_path)} 句、"
                    f"{right.role}命中 {len(right_path)} 句"
                    "（要求各侧 1–5 句）。候选："
                    f"{left.role}「{'；'.join(left_path) or '无'}」；"
                    f"{right.role}「{'；'.join(right_path) or '无'}」。需语义复核。"
                )
                unresolved = ["路径句数量不在 1–5 范围内，未给出结论"]
            elif [_ws(line) for line in left_path] == [
                _ws(line) for line in right_path
            ]:
                answer = (
                    f"一致：{left.role}与{right.role}的进入路径原文相同："
                    + "；".join(left_path)
                )
                status, unresolved = "answered", []
            else:
                answer = (
                    f"不同：{left.role}路径："
                    + "；".join(left_path)
                    + f"。{right.role}路径："
                    + "；".join(right_path)
                    + "。"
                )
                status = "answered"
                unresolved = ["两侧路径文本不同；是否为同一操作的改写需人工复核"]
        else:
            left_context = _context_sentences(left_chunk.text, anchors)
            right_context = _context_sentences(right_chunk.text, anchors)
            for sentence in left_context:
                add_claim(
                    f"{left.role}对应句", sentence, left, left_chunk, left_facts
                )
            for sentence in right_context:
                add_claim(
                    f"{right.role}对应句", sentence, right, right_chunk, right_facts
                )
            if same:
                answer = (
                    f"一致：{left.role}与{right.role}对齐段落在空白归一后文本相同。"
                    f"原文：{'；'.join(left_context[:3])}"
                )
                status, unresolved = "answered", []
            else:
                status = "partial"
                left_only, right_only = _sentence_difference(
                    left_chunk.text, right_chunk.text
                )
                for sentence in left_only:
                    add_claim(
                        f"{left.role}独有句", sentence, left, left_chunk, left_facts
                    )
                for sentence in right_only:
                    add_claim(
                        f"{right.role}独有句", sentence, right, right_chunk, right_facts
                    )
                answer = (
                    "文本不一致，需语义复核："
                    f"{left.role}独有句「{'；'.join(left_only) or '无'}」；"
                    f"{right.role}独有句「{'；'.join(right_only) or '无'}」。"
                    "原型只做 exact/whitespace 级比较，不声称语义等价。"
                )
                unresolved = [
                    "两侧对齐段落 whitespace 归一后文本不同；语义等价需人工复核"
                ]
        return _finish(
            question,
            status=status,
            answer=answer,
            claims=claims,
            operators=operators,
            evidence=evidence,
            unresolved=unresolved,
            notes="\n".join(notes),
            alignment=alignment,
            facts_path=facts_path,
        )

    if task == "version_diff":
        left_sentences = _figure_sentences(left_chunk.text, anchors)
        right_sentences = _figure_sentences(right_chunk.text, anchors)
        figures_left = list(
            dict.fromkeys(
                ref for line in left_sentences for ref in _figure_refs(line)
            )
        )
        figures_right = list(
            dict.fromkeys(
                ref for line in right_sentences for ref in _figure_refs(line)
            )
        )
        figure_ambiguous = len(figures_left) > 1 or len(figures_right) > 1
        if "图号" in terms.concepts and figures_left and figures_right and not figure_ambiguous:
            left_focus = "\n".join(left_sentences)
            right_focus = "\n".join(right_sentences)
            for sentence in _context_sentences(left_chunk.text, anchors):
                add_claim(
                    f"{left.role}对应句", sentence, left, left_chunk, left_facts
                )
            for sentence in _context_sentences(right_chunk.text, anchors):
                add_claim(
                    f"{right.role}对应句", sentence, right, right_chunk, right_facts
                )
            add_claim(
                f"{left.role}图号引用", figures_left[0], left, left_chunk, left_facts
            )
            add_claim(
                f"{right.role}图号引用", figures_right[0], right, right_chunk, right_facts
            )
            left_devices = _device_list(left_focus)
            right_devices = _device_list(right_focus)
            coverage = ""
            if left_devices and right_devices:
                if left_devices == right_devices:
                    coverage = f"；设备覆盖相同：{left_devices}"
                    add_claim(
                        f"{left.role}设备清单",
                        left_devices,
                        left,
                        left_chunk,
                        left_facts,
                    )
                    add_claim(
                        f"{right.role}设备清单",
                        right_devices,
                        right,
                        right_chunk,
                        right_facts,
                    )
                else:
                    coverage = (
                        f"；设备清单不同：{left.role}「{left_devices}」/"
                        f"{right.role}「{right_devices}」"
                    )
            if set(figures_left) == set(figures_right):
                answer = f"相同：{figures_left[0]}" + coverage + "。"
            else:
                answer = (
                    f"不同：{figures_left[0]} / {figures_right[0]}"
                    f"（{left.role} / {right.role}）" + coverage + "。"
                    "两侧原文均逐字引用，未做语义解释。"
                )
            status, unresolved = "answered", []
        elif "图号" in terms.concepts:
            status = "partial"
            answer = (
                "图号不唯一，需语义复核："
                f"{left.role}候选句「{'；'.join(left_sentences) or '无'}」→ "
                f"{'、'.join(figures_left) or '未提取到图号'}；"
                f"{right.role}候选句「{'；'.join(right_sentences) or '无'}」→ "
                f"{'、'.join(figures_right) or '未提取到图号'}。"
            )
            unresolved = ["同一侧候选句中提取到多个或零个图号，无法唯一确定"]
        elif path_question:
            left_path, right_path = add_path_claims()
            if not (1 <= len(left_path) <= 5 and 1 <= len(right_path) <= 5):
                status = "partial"
                answer = (
                    "无法确定具体进入路径："
                    f"{left.role}命中 {len(left_path)} 句、"
                    f"{right.role}命中 {len(right_path)} 句"
                    "（要求各侧 1–5 句）。候选："
                    f"{left.role}「{'；'.join(left_path) or '无'}」；"
                    f"{right.role}「{'；'.join(right_path) or '无'}」。需语义复核。"
                )
                unresolved = ["路径句数量不在 1–5 范围内，未给出结论"]
            else:
                answer = (
                    f"不同：{left.role}路径："
                    + "；".join(left_path)
                    + f"。{right.role}路径："
                    + "；".join(right_path)
                    + "。"
                )
                status = "answered"
                unresolved = ["两侧路径表述不同；语义等价需人工复核"]
        else:
            left_only, right_only = _sentence_difference(
                left_chunk.text, right_chunk.text, anchors
            )
            if left_only or right_only:
                for sentence in left_only:
                    add_claim(
                        f"{left.role}独有句", sentence, left, left_chunk, left_facts
                    )
                for sentence in right_only:
                    add_claim(
                        f"{right.role}独有句", sentence, right, right_chunk, right_facts
                    )
                answer = (
                    f"不同：{left.role}独有句「{'；'.join(left_only) or '无'}」；"
                    f"{right.role}独有句「{'；'.join(right_only) or '无'}」。"
                    "原型只做 exact/whitespace 级比较，语义等价需人工复核。"
                )
            elif same:
                answer = f"两侧对应段落文本相同：{left_focal}。"
            else:
                left_context = _context_sentences(left_chunk.text, anchors)
                right_context = _context_sentences(right_chunk.text, anchors)
                for sentence in left_context:
                    add_claim(
                        f"{left.role}对应句", sentence, left, left_chunk, left_facts
                    )
                for sentence in right_context:
                    add_claim(
                        f"{right.role}对应句", sentence, right, right_chunk, right_facts
                    )
                answer = (
                    f"不同：{left.role}「{'；'.join(left_context[:3])}」；"
                    f"{right.role}「{'；'.join(right_context[:3])}」。"
                    "原型只做 exact/whitespace 级比较，语义等价需人工复核。"
                )
            status = "answered"
            unresolved = ["两侧对应表述的语义是否等价需人工复核"]
        return _finish(
            question,
            status=status,
            answer=answer,
            claims=claims,
            operators=operators,
            evidence=evidence,
            unresolved=unresolved,
            notes="\n".join(notes),
            alignment=alignment,
            facts_path=facts_path,
        )

    # version_added / version_removed
    probes = list(terms.probes)
    if not probes:
        status = "partial"
        answer = (
            "题干未给出可核验的增删项标识；两侧对齐段落原文："
            f"{left.role}「{left_focal}」；{right.role}「{right_focal}」。"
            "缺少标识时只比较文本，无法判定具体增删项，需语义复核。"
        )
        unresolved = ["题干未给出可核验的增删项标识（如 APPLY、图号、型号）"]
        return _finish(
            question,
            status=status,
            answer=answer,
            claims=claims,
            operators=operators,
            evidence=evidence,
            unresolved=unresolved,
            notes="\n".join(notes),
            alignment=alignment,
            facts_path=facts_path,
        )

    probe_rows = []
    for probe in probes:
        on_left = _contains(left_chunk.text, probe)
        on_right = _contains(right_chunk.text, probe)
        probe_rows.append(
            {
                "probe": probe,
                "left": on_left,
                "right": on_right,
                "left_sentence": _probe_sentence(left_chunk.text, probe),
                "right_sentence": _probe_sentence(right_chunk.text, probe),
            }
        )
    one_sided = [
        row for row in probe_rows if row["left"] != row["right"]
    ]
    if len(one_sided) == 1:
        row = one_sided[0]
        present_side = left if row["left"] else right
        absent_side = right if row["left"] else left
        present_chunk = left_chunk if row["left"] else right_chunk
        present_facts = left_facts if row["left"] else right_facts
        present_sentence = row["left_sentence"] if row["left"] else row["right_sentence"]
        verb = "新增" if task == "version_added" else "删除"
        claims.append(
            _claim(
                f"P{len(claims) + 1}",
                f"{present_side.role}对齐段落中的标识「{row['probe']}」",
                row["probe"],
                present_chunk.chunk_id,
                present_facts,
            )
        )
        claims.append(
            _claim(
                f"P{len(claims) + 1}",
                f"{present_side.role}对齐段落中的标识「{row['probe']}」所在句",
                present_sentence,
                present_chunk.chunk_id,
                present_facts,
            )
        )
        answer = (
            f"{verb}：标识「{row['probe']}」只出现在{present_side.role}"
            f"；{absent_side.role}对齐段落中未出现该标识。"
            f"{present_side.role}原文：{present_sentence}"
        )
        return _finish(
            question,
            status="answered",
            answer=answer,
            claims=claims,
            operators=operators,
            evidence=evidence,
            unresolved=[],
            notes="\n".join(notes),
            alignment=alignment,
            facts_path=facts_path,
        )

    if not one_sided:
        status = "partial"
        both = [row["probe"] for row in probe_rows if row["left"] and row["right"]]
        neither = [row["probe"] for row in probe_rows if not row["left"] and not row["right"]]
        detail = []
        if both:
            detail.append("两侧均出现：" + "、".join(both))
        if neither:
            detail.append("两侧均未出现：" + "、".join(neither))
        answer = (
            "无法判定增删：" + ("；".join(detail) or "标识存在性不唯一")
            + f"。两侧原文：{left.role}「{left_focal}」；"
            f"{right.role}「{right_focal}」。需语义复核。"
        )
        unresolved = ["增删项标识在两侧的存在性相同或不唯一，无法归因为单向增删"]
    else:
        status = "partial"
        answer = (
            "多个增删项标识存在性不一致："
            + "；".join(
                f"{row['probe']}（左={'有' if row['left'] else '无'}，"
                f"右={'有' if row['right'] else '无'}）"
                for row in one_sided
            )
            + "。需语义复核。"
        )
        unresolved = ["多个标识的增删方向不一致，原型不合并判定"]
    return _finish(
        question,
        status=status,
        answer=answer,
        claims=claims,
        operators=operators,
        evidence=evidence,
        unresolved=unresolved,
        notes="\n".join(notes),
        alignment=alignment,
        facts_path=facts_path,
    )


def _probe_sentence(text: str, probe: str) -> str:
    """Prefer the prose sentence carrying the probe over screenshot OCR lines."""

    lines = [line for line in _sentences(text) if probe in line]
    if not lines:
        return _sentences(text)[0] if text.strip() else ""

    def cjk_count(line: str) -> int:
        return sum(1 for ch in line if "\u4e00" <= ch <= "\u9fff")

    return max(lines, key=lambda line: (cjk_count(line), -lines.index(line)))


# ---------------------------------------------------------------------------
# split runner / CLI
# ---------------------------------------------------------------------------


def evaluate_split(split: str, facts, facts_path=common.DEFAULT_FACTS) -> dict:
    if split not in ("dev", "val"):
        raise ValueError(f"split not allowed in phase 2: {split}")
    questions = [
        item
        for _, item in sorted(common.question_index((split,)).items())
        if item.get("scenario") == "s2_revision"
    ]
    reports = [evaluate(question, facts, facts_path) for question in questions]
    status_counts = collections.Counter(report["status"] for report in reports)
    task_counts: dict[str, collections.Counter] = {}
    for report in reports:
        task_counts.setdefault(report["task_type"], collections.Counter())[
            report["status"]
        ] += 1
    return {
        "schema_version": "phase2-p2-run-v1",
        "split": split,
        "scenario": "s2_revision",
        "facts_sha256": common.facts_digest(facts_path),
        "question_count": len(reports),
        "status_counts": dict(sorted(status_counts.items())),
        "task_status_counts": {
            task: dict(sorted(counts.items())) for task, counts in sorted(task_counts.items())
        },
        "answered_or_partial": sum(
            1 for report in reports if report["status"] in SUPPORTED_STATUSES
        ),
        "questions": [
            {
                "question_id": report["question_id"],
                "task_type": report["task_type"],
                "status": report["status"],
                "answer": report["answer"],
            }
            for report in reports
        ],
        "reports": reports,
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--question", help="dev/val base_id")
    group.add_argument("--all", action="store_true", help="run every S2 question")
    parser.add_argument("--split", choices=["dev", "val"], default="")
    parser.add_argument("--facts", default=str(common.DEFAULT_FACTS))
    parser.add_argument("--out", default="", help="report path; empty prints JSON")
    args = parser.parse_args(argv)
    if args.all and not args.split:
        parser.error("--all 需要 --split dev|val")
    facts = common.load_facts(args.facts)
    if args.question:
        question = common.get_question(args.question)
        report = evaluate(question, facts, args.facts)
        common.emit(report, args.out)
        return
    result = evaluate_split(args.split, facts, args.facts)
    if args.out:
        common.write_report(args.out, result)
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "reports"},
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":  # pragma: no cover
    main()
