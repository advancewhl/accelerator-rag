"""Request-wide eligibility filtering for every recall channel."""

from dataclasses import replace

import pytest

from accelerator_rag.retrieval.scope import (
    RetrievalScope,
    default_scope,
    reference_scope,
    version_scope,
)


def metadata_chunk(chunk, **overrides):
    values = {
        "family_id": "shine-interlock",
        "document_kind": "subsystem_design",
        "evidence_role": "design_target",
        "usage_status": "reference",
        "approval_status": "unknown",
        "access_scope": "internal",
        "position_kind": "pdf_page",
    }
    values.update(overrides)
    return replace(chunk, **values)


def test_default_scope_is_legacy_compatible():
    scope = default_scope("kb-2.0.0")
    # A v1 chunk has empty usage/access metadata; the default scope keeps it
    # queryable until the governance build migrates it.
    assert scope.allows(_plain_chunk()) is True
    assert scope.release_id == "kb-2.0.0"
    assert scope.describe()["usage_statuses"] == ["current", "reference"]


def test_default_scope_excludes_non_current_usage():
    scope = default_scope()
    assert scope.allows(metadata_chunk(_plain_chunk(), usage_status="current"))
    assert scope.allows(metadata_chunk(_plain_chunk(), usage_status="reference"))
    assert not scope.allows(metadata_chunk(_plain_chunk(), usage_status="historical"))
    assert not scope.allows(
        metadata_chunk(_plain_chunk(), usage_status="pending_review")
    )


def test_revision_and_family_filters_use_explicit_identity():
    chunk = metadata_chunk(_plain_chunk(), document_id="revision-a")
    scope = RetrievalScope(
        revision_ids=frozenset({"revision-a"}),
        allow_unknown_usage=False,
    )
    assert scope.allows(chunk)
    assert not scope.allows(replace(chunk, document_id="revision-b"))

    family_scope = RetrievalScope(
        family_ids=frozenset({"shine-interlock"}),
        allow_unknown_usage=False,
    )
    assert family_scope.allows(chunk)
    assert not family_scope.allows(replace(chunk, family_id="other-family"))


def test_kind_role_topic_filters_do_not_guess_for_legacy_chunks():
    legacy = _plain_chunk()
    scope = RetrievalScope(
        document_kinds=frozenset({"operation_manual"}),
        allow_unknown_usage=False,
    )
    assert not scope.allows(legacy)
    assert not RetrievalScope(
        evidence_roles=frozenset({"test_result"}), allow_unknown_usage=False
    ).allows(legacy)
    assert RetrievalScope(topics=frozenset({"ioc"})).allows(legacy)


def test_access_scope_defaults_are_internal_but_legacy_unknown_is_opt_in():
    restricted = metadata_chunk(_plain_chunk(), access_scope="restricted")
    assert not default_scope().allows(restricted)
    assert RetrievalScope(
        access_scopes=frozenset({"internal", "restricted"}),
        allow_unknown_usage=False,
    ).allows(restricted)
    unknown = metadata_chunk(_plain_chunk(), access_scope="")
    assert default_scope().allows(unknown)
    assert not RetrievalScope(
        allow_unknown_access=False, allow_unknown_usage=False
    ).allows(unknown)


def test_version_and_reference_scopes_are_explicit_modes():
    historical = metadata_chunk(_plain_chunk(), usage_status="historical")
    pending = metadata_chunk(_plain_chunk(), usage_status="pending_review")
    assert version_scope(["revision-a"]).allows(
        replace(historical, document_id="revision-a")
    )
    assert reference_scope(revision_ids=["revision-a"]).allows(
        replace(pending, document_id="revision-a")
    )
    assert not reference_scope(revision_ids=["revision-a"]).allows(
        replace(pending, document_id="revision-b")
    )


@pytest.mark.parametrize(
    "values",
    [
        {"usage_statuses": frozenset({"excluded"})},
        {"usage_statuses": frozenset()},
        {"usage_statuses": frozenset({"unknown"})},
        {"access_scopes": frozenset({"public"})},
        {"revision_ids": "revision-a"},
        {"revision_ids": frozenset()},
    ],
)
def test_invalid_scope_is_rejected(values):
    with pytest.raises(ValueError):
        RetrievalScope(**values)


def _plain_chunk():
    """A v1-shaped chunk with no Schema v2 metadata."""

    from accelerator_rag.domain.knowledge import KnowledgeChunk

    return KnowledgeChunk(
        chunk_id="legacy:test",
        document_id="legacy-document",
        document_title="Legacy",
        text="EPICS IOC manages SR:BPM01:X.",
        source_path="data/l0_raw/legacy.pdf",
        document_version="1",
        language="en",
        category="control_system",
        topic="ioc",
        page_start=1,
        page_end=1,
    )
