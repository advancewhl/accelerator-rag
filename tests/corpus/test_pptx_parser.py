"""PPTX adapter: slide order, placeholders, tables, groups, pictures, notes."""

import base64

from pptx import Presentation
from pptx.util import Inches

from accelerator_rag.corpus.pptx_parser import parse_pptx
from accelerator_rag.domain.position import BlockType


SOURCE = "data/l0_raw/tests/deck.pptx"
REVISION = "pptx-sample-r1"
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def parse(path, **overrides):
    return parse_pptx(
        path,
        revision_id=REVISION,
        source_path=SOURCE,
        **overrides,
    )


def _add_picture(slide, tmp_path):
    image_path = tmp_path / "tiny.png"
    image_path.write_bytes(_PNG)
    return slide.shapes.add_picture(
        str(image_path), Inches(1), Inches(6), Inches(1), Inches(1)
    )


def test_slides_shapes_table_picture_and_notes(tmp_path):
    path = tmp_path / "deck.pptx"
    presentation = Presentation()
    first = presentation.slides.add_slide(presentation.slide_layouts[1])
    first.shapes.title.text = "第一页标题"
    first.placeholders[1].text = "正文内容"
    textbox = first.shapes.add_textbox(
        Inches(1), Inches(2), Inches(3), Inches(1)
    )
    textbox.text_frame.text = "文本框内容"

    table_shape = first.shapes.add_table(
        2, 2, Inches(1), Inches(3), Inches(3), Inches(1)
    )
    table = table_shape.table
    table.cell(0, 0).text = "名称"
    table.cell(0, 1).text = "数值"
    table.cell(1, 0).text = "联锁响应"
    table.cell(1, 1).text = "100 µs"

    _add_picture(first, tmp_path)
    first.notes_slide.notes_text_frame.text = "演讲者备注"

    second = presentation.slides.add_slide(presentation.slide_layouts[5])
    second.shapes.title.text = "第二页标题"
    presentation.save(path)

    parsed = parse(path)

    assert [
        (block.block_type, block.position.start) for block in parsed.blocks
    ] == [
        (BlockType.HEADING.value, 1),
        (BlockType.PARAGRAPH.value, 1),
        (BlockType.PARAGRAPH.value, 1),
        (BlockType.TABLE.value, 1),
        (BlockType.IMAGE.value, 1),
        (BlockType.NOTE.value, 1),
        (BlockType.HEADING.value, 2),
    ]
    assert parsed.blocks[0].text == "第一页标题"
    assert parsed.blocks[0].heading_level == 1
    assert parsed.blocks[2].text == "文本框内容"

    table_data = parsed.blocks[3].table
    assert table_data.header_rows == 1
    assert table_data.rows == (("名称", "数值"), ("联锁响应", "100 µs"))
    assert parsed.blocks[3].position.label == "slide-1"

    image = parsed.blocks[4]
    assert image.text == ""
    assert dict(image.metadata)["kind"] == "image"
    assert dict(image.metadata)["image_format"] == "png"

    note = parsed.blocks[5]
    assert note.text == "演讲者备注"
    assert dict(note.metadata)["source"] == "notes"
    assert all(
        "演讲者备注" not in block.text
        for block in parsed.blocks
        if block.block_type != BlockType.NOTE.value
    )

    assert parsed.blocks[6].position.start == 2
    assert parsed.blocks[6].position.label == "slide-2"
    assert all(block.position.kind == "slide" for block in parsed.blocks)
    assert len({block.block_id for block in parsed.blocks}) == len(parsed.blocks)

    body_locator = dict(parsed.blocks[1].position.locator)
    assert "shape_id" in body_locator
    assert "shape_name" in body_locator
    assert dict(parsed.blocks[5].position.locator)["source"] == "notes"

    metadata = dict(parsed.metadata)
    assert metadata["slide_count"] == "2"
    assert metadata["table_count"] == "1"
    assert metadata["image_count"] == "1"
    assert metadata["note_count"] == "1"


