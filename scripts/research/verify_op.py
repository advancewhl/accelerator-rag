"""Run one deterministic operator from this worktree without installing it.

Usage:
  python3 scripts/research/verify_op.py --op port_range_membership \
      --request /tmp/req.json
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.verify.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
