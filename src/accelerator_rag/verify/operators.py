"""Deterministic verification operators (research plan §4.3).

Six pure functions over caller-supplied JSON structures:

``exact_join``, ``port_range_membership``, ``set_enumeration``,
``unit_convert``, ``boundary_compare``, ``version_diff``.

Every operator returns the phase-2 envelope required by DESIGN §5::

    {"op": str,
     "status": "ok" | "refused",
     "value": dict,
     "trace": list,
     "assumptions": list,
     "refusal": None | {"code": str, "message": str}}

The module has no network, model, clock or filesystem dependency and does not
import the ``facts`` package; requests and responses are plain JSON values.
Comparison may normalise text (NFKC + casefold + strip), but every reported
value stays exactly as the caller supplied it.  Operators never assume a unit,
a range or an object identity: unknown or conflicting input is refused with an
explicit code.

Public API
----------
``OPERATORS``          mapping of operator name to function.
``run_operator(name, request)``
                       dispatch entry point.  Raises ``KeyError`` for an
                       unknown operator (the CLI turns that into exit code 2).
                       It never mutates ``request`` and repeated calls with
                       equal requests return equal responses.

Data units: ``B``/``KB``/``MB``/``GB`` are decimal SI units (powers of 1000).
Binary units (``KiB``/``MiB``/``GiB``) are not part of this contract and are
refused as unknown.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
import re
import unicodedata

# ---------------------------------------------------------------------------
# response envelope
# ---------------------------------------------------------------------------

STATUS_OK = "ok"
STATUS_REFUSED = "refused"

OP_NAMES = (
    "exact_join",
    "port_range_membership",
    "set_enumeration",
    "unit_convert",
    "boundary_compare",
    "version_diff",
)

# Decimal context used only when a conversion is not exactly representable.
DECIMAL_PRECISION = 28


class _Refused(Exception):
    """Internal signal: the request cannot be answered deterministically."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _refuse(code: str, message: str) -> None:
    raise _Refused(code, message)


def _envelope(
    op: str,
    status: str,
    value: dict,
    trace: list,
    assumptions: list,
    refusal: dict | None,
) -> dict:
    return {
        "op": op,
        "status": status,
        "value": value,
        "trace": trace,
        "assumptions": assumptions,
        "refusal": refusal,
    }


def _caller_assumptions(request: Mapping) -> tuple[list, dict | None]:
    """Only assumptions explicitly supplied by the caller are echoed."""

    raw = request.get("assumptions")
    if raw is None:
        return [], None
    if not isinstance(raw, (list, tuple)):
        return [], {
            "code": "BAD_REQUEST",
            "message": "assumptions must be a list of strings",
        }
    if any(not isinstance(item, str) for item in raw):
        return [], {
            "code": "BAD_REQUEST",
            "message": "assumptions must be a list of strings",
        }
    return list(raw), None


def _execute(op: str, request: object, body) -> dict:
    if not isinstance(request, Mapping):
        return _envelope(
            op,
            STATUS_REFUSED,
            {},
            [],
            [],
            {"code": "BAD_REQUEST", "message": "request must be a JSON object"},
        )
    assumptions, problem = _caller_assumptions(request)
    if problem is not None:
        return _envelope(op, STATUS_REFUSED, {}, [], [], problem)
    trace: list = []
    try:
        value = body(request, trace)
    except _Refused as exc:
        return _envelope(
            op,
            STATUS_REFUSED,
            {},
            trace,
            assumptions,
            {"code": exc.code, "message": exc.message},
        )
    return _envelope(op, STATUS_OK, value, trace, assumptions, None)


# ---------------------------------------------------------------------------
# shared text / number helpers
# ---------------------------------------------------------------------------


def _compare_text(value: str) -> str:
    """Normalisation used only for comparison; original values are kept."""

    return unicodedata.normalize("NFKC", value).casefold().strip()


def _json_scalar(value: object) -> object:
    """Make a scalar echo JSON-serialisable without changing its meaning."""

    if isinstance(value, Decimal):
        return _decimal_text(value)
    return value


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _decimal_from_scalar(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        _refuse("BAD_REQUEST", f"{field} must be a number, not a boolean")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            _refuse("BAD_REQUEST", f"{field} must be finite")
        result = Decimal(str(value))
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip())
        except InvalidOperation:
            _refuse(
                "BAD_REQUEST",
                f"{field} is not a decimal number: {value!r}",
            )
    else:
        _refuse(
            "BAD_REQUEST",
            f"{field} must be a number or numeric string, "
            f"got {type(value).__name__}",
        )
    if not result.is_finite():
        _refuse("BAD_REQUEST", f"{field} must be finite")
    return result


def _fraction_to_decimal(value: Fraction) -> Decimal | None:
    """Exact decimal for terminating fractions, ``None`` otherwise."""

    denominator = value.denominator
    twos = 0
    fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        return None
    scale = max(twos, fives)
    scaled = value.numerator * (10**scale) // value.denominator
    return Decimal(scaled).scaleb(-scale)


def _fraction_text(value: Fraction) -> str:
    exact = _fraction_to_decimal(value)
    if exact is not None:
        return _decimal_text(exact)
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        rounded = Decimal(value.numerator) / Decimal(value.denominator)
    return _decimal_text(rounded)


# ---------------------------------------------------------------------------
# 1. exact_join
# ---------------------------------------------------------------------------


