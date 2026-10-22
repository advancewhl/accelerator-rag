from dataclasses import asdict

from accelerator_rag.corpus.chunking import chunk_pdf
from accelerator_rag.corpus.cleaning import clean_page_texts, normalize_text
from accelerator_rag.corpus.pdf_parser import ParsedPdfDocument, PdfPage, PdfTextBlock


def block(number, text, bbox=(60, 120, 280, 300)):
    return PdfTextBlock(number, 0, bbox, text)


def document(record, pages):
    return ParsedPdfDocument(
        record.source_path,
        "fixture.pdf",
        len(pages),
        {},
        [
            PdfPage(
                i + 1,
                600,
                800,
                "\n".join(b.text for b in blocks),
                sum(len(b.text) for b in blocks),
                blocks,
                0,
            )
            for i, blocks in enumerate(pages)
        ],
    )


def test_cleanup_removes_generic_publication_edges_but_keeps_raw_evidence(record):
    pages = []
    for index in range(3):
        pages.append(
            [
                block(
                    0, f"Workshop volume {index + 1}. ISBN: 12345", (50, 20, 550, 40)
                ),
                block(1, "Repeated meaningful EPICS body evidence."),
                block(
                    2,
                    "Copyright © Author; licensed for distribution",
                    (545, 80, 555, 720),
                ),
                block(
                    3, f"{100 + index}\nData and control systems", (50, 760, 550, 775)
                ),
                block(4, "AB123", (520, 745, 550, 755)),
            ]
        )
    parsed = document(record, pages)
    before = asdict(parsed)
    texts = clean_page_texts(parsed)
    assert [text for _, text in texts] == [
        "Repeated meaningful EPICS body evidence."
    ] * 3
    chunks = chunk_pdf(parsed, record)
    assert chunks == chunk_pdf(parsed, record)
    assert [c.page_start for c in chunks] == [1, 2, 3]
    assert all(
        c.page_start == c.page_end
        and c.source_path == record.source_path
        and c.document_id == record.doc_id
        for c in chunks
    )
    assert asdict(parsed) == before


def test_repetition_alone_does_not_remove_body_and_single_page_is_conservative(record):
    parsed = document(
        record,
        [
            [
                block(0, "A legitimate heading", (50, 20, 300, 40)),
                block(1, "Body discussing copyright and ISBN identifiers."),
            ]
        ],
    )
    text = clean_page_texts(parsed)[0][1]
    assert "legitimate heading" in text and "copyright and ISBN" in text


def test_academic_front_matter_removed_at_abstract_boundary(record):
    parsed = document(
        record,
        [
            [
                block(0, "INFORMATION MANAGEMENT SYSTEM", (60, 60, 550, 80)),
                block(1, "A. Author, Research Institute", (60, 90, 550, 110)),
                block(2, "Abstract", (60, 130, 150, 145)),
                block(3, "EPICS IOC information is managed in a database."),
            ]
        ],
    )
    text = clean_page_texts(parsed)[0][1]
    assert "INFORMATION MANAGEMENT SYSTEM" not in text and "A. Author" not in text
    assert "EPICS IOC information" in text


def test_column_boundary_hyphenation_is_repaired_before_chunk_splitting(record):
    # Native order has footer before the continuation. Cleaning must remove it
    # and join consecutive body evidence, retaining a genuine technical hyphen.
    parsed = document(
        record,
        [
            [
                block(0, "Hundreds of devices use real-world control.\nThere are hun-"),
                block(1, "42", (520, 760, 550, 775)),
                block(2, "dreds of PVs in this IOC. real-\nworld I/O is supported."),
            ]
        ],
    )
    chunks = chunk_pdf(parsed, record)
    assert len(chunks) == 1
    text = chunks[0].text
    assert "hundreds of PVs" in text
    assert "real-world I/O" in text and "realworld" not in text
    assert "\n\ndreds" not in text


