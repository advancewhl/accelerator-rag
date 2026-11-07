"""Contract tests for the phase-2 deterministic verification operators."""

from __future__ import annotations

import copy
import json

import pytest

from accelerator_rag.verify import cli as verify_cli

from accelerator_rag.verify.operators import (
    OP_NAMES,
    OPERATORS,
    boundary_compare,
    exact_join,
    port_range_membership,
    run_operator,
    set_enumeration,
    unit_convert,
    version_diff,
)

ENVELOPE_KEYS = {"op", "status", "value", "trace", "assumptions", "refusal"}


def assert_ok(response, op):
    assert set(response) == ENVELOPE_KEYS
    assert response["op"] == op
    assert response["status"] == "ok"
    assert response["refusal"] is None
    assert isinstance(response["value"], dict)
    assert isinstance(response["trace"], list)
    assert response["assumptions"] == []
    return response["value"]


def assert_refused(response, op, code):
    assert set(response) == ENVELOPE_KEYS
    assert response["op"] == op
    assert response["status"] == "refused"
    assert response["value"] == {}
    assert isinstance(response["trace"], list)
    assert response["assumptions"] == []
    assert response["refusal"] is not None
    assert response["refusal"]["code"] == code
    assert response["refusal"]["message"]
    return response["refusal"]


# ---------------------------------------------------------------------------
# dispatch contract
# ---------------------------------------------------------------------------


def join_request():
    return {
        "left": [
            {
                "id": "l1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {"vlan": 100},
            }
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {"ports": "45-48"},
            }
        ],
        "join_keys": ["device"],
    }


SAMPLE_REQUESTS = {
    "exact_join": join_request(),
    "port_range_membership": {"spec": "45-48", "probe": 48},
    "set_enumeration": {"observed": ["A", "B"], "expected": ["A"]},
    "unit_convert": {"value": 1000, "from": "ns", "to": "us"},
    "boundary_compare": {
        "value": 1,
        "unit": "us",
        "op": "lt",
        "bound": 1,
        "bound_unit": "ms",
    },
    "version_diff": {
        "left": {"revision_id": "rev-a", "items": []},
        "right": {"revision_id": "rev-b", "items": []},
        "normalizer": "exact",
    },
}


def test_operators_registry_covers_the_six_names():
    assert set(OPERATORS) == set(OP_NAMES)
    assert len(OP_NAMES) == 6


@pytest.mark.parametrize("name", OP_NAMES)
def test_run_operator_dispatches_without_mutation(name):
    request = copy.deepcopy(SAMPLE_REQUESTS[name])
    before = copy.deepcopy(request)
    response = run_operator(name, request)
    assert response["op"] == name
    assert response["status"] == "ok"
    assert request == before
    again = run_operator(name, copy.deepcopy(request))
    assert again == response


def test_run_operator_rejects_unknown_operator():
    assert OPERATORS
    with pytest.raises(KeyError):
        run_operator("no_such_operator", {})


def test_run_operator_refuses_non_object_request():
    response = run_operator("set_enumeration", ["not", "a", "mapping"])
    assert_refused(response, "set_enumeration", "BAD_REQUEST")


def test_caller_assumptions_are_echoed():
    response = set_enumeration(
        {
            "observed": ["A"],
            "expected": ["A"],
            "assumptions": ["cabinet list is complete for this table"],
        }
    )
    assert set(response) == ENVELOPE_KEYS
    assert response["status"] == "ok"
    assert response["value"]["complete"] is True
    assert response["assumptions"] == [
        "cabinet list is complete for this table"
    ]


def test_invalid_assumptions_refused():
    response = set_enumeration(
        {"observed": [], "expected": [], "assumptions": "not-a-list"}
    )
    assert_refused(response, "set_enumeration", "BAD_REQUEST")


# ---------------------------------------------------------------------------
# port_range_membership
# ---------------------------------------------------------------------------


def test_port_range_closed_boundaries():
    for probe, expected in ((44, False), (45, True), (48, True), (49, False)):
        value = assert_ok(
            port_range_membership({"spec": "45-48", "probe": probe}),
            "port_range_membership",
        )
        assert value["contained"] is expected