def exact_join(request: Mapping) -> dict:
    """Join two record sets on explicit keys and scopes.

    Request: ``{"left": [record], "right": [record], "join_keys": [name],
    "scope_keys": [name]?}`` where a record is
    ``{"id", "keys": {}, "scope": {}, "payload": {}}``.  Keys compare after
    NFKC + casefold + strip; reported values keep the caller's original text.

    Without ``scope_keys``, every join-key value on either side must resolve
    to exactly one non-empty scope across all records that carry it, otherwise
    the whole request is refused with ``AMBIGUOUS_SCOPE``.  With ``scope_keys``
    the scope values join the key tuple; records missing any scope key are
    reported as unmatched instead of being guessed.
    """

    return _execute("exact_join", request, _exact_join_body)


def _join_records(request: Mapping, field: str) -> list[dict]:
    records = request.get(field)
    if not isinstance(records, list):
        _refuse("BAD_REQUEST", f"{field} must be a list of records")
    cleaned = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            _refuse("BAD_REQUEST", f"{field}[{index}] must be an object")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            _refuse(
                "BAD_REQUEST",
                f"{field}[{index}].id must be a non-empty string",
            )
        if record_id in seen_ids:
            _refuse(
                "DUPLICATE_RECORD_ID",
                f"{field} repeats record id {record_id!r}",
            )
        seen_ids.add(record_id)
        keys = record.get("keys")
        if not isinstance(keys, Mapping):
            _refuse("BAD_REQUEST", f"{field}[{index}].keys must be an object")
        scope = record.get("scope")
        if scope is None:
            scope = {}
        if not isinstance(scope, Mapping):
            _refuse("BAD_REQUEST", f"{field}[{index}].scope must be an object")
        for name, value in scope.items():
            if not isinstance(name, str) or not isinstance(value, str):
                _refuse(
                    "BAD_REQUEST",
                    f"{field}[{index}].scope must map strings to strings",
                )
        cleaned.append(
            {
                "id": record_id,
                "keys": dict(keys),
                "scope": dict(scope),
                "payload": record.get("payload", {}),
            }
        )
    return cleaned


def _name_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        _refuse("BAD_REQUEST", f"{field} must be a non-empty list")
    names = []
    for item in value:
        if not isinstance(item, str) or not item:
            _refuse("BAD_REQUEST", f"{field} entries must be non-empty strings")
        names.append(item)
    if len(set(names)) != len(names):
        _refuse("BAD_REQUEST", f"{field} contains duplicates")
    return names


def _join_key_values(record: dict, names: list[str]) -> tuple[str, ...] | None:
    """Compare tuple for the join keys, or ``None`` when a key is unusable.

    A key that is absent, or whose normalised form is empty, carries no
    identity and is treated as missing; it must never participate in a match.
    """

    values = []
    for name in names:
        if name not in record["keys"]:
            return None
        raw = record["keys"][name]
        if not isinstance(raw, str):
            _refuse(
                "BAD_REQUEST",
                f"record {record['id']!r} key {name!r} must be a string",
            )
        normalized = _compare_text(raw)
        if not normalized:
            return None
        values.append(normalized)
    return tuple(values)


def _scope_signature(record: dict) -> tuple[tuple[str, str], ...] | None:
    """Scope signature, or ``None`` when the scope is empty or blank."""

    scope = record["scope"]
    if not scope:
        return None
    signature = []
    for name, raw in scope.items():
        if not isinstance(name, str) or not isinstance(raw, str):
            _refuse(
                "BAD_REQUEST",
                f"record {record['id']!r} scope must map strings to strings",
            )
        normalized = _compare_text(raw)
        if not normalized:
            return None
        signature.append((name, normalized))
    return tuple(sorted(signature))


def _key_text(join_keys: list[str], values: tuple[str, ...]) -> dict:
    return dict(zip(join_keys, values))


def _pair_payload(
    left_record: dict,
    right_record: dict,
    join_keys: list[str],
    scope_keys: list[str],
    shared_scope: bool = False,
) -> dict:
    payload = {
        "left_id": left_record["id"],
        "right_id": right_record["id"],
        "join": {
            name: {
                "left": left_record["keys"][name],
                "right": right_record["keys"][name],
            }
            for name in join_keys
        },
        "scope": {
            name: {
                "left": left_record["scope"][name],
                "right": right_record["scope"][name],
            }
            for name in scope_keys
        },
        # Shape stays stable across both scope modes: the raw scopes that the
        # uniform-scope check held identical, or null when scope_keys decided.
        "shared_scope": (
            {
                "left": dict(left_record["scope"]),
                "right": dict(right_record["scope"]),
            }
            if shared_scope
            else None
        ),
    }
    return payload


def _unmatched_payload(record: dict, reason: str) -> dict:
    return {
        "id": record["id"],
        "keys": dict(record["keys"]),
        "scope": dict(record["scope"]),
        "payload": record["payload"],
        "reason": reason,
    }


def _plain_index(
    records: list[dict], join_keys: list[str]
) -> tuple[dict[tuple[str, ...], list[dict]], list[dict]]:
    index: dict[tuple[str, ...], list[dict]] = {}
    missing = []
    for record in records:
        values = _join_key_values(record, join_keys)
        if values is None:
            missing.append(record)
            continue
        index.setdefault(values, []).append(record)
    return index, missing


