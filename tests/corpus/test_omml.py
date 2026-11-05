"""OMML conversion keeps common equation structure and never guesses."""

from docx import Document
from docx.oxml import parse_xml
import pytest

from accelerator_rag.corpus.docx_parser import parse_docx
from accelerator_rag.corpus.omml import OMMLConversionError, omml_to_latex


M = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def math(body):
    return parse_xml(f"<m:oMath {M} {W}>{body}</m:oMath>")


def test_fraction_subscript_and_superscript():
    element = math(
        "<m:f><m:num><m:r><m:t>a</m:t></m:r></m:num>"
        "<m:den><m:r><m:t>b</m:t></m:r></m:den></m:f>"
        "<m:sSub><m:e><m:r><m:t>x</m:t></m:r></m:e>"
        "<m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub>"
        "<m:sSup><m:e><m:r><m:t>y</m:t></m:r></m:e>"
        "<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>"
    )
    latex = omml_to_latex(element)

    assert r"\frac{a}{b}" in latex
    assert "{x}_{i}" in latex
    assert "{y}^{2}" in latex


def test_radical_nary_and_delimiters():
    element = math(
        "<m:rad><m:deg><m:r><m:t>3</m:t></m:r></m:deg>"
        "<m:e><m:r><m:t>x</m:t></m:r></m:e></m:rad>"
        "<m:nary><m:naryPr><m:chr m:val=\"∑\"/></m:naryPr>"
        "<m:sub><m:r><m:t>i</m:t></m:r></m:sub>"
        "<m:sup><m:r><m:t>n</m:t></m:r></m:sup>"
        "<m:e><m:r><m:t>a</m:t></m:r></m:e></m:nary>"
        "<m:d><m:dPr><m:begChr m:val=\"[\"/><m:endChr m:val=\"]\"/></m:dPr>"
        "<m:e><m:r><m:t>z</m:t></m:r></m:e></m:d>"
    )
    latex = omml_to_latex(element)

    assert r"\sqrt[3]{x}" in latex
    assert r"\sum_{i}^{n}{a}" in latex
    assert r"\left[z\right]" in latex


def test_cjk_text_is_kept_in_text_mode():
    element = math("<m:r><m:t>增益</m:t></m:r>")

    assert omml_to_latex(element) == r"\text{增益}"


def test_unknown_math_construct_is_not_guessed():
    with pytest.raises(OMMLConversionError, match="unsupported"):
        omml_to_latex(math("<m:unknown><m:r><m:t>x</m:t></m:r></m:unknown>"))


def test_non_math_element_is_rejected():
    with pytest.raises(OMMLConversionError):
        omml_to_latex(parse_xml(f"<w:p {W}/>"))


def test_docx_formula_block_carries_latex_and_status(tmp_path):
    path = tmp_path / "formula.docx"
    document = Document()
    paragraph = document.add_paragraph()
    paragraph._p.append(
        math(
            "<m:f><m:num><m:r><m:t>P</m:t></m:r></m:num>"
            "<m:den><m:r><m:t>Q</m:t></m:r></m:den></m:f>"
        )
    )
    document.save(path)

    parsed = parse_docx(
        path,
        revision_id="formula-rev",
        source_path="data/l0_raw/incoming/batch/formula.docx",
    )
    block = next(item for item in parsed.blocks if item.block_type == "formula")
    metadata = dict(block.metadata)

    assert block.text == r"\(\frac{P}{Q}\)"
    assert metadata["latex_status"] == "latex"
    assert metadata["latex_source"] == "omml"


def test_unicode_operators_are_not_double_escaped():
    element = math("<m:r><m:t>a×b≤c</m:t></m:r>")
    latex = omml_to_latex(element)

    assert r"\times" in latex
    assert r"\leq" in latex
    assert r"\backslash" not in latex


def test_text_mode_escapes_latex_specials():
    element = math("<m:r><m:t>效率95%</m:t></m:r>")

    assert omml_to_latex(element) == r"\text{效率95\%}"


def test_malformed_fraction_is_rejected_instead_of_crashing():
    with pytest.raises(OMMLConversionError, match="den"):
        omml_to_latex(math("<m:f><m:num><m:r><m:t>a</m:t></m:r></m:num></m:f>"))


def test_unknown_nary_operator_is_rejected():
    with pytest.raises(OMMLConversionError, match="n-ary"):
        omml_to_latex(
            math(
                '<m:nary><m:naryPr><m:chr m:val="%"/></m:naryPr>'
                "<m:e><m:r><m:t>a</m:t></m:r></m:e></m:nary>"
            )
        )


def test_braces_in_delimiters_are_escaped():
    element = math(
        '<m:d><m:dPr><m:begChr m:val="{"/><m:endChr m:val="}"/></m:dPr>'
        "<m:e><m:r><m:t>x</m:t></m:r></m:e></m:d>"
    )

    assert omml_to_latex(element) == r"\left\{x\right\}"


def test_paragraph_keeps_prose_and_every_formula(tmp_path):
    path = tmp_path / "multi.docx"
    document = Document()
    paragraph = document.add_paragraph("当增益 G 大于阈值时：")
    paragraph._p.append(
        math("<m:f><m:num><m:r><m:t>G</m:t></m:r></m:num>"
             "<m:den><m:r><m:t>Gmax</m:t></m:r></m:den></m:f>")
    )
    paragraph._p.append(
        math("<m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e>"
             "<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>")
    )
    document.save(path)

    parsed = parse_docx(
        path,
        revision_id="multi-formula-rev",
        source_path="data/l0_raw/incoming/batch/multi.docx",
    )
    formula = next(
        block for block in parsed.blocks if block.block_type == "formula"
    )

    assert "当增益" in formula.text
    assert formula.text.count(r"\(") == 2
    assert r"\frac{G}{Gmax}" in formula.text
    assert "{x}^{2}" in formula.text
    assert dict(formula.metadata)["latex_status"] == "latex"


def test_hide_markers_are_child_elements():
    sup = math(
        "<m:sSup><m:sSupPr><m:supHide m:val=\"1\"/></m:sSupPr>"
        "<m:e><m:r><m:t>x</m:t></m:r></m:e>"
        "<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>"
    )
    rad = math(
        "<m:rad><m:radPr><m:degHide m:val=\"1\"/></m:radPr>"
        "<m:deg><m:r><m:t>3</m:t></m:r></m:deg>"
        "<m:e><m:r><m:t>x</m:t></m:r></m:e></m:rad>"
    )

    assert omml_to_latex(sup) == "{x}"
    assert omml_to_latex(rad) == r"\sqrt{x}"