@pytest.mark.parametrize(
    "spec",
    ["45-48", "45~48", "45～48", "45至48", "45—48", "４５－４８"],
)
def test_port_range_accepts_separators_and_fullwidth(spec):
    for probe in (45, 48, "４８"):
        value = assert_ok(
            port_range_membership({"spec": spec, "probe": probe}),
            "port_range_membership",
        )
        assert value["contained"] is True
    for probe in (44, 49):
        value = assert_ok(
            port_range_membership({"spec": spec, "probe": probe}),
            "port_range_membership",
        )
        assert value["contained"] is False


def test_port_reversed_spec_is_sorted_and_flagged():
    response = port_range_membership({"spec": "48-45", "probe": 45})
    value = assert_ok(response, "port_range_membership")
    assert value["spec_ranges"] == [[45, 48]]
    assert value["spec_reversed"] == [True]
    assert value["contained"] is True
    parse_steps = [
        step for step in response["trace"] if step.get("step") == "parse_spec"
    ]
    assert parse_steps and parse_steps[0]["reversed"] == [True]


@pytest.mark.parametrize("spec", ["17-24,45-48", "１７－２４，４５－４８"])
def test_port_list_spec(spec):
    for probe, expected in ((17, True), (24, True), (46, True), (30, False)):
        value = assert_ok(
            port_range_membership({"spec": spec, "probe": probe}),
            "port_range_membership",
        )
        assert value["contained"] is expected


def test_port_single_port_spec():
    assert (
        assert_ok(
            port_range_membership({"spec": "48", "probe": 48}),
            "port_range_membership",
        )["contained"]
        is True
    )
    assert (
        assert_ok(
            port_range_membership({"spec": "48", "probe": 49}),
            "port_range_membership",
        )["contained"]
        is False
    )


@pytest.mark.parametrize(
    ("spec", "probe", "overlap", "contained"),
    [
        ("17-30", "20-24", True, True),
        ("45-48", "17-24", False, False),
        ("17-24", "20-30", True, False),
        ("45-48", "45-48", True, True),
        ("17-24", "24-45", True, False),
        ("45-48,50-52", "48-50", True, False),
        ("45-52", "48-50", True, True),
    ],
)
def test_port_range_probe_overlap_and_containment(
    spec, probe, overlap, contained
):
    value = assert_ok(
        port_range_membership({"spec": spec, "probe": probe}),
        "port_range_membership",
    )
    assert value["probe_kind"] == "range"
    assert value["overlap"] is overlap
    assert value["contained"] is contained


def test_port_reversed_probe_is_flagged():
    response = port_range_membership({"spec": "17-30", "probe": "24-17"})
    value = assert_ok(response, "port_range_membership")
    assert value["probe_reversed"] is True
    assert value["probe_ranges"] == [[17, 24]]
    assert value["overlap"] is True
    assert value["contained"] is True
    parse_steps = [
        step for step in response["trace"] if step.get("step") == "parse_probe"
    ]
    assert parse_steps and parse_steps[0]["reversed"] == [True]


def test_port_value_shape_is_stable_and_matched_range_is_original():
    port_response = port_range_membership(
        {"spec": "45-48,50-52", "probe": 48}
    )
    port_value = assert_ok(port_response, "port_range_membership")
    range_value = assert_ok(
        port_range_membership({"spec": "45-48,50-52", "probe": "47-51"}),
        "port_range_membership",
    )
    assert set(port_value) == set(range_value)
    # The original spec interval, not the merged union [45, 52].
    assert port_value["spec_merged"] == [[45, 48], [50, 52]]
    assert port_value["matched_range"] == [45, 48]
    assert port_value["overlap"] is None
    assert port_value["overlap_ranges"] == []
    assert range_value["matched_range"] is None
    assert range_value["probe_reversed"] is False
    assert range_value["overlap_ranges"] == [[47, 48], [50, 51]]


def test_port_oversized_digit_string_refused():
    huge = "9" * 10000
    assert_refused(
        port_range_membership({"spec": huge, "probe": 1}),
        "port_range_membership",
        "BAD_PORT_SPEC",
    )
    assert_refused(
        port_range_membership({"spec": "1", "probe": huge}),
        "port_range_membership",
        "BAD_PROBE",
    )


