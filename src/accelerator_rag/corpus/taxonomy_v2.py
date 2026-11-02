"""Controlled vocabulary v2 for the expanded SHINE control-system corpus.

The v1 taxonomy stays frozen for historical registries.  This module extends it
with topics that only appear in the 2026-11 batch (network, data storage,
archiving, power, vacuum, laser, motion control, cybersecurity, ...).  A topic
is a stable lowercase slug; document kind, file format and evidence role are
separate axes and must not be folded into the topic value.
"""

from __future__ import annotations

from accelerator_rag.corpus.taxonomy import (
    TOPICS_BY_CATEGORY as V1_TOPICS_BY_CATEGORY,
)


_EXTRA_TOPICS: dict[str, frozenset[str]] = {
    "control_system": frozenset(
        {
            "alarm",
            "archiver",
            "acceptance",
            "control_room",
            "cybersecurity",
            "data_acquisition",
            "data_storage",
            "database",
            "design",
            "documentation",
            "gui",
            "installation",
            "laser",
            "motion_control",
            "network",
            "pdu",
            "power_supply",
            "review",
            "standards",
            "vacuum",
        }
    ),
    "high_level_application": frozenset(
        {"database", "gui", "operation_log", "web_application"}
    ),
    "beam_diagnostics": frozenset({"archiver", "bpm", "data_storage"}),
    "accelerator_physics": frozenset({"design", "review"}),
}


TOPICS_BY_CATEGORY: dict[str, frozenset[str]] = {
    category: frozenset(
        set(v1_topics) | set(_EXTRA_TOPICS.get(category, frozenset()))
    )
    for category, v1_topics in V1_TOPICS_BY_CATEGORY.items()
}

VALID_CATEGORIES = frozenset(TOPICS_BY_CATEGORY)


TOPIC_SYNONYMS: dict[str, str] = {
    "联锁": "interlock",
    "快联锁": "interlock",
    "慢联锁": "interlock",
    "定时": "timing",
    "时序": "timing",
    "白兔": "timing",
    "真空": "vacuum",
    "电源": "power_supply",
    "磁铁电源": "power_supply",
    "激光": "laser",
    "运动控制": "motion_control",
    "电机控制": "motion_control",
    "低温": "cryogenics",
    "恒温机柜": "cryogenics",
    "网络": "network",
    "控制网络": "network",
    "网络安全": "cybersecurity",
    "信息安全": "cybersecurity",
    "数据存储": "data_storage",
    "数据存档": "archiver",
    "存档": "archiver",
    "报警": "alarm",
    "告警": "alarm",
    "数据库": "database",
    "界面": "gui",
    "操作界面": "gui",
    "安装": "installation",
    "规范": "standards",
    "标准": "standards",
    "验收": "acceptance",
    "评审": "review",
    "设计": "design",
    "文档": "documentation",
    "pdu": "pdu",
    "电源分配单元": "pdu",
    "epics": "epics",
    "ioc": "ioc",
    "opi": "opi",
    "pv": "pv",
}


def normalize_topic(value: str) -> str | None:
    """Return a canonical topic slug, or None when the value is unknown.

    Matching is case-insensitive for ASCII and exact for the Chinese synonym
    table.  The function never guesses from substrings: an unrecognized value
    must be reviewed instead of being silently folded into a neighbouring topic.
    """

    if not isinstance(value, str):
        return None
    candidate = value.strip().casefold()
    if not candidate:
        return None
    if candidate in TOPIC_SYNONYMS:
        return TOPIC_SYNONYMS[candidate]
    for topics in TOPICS_BY_CATEGORY.values():
        if candidate in topics:
            return candidate
    return None


def is_valid_category_topic(category: str, topic: str) -> bool:
    """Whether the pair is allowed by the v2 controlled vocabulary."""

    return topic in TOPICS_BY_CATEGORY.get(category, frozenset())