def test_technical_hyphens_win_over_unhyphenated_words():
    vocab = frozenset({"recreation", "re-creation", "information"})
    text = normalize_text("re-\ncreation infor-\nmation SR:BPM-\nX", vocabulary=vocab)
    assert text == "re-creation information SR:BPM-X"
    assert normalize_text("un-\nknown") == "un-known"
    assert normalize_text("beam-synchronous real-world SR:BPM01:X") == (
        "beam-synchronous real-world SR:BPM01:X"
    )


def test_explicit_reference_list_excluded_without_removing_body_citations(record):
    parsed = document(
        record,
        [
            [
                block(0, "The CA library [1] manages PV channels."),
                block(1, "REFERENCES"),
                block(2, "[1] A. Author, Channel access"),
                block(3, "[2] B. Author, Database system"),
            ]
        ],
    )
    text = clean_page_texts(parsed)[0][1]
    assert "library [1]" in text
    assert "A. Author" not in text and "REFERENCES" not in text


def test_two_column_order_places_late_script_block_before_right_column():
    from accelerator_rag.corpus.cleaning import order_body_blocks

    def block(number, x, y, text):
        return PdfTextBlock(number, 0, (x, y, x + 220, y + 40), text)

    left_top = block(0, 50, 100, "left top " * 15)
    left_bottom = block(1, 50, 300, "left bottom " * 15)
    right_top = block(2, 330, 100, "right top " * 15)
    right_bottom = block(3, 330, 300, "right bottom " * 15)
    script = block(4, 50, 200, "startup script")
    header = PdfTextBlock(5, 0, (50, 20, 550, 40), "heading")
    native = [left_top, left_bottom, right_top, right_bottom, script, header]
    assert order_body_blocks(native, 600) == [
        header,
        left_top,
        script,
        left_bottom,
        right_top,
        right_bottom,
    ]


def test_wrapped_word_punctuation_and_technical_identifiers():
    text = normalize_text(
        "infor-\nmation. EPICS-\nCA SR:BPM-\nX",
        vocabulary=frozenset(
            {"information", "EPICS-CA".casefold(), "SR:BPM-X".casefold()}
        ),
    )
    assert text == "information. EPICS-CA SR:BPM-X"


def test_null_and_inset_running_header_keep_raw_and_unique_heading(record):
    pages = []
    for i in range(8):
        pages.append(
            [
                block(
                    0, "Generic engineering design running header", (60, 90, 520, 105)
                ),
                block(1, str(i + 1), (290, 110, 310, 123)),
                block(
                    2,
                    "Unique chapter heading" if i == 0 else f"Body topic {i}",
                    (60, 130, 500, 145),
                ),
                block(
                    3,
                    "EPICS evidence\x00 continues with scientific details.",
                    (60, 220, 500, 500),
                ),
            ]
        )
    parsed = document(record, pages)
    before = asdict(parsed)
    texts = clean_page_texts(parsed)
    assert all("running header" not in t and "\x00" not in t for _, t in texts)
    assert all(not t.startswith(str(i + 1)) for i, (_, t) in enumerate(texts))
    assert "Unique chapter heading" in texts[0][1]
    assert all("EPICS evidence continues" in t for _, t in texts)
    assert asdict(parsed) == before


def test_repeated_body_and_unexplained_pua_preserved(record):
    parsed = document(
        record,
        [
            [block(0, "Repeated scientific body evidence \uf071", (60, 250, 500, 400))]
            for _ in range(8)
        ],
    )
    assert all(
        "\uf071" in t and "scientific body" in t for _, t in clean_page_texts(parsed)
    )


def test_numbered_unique_chapter_headings_are_not_masked_together(record):
    parsed = document(
        record,
        [
            [
                block(0, f"{i + 1}. Unique chapter title", (60, 100, 520, 115)),
                block(1, "Normal body.", (60, 250, 520, 400)),
            ]
            for i in range(8)
        ],
    )
    for i, (_, text) in enumerate(clean_page_texts(parsed)):
        assert f"{i + 1}. Unique chapter title" in text