@pytest.mark.parametrize(
    "spec", ["45-", "abc", "", "45-48-50", "-45", "4.5-8", "45--48", 48]
)
def test_port_bad_spec_refused(spec):
    response = port_range_membership({"spec": spec, "probe": 48})
    assert_refused(response, "port_range_membership", "BAD_PORT_SPEC")


@pytest.mark.parametrize(
    "probe", ["abc", True, [45, 48], 48.5, "", "17-24,45-48"]
)
def test_port_bad_probe_refused(probe):
    response = port_range_membership({"spec": "45-48", "probe": probe})
    assert_refused(response, "port_range_membership", "BAD_PROBE")


def test_port_missing_fields_refused():
    assert_refused(
        port_range_membership({"probe": 48}),
        "port_range_membership",
        "BAD_PORT_SPEC",
    )
    assert_refused(
        port_range_membership({"spec": "45-48"}),
        "port_range_membership",
        "BAD_PROBE",
    )


# ---------------------------------------------------------------------------
# unit_convert
# ---------------------------------------------------------------------------


def test_unit_ns_to_us_is_exact():
    value = assert_ok(
        unit_convert({"value": 154.3, "from": "ns", "to": "us"}),
        "unit_convert",
    )
    assert value["value"] == "0.1543"
    assert value["exact"] is True
    assert value["factor"] == "0.001"
    assert value["factor_exact"] == "1/1000"
    assert value["dimension"] == "time"


@pytest.mark.parametrize(
    ("from_unit", "to_unit"), [("us", "µs"), ("µs", "μs"), ("μs", "us")]
)
def test_unit_micro_signs_are_the_same_unit(from_unit, to_unit):
    value = assert_ok(
        unit_convert({"value": 7, "from": from_unit, "to": to_unit}),
        "unit_convert",
    )
    assert value["value"] == "7"
    assert value["factor"] == "1"
    assert value["exact"] is True


def test_unit_ns_to_micro():
    value = assert_ok(
        unit_convert({"value": 1000, "from": "ns", "to": "μs"}),
        "unit_convert",
    )
    assert value["value"] == "1"


def test_unit_frequency_conversion():
    value = assert_ok(
        unit_convert({"value": 2, "from": "GHz", "to": "MHz"}),
        "unit_convert",
    )
    assert value["value"] == "2000"
    assert value["dimension"] == "frequency"


def test_unit_data_conversion_is_decimal():
    value = assert_ok(
        unit_convert({"value": 1, "from": "KB", "to": "B"}),
        "unit_convert",
    )
    assert value["value"] == "1000"
    value = assert_ok(
        unit_convert({"value": 1, "from": "GB", "to": "MB"}),
        "unit_convert",
    )
    assert value["value"] == "1000"


def test_unit_preserves_input_unit_spelling():
    value = assert_ok(
        unit_convert({"value": 1, "from": "µs", "to": "μs"}),
        "unit_convert",
    )
    assert value["input_from"] == "µs"
    assert value["input_to"] == "μs"
    assert value["from"] == "us"
    assert value["to"] == "us"


def test_unit_non_terminating_is_marked_inexact():
    value = assert_ok(
        unit_convert({"value": 1, "from": "s", "to": "min"}),
        "unit_convert",
    )
    assert value["exact"] is False
    assert float(value["value"]) == pytest.approx(1 / 60)


@pytest.mark.parametrize("unit", ["fortnight", "KiB", "NS", ""])
def test_unit_unknown_refused(unit):
    assert_refused(
        unit_convert({"value": 1, "from": unit, "to": "s"}),
        "unit_convert",
        "UNKNOWN_UNIT",
    )


def test_unit_unknown_target_refused():
    assert_refused(
        unit_convert({"value": 1, "from": "ns", "to": "furlong"}),
        "unit_convert",
        "UNKNOWN_UNIT",
    )


@pytest.mark.parametrize(
    ("from_unit", "to_unit"), [("m", "s"), ("Hz", "s"), ("KB", "m")]
)
def test_unit_cross_dimension_refused(from_unit, to_unit):
    assert_refused(
        unit_convert({"value": 1, "from": from_unit, "to": to_unit}),
        "unit_convert",
        "UNIT_DIMENSION",
    )


