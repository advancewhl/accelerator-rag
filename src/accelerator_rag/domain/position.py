"""Position and block types shared by evidence and parsing contracts.

These enums live in the domain layer so ``KnowledgeChunk`` does not depend on
the corpus package.  Schema v2 re-exports them for registry validation.
"""

from enum import Enum


class PositionKind(str, Enum):
    PDF_PAGE = "pdf_page"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    SLIDE = "slide"
    CELL_RANGE = "cell_range"
    LINE_RANGE = "line_range"


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CODE = "code"
    FORMULA = "formula"
    CAPTION = "caption"
    IMAGE = "image"
    NOTE = "note"