def _exact_join_body(request: Mapping, trace: list) -> dict:
    left = _join_records(request, "left")
    right = _join_records(request, "right")
    join_keys = _name_list(request.get("join_keys"), "join_keys")
    scope_keys_raw = request.get("scope_keys")
    scope_keys: list[str] | None = None
    if scope_keys_raw is not None:
        scope_keys = _name_list(scope_keys_raw, "scope_keys")
        overlap = set(scope_keys) & set(join_keys)
        if overlap:
            _refuse(
                "BAD_REQUEST",
                f"scope_keys repeats join_keys: {sorted(overlap)}",
            )
    trace.append(
        {
            "step": "validate",
            "join_keys": list(join_keys),
            "scope_keys": None if scope_keys is None else list(scope_keys),
            "left_records": len(left),
            "right_records": len(right),
        }
    )

    if scope_keys is None:
        matched, unmatched_left, unmatched_right = _join_uniform_scope(
            left, right, join_keys, trace
        )
        scope_mode = "identical_scope_required"
    else:
        matched, unmatched_left, unmatched_right = _join_explicit_scope(
            left, right, join_keys, scope_keys, trace
        )
        scope_mode = "explicit_scope_keys"

    return {
        "join_keys": list(join_keys),
        "scope_keys": None if scope_keys is None else list(scope_keys),
        "scope_mode": scope_mode,
        "matched": matched,
        "unmatched_left": unmatched_left,
        "unmatched_right": unmatched_right,
        "counts": {
            "matched": len(matched),
            "unmatched_left": len(unmatched_left),
            "unmatched_right": len(unmatched_right),
        },
    }


def _check_uniform_scopes(
    left: list[dict],
    right: list[dict],
    join_keys: list[str],
    trace: list,
) -> None:
    """Refuse unless every join-key value resolves to a single scope.

    The check covers every record on either side, not only keys that happen to
    have a counterpart: DESIGN §5 says a join-key value that maps to several
    scopes (or has no scope) must be refused when ``scope_keys`` is absent.
    """

    groups: dict[tuple[str, ...], list[dict]] = {}
    for record in left + right:
        key = []
        absent = False
        for name in join_keys:
            if name not in record["keys"]:
                absent = True
                break
            raw = record["keys"][name]
            if not isinstance(raw, str):
                _refuse(
                    "BAD_REQUEST",
                    f"record {record['id']!r} key {name!r} must be a string",
                )
            normalized = _compare_text(raw)
            if not normalized:
                _refuse(
                    "AMBIGUOUS_SCOPE",
                    f"record {record['id']!r} join key {name!r} is blank "
                    "after normalisation; it cannot establish identity",
                )
            key.append(normalized)
        if absent:
            continue
        groups.setdefault(tuple(key), []).append(record)
    for key, group in groups.items():
        signatures: list[tuple] = []
        for record in group:
            signature = _scope_signature(record)
            if signature is None:
                _refuse(
                    "AMBIGUOUS_SCOPE",
                    f"join key {_key_text(join_keys, key)} has a record "
                    "without scope; supply scope_keys to disambiguate",
                )
            signatures.append(signature)
        distinct = set(signatures)
        if len(distinct) > 1:
            _refuse(
                "AMBIGUOUS_SCOPE",
                f"join key {_key_text(join_keys, key)} spans "
                f"{len(distinct)} distinct scopes; supply scope_keys to "
                "disambiguate",
            )
        trace.append(
            {
                "step": "scope_check",
                "join_key": _key_text(join_keys, key),
                "distinct_scopes": len(distinct),
                "scope": dict(distinct.pop()),
            }
        )


def _join_uniform_scope(
    left: list[dict],
    right: list[dict],
    join_keys: list[str],
    trace: list,
) -> tuple[list[dict], list[dict], list[dict]]:
    _check_uniform_scopes(left, right, join_keys, trace)
    left_index, left_missing = _plain_index(left, join_keys)
    right_index, right_missing = _plain_index(right, join_keys)
    if left_missing:
        trace.append(
            {
                "step": "missing_keys",
                "side": "left",
                "ids": [record["id"] for record in left_missing],
            }
        )
    if right_missing:
        trace.append(
            {
                "step": "missing_keys",
                "side": "right",
                "ids": [record["id"] for record in right_missing],
            }
        )

    matched: list[dict] = []
    consumed_left: set[int] = set()
    consumed_right: set[int] = set()
    for key, left_group in left_index.items():
        right_group = right_index.get(key)
        if right_group is None:
            continue
        if len(left_group) > 1 or len(right_group) > 1:
            trace.append(
                {
                    "step": "duplicate_join_key",
                    "join_key": _key_text(join_keys, key),
                    "left": len(left_group),
                    "right": len(right_group),
                }
            )
        for left_record in left_group:
            for right_record in right_group:
                matched.append(
                    _pair_payload(
                        left_record,
                        right_record,
                        join_keys,
                        [],
                        shared_scope=True,
                    )
                )
                consumed_left.add(id(left_record))
                consumed_right.add(id(right_record))

    def reason(record: dict, missing: list[dict]) -> str:
        if any(record is item for item in missing):
            return "missing_join_key"
        return "no_key_match"

    unmatched_left = [
        _unmatched_payload(record, reason(record, left_missing))
        for record in left
        if id(record) not in consumed_left
    ]
    unmatched_right = [
        _unmatched_payload(record, reason(record, right_missing))
        for record in right
        if id(record) not in consumed_right
    ]
    trace.append(
        {
            "step": "match",
            "matched": len(matched),
            "unmatched_left": len(unmatched_left),
            "unmatched_right": len(unmatched_right),
        }
    )
    return matched, unmatched_left, unmatched_right