# ---------------------------------------------------------------------------
# boundary_compare
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("op", "expected"),
    [("lt", False), ("le", True), ("gt", False), ("ge", True), ("eq", True)],
)
def test_boundary_equal_10us_vs_10000ns(op, expected):
    value = assert_ok(
        boundary_compare(
            {
                "value": 10,
                "unit": "µs",
                "op": op,
                "bound": 10000,
                "bound_unit": "ns",
            }
        ),
        "boundary_compare",
    )
    assert value["boundary_equal"] is True
    assert value["result"] is expected
    assert value["converted_value"] == "10000"


def test_boundary_converts_before_comparing():
    value = assert_ok(
        boundary_compare(
            {
                "value": 0.5,
                "unit": "us",
                "op": "lt",
                "bound": 600,
                "bound_unit": "ns",
            }
        ),
        "boundary_compare",
    )
    assert value["boundary_equal"] is False
    assert value["result"] is True
    assert value["factor"] == "1000"


def test_boundary_unequal_le_and_lt_agree():
    value = assert_ok(
        boundary_compare(
            {
                "value": 1,
                "unit": "ns",
                "op": "le",
                "bound": 1,
                "bound_unit": "us",
            }
        ),
        "boundary_compare",
    )
    assert value["boundary_equal"] is False
    assert value["result"] is True


@pytest.mark.parametrize(
    "bad_value", [[45, 48], "17-24", {"low": 45, "high": 48}, "10±0.1"]
)
def test_boundary_non_scalar_refused(bad_value):
    assert_refused(
        boundary_compare(
            {
                "value": bad_value,
                "unit": "ns",
                "op": "lt",
                "bound": 10,
                "bound_unit": "us",
            }
        ),
        "boundary_compare",
        "NON_SCALAR",
    )


@pytest.mark.parametrize("field", ["value", "bound"])
def test_boundary_null_scalar_refused(field):
    request = {
        "value": 1,
        "unit": "ns",
        "op": "lt",
        "bound": 10,
        "bound_unit": "us",
    }
    request[field] = None
    assert_refused(
        boundary_compare(request), "boundary_compare", "NON_SCALAR"
    )


def test_boundary_preserves_input_unit_spelling():
    value = assert_ok(
        boundary_compare(
            {
                "value": 1,
                "unit": "µs",
                "op": "ge",
                "bound": 1000000,
                "bound_unit": "ps",
            }
        ),
        "boundary_compare",
    )
    assert value["input_unit"] == "µs"
    assert value["unit"] == "us"
    assert value["input_bound_unit"] == "ps"
    assert value["bound_unit"] == "ps"
    assert value["boundary_equal"] is True
    assert value["result"] is True


def test_boundary_bad_op_refused():
    assert_refused(
        boundary_compare(
            {
                "value": 1,
                "unit": "ns",
                "op": "ne",
                "bound": 10,
                "bound_unit": "us",
            }
        ),
        "boundary_compare",
        "BAD_OP",
    )


def test_boundary_unit_errors_refused():
    assert_refused(
        boundary_compare(
            {
                "value": 1,
                "unit": "furlong",
                "op": "lt",
                "bound": 10,
                "bound_unit": "us",
            }
        ),
        "boundary_compare",
        "UNKNOWN_UNIT",
    )
    assert_refused(
        boundary_compare(
            {
                "value": 1,
                "unit": "m",
                "op": "lt",
                "bound": 10,
                "bound_unit": "s",
            }
        ),
        "boundary_compare",
        "UNIT_DIMENSION",
    )


# ---------------------------------------------------------------------------
# set_enumeration
# ---------------------------------------------------------------------------


def test_set_missing_extra_and_complete():
    value = assert_ok(
        set_enumeration(
            {"observed": ["A", "B", "C"], "expected": ["B", "C", "D"]}
        ),
        "set_enumeration",
    )
    assert value["missing"] == ["D"]
    assert value["extra"] == ["A"]
    assert value["duplicates"] == []
    assert value["complete"] is False
    assert value["exact"] is False
    assert value["out_of_universe"] is None
    assert value["counts"]["observed"] == 3
    assert value["counts"]["expected"] == 3


