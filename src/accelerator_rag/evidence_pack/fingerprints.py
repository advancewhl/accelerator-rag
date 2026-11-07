"""Content digests pinned into every replayable phase-3 report."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "tmp" / "research-rc3"
QUESTIONS = ROOT / "data" / "evaluation" / "research-benchmark-300-v1"
ALLOWED_SPLITS = ("dev", "val")


def _file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=8)
def facts_digest(path: str | Path) -> str:
    return _file_sha256(path)


@lru_cache(maxsize=4)
def questions_digest(split: str) -> str:
    if split not in ALLOWED_SPLITS:
        raise ValueError(f"split not allowed in phase 3: {split}")
    return _file_sha256(QUESTIONS / split / "questions.json")


@lru_cache(maxsize=4)
def corpus_digest(splits: tuple[str, ...] = ALLOWED_SPLITS) -> str:
    for split in splits:
        if split not in ALLOWED_SPLITS:
            raise ValueError(f"split not allowed in phase 3: {split}")
    inventories = BASE / "inventory"
    families_path = inventories / "families.json"
    digest = hashlib.sha256()
    for name in ("families.json", "revisions.json"):
        digest.update(name.encode())
        digest.update(bytes.fromhex(_file_sha256(inventories / name)))
    families = json.loads(families_path.read_text(encoding="utf-8"))
    family_ids = set()
    for split in splits:
        payload = json.loads(
            (QUESTIONS / split / "questions.json").read_text(encoding="utf-8")
        )
        for item in payload["items"]:
            family_ids.update(item["family_ids"])
    revision_ids = sorted(
        {
            revision_id
            for family_id in family_ids
            for revision_id in families[family_id]["revision_ids"]
        }
    )
    for revision_id in revision_ids:
        digest.update(revision_id.encode())
        digest.update(
            bytes.fromhex(_file_sha256(BASE / "chunks" / f"{revision_id}.json"))
        )
        parsed = BASE / "parsed" / f"{revision_id}.json"
        if parsed.exists():
            digest.update(b"parsed")
            digest.update(bytes.fromhex(_file_sha256(parsed)))
    return digest.hexdigest()