def _explicit_index(
    records: list[dict],
    join_keys: list[str],
    scope_keys: list[str],
) -> tuple[
    dict[tuple[str, ...], list[tuple[dict, tuple[str, ...]]]],
    list[tuple[dict, str]],
    set[tuple[str, ...]],
]:
    index: dict[tuple[str, ...], list[tuple[dict, tuple[str, ...]]]] = {}
    missing: list[tuple[dict, str]] = []
    join_tuples: set[tuple[str, ...]] = set()
    for record in records:
        join_values = _join_key_values(record, join_keys)
        if join_values is None:
            missing.append((record, "missing_join_key"))
            continue
        join_tuples.add(join_values)
        scope_values = []
        absent = False
        for name in scope_keys:
            if name not in record["scope"]:
                missing.append((record, "missing_scope_key"))
                absent = True
                break
            raw = record["scope"][name]
            if not isinstance(raw, str):
                _refuse(
                    "BAD_REQUEST",
                    f"record {record['id']!r} scope {name!r} must be a string",
                )
            normalized = _compare_text(raw)
            if not normalized:
                missing.append((record, "missing_scope_key"))
                absent = True
                break
            scope_values.append(normalized)
        if absent:
            continue
        key = join_values + tuple(scope_values)
        index.setdefault(key, []).append((record, join_values))
    return index, missing, join_tuples


def _join_explicit_scope(
    left: list[dict],
    right: list[dict],
    join_keys: list[str],
    scope_keys: list[str],
    trace: list,
) -> tuple[list[dict], list[dict], list[dict]]:
    left_index, left_missing, left_joins = _explicit_index(
        left, join_keys, scope_keys
    )
    right_index, right_missing, right_joins = _explicit_index(
        right, join_keys, scope_keys
    )
    for side, missing in (("left", left_missing), ("right", right_missing)):
        if missing:
            trace.append(
                {
                    "step": "missing_keys",
                    "side": side,
                    "entries": [
                        {"id": record["id"], "reason": reason}
                        for record, reason in missing
                    ],
                }
            )

    matched: list[dict] = []
    consumed_left: set[int] = set()
    consumed_right: set[int] = set()
    for key, left_group in left_index.items():
        right_group = right_index.get(key)
        if right_group is None:
            continue
        for left_record, _ in left_group:
            for right_record, _ in right_group:
                matched.append(
                    _pair_payload(
                        left_record, right_record, join_keys, scope_keys
                    )
                )
                consumed_left.add(id(left_record))
                consumed_right.add(id(right_record))

    def reason_for(
        record: dict,
        missing: list[tuple[dict, str]],
        other_joins: set[tuple[str, ...]],
    ) -> str:
        for missing_record, reason in missing:
            if missing_record is record:
                return reason
        join_values = _join_key_values(record, join_keys)
        if join_values is not None and join_values in other_joins:
            return "scope_mismatch"
        return "no_key_match"

    unmatched_left = [
        _unmatched_payload(
            record, reason_for(record, left_missing, right_joins)
        )
        for record in left
        if id(record) not in consumed_left
    ]
    unmatched_right = [
        _unmatched_payload(
            record, reason_for(record, right_missing, left_joins)
        )
        for record in right
        if id(record) not in consumed_right
    ]
    trace.append(
        {
            "step": "match_scope",
            "scope_keys": list(scope_keys),
            "matched": len(matched),
            "unmatched_left": len(unmatched_left),
            "unmatched_right": len(unmatched_right),
        }
    )
    return matched, unmatched_left, unmatched_right


# ---------------------------------------------------------------------------
# 2. port_range_membership
# ---------------------------------------------------------------------------

_PORT_SEPARATORS = ("-", "~", "～", "至", "—")
_ASCII_DIGITS = re.compile(r"\A[0-9]+\Z")


def port_range_membership(request: Mapping) -> dict:
    """Test port membership in a spec list/range, or interval containment.

    Request: ``{"spec": "45-48", "probe": 48}`` or ``{"probe": "17-24"}``.
    Spec and probe accept ``-``, ``~``, ``～``, ``至`` and ``—`` separators,
    full-width digits (NFKC) and comma lists; intervals are closed, so the
    endpoints themselves belong.  A reversed spec range such as ``"48-45"``
    is normalised and flagged ``reversed=true`` in the trace.  Ports are
    treated as integer intervals: a negative value is invalid, but no port
    upper bound (for example 65535) is assumed or enforced.
    """

    return _execute(
        "port_range_membership", request, _port_range_membership_body
    )


def _parse_port_token(
    token: str, code: str, field: str
) -> dict[str, object]:
    token = token.strip()
    if not token:
        _refuse(code, f"{field} contains an empty port")
    parts = [token]
    separator = None
    for candidate in _PORT_SEPARATORS:
        if candidate in token:
            parts = [part.strip() for part in token.split(candidate)]
            separator = candidate
            break
    if separator is not None and len(parts) != 2:
        _refuse(
            code,
            f"{field} range must have exactly two endpoints: {token!r}",
        )
    if not all(_ASCII_DIGITS.match(part) for part in parts):
        _refuse(
            code,
            f"{field} is not an ASCII-digit port or range: {token!r}",
        )
    try:
        values = [int(part) for part in parts]
    except ValueError:
        _refuse(
            code,
            f"{field} number exceeds the integer parsing limit: {token!r}",
        )
    if separator is None:
        port = values[0]
        return {
            "low": port,
            "high": port,
            "raw": token,
            "reversed": False,
            "is_range": False,
        }
    low, high = values
    reversed_flag = low > high
    if reversed_flag:
        low, high = high, low
    return {
        "low": low,
        "high": high,
        "raw": token,
        "reversed": reversed_flag,
        "is_range": True,
    }