def test_set_complete_only_over_given_inputs():
    value = assert_ok(
        set_enumeration({"observed": ["B", "A"], "expected": ["A", "B"]}),
        "set_enumeration",
    )
    assert value["complete"] is True
    assert value["exact"] is True
    note = value["scope_note"]
    assert "supplied inputs" in note
    assert "complete means only that no expected value is missing" in note
    assert "no missing, no extra and no repeated value in observed" in note
    assert "duplicate" in note


def test_set_duplicates_are_reported():
    value = assert_ok(
        set_enumeration(
            {"observed": ["A", "A", "B", "A"], "expected": ["A", "B"]}
        ),
        "set_enumeration",
    )
    assert value["duplicates"] == [
        {"side": "observed", "value": "A", "count": 3}
    ]
    assert value["counts"]["observed"] == 4
    assert value["counts"]["observed_unique"] == 2
    assert value["complete"] is True
    assert value["exact"] is False
    note = value["scope_note"]
    assert "duplicates lists observed repeats only" in note
    assert "do not change complete or exact" in note
    assert "duplicates is defined on the observed enumeration only" in note


def test_set_expected_duplicates_are_folded_consistently():
    value = assert_ok(
        set_enumeration(
            {"observed": ["A"], "expected": ["A", "A"]}
        ),
        "set_enumeration",
    )
    assert value["duplicates"] == []
    assert value["counts"]["expected"] == 2
    assert value["counts"]["expected_unique"] == 1
    assert value["complete"] is True
    assert value["exact"] is True


def test_set_universe_out_of_bounds():
    value = assert_ok(
        set_enumeration(
            {
                "observed": ["A", "B", "C"],
                "expected": ["A", "D"],
                "universe": ["A", "B", "D"],
            }
        ),
        "set_enumeration",
    )
    assert value["out_of_universe"] == {"observed": ["C"], "expected": []}
    assert value["missing"] == ["D"]
    assert value["extra"] == ["B", "C"]
    assert "complete means only that no expected value is missing" in (
        value["scope_note"]
    )
    assert "universe" in value["scope_note"]


def test_set_comparison_is_exact_string():
    value = assert_ok(
        set_enumeration({"observed": ["a"], "expected": ["A"]}),
        "set_enumeration",
    )
    assert value["missing"] == ["A"]
    assert value["extra"] == ["a"]
    assert value["complete"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"observed": "A", "expected": []},
        {"observed": [], "expected": [1]},
        {"observed": [], "expected": [], "universe": "abc"},
    ],
)
def test_set_bad_request_refused(payload):
    assert_refused(
        set_enumeration(payload), "set_enumeration", "BAD_REQUEST"
    )


# ---------------------------------------------------------------------------
# exact_join
# ---------------------------------------------------------------------------


def test_exact_join_matches_identical_scope():
    value = assert_ok(exact_join(join_request()), "exact_join")
    assert value["scope_mode"] == "identical_scope_required"
    assert value["matched"] == [
        {
            "left_id": "l1",
            "right_id": "r1",
            "join": {"device": {"left": "DEVSW001", "right": "DEVSW001"}},
            "scope": {},
            "shared_scope": {
                "left": {"cabinet": "L3-CN01"},
                "right": {"cabinet": "L3-CN01"},
            },
        }
    ]
    assert value["unmatched_left"] == []
    assert value["unmatched_right"] == []
    assert value["counts"] == {
        "matched": 1,
        "unmatched_left": 0,
        "unmatched_right": 0,
    }


def test_exact_join_same_name_different_cabinet_refused():
    request = join_request()
    request["right"][0]["scope"] = {"cabinet": "L4-CN01"}
    assert_refused(exact_join(request), "exact_join", "AMBIGUOUS_SCOPE")


def test_exact_join_multiple_scopes_on_one_side_refused():
    request = join_request()
    request["left"].append(
        {
            "id": "l2",
            "keys": {"device": "DEVSW001"},
            "scope": {"cabinet": "L4-CN01"},
            "payload": {},
        }
    )
    assert_refused(exact_join(request), "exact_join", "AMBIGUOUS_SCOPE")


def test_exact_join_ambiguous_scope_without_counterpart_refused():
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            },
            {
                "id": "l2",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "L4-CN01"},
                "payload": {},
            },
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": "DEVSW002"},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            }
        ],
        "join_keys": ["device"],
    }
    assert_refused(exact_join(request), "exact_join", "AMBIGUOUS_SCOPE")


