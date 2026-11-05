"""Focused OMML-to-LaTeX conversion for Word equations.

Only structures that can be represented reliably are converted.  Unsupported
constructs fall back to the caller's original text/placeholder; this module
never invents an equation from OCR or from damaged markup.
"""

from __future__ import annotations

import re

_MATH_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


class OMMLConversionError(ValueError):
    """The equation has no convertible structure or text."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child(node, name: str):
    if node is None:
        return None
    return next(
        (
            child
            for child in node
            if str(child.tag).startswith(_MATH_NS) and _local(child.tag) == name
        ),
        None,
    )


def _children(node, name: str):
    if node is None:
        return []
    return [
        child
        for child in node
        if str(child.tag).startswith(_MATH_NS) and _local(child.tag) == name
    ]


def _attr(node, name: str, default: str = "") -> str:
    if node is None:
        return default
    for key, value in node.attrib.items():
        if _local(key) == name:
            return value
    return default


def _hidden(parent, name: str) -> bool:
    """Read ``m:supHide``/``m:subHide``/``m:degHide`` child elements."""

    marker = _child(parent, name)
    return marker is not None and _attr(marker, "val", "0") == "1"


_LATEX_ESCAPES = {
    "\\": r"\backslash ",
    "{": r"\{",
    "}": r"\}",
    "_": r"\_",
    "^": r"\^{}",
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "$": r"\$",
}
_UNICODE_COMMANDS = {
    "−": "-",
    "×": r"\times ",
    "÷": r"\div ",
    "≤": r"\leq ",
    "≥": r"\geq ",
    "≠": r"\neq ",
    "≈": r"\approx ",
    "∼": r"\sim ",
    "≡": r"\equiv ",
    "∞": r"\infty ",
    "±": r"\pm ",
    "·": r"\cdot ",
    "→": r"\to ",
    "∈": r"\in ",
    "∝": r"\propto ",
    "∂": r"\partial ",
}


def _escape(text: str) -> str:
    """Escape source characters first, then map Unicode operators to commands."""

    escaped = "".join(_LATEX_ESCAPES.get(char, char) for char in text)
    if re.search(r"[㐀-鿿]", text):
        # Commands such as \times are not valid inside \text{}; keep the
        # original symbols in text mode instead.
        return r"\text{" + escaped + "}"
    for source, command in _UNICODE_COMMANDS.items():
        escaped = escaped.replace(source, command)
    return escaped


def _run_text(node) -> str:
    parts = [
        child.text
        for child in node.iter()
        if str(child.tag) == _MATH_NS + "t" and child.text
    ]
    return _escape("".join(parts))


def _join(node) -> str:
    if node is None:
        return ""
    return "".join(_convert(child) for child in node)


def _required(node, name: str):
    child = _child(node, name)
    if child is None:
        raise OMMLConversionError(f"missing required OMML child: {name}")
    return child


_DELIMITERS = {
    "(": "(",
    ")": ")",
    "[": "[",
    "]": "]",
    "|": "|",
    "{": r"\{",
    "}": r"\}",
    "⟨": r"\langle",
    "⟩": r"\rangle",
    "": ".",
}


def _delimiter(value: str) -> str:
    if value in _DELIMITERS:
        return _DELIMITERS[value]
    raise OMMLConversionError(f"unsupported delimiter: {value}")


def _convert(node) -> str:
    if not str(node.tag).startswith(_MATH_NS):
        return _run_text(node)
    name = _local(node.tag)
    if name == "oMathPara":
        equations = [_convert(child) for child in _children(node, "oMath")]
        return r"\quad ".join(equations) if equations else _join(node)
    if name in {"oMath", "e", "num", "den", "sub", "sup", "deg", "lim", "fName"}:
        return _join(node)
    if name == "t":
        return _escape(node.text or "")
    if name == "r":
        return _run_text(node)
    if name in {"rPr", "ctrlPr", "argPr", "naryPr", "dPr", "accPr", "barPr", "groupChrPr", "funcPr", "limLowPr", "limUppPr", "sSupPr", "sSubPr", "sSubSupPr", "fPr", "radPr", "eqArrPr", "mPr", "sPrePr", "oMathParaPr", "oMathPr", "boxPr", "borderBoxPr", "phantPr"}:
        return ""
    if name == "f":
        numerator = _required(node, "num")
        denominator = _required(node, "den")
        return (
            r"\frac{" + _join(numerator) + "}{" + _join(denominator) + "}"
        )
    if name == "sSup":
        base = _required(node, "e")
        sup = _required(node, "sup")
        hidden = _hidden(_child(node, "sSupPr"), "supHide")
        if hidden:
            return "{" + _join(base) + "}"
        return "{" + _join(base) + "}^{" + _join(sup) + "}"
    if name == "sSub":
        base = _required(node, "e")
        sub = _required(node, "sub")
        hidden = _hidden(_child(node, "sSubPr"), "subHide")
        if hidden:
            return "{" + _join(base) + "}"
        return "{" + _join(base) + "}_{" + _join(sub) + "}"
    if name == "sSubSup":
        base = _required(node, "e")
        sub = _required(node, "sub")
        sup = _required(node, "sup")
        props = _child(node, "sSubSupPr")
        sub_hide = _hidden(props, "subHide")
        sup_hide = _hidden(props, "supHide")
        if sub_hide and sup_hide:
            return "{" + _join(base) + "}"
        if sub_hide:
            return "{" + _join(base) + "}^{" + _join(sup) + "}"
        if sup_hide:
            return "{" + _join(base) + "}_{" + _join(sub) + "}"
        return (
            "{" + _join(base) + "}_{" + _join(sub) + "}^{" + _join(sup) + "}"
        )
    if name == "sPre":
        sub = _required(node, "sub")
        sup = _required(node, "sup")
        base = _required(node, "e")
        return (
            "{}_{" + _join(sub) + "}^{" + _join(sup) + "}" + "{" + _join(base) + "}"
        )
    if name == "rad":
        degree = _child(node, "deg")
        base = _required(node, "e")
        hidden = _hidden(_child(node, "radPr"), "degHide")
        degree_text = "" if hidden else _join(degree)
        if degree_text:
            return r"\sqrt[" + degree_text + "]{" + _join(base) + "}"
        return r"\sqrt{" + _join(base) + "}"
    if name == "nary":
        operator = _attr(
            _child(_child(node, "naryPr"), "chr"), "val", "∫"
        )
        commands = {
            "∑": r"\sum",
            "∏": r"\prod",
            "∫": r"\int",
            "∮": r"\oint",
            "⋃": r"\bigcup",
            "⋂": r"\bigcap",
        }
        if operator not in commands:
            raise OMMLConversionError(f"unsupported n-ary operator: {operator}")
        props = _child(node, "naryPr")
        sub_hide = _hidden(props, "subHide")
        sup_hide = _hidden(props, "supHide")
        sub = _child(node, "sub")
        sup = _child(node, "sup")
        base = _required(node, "e")
        text = commands[operator]
        if sub is not None and not sub_hide and _join(sub):
            text += "_{" + _join(sub) + "}"
        if sup is not None and not sup_hide and _join(sup):
            text += "^{" + _join(sup) + "}"
        return text + "{" + _join(base) + "}"
    if name == "d":
        props = _child(node, "dPr")
        begin = _delimiter(_attr(_child(props, "begChr"), "val", "("))
        end = _delimiter(_attr(_child(props, "endChr"), "val", ")"))
        separator = _attr(_child(props, "sepChr"), "val", "")
        bodies = [_join(body) for body in _children(node, "e")]
        if not bodies:
            raise OMMLConversionError("delimiter has no body")
        joined = (separator or ",").join(bodies)
        return r"\left" + begin + joined + r"\right" + end
    if name == "eqArr":
        rows = [_join(body) for body in _children(node, "e")]
        return r"\begin{aligned}" + r" \\ ".join(rows) + r"\end{aligned}"
    if name == "m":
        rows = []
        for row in _children(node, "mr"):
            cells = [_join(cell) for cell in _children(row, "e")]
            rows.append(" & ".join(cells))
        return r"\begin{matrix}" + r" \\ ".join(rows) + r"\end{matrix}"
    if name == "func":
        function = _join(_required(node, "fName"))
        base = _join(_required(node, "e"))
        return "{" + function + "}(" + base + ")"
    if name == "acc":
        accent = _attr(_child(_child(node, "accPr"), "chr"), "val", "̂")
        mapping = {
            "̂": r"\hat",
            "̄": r"\bar",
            "→": r"\vec",
            "̇": r"\dot",
            "̈": r"\ddot",
            "̃": r"\tilde",
        }
        if accent not in mapping:
            raise OMMLConversionError(f"unsupported accent: {accent}")
        return mapping[accent] + "{" + _join(_required(node, "e")) + "}"
    if name == "bar":
        pos = _attr(_child(_child(node, "barPr"), "pos"), "val", "top")
        if pos not in {"top", "bot"}:
            raise OMMLConversionError(f"unsupported bar position: {pos}")
        command = r"\underline" if pos == "bot" else r"\overline"
        return command + "{" + _join(_required(node, "e")) + "}"
    if name == "groupChr":
        props = _child(node, "groupChrPr")
        char = _attr(_child(props, "chr"), "val", "⏟")
        pos = _attr(_child(props, "pos"), "val", "bot")
        if (char, pos) == ("⏞", "top"):
            command = r"\overbrace"
        elif (char, pos) == ("⏟", "bot"):
            command = r"\underbrace"
        else:
            raise OMMLConversionError(
                f"unsupported group character: {char}/{pos}"
            )
        return command + "{" + _join(_required(node, "e")) + "}"
    if name == "limLow":
        base = _join(_required(node, "e"))
        limit = _join(_required(node, "lim"))
        return r"\underset{" + limit + "}{" + base + "}"
    if name == "limUpp":
        base = _join(_required(node, "e"))
        limit = _join(_required(node, "lim"))
        return r"\overset{" + limit + "}{" + base + "}"
    if name in {"box", "borderBox", "phant"}:
        base = _child(node, "e")
        inner = _join(base) if base is not None else _join(node)
        return r"\boxed{" + inner + "}" if name != "phant" else inner
    # Never turn an unknown construct into plausible-looking LaTeX.
    raise OMMLConversionError(f"unsupported OMML element: {name}")


def omml_paragraph_latex(element) -> tuple[str, bool]:
    """Convert every equation in a Word paragraph in place.

    Returns ``(text, all_converted)``.  Word runs outside equations are kept in
    order, so a paragraph containing prose and one or more formulas no longer
    collapses to the first formula.
    """

    word_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    parts = []
    converted = False
    for child in element:
        tag = str(child.tag)
        name = _local(tag)
        if tag.startswith(_MATH_NS) and name in {"oMath", "oMathPara"}:
            try:
                parts.append(r"\(" + omml_to_latex(child) + r"\)")
                converted = True
            except OMMLConversionError:
                return "", False
            continue
        if tag.startswith(word_ns) and name not in {
            "pPr",
            "bookmarkStart",
            "bookmarkEnd",
            "proofErr",
            "commentRangeStart",
            "commentRangeEnd",
            "commentReference",
        }:
            text = "".join(
                item.text
                for item in child.iter()
                if str(item.tag) == word_ns + "t" and item.text
            )
            if text.strip():
                parts.append(text)
    text = " ".join(parts).strip()
    return text, converted and bool(text)


def omml_to_latex(element) -> str:
    """Convert one ``m:oMath``/``m:oMathPara`` subtree to bare LaTeX."""

    math = element
    if _local(math.tag) not in {"oMath", "oMathPara"}:
        math = next(
            (
                child
                for child in element.iter()
                if str(child.tag).startswith(_MATH_NS)
                and _local(child.tag) in {"oMath", "oMathPara"}
            ),
            None,
        )
    if math is None:
        raise OMMLConversionError("no OMML math element")
    latex = _convert(math).strip()
    if not latex or not re.search(r"[A-Za-z0-9㐀-鿿\\]", latex):
        raise OMMLConversionError("OMML produced no usable LaTeX")
    return latex