def _parse_port_spec(
    spec: object, code: str, field: str
) -> tuple[str, list[dict]]:
    if not isinstance(spec, str):
        _refuse(code, f"{field} must be a string")
    normalized = unicodedata.normalize("NFKC", spec).strip()
    if not normalized:
        _refuse(code, f"{field} must not be empty")
    tokens = [token.strip() for token in normalized.split(",")]
    if any(not token for token in tokens):
        _refuse(code, f"{field} contains an empty element: {spec!r}")
    intervals = [
        _parse_port_token(token, code, f"{field} element") for token in tokens
    ]
    return normalized, intervals


def _parse_port_probe(probe: object) -> dict[str, object]:
    if isinstance(probe, bool):
        _refuse(
            "BAD_PROBE",
            "probe must be a port number or a port range, not a boolean",
        )
    if isinstance(probe, int):
        if probe < 0:
            _refuse("BAD_PROBE", f"probe must be a non-negative port: {probe}")
        return {
            "kind": "port",
            "intervals": [
                {
                    "low": probe,
                    "high": probe,
                    "raw": probe,
                    "reversed": False,
                    "is_range": False,
                }
            ],
        }
    if isinstance(probe, float):
        if not probe.is_integer():
            _refuse(
                "BAD_PROBE",
                f"probe must be a whole port number: {probe!r}",
            )
        return _parse_port_probe(int(probe))
    if isinstance(probe, str):
        normalized = unicodedata.normalize("NFKC", probe).strip()
        if not normalized:
            _refuse("BAD_PROBE", "probe must not be empty")
        if "," in normalized:
            _refuse(
                "BAD_PROBE",
                "probe must be a single port or a single range",
            )
        interval = _parse_port_token(normalized, "BAD_PROBE", "probe")
        return {
            "kind": "range" if interval["is_range"] else "port",
            "intervals": [interval],
        }
    _refuse(
        "BAD_PROBE",
        "probe must be an integer, numeric string or integral number; "
        f"got {type(probe).__name__}",
    )


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for low, high in sorted(intervals):
        if merged and low <= merged[-1][1] + 1:
            if high > merged[-1][1]:
                merged[-1] = (merged[-1][0], high)
        else:
            merged.append((low, high))
    return merged


def _port_range_membership_body(request: Mapping, trace: list) -> dict:
    if "spec" not in request:
        _refuse("BAD_PORT_SPEC", "missing required field: spec")
    if "probe" not in request:
        _refuse("BAD_PROBE", "missing required field: probe")
    normalized, spec_intervals = _parse_port_spec(
        request["spec"], "BAD_PORT_SPEC", "spec"
    )
    trace.append(
        {
            "step": "parse_spec",
            "raw": request["spec"],
            "normalized": normalized,
            "ranges": [
                [interval["low"], interval["high"]]
                for interval in spec_intervals
            ],
            "reversed": [
                interval["reversed"] for interval in spec_intervals
            ],
        }
    )
    probe = _parse_port_probe(request["probe"])
    probe_reversed = any(
        interval["reversed"] for interval in probe["intervals"]
    )
    trace.append(
        {
            "step": "parse_probe",
            "raw": _json_scalar(request["probe"]),
            "kind": probe["kind"],
            "ranges": [
                [interval["low"], interval["high"]]
                for interval in probe["intervals"]
            ],
            "reversed": [
                interval["reversed"] for interval in probe["intervals"]
            ],
        }
    )
    spec_merged = _merge_intervals(
        [(interval["low"], interval["high"]) for interval in spec_intervals]
    )
    trace.append(
        {"step": "merge_spec", "merged": [list(pair) for pair in spec_merged]}
    )
    # Same key set for both probe kinds; not-applicable fields stay explicit.
    value: dict[str, object] = {
        "spec": request["spec"],
        "spec_normalized": normalized,
        "spec_ranges": [
            [interval["low"], interval["high"]] for interval in spec_intervals
        ],
        "spec_reversed": [
            interval["reversed"] for interval in spec_intervals
        ],
        "spec_merged": [list(pair) for pair in spec_merged],
        "probe": _json_scalar(request["probe"]),
        "probe_kind": probe["kind"],
        "probe_ranges": [
            [interval["low"], interval["high"]]
            for interval in probe["intervals"]
        ],
        "probe_reversed": probe_reversed,
        "contained": False,
        "matched_range": None,
        "overlap": None,
        "overlap_ranges": [],
    }
    if probe["kind"] == "port":
        low = probe["intervals"][0]["low"]
        matched_range = None
        for interval in spec_intervals:
            if interval["low"] <= low <= interval["high"]:
                matched_range = [interval["low"], interval["high"]]
                break
        value["contained"] = matched_range is not None
        # The original spec interval, not the merged union.
        value["matched_range"] = matched_range
        trace.append(
            {
                "step": "membership",
                "probe": low,
                "probe_reversed": probe_reversed,
                "contained": value["contained"],
                "matched_range": matched_range,
            }
        )
        return value

    probe_intervals = [
        (interval["low"], interval["high"]) for interval in probe["intervals"]
    ]
    overlap_ranges: list[tuple[int, int]] = []
    for probe_low, probe_high in probe_intervals:
        for spec_low, spec_high in spec_merged:
            low = max(probe_low, spec_low)
            high = min(probe_high, spec_high)
            if low <= high:
                overlap_ranges.append((low, high))
    contained = all(
        any(
            spec_low <= probe_low and probe_high <= spec_high
            for spec_low, spec_high in spec_merged
        )
        for probe_low, probe_high in probe_intervals
    )
    value["overlap"] = bool(overlap_ranges)
    value["contained"] = contained
    value["overlap_ranges"] = [
        list(pair) for pair in _merge_intervals(overlap_ranges)
    ]
    trace.append(
        {
            "step": "interval_compare",
            "overlap": value["overlap"],
            "contained": contained,
        }
    )
    return value


