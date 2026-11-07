"""Normalize an MCP-exported Archiver JSON into read-only evidence atoms.

Usage:
  python3 scripts/research/ingest_archiver.py --export reports/research-reset-20261107/archiver-probes.json
  python3 scripts/research/ingest_archiver.py --export probe.json --question S1-DEV-001 --out /tmp/atoms.json

The script never connects to an Archiver; it consumes a JSON document exported
by the MCP tools.  Downsampled/truncated flags and segment warnings are kept
with every observation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.evidence_pack.archiver import (  # noqa: E402
    atoms_for_needs,
    load_export,
)
from accelerator_rag.evidence_pack.needs import parse_needs  # noqa: E402
from accelerator_rag.facts.corpus import split_questions  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", required=True)
    parser.add_argument("--question", default="", help="dev/val base_id")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    export = load_export(args.export)
    payload = {
        "schema_version": "phase3-archiver-ingest-v1",
        "captured_on": export.captured_on,
        "timezone": export.timezone,
        "capabilities": export.capabilities,
        "health": export.health,
        "observations": [item.to_dict() for item in export.observations],
        "atoms": [],
    }
    if args.question:
        questions = {
            item["base_id"]: item for item in split_questions(("dev", "val"))
        }
        if args.question not in questions:
            raise SystemExit(f"question not found in dev/val: {args.question}")
        atoms = atoms_for_needs(export, parse_needs(questions[args.question]))
        payload["atoms"] = [atom.to_dict() for atom in atoms]
    text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