def test_exact_join_blank_join_key_refused():
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {"device": "   "},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            }
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": ""},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            }
        ],
        "join_keys": ["device"],
    }
    assert_refused(exact_join(request), "exact_join", "AMBIGUOUS_SCOPE")


def test_exact_join_blank_scope_refused():
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "  "},
                "payload": {},
            }
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": ""},
                "payload": {},
            }
        ],
        "join_keys": ["device"],
    }
    assert_refused(exact_join(request), "exact_join", "AMBIGUOUS_SCOPE")


def test_exact_join_explicit_blank_scope_is_unmatched():
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "  "},
                "payload": {},
            }
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": ""},
                "payload": {},
            }
        ],
        "join_keys": ["device"],
        "scope_keys": ["cabinet"],
    }
    value = assert_ok(exact_join(request), "exact_join")
    assert value["matched"] == []
    assert value["unmatched_left"][0]["reason"] == "missing_scope_key"
    assert value["unmatched_right"][0]["reason"] == "missing_scope_key"


def test_exact_join_explicit_blank_join_key_is_unmatched():
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {"device": "   "},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            }
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": ""},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            }
        ],
        "join_keys": ["device"],
        "scope_keys": ["cabinet"],
    }
    value = assert_ok(exact_join(request), "exact_join")
    assert value["matched"] == []
    assert value["unmatched_left"][0]["reason"] == "missing_join_key"
    assert value["unmatched_right"][0]["reason"] == "missing_join_key"


def test_exact_join_uniform_pair_keeps_raw_shared_scope():
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": " l3-cn01 "},
                "payload": {},
            }
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": "devsw001"},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            }
        ],
        "join_keys": ["device"],
    }
    value = assert_ok(exact_join(request), "exact_join")
    assert value["matched"][0]["shared_scope"] == {
        "left": {"cabinet": " l3-cn01 "},
        "right": {"cabinet": "L3-CN01"},
    }


@pytest.mark.parametrize("side", ["left", "right"])
def test_exact_join_duplicate_record_id_refused(side):
    request = join_request()
    request[side].append(copy.deepcopy(request[side][0]))
    assert_refused(exact_join(request), "exact_join", "DUPLICATE_RECORD_ID")


def test_exact_join_invalid_scope_on_record_without_join_key():
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {},
                "scope": {"cabinet": 5},
                "payload": {},
            }
        ],
        "right": [],
        "join_keys": ["device"],
    }
    assert_refused(exact_join(request), "exact_join", "BAD_REQUEST")


def test_exact_join_missing_scope_refused():
    request = join_request()
    request["left"][0]["scope"] = {}
    assert_refused(exact_join(request), "exact_join", "AMBIGUOUS_SCOPE")

    request = join_request()
    del request["left"][0]["scope"]
    assert_refused(exact_join(request), "exact_join", "AMBIGUOUS_SCOPE")


def test_exact_join_scope_keys_disambiguate():
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            },
            {
                "id": "l2",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "L4-CN01"},
                "payload": {},
            },
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            }
        ],
        "join_keys": ["device"],
        "scope_keys": ["cabinet"],
    }
    value = assert_ok(exact_join(request), "exact_join")
    assert value["scope_mode"] == "explicit_scope_keys"
    assert [pair["left_id"] for pair in value["matched"]] == ["l1"]
    assert value["matched"][0]["scope"] == {
        "cabinet": {"left": "L3-CN01", "right": "L3-CN01"}
    }
    assert value["matched"][0]["shared_scope"] is None
    assert [item["id"] for item in value["unmatched_left"]] == ["l2"]
    assert value["unmatched_left"][0]["reason"] == "scope_mismatch"
    assert value["unmatched_right"] == []


def test_exact_join_unmatched_records_preserved():
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {"note": "left-only"},
            }
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": "DEVSW002"},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {"note": "right-only"},
            }
        ],
        "join_keys": ["device"],
    }
    value = assert_ok(exact_join(request), "exact_join")
    assert value["matched"] == []
    assert [item["id"] for item in value["unmatched_left"]] == ["l1"]
    assert value["unmatched_left"][0]["reason"] == "no_key_match"
    assert value["unmatched_left"][0]["payload"] == {"note": "left-only"}
    assert [item["id"] for item in value["unmatched_right"]] == ["r1"]
    assert value["unmatched_right"][0]["payload"] == {"note": "right-only"}