# ---------------------------------------------------------------------------
# 3. set_enumeration
# ---------------------------------------------------------------------------


def set_enumeration(request: Mapping) -> dict:
    """Compare an observed value set against an expected set.

    Request: ``{"observed": [str], "expected": [str], "universe": [str]?}``.
    Values compare as exact strings.  ``duplicates`` reports repeated values
    in ``observed``; ``complete`` means every expected value is present and
    only claims completeness over the supplied inputs (see ``scope_note``).
    ``out_of_universe`` is reported only when a universe is supplied.
    """

    return _execute("set_enumeration", request, _set_enumeration_body)


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        _refuse("BAD_REQUEST", f"{field} must be a list of strings")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            _refuse("BAD_REQUEST", f"{field}[{index}] must be a string")
    return list(value)


def _set_enumeration_body(request: Mapping, trace: list) -> dict:
    observed = _string_list(request.get("observed"), "observed")
    expected = _string_list(request.get("expected"), "expected")
    universe_raw = request.get("universe")
    universe = None
    if universe_raw is not None:
        universe = _string_list(universe_raw, "universe")

    observed_counts: dict[str, int] = {}
    for value in observed:
        observed_counts[value] = observed_counts.get(value, 0) + 1
    expected_order = list(dict.fromkeys(expected))
    observed_set = set(observed)
    expected_set = set(expected)

    missing = [value for value in expected_order if value not in observed_set]
    extra = [
        value for value in observed_counts if value not in expected_set
    ]
    duplicates = [
        {"side": "observed", "value": value, "count": count}
        for value, count in observed_counts.items()
        if count > 1
    ]
    out_of_universe = None
    if universe is not None:
        universe_set = set(universe)
        out_of_universe = {
            "observed": [
                value
                for value in observed_counts
                if value not in universe_set
            ],
            "expected": [
                value
                for value in expected_order
                if value not in universe_set
            ],
        }

    complete = not missing
    exact = complete and not extra and not duplicates
    note = (
        "complete means only that no expected value is missing; exact is "
        "true only when there is no missing, no extra and no repeated value "
        "in observed. duplicates lists observed repeats only (side="
        "'observed'); repeated expected values are folded into "
        "counts.expected_unique and do not change complete or exact, because "
        "duplicates is defined on the observed enumeration only. These "
        "claims cover the supplied inputs only, not the completeness of the "
        "observed source or of any material beyond them"
    )
    if universe is not None:
        note += (
            "; out_of_universe is relative to the supplied universe only"
        )
    trace.append(
        {
            "step": "enumerate",
            "observed": len(observed),
            "expected": len(expected),
            "missing": len(missing),
            "extra": len(extra),
            "duplicate_groups": len(duplicates),
        }
    )
    return {
        "missing": missing,
        "extra": extra,
        "duplicates": duplicates,
        "counts": {
            "observed": len(observed),
            "observed_unique": len(observed_counts),
            "expected": len(expected),
            "expected_unique": len(expected_set),
            "missing": len(missing),
            "extra": len(extra),
            "duplicates": len(duplicates),
        },
        "complete": complete,
        "exact": exact,
        "out_of_universe": out_of_universe,
        "scope_note": note,
    }


# ---------------------------------------------------------------------------
# 4. unit_convert
# ---------------------------------------------------------------------------

_UNIT_TABLE: dict[str, tuple[str, Fraction]] = {
    # time
    "s": ("time", Fraction(1)),
    "ms": ("time", Fraction(1, 1000)),
    "us": ("time", Fraction(1, 10**6)),
    "ns": ("time", Fraction(1, 10**9)),
    "ps": ("time", Fraction(1, 10**12)),
    "min": ("time", Fraction(60)),
    "h": ("time", Fraction(3600)),
    # frequency
    "Hz": ("frequency", Fraction(1)),
    "kHz": ("frequency", Fraction(1000)),
    "MHz": ("frequency", Fraction(10**6)),
    "GHz": ("frequency", Fraction(10**9)),
    # length
    "m": ("length", Fraction(1)),
    "cm": ("length", Fraction(1, 100)),
    "mm": ("length", Fraction(1, 1000)),
    "km": ("length", Fraction(1000)),
    # data (decimal SI)
    "B": ("data", Fraction(1)),
    "KB": ("data", Fraction(1000)),
    "MB": ("data", Fraction(10**6)),
    "GB": ("data", Fraction(10**9)),
}

_UNIT_ALIASES = {"µs": "us", "μs": "us"}


def _canonical_unit(name: object, field: str) -> str:
    if not isinstance(name, str) or not name.strip():
        _refuse("UNKNOWN_UNIT", f"{field} must be a unit string")
    normalized = unicodedata.normalize("NFKC", name).strip()
    normalized = _UNIT_ALIASES.get(normalized, normalized)
    if normalized not in _UNIT_TABLE:
        _refuse("UNKNOWN_UNIT", f"unknown unit: {name!r}")
    return normalized


def _unit_factor(from_unit: str, to_unit: str) -> tuple[str, Fraction]:
    from_kind, from_factor = _UNIT_TABLE[from_unit]
    to_kind, to_factor = _UNIT_TABLE[to_unit]
    if from_kind != to_kind:
        _refuse(
            "UNIT_DIMENSION",
            f"cannot convert {from_unit} ({from_kind}) to "
            f"{to_unit} ({to_kind})",
        )
    return from_kind, from_factor / to_factor


