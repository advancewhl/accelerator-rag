"""Minimal release identity contract for the standalone RAG service.

A real release manifest (accepted build, frozen index checksums, attachment
inventory) belongs to K3 and is not implemented here.  The runtime therefore
reports only facts it can actually read from configuration; anything absent is
``unknown`` and never inferred from file names, timestamps or the newest
document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


UNKNOWN = "unknown"
_CONFIG_SOURCE = "runtime-config"


@dataclass(frozen=True)
class ReleaseIdentity:
    """Identity of the knowledge-base state this runtime serves."""

    release_id: str = UNKNOWN
    build_id: str = UNKNOWN
    source: str = _CONFIG_SOURCE

    def __post_init__(self) -> None:
        for name in ("release_id", "build_id", "source"):
            value = getattr(self, name)
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
            ):
                raise ValueError(
                    f"{name} must be a non-empty string without outer whitespace"
                )


def _configured_value(config: Any, key: str) -> str:
    """Read ``key`` from the top level or a nested ``release`` mapping."""

    candidates: list[Any] = []
    if isinstance(config, Mapping):
        candidates.append(config.get(key))
        release = config.get("release")
        if isinstance(release, Mapping):
            candidates.append(release.get(key))
    for value in candidates:
        if value is None or value == "":
            continue
        if not isinstance(value, str) or value != value.strip():
            raise ValueError(f"config {key} must be a trimmed string")
        return value
    return UNKNOWN


def release_identity_from_config(
    config: Mapping[str, Any] | None,
) -> ReleaseIdentity:
    """Build the identity from runtime configuration without inventing facts.

    Only ``release_id`` may come from plain runtime configuration.  A build ID
    belongs to a release manifest (K3); until one exists it stays ``unknown``
    rather than being copied from an unrelated config key.
    """

    return ReleaseIdentity(
        release_id=_configured_value(config, "release_id"),
        build_id=UNKNOWN,
        source=_CONFIG_SOURCE,
    )


def release_status(identity: ReleaseIdentity, snapshot: dict | None = None) -> dict:
    """Public ``/v1/rag/releases/current`` payload.

    ``snapshot`` is the document catalog listing.  One catalog row corresponds
    to one indexed revision because the legacy index contract stores a single
    revision per ``document_id``.  Read-only attachments are not tracked by the
    index yet, so their count is reported as zero rather than guessed.
    """

    snapshot = snapshot or {}
    documents = snapshot.get("documents") or []
    families = snapshot.get("families")
    if families is None:
        families = [
            {
                "family_id": (document.get("family_ids") or [document["document_id"]])[
                    0
                ]
            }
            for document in documents
            if document.get("document_id")
        ]
    indexed_sections = snapshot.get("indexed_section_count")
    if indexed_sections is None:
        indexed_sections = sum(
            document.get("indexed_section_count") or 0 for document in documents
        )
    return {
        "release_id": identity.release_id,
        "build_id": identity.build_id,
        "document_count": snapshot.get("document_count", len(documents)),
        "revision_count": len(documents),
        "family_count": len(families),
        "indexed_section_count": indexed_sections,
        "read_only_attachment_count": 0,
        "source": identity.source,
    }
