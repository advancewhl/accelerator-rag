"""Read-only Archiver observation adapter (phase-3 extension, §8).

The Python side consumes an MCP-exported JSON document; it never opens a
network connection, writes an archive or triggers acquisition.  Every
observation keeps its requested window, strategy, bin size, point counts,
segment warnings and completeness flags, because a downsampled or truncated
return cannot support a claim about continuous physical state.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .schema import Atom, Needs, estimate_tokens, normalize_key


def _text(value: object) -> str:
    return "" if value is None else str(value)


@dataclass(frozen=True)
class Observation:
    probe: str
    pv: str
    start: str
    end: str
    strategy: str
    points: tuple[dict, ...]
    point_count: int
    in_range_point_count: int
    context_point_count: int
    data_state: str
    segments: tuple[dict, ...]
    source_ids: tuple[str, ...]
    bin_seconds: int | None
    downsampled: bool
    truncated: bool
    complete: bool
    warnings: tuple[str, ...]
    error: str
    unit: str = ""

    def limitations(self) -> tuple[str, ...]:
        items: list[str] = []
        if self.downsampled:
            items.append("downsampled：粗查询/降采样，不能声称连续物理状态")
        if self.truncated:
            items.append("truncated：归档返回被截断，仅保留返回部分")
        if self.context_point_count:
            items.append(
                f"context_points={self.context_point_count}：含窗口外上下文点，"
                "不计入窗口统计"
            )
        if self.data_state and self.data_state != "available":
            items.append(f"data_state={self.data_state}")
        if self.error:
            items.append(f"error={self.error}")
        for warning in self.warnings:
            items.append(f"warning={warning}")
        for segment in self.segments:
            for warning in segment.get("warnings", ()) or ():
                items.append(f"segment_warning={warning}")
            if segment.get("error"):
                items.append(f"segment_error={segment['error']}")
        if not self.unit:
            items.append("unit_unknown：返回本身未提供单位")
        return tuple(dict.fromkeys(items))

    def values(self) -> tuple[str, ...]:
        seen: list[str] = []
        for point in self.points:
            value = point.get("value")
            text = json.dumps(value, ensure_ascii=False)
            if text not in seen:
                seen.append(text)
        return tuple(seen)

    def within_window_points(self) -> int:
        return max(0, self.point_count - self.context_point_count)

    def summary(self) -> str:
        values = ",".join(self.values()[:12])
        return (
            f"PV={self.pv} window={self.start}..{self.end} "
            f"strategy={self.strategy} bin_seconds={self.bin_seconds} "
            f"points={self.point_count} in_range={self.in_range_point_count} "
            f"context={self.context_point_count} values={values} "
            f"complete={str(self.complete).lower()} "
            f"downsampled={str(self.downsampled).lower()} "
            f"truncated={str(self.truncated).lower()}"
        )

    def to_dict(self) -> dict:
        return {
            "probe": self.probe,
            "pv": self.pv,
            "start": self.start,
            "end": self.end,
            "strategy": self.strategy,
            "point_count": self.point_count,
            "in_range_point_count": self.in_range_point_count,
            "context_point_count": self.context_point_count,
            "data_state": self.data_state,
            "source_ids": list(self.source_ids),
            "bin_seconds": self.bin_seconds,
            "downsampled": self.downsampled,
            "truncated": self.truncated,
            "complete": self.complete,
            "warnings": list(self.warnings),
            "error": self.error,
            "unit": self.unit,
            "limitations": list(self.limitations()),
            "values": list(self.values()[:32]),
        }


@dataclass(frozen=True)
class ArchiverExport:
    captured_on: str
    timezone: str
    capabilities: dict
    health: dict
    sources: dict
    observations: tuple[Observation, ...]

    def to_dict(self) -> dict:
        return {
            "captured_on": self.captured_on,
            "timezone": self.timezone,
            "capabilities": self.capabilities,
            "health": self.health,
            "sources": self.sources,
            "observations": [item.to_dict() for item in self.observations],
        }


def _observation(probe: str, request: dict, result: dict) -> Observation:
    segments = tuple(result.get("segments", ()) or ())
    return Observation(
        probe=probe,
        pv=_text(result.get("pv")),
        start=_text(result.get("start") or request.get("start")),
        end=_text(result.get("end") or request.get("end")),
        strategy=_text(result.get("strategy") or request.get("strategy")),
        points=tuple(result.get("points", ()) or ()),
        point_count=int(result.get("point_count", 0) or 0),
        in_range_point_count=int(result.get("in_range_point_count", 0) or 0),
        context_point_count=int(result.get("context_point_count", 0) or 0),
        data_state=_text(result.get("data_state")),
        segments=segments,
        source_ids=tuple(result.get("source_ids", ()) or ()),
        bin_seconds=result.get("bin_seconds"),
        downsampled=bool(result.get("downsampled", False)),
        truncated=bool(result.get("truncated", False)),
        complete=bool(result.get("complete", False)),
        warnings=tuple(result.get("warnings", ()) or ()),
        error=_text(result.get("error")),
    )


def normalize_export(payload: dict) -> ArchiverExport:
    if not isinstance(payload, dict):
        raise ValueError("archiver export must be a JSON object")
    probes = payload.get("probes")
    if probes is None and "request" in payload and "response" in payload:
        probes = {"single": payload}
    if not isinstance(probes, dict) or not probes:
        raise ValueError("archiver export has no probes")
    observations: list[Observation] = []
    for name in sorted(probes):
        probe = probes[name]
        request = probe.get("request", {}) if isinstance(probe, dict) else {}
        response = probe.get("response", {}) if isinstance(probe, dict) else {}
        for result in response.get("results", ()) or ():
            observations.append(_observation(name, request, result))
    return ArchiverExport(
        captured_on=_text(payload.get("captured_on")),
        timezone=_text(payload.get("timezone")),
        capabilities=dict(payload.get("archiver", {}).get("capabilities", {}) or {}),
        health=dict(payload.get("archiver", {}).get("health", {}) or {}),
        sources=dict(payload.get("archiver", {}).get("sources", {}) or {}),
        observations=tuple(observations),
    )


def load_export(path: str | Path) -> ArchiverExport:
    return normalize_export(json.loads(Path(path).read_text(encoding="utf-8")))


def atom_for_observation(observation: Observation) -> Atom:
    limitations = observation.limitations()
    excerpt = observation.summary()
    return Atom(
        atom_id="A" + __import__("hashlib").sha256(
            f"{observation.probe}\x1f{excerpt}".encode("utf-8")
        ).hexdigest()[:20],
        chunk_id="",
        revision_id="external",
        locator_kind="external_observation",
        locator_label=f"{observation.pv}@{observation.start}",
        excerpt=excerpt,
        source_role="external_observation",
        evidence_role="external_observation",
        route="archiver",
        score=1.0,
        tokens=estimate_tokens(excerpt),
        external={
            "probe": observation.probe,
            "pv": observation.pv,
            "start": observation.start,
            "end": observation.end,
            "strategy": observation.strategy,
            "bin_seconds": observation.bin_seconds,
            "point_count": observation.point_count,
            "in_range_point_count": observation.in_range_point_count,
            "context_point_count": observation.context_point_count,
            "data_state": observation.data_state,
            "source_ids": list(observation.source_ids),
            "complete": observation.complete,
            "downsampled": observation.downsampled,
            "truncated": observation.truncated,
            "warnings": list(observation.warnings),
            "limitations": list(limitations),
            "unit": observation.unit,
        },
    )


def atoms_for_needs(
    export: ArchiverExport, needs: Needs
) -> tuple[Atom, ...]:
    """Only observations whose PV is named by the question enter a pack."""

    pvs = {
        normalize_key(item.raw)
        for item in needs.entities
        if item.kind == "pv"
    }
    if not pvs:
        return ()
    selected = [
        observation
        for observation in export.observations
        if normalize_key(observation.pv) in pvs
    ]
    return tuple(atom_for_observation(item) for item in selected)


class UnavailableArchiver:
    name = "archiver"
    available = False

    def atoms_for(self, needs: Needs) -> tuple[Atom, ...]:
        return ()


class StaticArchiver:
    name = "archiver"
    available = True

    def __init__(self, export: ArchiverExport):
        self.export = export

    def atoms_for(self, needs: Needs) -> tuple[Atom, ...]:
        return atoms_for_needs(self.export, needs)
