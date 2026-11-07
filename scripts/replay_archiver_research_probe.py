"""Replay the captured Archiver probe; no network, LLM or production changes.

This is a rule-based research baseline, not an autonomous diagnosis system.
It distinguishes a returned observation from an unsupported absence claim.
"""

import argparse
import json
from pathlib import Path

from pydantic import AwareDatetime, BaseModel


class Point(BaseModel):
    timestamp: AwareDatetime
    value: float


class Segment(BaseModel):
    source_id: str
    ok: bool
    warnings: list[str]


class Series(BaseModel):
    pv: str
    start: AwareDatetime
    end: AwareDatetime
    points: list[Point]
    in_range_point_count: int
    context_point_count: int
    bin_seconds: int
    downsampled: bool
    truncated: bool
    complete: bool
    data_state: str
    warnings: list[str]
    segments: list[Segment]


class Response(BaseModel):
    results: list[Series]
    warnings: list[str]


class Probe(BaseModel):
    response: Response


class Capture(BaseModel):
    captured_on: str
    probes: dict[str, Probe]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("reports/research-reset-20261107/archiver-probes.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/research-reset-20261107/probe-analysis.json"),
    )
    args = parser.parse_args()
    capture = Capture.model_validate_json(args.input.read_text(encoding="utf-8"))
    rows = []
    for name, probe in capture.probes.items():
        for series in probe.response.results:
            # All analysis uses [start, end); a leading context point is not
            # an observation inside this window.
            points = [
                p for p in series.points if series.start <= p.timestamp < series.end
            ]
            limitations = []
            if series.downsampled:
                limitations.append("downsampled")
            if series.truncated:
                limitations.append("truncated")
            if not series.complete or any(not s.ok for s in series.segments):
                limitations.append("incomplete_source_response")
            if not points:
                limitations.append("no_in_window_observations")
            warnings = [
                *probe.response.warnings,
                *series.warnings,
                *[w for segment in series.segments for w in segment.warnings],
            ]
            row = {
                "probe": name,
                "pv": series.pv,
                "in_window_points": len(points),
                "context_points_reported": series.context_point_count,
                "bin_seconds": series.bin_seconds,
                "complete": series.complete,
                "data_state": series.data_state,
                "limitations": limitations,
                "warnings": warnings,
                "source_ids": [s.source_id for s in series.segments],
                "physical_absence_certified": False,
            }
            if name.startswith("timing-"):
                witnesses = [p.timestamp.isoformat() for p in points if p.value == 20]
                row.update(
                    observed_values=sorted({p.value for p in points}),
                    target_value=20,
                    witness_timestamps=witnesses,
                    verdict=(
                        "observed_in_returned_archive"
                        if witnesses
                        else "not_observed_in_returned_points"
                    ),
                    next_action=(
                        "report_timestamped_observation"
                        if witnesses
                        else (
                            "refine_query_before_deciding_absence"
                            if limitations or warnings
                            else "report_archive_nonobservation_without_physical_absence"
                        )
                    ),
                )
            rows.append(row)
    output = {
        "capture_date": capture.captured_on,
        "analysis_window_semantics": "start inclusive, end exclusive",
        "scope": "three feasibility probes; not diagnostic accuracy or causal evidence",
        "rows": rows,
        "interpretation": [
            "complete describes returned source execution, not diagnostic sufficiency",
            "a leading context point does not establish an in-window observation",
            "the fine query can witness a recorded value that the coarse query omits",
            "unaggregated archive records do not prove continuous physical coverage",
            "coarse plus fine uses two calls and more returned points than fine alone",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
