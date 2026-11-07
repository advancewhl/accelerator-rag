"""Run one deterministic verification operator on a JSON request.

Usage:
  python -m accelerator_rag.verify.cli --op port_range_membership \
      --request /tmp/req.json

The response envelope (DESIGN §5) is printed as JSON.  Exit codes: 0 for any
executed operator (``ok`` or ``refused`` — inspect ``status``), 2 for usage
errors, an unknown operator or an unreadable request file, 1 for an unexpected
internal failure (reported as JSON, never as a traceback).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .operators import OP_NAMES, OPERATORS, run_operator


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=1))


def _error(op: str, code: str, message: str) -> dict:
    return {
        "op": op,
        "status": "refused",
        "value": {},
        "trace": [],
        "assumptions": [],
        "refusal": {"code": code, "message": message},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--op", required=True, help="operator name")
    parser.add_argument(
        "--request", required=True, help="path to a JSON request file"
    )
    args = parser.parse_args(argv)

    if args.op not in OPERATORS:
        _emit(
            _error(
                args.op,
                "UNKNOWN_OPERATOR",
                f"unknown operator: {args.op!r}; known: "
                f"{', '.join(OP_NAMES)}",
            )
        )
        return 2

    try:
        text = Path(args.request).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        _emit(
            _error(
                args.op,
                "BAD_REQUEST_FILE",
                f"cannot read request file {args.request!r}: {exc}",
            )
        )
        return 2
    try:
        # ``ValueError`` also covers json.JSONDecodeError and the interpreter's
        # integer-digit limit; ``RecursionError`` covers pathological nesting.
        request = json.loads(text)
    except (ValueError, RecursionError) as exc:
        _emit(
            _error(
                args.op,
                "BAD_REQUEST_JSON",
                f"request file is not valid JSON: {exc}",
            )
        )
        return 2

    try:
        response = run_operator(args.op, request)
    except Exception as exc:  # noqa: BLE001 - emit JSON, never a traceback
        _emit(
            _error(
                args.op,
                "INTERNAL_ERROR",
                f"{type(exc).__name__}: {exc}",
            )
        )
        return 1
    _emit(response)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