def test_group_shapes_are_traversed_recursively(tmp_path):
    path = tmp_path / "group.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    group = slide.shapes.add_group_shape()
    group.shapes.add_textbox(
        Inches(1), Inches(1), Inches(2), Inches(1)
    ).text_frame.text = "组内文本"
    nested = group.shapes.add_group_shape()
    nested.shapes.add_textbox(
        Inches(1), Inches(2), Inches(2), Inches(1)
    ).text_frame.text = "嵌套组文本"
    presentation.save(path)

    parsed = parse(path)

    assert [
        block.text for block in parsed.blocks
    ] == ["组内文本", "嵌套组文本"]
    assert all(
        block.position.start == 1 for block in parsed.blocks
    )


def test_notes_only_slide_keeps_note_separate(tmp_path):
    path = tmp_path / "notes.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "标题"
    slide.notes_slide.notes_text_frame.text = "仅备注内容"
    presentation.save(path)

    parsed = parse(path)

    assert [block.block_type for block in parsed.blocks] == [
        BlockType.HEADING.value,
        BlockType.NOTE.value,
    ]
    assert parsed.blocks[1].text == "仅备注内容"
    assert parsed.blocks[1].position.start == 1


def test_unknown_shape_type_keeps_text_and_does_not_fail_deck(
    tmp_path, monkeypatch
):
    import pptx.shapes.autoshape as autoshape

    path = tmp_path / "unknown-shape.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(
        Inches(1), Inches(1), Inches(3), Inches(1)
    ).text_frame.text = "未知类型但文本仍应保留"
    slide.shapes.add_textbox(
        Inches(1), Inches(3), Inches(3), Inches(1)
    )
    presentation.save(path)

    def fail(self):
        raise NotImplementedError("Shape instance of unrecognized shape type")

    monkeypatch.setattr(
        autoshape.Shape, "shape_type", property(fail)
    )

    parsed = parse(path)

    assert [block.text for block in parsed.blocks] == [
        "未知类型但文本仍应保留"
    ]
    assert any(
        warning.startswith("unrecognized_shape_type")
        and "NotImplementedError" in warning
        for warning in parsed.warnings
    )
    assert not any(
        warning.startswith("shape_processing_failed")
        for warning in parsed.warnings
    )
    assert dict(parsed.metadata)["unsupported_shape_count"] == "2"
    assert dict(parsed.metadata)["unhandled_unknown_shape_count"] == "1"


def test_chart_graphic_frame_is_skipped_with_warning(tmp_path):
    from pptx.chart.data import ChartData
    from pptx.enum.chart import XL_CHART_TYPE

    path = tmp_path / "chart.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "图表页"
    chart_data = ChartData()
    chart_data.categories = ["A"]
    chart_data.add_series("S", (1,))
    slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(1),
        Inches(1),
        Inches(4),
        Inches(3),
        chart_data,
    )
    presentation.save(path)

    parsed = parse(path)

    assert [block.text for block in parsed.blocks] == ["图表页"]
    assert any(
        warning.startswith("chart_not_extracted")
        for warning in parsed.warnings
    )
    assert dict(parsed.metadata)["chart_count"] == "1"


def test_source_text_is_not_repaired_or_normalized(tmp_path):
    path = tmp_path / "defect.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    textbox = slide.shapes.add_textbox(
        Inches(1), Inches(1), Inches(3), Inches(1)
    )
    textbox.text_frame.text = "019年11月21日"
    presentation.save(path)

    parsed = parse(path)

    assert parsed.blocks[0].text == "019年11月21日"
    assert "2019" not in parsed.text


def test_empty_presentation_has_warning(tmp_path):
    path = tmp_path / "empty.pptx"
    Presentation().save(path)

    parsed = parse(path)

    assert parsed.blocks == ()
    assert parsed.warnings == ("empty_document",)
    assert dict(parsed.metadata)["slide_count"] == "0"
