"""DOCX adapter: body order, headings, tables, formulas, text boxes."""

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.shared import Pt

from accelerator_rag.corpus.docx_parser import parse_docx
from accelerator_rag.domain.position import BlockType


SOURCE = "data/l0_raw/tests/sample.docx"
REVISION = "docx-sample-r1"


def parse(path, **overrides):
    return parse_docx(
        path,
        revision_id=REVISION,
        source_path=SOURCE,
        **overrides,
    )


def _heading(container, text, style):
    return container.add_paragraph(text, style=style)


def _omml_paragraph(document, text):
    paragraph = document.add_paragraph("")
    math = parse_xml(
        '<m:oMathPara xmlns:m="http://schemas.openxmlformats.org/'
        'officeDocument/2006/math" '
        'xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main">'
        f"<m:oMath><m:r><m:t>{text}</m:t></m:r></m:oMath></m:oMathPara>"
    )
    paragraph._p.append(math)
    return paragraph


def _textbox_paragraph(document, lines):
    anchor = document.add_paragraph("")
    body = "".join(
        f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in lines
    )
    fragment = parse_xml(
        '<w:r xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main" '
        'xmlns:wp="http://schemas.openxmlformats.org/'
        'drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/'
        'wordprocessingShape">'
        "<w:drawing><wp:inline><a:graphic><a:graphicData "
        'uri="http://schemas.microsoft.com/office/word/2010/'
        'wordprocessingShape"><wps:wsp><wps:txbx><w:txbxContent>'
        f"{body}</w:txbxContent></wps:txbx></wps:wsp></a:graphicData>"
        "</a:graphic></wp:inline></w:drawing></w:r>"
    )
    anchor._p.append(fragment)
    return anchor


def _insert_sdt(document, lines, index=1):
    body = document.element.body
    content = "".join(
        f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in lines
    )
    sdt = parse_xml(
        '<w:sdt xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:sdtPr/><w:sdtContent>'
        f"{content}</w:sdtContent></w:sdt>"
    )
    body.insert(index, sdt)
    return sdt


def test_toc_inside_content_control_is_skipped_but_body_is_kept(tmp_path):
    path = tmp_path / "sdt-toc.docx"
    document = Document()
    document.add_paragraph("封面内容")
    document.add_heading("概述", level=2)
    document.add_paragraph("这是正文。")
    _insert_sdt(
        document,
        ["目录", "1 概述", "2 设计目标", "3.1 总体方案"],
    )
    document.save(path)

    parsed = parse(path)

    assert dict(parsed.metadata)["toc_block_count"] == "4"
    assert [block.text for block in parsed.blocks] == [
        "封面内容",
        "概述",
        "这是正文。",
    ]
    assert parsed.blocks[1].block_type == BlockType.HEADING.value
    assert not any(block.text == "1 概述" for block in parsed.blocks)


def test_content_control_without_toc_is_flattened(tmp_path):
    path = tmp_path / "sdt-body.docx"
    document = Document()
    _insert_sdt(document, ["内容控件中的正文"], index=0)
    document.save(path)

    parsed = parse(path)

    assert [block.text for block in parsed.blocks] == ["内容控件中的正文"]
    assert dict(parsed.metadata)["toc_block_count"] == "0"


def test_toc_styles_fields_and_leaders_are_skipped(tmp_path):
    path = tmp_path / "toc-markers.docx"
    document = Document()
    for name in ("TOC Heading", "TOC 1"):
        if name not in {style.name for style in document.styles}:
            document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    document.add_paragraph("目录", style="TOC Heading")
    document.add_paragraph("1 概述\t3", style="TOC 1")

    field_paragraph = document.add_paragraph("")
    field = parse_xml(
        '<w:fldSimple xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main" '
        'w:instr=" TOC \\o &quot;1-3&quot; \\h \\z \\u ">'
        "<w:r><w:t>2 设计目标\t4</w:t></w:r></w:fldSimple>"
    )
    field_paragraph._p.append(field)

    document.add_paragraph("3.1 总体方案..........12")
    document.add_paragraph("4.1 接口约定\t15")
    document.add_paragraph("正文段落。")
    document.save(path)

    parsed = parse(path)

    assert dict(parsed.metadata)["toc_block_count"] == "5"
    assert [block.text for block in parsed.blocks] == ["正文段落。"]


def test_real_heading_named_contents_is_not_deleted(tmp_path):
    path = tmp_path / "real-contents.docx"
    document = Document()
    document.add_heading("目录", level=2)
    document.add_paragraph("这里是真正的正文内容。")
    document.save(path)

    parsed = parse(path)

    assert parsed.blocks[0].block_type == BlockType.HEADING.value
    assert parsed.blocks[0].text == "目录"
    assert dict(parsed.metadata)["toc_block_count"] == "0"


def test_numbered_paragraph_without_toc_context_stays_a_heading(tmp_path):
    path = tmp_path / "numbering.docx"
    document = Document()
    document.add_paragraph("1 概述")
    document.add_paragraph("正文内容。")
    document.save(path)

    parsed = parse(path)

    assert parsed.blocks[0].block_type == BlockType.HEADING.value
    assert parsed.blocks[0].text == "1 概述"
    assert dict(parsed.metadata)["toc_block_count"] == "0"


