"""Conservative index policy; all chunks remain available to corpus auditing."""

from collections import Counter
from dataclasses import dataclass, asdict
import re
from accelerator_rag.domain.knowledge import KnowledgeChunk


@dataclass(frozen=True)
class EligibilityConfig:
    # Corpus has formula-damaged spans; reject only predominantly unreadable
    # chunks, not occasional damaged formulas surrounded by usable prose.
    replacement_ratio: float = 0.20
    minimum_replacements: int = 8

    def __post_init__(self):
        if not 0 < self.replacement_ratio <= 1 or self.minimum_replacements < 1:
            raise ValueError("invalid replacement eligibility configuration")


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reasons: tuple[str, ...]
    effective_characters: int
    effective_tokens: int
    replacement_ratio: float


def assess_retrieval_eligibility(
    chunk: KnowledgeChunk, config=EligibilityConfig()
) -> EligibilityResult:
    text = chunk.text.strip()
    compact = re.sub(r"\s+", "", text).casefold()
    effective = sum(c.isalnum() for c in text)
    tokens = len(
        re.findall(r"[A-Za-z]+[A-Za-z0-9]*|\d+(?:\.\d+)?|[\u3400-\u9fff]", text)
    )
    ratio = text.count("\ufffd") / max(1, len(re.sub(r"\s", "", text)))
    reasons = []
    if compact in {
        "谢谢",
        "谢谢!",
        "谢谢！",
        "thankyou",
        "thankyou!",
        "thanks",
        "acknowledgements",
        "致谢",
    }:
        reasons.append("boilerplate_only")
    elif re.fullmatch(r"\d+|[A-Z]{1,8}\d{1,8}", text):
        reasons.append("number_or_running_code_only")
    elif (
        compact == re.sub(r"\s+", "", chunk.document_title).casefold()
        and tokens >= 3
        and not any(c.isdigit() for c in text)
    ):
        reasons.append("document_title_only")
    elif not effective:
        reasons.append("too_little_semantic_content")
    if (
        text.count("\ufffd") >= config.minimum_replacements
        and ratio >= config.replacement_ratio
    ):
        reasons.append("mostly_replacement_chars")
    return EligibilityResult(not reasons, tuple(reasons), effective, tokens, ratio)


def eligibility_audit(chunks, config=EligibilityConfig()):
    assessed = [(c, assess_retrieval_eligibility(c, config)) for c in chunks]
    bad = [(c, a) for c, a in assessed if not a.eligible]
    return [c for c, a in assessed if a.eligible], {
        "config": asdict(config),
        "total_chunks": len(chunks),
        "eligible_chunks": len(chunks) - len(bad),
        "ineligible_chunks": len(bad),
        "ineligible_by_reason": dict(Counter(r for _, a in bad for r in a.reasons)),
        "per_document_ineligible": dict(Counter(c.document_id for c, _ in bad)),
        "examples": [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "page": c.page_start,
                "text": c.text,
                **asdict(a),
            }
            for c, a in bad
        ],
    }
