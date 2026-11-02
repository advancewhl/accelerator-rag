from dataclasses import replace

import pytest


@pytest.mark.parametrize(
    "changes",
    [
        {"page_start": 0},
        {"page_start": 4, "page_end": 3},
        {"page_start": "3"},
        {"page_end": True},
        {"text": " "},
        {"document_id": 123},
        {"source_path": "/home/user/file.pdf"},
        {"source_path": "data/l0_raw/../file.pdf"},
    ],
)
def test_malformed_core_fields_rejected(chunk, changes):
    with pytest.raises(ValueError):
        replace(chunk, **changes)


def test_legacy_projection_keeps_frozen_hash_shape(chunk):
    legacy = chunk.legacy_dict()

    assert set(legacy) == {
        "chunk_id",
        "document_id",
        "document_title",
        "text",
        "source_path",
        "document_version",
        "language",
        "category",
        "topic",
        "page_start",
        "page_end",
    }
    assert chunk.effective_position_kind == "pdf_page"
    assert chunk.effective_family_id == chunk.document_id