def test_body_order_headings_list_caption_and_table(tmp_path):
    path = tmp_path / "sample.docx"
    document = Document()
    document.core_properties.title = "测试文档"
    _heading(document, "第一章 概述", "Heading 1")
    document.add_paragraph("这是正文段落。")
    document.add_paragraph("项目一", style="List Bullet")
    document.add_paragraph("表 1 参数表")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "名称"
    table.cell(0, 1).text = "数值"
    table.cell(1, 0).text = "联锁响应"
    table.cell(1, 1).text = "100 µs"
    document.add_paragraph("")
    document.add_paragraph("表后正文。")
    document.save(path)

    parsed = parse(path)

    assert parsed.title == "测试文档"
    assert [block.block_type for block in parsed.blocks] == [
        BlockType.HEADING.value,
        BlockType.PARAGRAPH.value,
        BlockType.LIST_ITEM.value,
        BlockType.CAPTION.value,
        BlockType.TABLE.value,
        BlockType.PARAGRAPH.value,
    ]
    assert parsed.blocks[0].heading_level == 1
    assert parsed.blocks[0].text == "第一章 概述"

    table_block = parsed.blocks[4]
    assert table_block.table is not None
    assert table_block.table.header_rows == 1
    assert table_block.table.rows[0] == ("名称", "数值")
    assert table_block.table.data_rows() == (("联锁响应", "100 µs"),)
    assert table_block.table.caption == "表 1 参数表"
    assert table_block.caption == "表 1 参数表"

    # The empty paragraph still consumes a body ordinal; positions stay 1-based.
    assert [block.position.start for block in parsed.blocks] == [1, 2, 3, 4, 5, 7]
    assert [block.position.end for block in parsed.blocks] == [1, 2, 3, 4, 5, 7]
    assert parsed.blocks[-1].position.label == "paragraph-7"
    assert parsed.position_kinds == ("paragraph",)
    assert len({block.block_id for block in parsed.blocks}) == len(parsed.blocks)

    first = parsed.to_dict()
    second = parse(path).to_dict()
    assert first == second

    metadata = dict(parsed.metadata)
    assert metadata["heading_style_count"] == "1"
    assert metadata["heading_heuristic_count"] == "0"
    assert metadata["heading_detection"] == "conservative"


def test_chinese_heading_style_title_and_outline_level(tmp_path):
    path = tmp_path / "headings.docx"
    document = Document()
    if "标题 2" not in {style.name for style in document.styles}:
        document.styles.add_style("标题 2", WD_STYLE_TYPE.PARAGRAPH)
    _heading(document, "中文二级标题", "标题 2")
    _heading(document, "文档标题", "Title")
    outline = document.add_paragraph("大纲四级标题")
    outline_level = outline._p.get_or_add_pPr().makeelement(
        qn("w:outlineLvl"), {qn("w:val"): "3"}
    )
    outline._p.pPr.append(outline_level)
    document.save(path)

    parsed = parse(path)

    headings = parsed.blocks_of(BlockType.HEADING.value)
    assert [(block.text, block.heading_level) for block in headings] == [
        ("中文二级标题", 2),
        ("文档标题", 1),
        ("大纲四级标题", 4),
    ]
    assert [
        dict(block.metadata)["heading_source"] for block in headings
    ] == ["style", "style", "outline"]
    metadata = dict(parsed.metadata)
    assert metadata["heading_style_count"] == "2"
    assert metadata["heading_outline_count"] == "1"
    assert metadata["heading_heuristic_count"] == "0"


def test_numbered_and_bold_size_heading_fallbacks_are_conservative(tmp_path):
    path = tmp_path / "fallback.docx"
    document = Document()
    body = document.add_paragraph()
    body.add_run("这是普通正文，字号为十点五。")
    document.add_paragraph("2.1.3 接口约定")
    document.add_paragraph("1. 检查电源是否连接。")
    document.add_paragraph("3. " + "很长的编号段落" * 20)
    document.add_paragraph("1. 列表形式正文", style="List Bullet")
    large = document.add_paragraph()
    run = large.add_run("系统总体结构")
    run.bold = True
    run.font.size = Pt(16)
    document.save(path)

    parsed = parse(path)

    headings = parsed.blocks_of(BlockType.HEADING.value)
    assert [(block.text, block.heading_level) for block in headings] == [
        ("2.1.3 接口约定", 3),
        ("系统总体结构", 1),
    ]
    assert dict(headings[0].metadata) == {
        "heading_source": "heuristic",
        "heading_rule": "numbering",
    }
    assert dict(headings[1].metadata) == {
        "heading_source": "heuristic",
        "heading_rule": "bold-size",
    }
    assert "1. 检查电源是否连接。" in {
        block.text
        for block in parsed.blocks
        if block.block_type == BlockType.PARAGRAPH.value
    }
    assert any(
        block.block_type == BlockType.LIST_ITEM.value
        and block.text == "1. 列表形式正文"
        for block in parsed.blocks
    )
    metadata = dict(parsed.metadata)
    assert metadata["heading_style_count"] == "0"
    assert metadata["heading_heuristic_count"] == "2"
    assert metadata["body_font_size_pt"] == "10.5"