@pytest.mark.parametrize(
    ("left_key", "right_key"), [("DEVSW001", "devsw001"), ("ＤＥＶＳＷ００１", "DEVSW001")]
)
def test_exact_join_normalises_only_for_comparison(left_key, right_key):
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {"device": " DEVSW001 "},
                "scope": {"cabinet": "l3-cn01"},
                "payload": {},
            }
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": right_key},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            }
        ],
        "join_keys": ["device"],
    }
    request["left"][0]["keys"]["device"] = left_key
    value = assert_ok(exact_join(request), "exact_join")
    assert value["counts"]["matched"] == 1
    pair = value["matched"][0]
    assert pair["join"]["device"] == {
        "left": left_key,
        "right": right_key,
    }


def test_exact_join_explicit_scope_missing_value_is_unmatched():
    request = {
        "left": [
            {
                "id": "l1",
                "keys": {"device": "DEVSW001"},
                "scope": {},
                "payload": {},
            }
        ],
        "right": [
            {
                "id": "r1",
                "keys": {"device": "DEVSW001"},
                "scope": {"cabinet": "L3-CN01"},
                "payload": {},
            }
        ],
        "join_keys": ["device"],
        "scope_keys": ["cabinet"],
    }
    value = assert_ok(exact_join(request), "exact_join")
    assert value["matched"] == []
    assert value["unmatched_left"][0]["reason"] == "missing_scope_key"
    assert value["unmatched_right"][0]["reason"] == "scope_mismatch"


@pytest.mark.parametrize(
    "payload",
    [
        {"left": [], "right": [], "join_keys": []},
        {"left": [], "right": [], "join_keys": ["device", "device"]},
        {"left": {}, "right": [], "join_keys": ["device"]},
        {
            "left": [],
            "right": [],
            "join_keys": ["device"],
            "scope_keys": [],
        },
    ],
)
def test_exact_join_bad_request_refused(payload):
    assert_refused(exact_join(payload), "exact_join", "BAD_REQUEST")


# ---------------------------------------------------------------------------
# version_diff
# ---------------------------------------------------------------------------


def diff_request(left_items, right_items, normalizer="exact"):
    return {
        "left": {"revision_id": "rev-a", "items": left_items},
        "right": {"revision_id": "rev-b", "items": right_items},
        "normalizer": normalizer,
    }


def test_version_diff_categories():
    value = assert_ok(
        version_diff(
            diff_request(
                [
                    {"item_id": "A", "text": "alpha"},
                    {"item_id": "B", "text": "beta"},
                    {"item_id": "C", "text": "gamma"},
                ],
                [
                    {"item_id": "A", "text": "alpha"},
                    {"item_id": "B", "text": "beta 2"},
                    {"item_id": "D", "text": "delta"},
                ],
            )
        ),
        "version_diff",
    )
    assert value["left_revision"] == "rev-a"
    assert value["right_revision"] == "rev-b"
    assert value["same"] == [
        {
            "item_id": "A",
            "left_text": "alpha",
            "right_text": "alpha",
        }
    ]
    assert value["added"] == [{"item_id": "D", "text": "delta"}]
    assert value["removed"] == [{"item_id": "C", "text": "gamma"}]
    assert value["changed"] == [
        {
            "item_id": "B",
            "left_text": "beta",
            "right_text": "beta 2",
        }
    ]
    assert value["counts"] == {
        "left": 3,
        "right": 3,
        "same": 1,
        "added": 1,
        "removed": 1,
        "changed": 1,
    }


def test_version_diff_whitespace_normalizer():
    left_items = [{"item_id": "X", "text": "line   one\nline two"}]
    right_items = [{"item_id": "X", "text": "line one line two"}]
    exact = assert_ok(
        version_diff(diff_request(left_items, right_items, "exact")),
        "version_diff",
    )
    assert exact["same"] == []
    assert exact["changed"] == [
        {
            "item_id": "X",
            "left_text": "line   one\nline two",
            "right_text": "line one line two",
        }
    ]
    whitespace = assert_ok(
        version_diff(diff_request(left_items, right_items, "whitespace")),
        "version_diff",
    )
    assert whitespace["changed"] == []
    assert whitespace["same"] == [
        {
            "item_id": "X",
            "left_text": "line   one\nline two",
            "right_text": "line one line two",
        }
    ]


