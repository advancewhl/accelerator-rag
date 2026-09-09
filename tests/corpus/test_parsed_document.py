from accelerator_rag.corpus.parsed_document import ParsedDocument, ParsedUnit


def test_parsed_unit_to_dict() -> None:
    unit = ParsedUnit(
        index=1,
        unit_type="slide",
        title="EPICS Overview",
        text="EPICS Overview\nIOC\nPV",
        metadata={
            "slide_number": 1,
            "notes": "Speaker note",
        },
    )

    result = unit.to_dict()

    assert result["index"] == 1
    assert result["unit_type"] == "slide"
    assert result["title"] == "EPICS Overview"
    assert result["metadata"]["slide_number"] == 1


def test_parsed_document_to_dict() -> None:
    document = ParsedDocument(
        source_path="data/raw/control_system/example.pptx",
        file_name="example.pptx",
        document_type="pptx",
        units=[
            ParsedUnit(
                index=1,
                unit_type="slide",
                title="Title",
                text="Title\nBody",
            )
        ],
    )

    result = document.to_dict()

    assert result["document_type"] == "pptx"
    assert result["file_name"] == "example.pptx"
    assert len(result["units"]) == 1
    assert result["units"][0]["unit_type"] == "slide"