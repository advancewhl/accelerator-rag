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