def unit_convert(request: Mapping) -> dict:
    """Convert a numeric quantity between units of the same dimension.

    Request: ``{"value": 154.3, "from": "ns", "to": "us"}``.  Arithmetic uses
    ``Decimal``/``Fraction``; the result is a decimal string and ``exact`` is
    true only when the conversion terminates in base 10.  ``µs``/``μs``/``us``
    are the same unit.  Unknown units and cross-dimension requests are refused.
    """

    return _execute("unit_convert", request, _unit_convert_body)


def _unit_convert_body(request: Mapping, trace: list) -> dict:
    for field in ("value", "from", "to"):
        if field not in request:
            _refuse("BAD_REQUEST", f"missing required field: {field}")
    from_unit = _canonical_unit(request["from"], "from")
    to_unit = _canonical_unit(request["to"], "to")
    amount = _decimal_from_scalar(request["value"], "value")
    kind, factor = _unit_factor(from_unit, to_unit)
    converted = Fraction(amount) * factor
    exact_value = _fraction_to_decimal(converted)
    if exact_value is None:
        with localcontext() as context:
            context.prec = DECIMAL_PRECISION
            rounded = Decimal(converted.numerator) / Decimal(
                converted.denominator
            )
        converted_text = _decimal_text(rounded)
        exact = False
    else:
        converted_text = _decimal_text(exact_value)
        exact = True
    trace.append(
        {
            "step": "convert",
            "from": from_unit,
            "to": to_unit,
            "factor": _fraction_text(factor),
            "factor_exact": str(factor),
            "converted": converted_text,
            "exact": exact,
        }
    )
    if kind == "data":
        trace.append(
            {
                "step": "unit_basis",
                "dimension": "data",
                "basis": "decimal SI powers of 1000",
            }
        )
    value: dict[str, object] = {
        "value": converted_text,
        "from": from_unit,
        "to": to_unit,
        "input_value": _json_scalar(request["value"]),
        # Caller's original spelling, kept next to the canonical names.
        "input_from": request["from"],
        "input_to": request["to"],
        "factor": _fraction_text(factor),
        "factor_exact": str(factor),
        "exact": exact,
        "dimension": kind,
    }
    if kind == "data":
        value["note"] = (
            "KB/MB/GB are decimal SI units (powers of 1000); binary "
            "KiB/MiB/GiB are not accepted."
        )
    return value


# ---------------------------------------------------------------------------
# 5. boundary_compare
# ---------------------------------------------------------------------------

BOUNDARY_OPS = ("lt", "le", "gt", "ge", "eq")


def boundary_compare(request: Mapping) -> dict:
    """Compare one scalar against one bound, converting units first.

    Request: ``{"value": 154.3, "unit": "ns", "op": "lt", "bound": 10,
    "bound_unit": "us"}``.  ``op`` is one of ``lt``/``le``/``gt``/``ge``/``eq``;
    the value is converted into ``bound_unit`` before comparing.  On equality
    ``le``/``ge``/``eq`` are true and ``lt``/``gt`` are false, and
    ``value.boundary_equal`` is set.  Interval or otherwise non-scalar values
    are refused with ``NON_SCALAR``.
    """

    return _execute("boundary_compare", request, _boundary_compare_body)


def _boundary_scalar(value: object, field: str) -> Decimal:
    if value is None:
        _refuse("NON_SCALAR", f"{field} is missing (null)")
    if isinstance(value, bool):
        _refuse(
            "NON_SCALAR", f"{field} must be a single number, not a boolean"
        )
    if isinstance(value, (list, tuple, dict, set, frozenset)):
        _refuse(
            "NON_SCALAR",
            f"{field} is not a single number: {type(value).__name__}",
        )
    if isinstance(value, str):
        try:
            parsed = Decimal(value.strip())
        except InvalidOperation:
            _refuse(
                "NON_SCALAR",
                f"{field} is not a single number: {value!r} (ranges must be "
                "compared with port_range_membership)",
            )
        if not parsed.is_finite():
            _refuse("NON_SCALAR", f"{field} is not a finite number")
        return parsed
    return _decimal_from_scalar(value, field)


def _boundary_compare_body(request: Mapping, trace: list) -> dict:
    for field in ("value", "unit", "op", "bound", "bound_unit"):
        if field not in request:
            _refuse("BAD_REQUEST", f"missing required field: {field}")
    op = request["op"]
    if not isinstance(op, str) or op not in BOUNDARY_OPS:
        _refuse(
            "BAD_OP",
            f"op must be one of {', '.join(BOUNDARY_OPS)}; got {op!r}",
        )
    value_unit = _canonical_unit(request["unit"], "unit")
    bound_unit = _canonical_unit(request["bound_unit"], "bound_unit")
    value_number = _boundary_scalar(request["value"], "value")
    bound_number = _boundary_scalar(request["bound"], "bound")
    kind, factor = _unit_factor(value_unit, bound_unit)
    converted = Fraction(value_number) * factor
    bound_value = Fraction(bound_number)
    boundary_equal = converted == bound_value
    result = {
        "lt": converted < bound_value,
        "le": converted <= bound_value,
        "gt": converted > bound_value,
        "ge": converted >= bound_value,
        "eq": boundary_equal,
    }[op]
    exact_value = _fraction_to_decimal(converted)
    exact = exact_value is not None
    converted_text = (
        _decimal_text(exact_value)
        if exact_value is not None
        else _fraction_text(converted)
    )
    trace.append(
        {
            "step": "compare",
            "from": value_unit,
            "to": bound_unit,
            "factor": _fraction_text(factor),
            "converted": converted_text,
            "bound": _decimal_text(bound_number),
            "op": op,
            "boundary_equal": boundary_equal,
            "result": result,
        }
    )
    return {
        "op": op,
        "value": _json_scalar(request["value"]),
        "unit": value_unit,
        "bound": _json_scalar(request["bound"]),
        "bound_unit": bound_unit,
        # Caller's original spelling, kept next to the canonical names.
        "input_unit": request["unit"],
        "input_bound_unit": request["bound_unit"],
        "converted_value": converted_text,
        "factor": _fraction_text(factor),
        "factor_exact": str(factor),
        "boundary_equal": boundary_equal,
        "result": result,
        "exact": exact,
        "dimension": kind,
    }


