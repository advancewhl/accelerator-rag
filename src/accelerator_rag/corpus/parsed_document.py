from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ParsedUnit:
    """An ordered content unit extracted from a source document."""

    index: int
    unit_type: str
    text: str
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedDocument:
    """Format-independent representation of a parsed document."""

    source_path: str
    file_name: str
    document_type: str
    units: list[ParsedUnit]
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)