def test_version_diff_whitespace_same_keeps_both_texts():
    value = assert_ok(
        version_diff(
            diff_request(
                [{"item_id": "X", "text": "a  b\nc"}],
                [{"item_id": "X", "text": "a b c"}],
                "whitespace",
            )
        ),
        "version_diff",
    )
    assert value["changed"] == []
    assert value["same"] == [
        {
            "item_id": "X",
            "left_text": "a  b\nc",
            "right_text": "a b c",
        }
    ]


def test_version_diff_normalizer_defaults_to_exact():
    request = diff_request(
        [{"item_id": "X", "text": "line   one"}],
        [{"item_id": "X", "text": "line one"}],
    )
    del request["normalizer"]
    value = assert_ok(version_diff(request), "version_diff")
    assert value["normalizer"] == "exact"
    assert value["changed"] == [
        {
            "item_id": "X",
            "left_text": "line   one",
            "right_text": "line one",
        }
    ]


@pytest.mark.parametrize(
    "duplicated_side",
    ["left", "right"],
)
def test_version_diff_duplicate_item_id_refused(duplicated_side):
    request = diff_request(
        [{"item_id": "A", "text": "alpha"}],
        [{"item_id": "A", "text": "alpha"}],
    )
    request[duplicated_side]["items"].append(
        {"item_id": "A", "text": "duplicate"}
    )
    assert_refused(
        version_diff(request), "version_diff", "DUPLICATE_ALIGN_KEY"
    )


@pytest.mark.parametrize("normalizer", ["casefold", None])
def test_version_diff_bad_normalizer_refused(normalizer):
    request = diff_request([], [], normalizer)
    assert_refused(version_diff(request), "version_diff", "BAD_NORMALIZER")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_unknown_operator_exit_2(tmp_path, capsys):
    request = tmp_path / "req.json"
    request.write_text("{}", encoding="utf-8")
    assert (
        verify_cli.main(["--op", "nope", "--request", str(request)]) == 2
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused"
    assert payload["refusal"]["code"] == "UNKNOWN_OPERATOR"


def test_cli_refused_operator_still_exits_0(tmp_path, capsys):
    request = tmp_path / "req.json"
    request.write_text(
        '{"spec": "45-", "probe": 48}', encoding="utf-8"
    )
    code = verify_cli.main(
        ["--op", "port_range_membership", "--request", str(request)]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["refusal"]["code"] == "BAD_PORT_SPEC"


def test_cli_internal_error_is_json_not_traceback(
    tmp_path, capsys, monkeypatch
):
    request = tmp_path / "req.json"
    request.write_text("{}", encoding="utf-8")

    def boom(op, payload):
        raise RuntimeError("boom")

    monkeypatch.setattr(verify_cli, "run_operator", boom)
    code = verify_cli.main(
        ["--op", "set_enumeration", "--request", str(request)]
    )
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["refusal"]["code"] == "INTERNAL_ERROR"
    assert "RuntimeError" in payload["refusal"]["message"]


def test_cli_unreadable_request_file_exit_2(tmp_path, capsys):
    missing = tmp_path / "missing.json"
    code = verify_cli.main(
        ["--op", "set_enumeration", "--request", str(missing)]
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["refusal"]["code"] == "BAD_REQUEST_FILE"


def test_cli_bad_json_exit_2(tmp_path, capsys):
    request = tmp_path / "req.json"
    request.write_text("{not json", encoding="utf-8")
    code = verify_cli.main(
        ["--op", "set_enumeration", "--request", str(request)]
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["refusal"]["code"] == "BAD_REQUEST_JSON"


def test_cli_huge_json_number_exit_2_without_traceback(tmp_path, capsys):
    request = tmp_path / "req.json"
    request.write_text(
        '{"spec": "45-48", "probe": ' + "9" * 10000 + "}",
        encoding="utf-8",
    )
    code = verify_cli.main(
        ["--op", "port_range_membership", "--request", str(request)]
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["refusal"]["code"] == "BAD_REQUEST_JSON"