# ---------------------------------------------------------------------------
# 6. version_diff
# ---------------------------------------------------------------------------

VERSION_NORMALIZERS = ("exact", "whitespace")


def version_diff(request: Mapping) -> dict:
    """Classify aligned items between two revisions.

    Request: ``{"left": {"revision_id", "items": [{"item_id", "text"}]},
    "right": {...}, "normalizer": "exact" | "whitespace"?}``.  ``normalizer``
    is optional and defaults to ``"exact"`` when absent; any other supplied
    value is refused with ``BAD_NORMALIZER``.  ``same`` and ``changed`` both
    carry ``left_text``/``right_text`` so the item shape is stable even when
    ``whitespace`` makes two different spellings compare equal; ``added`` and
    ``removed`` keep one ``text``.  ``whitespace`` collapses whitespace runs
    for comparison only; reported texts keep their original form.  A repeated
    ``item_id`` on either side is refused with ``DUPLICATE_ALIGN_KEY``.
    """

    return _execute("version_diff", request, _version_diff_body)


def _version_side(request: Mapping, field: str) -> tuple[str, list[dict]]:
    side = request.get(field)
    if not isinstance(side, Mapping):
        _refuse("BAD_REQUEST", f"{field} must be an object")
    revision = side.get("revision_id")
    if not isinstance(revision, str) or not revision.strip():
        _refuse(
            "BAD_REQUEST",
            f"{field}.revision_id must be a non-empty string",
        )
    items = side.get("items")
    if not isinstance(items, list):
        _refuse("BAD_REQUEST", f"{field}.items must be a list")
    ordered = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            _refuse(
                "BAD_REQUEST", f"{field}.items[{index}] must be an object"
            )
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            _refuse(
                "BAD_REQUEST",
                f"{field}.items[{index}].item_id must be a non-empty string",
            )
        text = item.get("text")
        if not isinstance(text, str):
            _refuse(
                "BAD_REQUEST", f"{field}.items[{index}].text must be a string"
            )
        if item_id in seen:
            _refuse(
                "DUPLICATE_ALIGN_KEY",
                f"{field} repeats item_id {item_id!r}",
            )
        seen.add(item_id)
        ordered.append({"item_id": item_id, "text": text})
    return revision, ordered


def _diff_text(text: str, normalizer: str) -> str:
    if normalizer == "whitespace":
        return " ".join(text.split())
    return text


def _version_diff_body(request: Mapping, trace: list) -> dict:
    normalizer = request.get("normalizer", "exact")
    if not isinstance(normalizer, str) or normalizer not in (
        VERSION_NORMALIZERS
    ):
        _refuse(
            "BAD_NORMALIZER",
            "normalizer must be 'exact' or 'whitespace'; "
            f"got {normalizer!r}",
        )
    left_revision, left_items = _version_side(request, "left")
    right_revision, right_items = _version_side(request, "right")
    right_by_id = {item["item_id"]: item for item in right_items}
    left_ids = {item["item_id"] for item in left_items}

    same: list[dict] = []
    changed: list[dict] = []
    removed: list[dict] = []
    for item in left_items:
        counterpart = right_by_id.get(item["item_id"])
        if counterpart is None:
            removed.append(dict(item))
            continue
        if _diff_text(item["text"], normalizer) == _diff_text(
            counterpart["text"], normalizer
        ):
            # Same shape as changed: a whitespace-insensitive "same" can still
            # hold two different raw spellings, so both must be reported.
            same.append(
                {
                    "item_id": item["item_id"],
                    "left_text": item["text"],
                    "right_text": counterpart["text"],
                }
            )
        else:
            changed.append(
                {
                    "item_id": item["item_id"],
                    "left_text": item["text"],
                    "right_text": counterpart["text"],
                }
            )
    added = [
        dict(item)
        for item in right_items
        if item["item_id"] not in left_ids
    ]
    trace.append(
        {
            "step": "diff",
            "normalizer": normalizer,
            "left_items": len(left_items),
            "right_items": len(right_items),
            "same": len(same),
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        }
    )
    return {
        "left_revision": left_revision,
        "right_revision": right_revision,
        "normalizer": normalizer,
        "same": same,
        "added": added,
        "removed": removed,
        "changed": changed,
        "counts": {
            "left": len(left_items),
            "right": len(right_items),
            "same": len(same),
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
    }


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

OPERATORS = {
    "exact_join": exact_join,
    "port_range_membership": port_range_membership,
    "set_enumeration": set_enumeration,
    "unit_convert": unit_convert,
    "boundary_compare": boundary_compare,
    "version_diff": version_diff,
}


def run_operator(name: str, request: Mapping) -> dict:
    """Dispatch one operator by name.

    Returns the DESIGN §5 envelope.  Raises ``KeyError`` when ``name`` is not
    one of :data:`OPERATORS` (the CLI maps that to exit code 2).  The request
    is never mutated, and equal requests produce equal responses.
    """

    try:
        function = OPERATORS[name]
    except KeyError:
        raise KeyError(
            f"unknown operator: {name!r}; known: {', '.join(OP_NAMES)}"
        ) from None
    return function(request)