def test_caption_style_and_figure_caption_after_table(tmp_path):
    path = tmp_path / "captions.docx"
    document = Document()
    if "Caption" not in {style.name for style in document.styles}:
        document.styles.add_style("Caption", WD_STYLE_TYPE.PARAGRAPH)
    document.add_paragraph("设备清单", style="Caption")
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "设备"
    document.add_paragraph("图 1 系统结构")
    document.save(path)

    parsed = parse(path)

    assert [
        block.block_type for block in parsed.blocks
    ] == [
        BlockType.CAPTION.value,
        BlockType.TABLE.value,
        BlockType.CAPTION.value,
    ]
    assert parsed.blocks[0].text == "设备清单"
    assert parsed.blocks[2].text == "图 1 系统结构"


def test_merged_cells_keep_every_column(tmp_path):
    path = tmp_path / "merged.docx"
    document = Document()
    table = document.add_table(rows=2, cols=3)
    merged = table.cell(0, 0).merge(table.cell(0, 1))
    merged.text = "合并表头"
    table.cell(0, 2).text = "备注"
    table.cell(1, 0).text = "A"
    table.cell(1, 1).text = "B"
    table.cell(1, 2).text = "C"
    document.save(path)

    parsed = parse(path)

    table_data = parsed.blocks_of(BlockType.TABLE.value)[0].table
    assert len(table_data.rows[0]) == 3
    assert table_data.rows[0][0] == table_data.rows[0][1] == "合并表头"
    assert table_data.rows[0][2] == "备注"
    assert table_data.rows[1] == ("A", "B", "C")


def test_omml_formula_is_kept_without_fake_latex(tmp_path):
    path = tmp_path / "formula.docx"
    document = Document()
    document.add_paragraph("公式如下：")
    _omml_paragraph(document, "E=mc^2")
    document.save(path)

    parsed = parse(path)

    formulas = parsed.blocks_of(BlockType.FORMULA.value)
    assert len(formulas) == 1
    formula = formulas[0]
    assert formula.text == "E=mc^2"
    assert dict(formula.metadata) == {
        "formula_source": "omml",
        "latex_status": "unresolved",
    }
    assert "\\" not in formula.text
    assert dict(formula.position.locator)["omml"] == "true"


def test_omml_without_text_keeps_block_and_warns(tmp_path):
    path = tmp_path / "empty-formula.docx"
    document = Document()
    empty_math = parse_xml(
        '<m:oMathPara xmlns:m="http://schemas.openxmlformats.org/'
        'officeDocument/2006/math">'
        "<m:oMath><m:r><m:t></m:t></m:r></m:oMath></m:oMathPara>"
    )
    paragraph = document.add_paragraph("")
    paragraph._p.append(empty_math)
    document.save(path)

    parsed = parse(path)

    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].block_type == BlockType.FORMULA.value
    assert parsed.blocks[0].text == "[formula]"
    assert dict(parsed.blocks[0].metadata)["formula_text_status"] == "unavailable"
    assert any(
        warning.startswith("formula_text_unavailable")
        for warning in parsed.warnings
    )


def test_textbox_content_is_extracted_and_reported(tmp_path):
    path = tmp_path / "textbox.docx"
    document = Document()
    document.add_paragraph("正文前")
    _textbox_paragraph(document, ["文本框内容", "第二段"])
    document.add_paragraph("正文后")
    document.save(path)

    parsed = parse(path)

    textbox_blocks = [
        block
        for block in parsed.blocks
        if dict(block.metadata).get("container") == "textbox"
    ]
    assert [block.text for block in textbox_blocks] == ["文本框内容", "第二段"]
    assert all(
        block.block_type == BlockType.PARAGRAPH.value
        for block in textbox_blocks
    )
    assert all(block.position.start == 2 for block in textbox_blocks)
    assert all(
        dict(block.position.locator)["container"] == "paragraph"
        for block in textbox_blocks
    )
    metadata = dict(parsed.metadata)
    assert metadata["textbox_count"] == "1"
    assert metadata["textbox_paragraph_count"] == "2"


def test_empty_paragraphs_skipped_and_empty_document_warned(tmp_path):
    path = tmp_path / "empty.docx"
    document = Document()
    document.save(path)

    parsed = parse(path)

    assert parsed.blocks == ()
    assert parsed.warnings == ("empty_document",)
    assert dict(parsed.metadata)["heading_count"] == "0"


def test_headers_and_footers_are_not_body_text(tmp_path):
    path = tmp_path / "header.docx"
    document = Document()
    document.sections[0].header.paragraphs[0].text = "页眉内容"
    document.sections[0].footer.paragraphs[0].text = "页脚内容"
    document.add_paragraph("正文内容")
    document.save(path)

    parsed = parse(path)

    assert [block.text for block in parsed.blocks] == ["正文内容"]
