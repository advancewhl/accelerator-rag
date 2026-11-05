"""One request-wide eligibility rule for every recall path.

Version filtering belongs before candidate selection.  Building a scope once and
passing it to BM25, both dense collections, same-page expansion and any second
retrieval round prevents a newer-but-inapplicable revision from entering one
channel after another channel already filtered it out.

Legacy v1 chunks have no usage/access metadata.  They remain eligible under the
default scope only because ``allow_unknown_*`` defaults to true; a governance
build should replace them with Schema v2 metadata instead of relying on this
compatibility path indefinitely.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from accelerator_rag.corpus.schema_v2 import AccessScope, UsageStatus
from accelerator_rag.domain.knowledge import KnowledgeChunk


DEFAULT_USAGE_STATUSES = frozenset(
    {UsageStatus.CURRENT.value, UsageStatus.REFERENCE.value}
)
DEFAULT_ACCESS_SCOPES = frozenset({AccessScope.INTERNAL.value})
_QUERYABLE_USAGE_STATUSES = frozenset(
    {
        UsageStatus.CURRENT.value,
        UsageStatus.HISTORICAL.value,
        UsageStatus.REFERENCE.value,
        UsageStatus.PENDING_REVIEW.value,
    }
)
_VALID_ACCESS_SCOPES = frozenset(item.value for item in AccessScope)
# Old clients may still send the pre-split series family ID.  Keep it working
# through the series tag rather than silently returning no documents.
LEGACY_FAMILY_TAGS = {
    "shine-control-operation-manual-series": (
        "series:shine-control-operation-manual-series"
    )
}


def _freeze(
    value: Iterable[str] | None, field_name: str
) -> frozenset[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        raise ValueError(f"{field_name} 必须是字符串集合，不能是单个字符串")
    items = frozenset(value)
    if not items:
        raise ValueError(f"{field_name} 不能为空集合；不筛选请使用 None")
    for item in items:
        if not isinstance(item, str) or not item.strip() or item != item.strip():
            raise ValueError(f"{field_name} 元素必须是非空无首尾空白字符串")
    return items


@dataclass(frozen=True)
class RetrievalScope:
    """Eligibility metadata resolved once per request or release build."""

    release_id: str = ""
    revision_ids: frozenset[str] | None = None
    family_ids: frozenset[str] | None = None
    usage_statuses: frozenset[str] = DEFAULT_USAGE_STATUSES
    document_kinds: frozenset[str] | None = None
    evidence_roles: frozenset[str] | None = None
    approval_statuses: frozenset[str] | None = None
    topics: frozenset[str] | None = None
    tags: frozenset[str] | None = None
    access_scopes: frozenset[str] = DEFAULT_ACCESS_SCOPES
    allow_unknown_usage: bool = True
    allow_unknown_access: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.release_id, str) or (
            self.release_id != self.release_id.strip()
        ):
            raise ValueError("release_id 必须是无首尾空白的字符串")
        for name in (
            "revision_ids",
            "family_ids",
            "document_kinds",
            "evidence_roles",
            "approval_statuses",
            "topics",
            "tags",
        ):
            object.__setattr__(
                self, name, _freeze(getattr(self, name), name)
            )
        object.__setattr__(
            self,
            "usage_statuses",
            _freeze(self.usage_statuses, "usage_statuses"),
        )
        object.__setattr__(
            self,
            "access_scopes",
            _freeze(self.access_scopes, "access_scopes"),
        )
        if self.usage_statuses is None or not self.usage_statuses:
            raise ValueError("usage_statuses 不能为空")
        if not self.usage_statuses <= _QUERYABLE_USAGE_STATUSES:
            unknown = sorted(self.usage_statuses - _QUERYABLE_USAGE_STATUSES)
            raise ValueError(
                "usage_statuses 含不可查询状态: " + ", ".join(unknown)
            )
        if not self.access_scopes <= _VALID_ACCESS_SCOPES:
            unknown = sorted(self.access_scopes - _VALID_ACCESS_SCOPES)
            raise ValueError("access_scopes 含未知状态: " + ", ".join(unknown))
        if type(self.allow_unknown_usage) is not bool:
            raise ValueError("allow_unknown_usage 必须是布尔值")
        if type(self.allow_unknown_access) is not bool:
            raise ValueError("allow_unknown_access 必须是布尔值")

    def allows(self, chunk: KnowledgeChunk) -> bool:
        """Return whether this canonical parent may enter any recall channel."""

        if not isinstance(chunk, KnowledgeChunk):
            raise TypeError("RetrievalScope.allows requires KnowledgeChunk")
        if self.revision_ids is not None and chunk.document_id not in self.revision_ids:
            return False
        if self.family_ids is not None:
            if chunk.effective_family_id not in self.family_ids:
                legacy_tags = {
                    LEGACY_FAMILY_TAGS[family_id]
                    for family_id in self.family_ids
                    if family_id in LEGACY_FAMILY_TAGS
                }
                if not (set(chunk.tag_list) & legacy_tags):
                    return False
        status = chunk.effective_usage_status
        if status == "unknown":
            if not self.allow_unknown_usage:
                return False
        elif status not in self.usage_statuses:
            return False
        if self.document_kinds is not None:
            if chunk.document_kind not in self.document_kinds:
                return False
        if self.evidence_roles is not None:
            if chunk.evidence_role not in self.evidence_roles:
                return False
        if self.approval_statuses is not None:
            if (chunk.approval_status or "unknown") not in self.approval_statuses:
                return False
        if self.topics is not None and chunk.topic not in self.topics:
            return False
        if self.tags is not None and not (set(chunk.tag_list) & self.tags):
            return False
        access = chunk.access_scope or "unknown"
        if access == "unknown":
            if not self.allow_unknown_access:
                return False
        elif access not in self.access_scopes:
            return False
        return True

    def filter(self, chunks: Iterable[KnowledgeChunk]) -> list[KnowledgeChunk]:
        return [chunk for chunk in chunks if self.allows(chunk)]

    def is_legacy_compatible(self) -> bool:
        """Return whether this is exactly the default eligibility policy.

        The default policy admits chunks whose usage/access metadata is unknown.
        Legacy v1 Qdrant payloads predate those fields entirely, so the vector
        store may skip server-side filtering for this one policy.  Any explicit
        deviation must be expressed as a strict payload filter.
        """

        return (
            self.revision_ids is None
            and self.family_ids is None
            and self.document_kinds is None
            and self.evidence_roles is None
            and self.topics is None
            and self.usage_statuses == DEFAULT_USAGE_STATUSES
            and self.access_scopes == DEFAULT_ACCESS_SCOPES
            and self.allow_unknown_usage
            and self.allow_unknown_access
        )

    def with_usage(self, *statuses: str) -> "RetrievalScope":
        return replace(self, usage_statuses=frozenset(statuses))

    def with_revisions(self, *revision_ids: str) -> "RetrievalScope":
        return replace(self, revision_ids=frozenset(revision_ids))

    def describe(self) -> dict:
        """Trace-friendly description; no source paths or credentials."""

        def values(value: frozenset[str] | None):
            return sorted(value) if value is not None else None

        return {
            "release_id": self.release_id,
            "revision_ids": values(self.revision_ids),
            "family_ids": values(self.family_ids),
            "usage_statuses": sorted(self.usage_statuses),
            "document_kinds": values(self.document_kinds),
            "evidence_roles": values(self.evidence_roles),
            "approval_statuses": values(self.approval_statuses),
            "topics": values(self.topics),
            "tags": values(self.tags),
            "access_scopes": sorted(self.access_scopes),
            "allow_unknown_usage": self.allow_unknown_usage,
            "allow_unknown_access": self.allow_unknown_access,
        }


def default_scope(release_id: str = "") -> RetrievalScope:
    """Current + reference material, internal access, legacy-compatible."""

    return RetrievalScope(release_id=release_id)


def version_scope(
    revision_ids: Iterable[str],
    *,
    release_id: str = "",
    usage_statuses: Iterable[str] = _QUERYABLE_USAGE_STATUSES,
) -> RetrievalScope:
    """Explicit revision selection used by version and historical queries."""

    return RetrievalScope(
        release_id=release_id,
        revision_ids=frozenset(revision_ids),
        usage_statuses=frozenset(usage_statuses),
        allow_unknown_usage=False,
    )


def reference_scope(
    *, release_id: str = "", revision_ids: Iterable[str] | None = None
) -> RetrievalScope:
    """Explicitly selected pending/review material; never included by default."""

    return RetrievalScope(
        release_id=release_id,
        revision_ids=None if revision_ids is None else frozenset(revision_ids),
        usage_statuses=frozenset(
            {
                UsageStatus.CURRENT.value,
                UsageStatus.HISTORICAL.value,
                UsageStatus.REFERENCE.value,
                UsageStatus.PENDING_REVIEW.value,
            }
        ),
        allow_unknown_usage=False,
    )
