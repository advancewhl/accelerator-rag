"""Build phase-2 fact layers from the frozen rc.3 snapshot.

Usage:
  python3 scripts/research/build_facts.py --splits dev,val --out data/facts
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.facts.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
