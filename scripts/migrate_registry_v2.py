#!/usr/bin/env python3
"""Build the Schema v2 registry from the frozen v1 registries.

This is a governance-build command, not a runtime command.  It never rewrites
the v1 registry and never claims that a legacy ``active`` document is current:
only documents with an explicit system/verification scope become ``current``;
all other legacy records become ``reference`` with ``approval_status=unknown``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.corpus.registry import load_registry  # noqa: E402
from accelerator_rag.corpus.schema_v2 import (  # noqa: E402
    from_legacy_records,
    write_registry_v2,
)


DEFAULT_OUTPUT = ROOT / "data/documents/v2/registry-v2.legacy-baseline.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT,
        help="repository root containing data/documents",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Schema v2 registry output path",
    )
    parser.add_argument(
        "--generated-on",
        default="2026-11-02",
        help="governance generation date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--release-target",
        default="kb-2.0.0",
        help="knowledge-base release target",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    records = []
    for name in ("registry.json", "registry-md.json"):
        path = project_root / "data/documents" / name
        if not path.is_file():
            raise SystemExit(f"missing legacy registry: {path}")
        records.extend(load_registry(path))
    if not records:
        raise SystemExit("legacy registries contain no records")
    registry = from_legacy_records(
        records,
        generated_on=args.generated_on,
        release_target=args.release_target,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_registry_v2(registry, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output.relative_to(project_root)),
                **registry.summary(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
