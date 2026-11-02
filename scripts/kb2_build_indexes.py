#!/usr/bin/env python3
"""Build the two production dense indexes from a candidate chunk build.

Input is ``<build-dir>/chunks/*.json`` as written by
``scripts/kb2_candidate_build.py``.  Every file carries the audited ``chunks``
plus the ``eligible_chunk_ids`` and ``indexable_chunk_ids`` sets; only the
indexable set is embedded.  The build reads the chunks exactly once and passes
the same in-memory parent objects to both routes, so E5 and Qwen3 cannot drift
into different parent sets or text.

Everything is local: models must already exist on disk (the embedding adapter
is constructed with ``local_files_only=True``) and Qdrant runs in embedded
directory mode.  No network is used and no server credential is read or
written.  Pass the runtime-visible paths (for a container, its ``/workspace``
paths) to ``--output-root``/``--model-root``/``--e5-model``/``--qwen-model``:
the reports and generated ``rag-production.json`` copy those strings unchanged.

Example (GPU host)::

    python scripts/kb2_build_indexes.py \
        --build-dir data/knowledge-builds/<build-id> \
        --model-root /workspace/tmp/stage-two-models \
        --output-root /workspace/tmp/kb2-indexes/<build-id> \
        --e5-model intfloat--multilingual-e5-base \
        --qwen-model Qwen--Qwen3-Embedding-0.6B \
        --device cuda:0 --batch-size 16 \
        --write-config /workspace/tmp/kb2-indexes/<build-id>/rag-production.json

A dry run reads and validates the corpus, prints the plan, and writes nothing::

    python scripts/kb2_build_indexes.py --dry-run \
        --build-dir data/knowledge-builds/<build-id> \
        --output-root tmp/kb2-indexes/<build-id>

``--route`` defaults to ``both``.  A single route reuses the other route's
existing ``index-report.json`` (validated against this corpus and its local
index) and writes ``rag-production.json`` only when both reports are available.
Pass the same ``--build-dir`` and ``--output-root`` strings used for the
completed route; their ``<output-root>/<route>/index-report.json`` and
``qdrant/`` paths must match exactly.
After a GPU out-of-memory failure, continue only the failed route, for example::

    python scripts/kb2_build_indexes.py --route qwen3 --batch-size 2 \
        --build-dir data/knowledge-builds/<build-id> \
        --output-root /workspace/tmp/kb2-indexes/<build-id> \
        --qwen-model Qwen--Qwen3-Embedding-0.6B --device cuda:1 \
        --write-config /workspace/tmp/kb2-indexes/<build-id>/rag-production.json \
        --overwrite

``--resume`` skips re-embedding a selected route whose report matches the
current build ID, corpus hashes and freshly computed model/passage contracts.
``--resume`` and ``--overwrite`` are mutually exclusive.

``--device cpu`` is supported for both models (Qwen3 is forced to float32) but
is much slower; Qwen3 on a busy GPU should use ``--batch-size 1`` or ``2``.
The script never changes the device automatically.  OOM handling clears the
CUDA cache and reports the failed route while keeping completed route reports.

The script refuses to overwrite an existing candidate index directory, report
or output configuration unless ``--overwrite`` is explicit.  It never deletes a
published index and only writes under ``--output-root`` and ``--write-config``.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from accelerator_rag.domain.knowledge import KnowledgeChunk  # noqa: E402
from accelerator_rag.retrieval.index_contract import (  # noqa: E402
    DenseIndexContract,
    canonical_sha256,
)

E5_MODEL_NAME = "intfloat/multilingual-e5-base"
QWEN_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
ROUTE_SPECS = (
    {
        "key": "e5",
        "model_name": E5_MODEL_NAME,
        "argument": "e5_model",
        "suffix": "e5",
    },
    {
        "key": "qwen3",
        "model_name": QWEN_MODEL_NAME,
        "argument": "qwen_model",
        "suffix": "qwen3",
    },
)
INDEX_REPORT_NAME = "index-report.json"
BUILD_REPORT_NAME = "index-build-report.json"
REPORT_SCHEMA = "kb2-index-report-v1"
BUILD_REPORT_SCHEMA = "kb2-index-build-v1"
DEFAULT_CONFIG_TEMPLATE = ROOT / "config" / "rag-production.json"
DEFAULT_RERANKER_KEYS = ("model_path", "device", "dtype", "batch_size")
CREDENTIAL_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "authorization",
        "bearer",
        "password",
        "secret",
        "token",
    }
)

EmbedderFactory = Callable[..., Any]

REUSE_REPORT_FIELDS = (
    "build_id",
    "route",
    "model_name",
    "model_path",
    "index_path",
    "collection",
    "dense_index_contract_id",
    "passage_contract_id",
    "parent_count",
    "point_count",
    "embedded_passage_count",
    "parent_set_sha256",
    "parent_text_sha256",
    "parent_evidence_sha256",
    "device",
    "dtype",
    "batch_size",
)


class BuildInputError(ValueError):
    """The chunk build or requested configuration cannot be indexed safely."""


class BuildSafetyError(RuntimeError):
    """A requested output path already exists or is otherwise unsafe."""


class BuildOOMError(RuntimeError):
    """The selected route ran out of memory; completed routes are kept."""


@dataclass(frozen=True)
class Corpus:
    """The single in-memory parent corpus shared by both index routes."""

    parents: tuple[KnowledgeChunk, ...]
    document_ids: tuple[str, ...]
    by_document: Mapping[str, int]
    chunk_files: tuple[str, ...]
    total_chunks: int
    eligible_chunks: int
    indexable_chunks: int
    parent_set_sha256: str
    parent_text_sha256: str
    parent_evidence_sha256: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical_text_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _parent_hashes(parents: Sequence[KnowledgeChunk]) -> tuple[str, str, str]:
    ordered = sorted(parents, key=lambda chunk: chunk.chunk_id)
    return (
        canonical_sha256([chunk.chunk_id for chunk in ordered]),
        canonical_sha256(
            [[chunk.chunk_id, _canonical_text_sha256(chunk.text)] for chunk in ordered]
        ),
        canonical_sha256([asdict(chunk) for chunk in ordered]),
    )


def _id_list(payload: Mapping[str, Any], key: str, path: Path) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise BuildInputError(f"{path.name}: {key} must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise BuildInputError(f"{path.name}: {key} must contain nonempty strings")
    if len(set(value)) != len(value):
        raise BuildInputError(f"{path.name}: {key} contains duplicate IDs")
    return tuple(value)


def load_corpus(build_dir: Path) -> Corpus:
    """Read and validate ``chunks/*.json`` exactly once.

    Only ``indexable_chunk_ids`` become parents.  The caller later hands the
    same ``Corpus`` to both routes; no route re-parses a chunk file.
    """

    chunks_dir = build_dir / "chunks"
    if not chunks_dir.is_dir():
        raise BuildInputError(f"chunk directory not found: {chunks_dir}")
    files = sorted(chunks_dir.glob("*.json"))
    if not files:
        raise BuildInputError(f"empty corpus: no chunk files in {chunks_dir}")

    by_id: dict[str, KnowledgeChunk] = {}
    owner: dict[str, str] = {}
    indexable_ids: list[str] = []
    eligible_chunks = 0
    total_chunks = 0
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BuildInputError(f"{path.name}: unreadable chunk JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise BuildInputError(f"{path.name}: chunk JSON must be an object")
        document_id = payload.get("document_id")
        if (
            not isinstance(document_id, str)
            or not document_id.strip()
            or document_id != document_id.strip()
        ):
            raise BuildInputError(f"{path.name}: invalid document_id")
        revision_id = payload.get("revision_id")
        if revision_id is not None and revision_id != document_id:
            raise BuildInputError(
                f"{path.name}: revision_id {revision_id!r} differs from "
                f"document_id {document_id!r}"
            )
        raw_chunks = payload.get("chunks")
        if not isinstance(raw_chunks, list) or not raw_chunks:
            raise BuildInputError(f"{path.name}: chunks must be a nonempty list")
        eligible_ids = _id_list(payload, "eligible_chunk_ids", path)
        file_indexable = _id_list(payload, "indexable_chunk_ids", path)

        local_ids: list[str] = []
        for raw in raw_chunks:
            if not isinstance(raw, dict):
                raise BuildInputError(f"{path.name}: chunk entries must be objects")
            try:
                chunk = KnowledgeChunk(**raw)
            except (TypeError, ValueError) as exc:
                raise BuildInputError(f"{path.name}: invalid chunk: {exc}") from exc
            if chunk.document_id != document_id:
                raise BuildInputError(
                    f"{path.name}: chunk {chunk.chunk_id} document_id "
                    f"{chunk.document_id!r} differs from file document_id "
                    f"{document_id!r}"
                )
            if chunk.chunk_id in by_id:
                raise BuildInputError(
                    f"{path.name}: duplicate chunk ID {chunk.chunk_id} "
                    f"(already in {owner[chunk.chunk_id]})"
                )
            by_id[chunk.chunk_id] = chunk
            owner[chunk.chunk_id] = path.name
            local_ids.append(chunk.chunk_id)
        local_set = set(local_ids)
        unknown = sorted(set(eligible_ids) - local_set)
        if unknown:
            raise BuildInputError(
                f"{path.name}: eligible_chunk_ids not in chunks: {unknown[:5]}"
            )
        unknown = sorted(set(file_indexable) - local_set)
        if unknown:
            raise BuildInputError(
                f"{path.name}: indexable_chunk_ids not in chunks: {unknown[:5]}"
            )
        not_eligible = sorted(set(file_indexable) - set(eligible_ids))
        if not_eligible:
            raise BuildInputError(
                f"{path.name}: indexable IDs are not eligible: {not_eligible[:5]}"
            )
        indexable_ids.extend(file_indexable)
        eligible_chunks += len(eligible_ids)
        total_chunks += len(local_ids)

    if len(set(indexable_ids)) != len(indexable_ids):
        raise BuildInputError("duplicate chunk IDs across indexable_chunk_ids")
    if not indexable_ids:
        raise BuildInputError("empty corpus: no indexable chunks")

    parents = tuple(by_id[chunk_id] for chunk_id in indexable_ids)
    restricted = sorted(
        chunk.chunk_id for chunk in parents if chunk.access_scope == "restricted"
    )
    if restricted:
        raise BuildInputError(
            "restricted chunks must not be indexable: " + ", ".join(restricted[:5])
        )
    document_ids = tuple(sorted({chunk.document_id for chunk in parents}))
    by_document = {
        document_id: sum(chunk.document_id == document_id for chunk in parents)
        for document_id in document_ids
    }
    parent_set_sha256, parent_text_sha256, parent_evidence_sha256 = _parent_hashes(
        parents
    )
    return Corpus(
        parents=parents,
        document_ids=document_ids,
        by_document=by_document,
        chunk_files=tuple(path.name for path in files),
        total_chunks=total_chunks,
        eligible_chunks=eligible_chunks,
        indexable_chunks=len(parents),
        parent_set_sha256=parent_set_sha256,
        parent_text_sha256=parent_text_sha256,
        parent_evidence_sha256=parent_evidence_sha256,
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not slug:
        raise BuildInputError(
            f"build directory name cannot form a collection name: {value!r}"
        )
    if len(slug) > 72:
        slug = slug[:56] + "_" + sha256(value.encode("utf-8")).hexdigest()[:12]
    return slug


def _collection_name(build_id: str, suffix: str) -> str:
    return f"knowledge_{_slug(build_id)}_{suffix}"


def _resolve_model_path(model_root: Path | None, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    base = Path(model_root) if model_root is not None else Path.cwd()
    return base / path


def _load_template(path: Path) -> dict[str, Any]:
    if not path.exists():
        try:
            is_default = path.resolve() == DEFAULT_CONFIG_TEMPLATE.resolve()
        except OSError:
            is_default = False
        if is_default:
            return {}
        raise BuildInputError(f"config template not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildInputError(f"unreadable config template {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BuildInputError(f"config template must be a JSON object: {path}")
    return data


def _pick_setting(
    cli_value: str | None,
    template: Mapping[str, Any],
    key: str,
    flag: str,
) -> str:
    value = cli_value if cli_value is not None else template.get(key)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise BuildInputError(
            f"{key} must be a nonempty trimmed string; pass {flag} or provide "
            "a config template"
        )
    return value


def _check_model_base_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError as exc:
        raise BuildInputError(f"invalid model_base_url: {value!r}") from exc
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise BuildInputError(f"model_base_url must be an http(s) URL: {value!r}")
    if parsed.username is not None or parsed.password is not None:
        raise BuildInputError("model_base_url must not contain credentials")
    return value


def _clean_reranker(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BuildInputError("reranker configuration must be an object")
    unknown = sorted(set(value) - set(DEFAULT_RERANKER_KEYS))
    if unknown:
        raise BuildInputError(f"unsupported reranker configuration keys: {unknown}")
    model_path = value.get("model_path")
    if not isinstance(model_path, str) or not model_path.strip():
        raise BuildInputError("reranker.model_path must be a nonempty string")
    result: dict[str, Any] = {"model_path": model_path}
    if "device" in value:
        device = value["device"]
        if not isinstance(device, str) or not device.strip():
            raise BuildInputError("reranker.device must be a nonempty string")
        result["device"] = device
    if "dtype" in value:
        dtype = value["dtype"]
        if dtype not in {"auto", "float32", "float16", "bfloat16"}:
            raise BuildInputError(f"unsupported reranker dtype: {dtype!r}")
        result["dtype"] = dtype
    if "batch_size" in value:
        batch_size = value["batch_size"]
        if type(batch_size) is not int or batch_size <= 0:
            raise BuildInputError("reranker.batch_size must be a positive integer")
        result["batch_size"] = batch_size
    return result


def _resolve_settings(
    args: argparse.Namespace, template: Mapping[str, Any]
) -> dict[str, Any]:
    model_base_url = _check_model_base_url(
        _pick_setting(
            args.model_base_url, template, "model_base_url", "--model-base-url"
        )
    )
    model_name = _pick_setting(args.model_name, template, "model_name", "--model-name")
    trace_dir = _pick_setting(args.trace_dir, template, "trace_dir", "--trace-dir")
    source_root = _pick_setting(
        args.source_root, template, "source_root", "--source-root"
    )
    if args.reranker_config is not None:
        try:
            reranker = json.loads(args.reranker_config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BuildInputError(
                f"unreadable reranker config {args.reranker_config}: {exc}"
            ) from exc
    elif "reranker" in template:
        reranker = template["reranker"]
    else:
        raise BuildInputError(
            "missing reranker configuration: pass --reranker-config or "
            "provide a config template"
        )
    generation_max_tokens = args.generation_max_tokens
    if generation_max_tokens is None:
        generation_max_tokens = template.get("generation_max_tokens")
    if generation_max_tokens is not None and (
        type(generation_max_tokens) is not int or not 1 <= generation_max_tokens <= 4096
    ):
        raise BuildInputError("generation_max_tokens must be an integer in 1..4096")
    return {
        "model_base_url": model_base_url,
        "model_name": model_name,
        "reranker": _clean_reranker(reranker),
        "trace_dir": trace_dir,
        "source_root": source_root,
        "generation_max_tokens": generation_max_tokens,
    }


def _index_entry(report: Mapping[str, Any]) -> dict[str, Any]:
    contract_id = report.get("dense_index_contract_id")
    if not isinstance(contract_id, str) or not re.fullmatch(
        r"[0-9a-f]{64}", contract_id
    ):
        raise BuildInputError("index report has no valid dense_index_contract_id")
    point_count = report.get("point_count")
    if type(point_count) is not int or point_count <= 0:
        raise BuildInputError("index report has no positive point_count")
    entry = {
        "model_name": report.get("model_name"),
        "model_path": report.get("model_path"),
        "index_path": report.get("index_path"),
        "collection": report.get("collection"),
        "dense_index_contract_id": contract_id,
        "point_count": point_count,
        "device": report.get("device"),
        "dtype": report.get("dtype"),
    }
    for key in (
        "model_name",
        "model_path",
        "index_path",
        "collection",
        "device",
        "dtype",
    ):
        value = entry[key]
        if not isinstance(value, str) or not value.strip():
            raise BuildInputError(f"index report has no valid {key}")
    return entry


def _reject_credentials(value: Any, path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in CREDENTIAL_KEYS:
                raise BuildInputError(
                    f"refusing to write credential-like key: {path}{key}"
                )
            _reject_credentials(item, f"{path}{key}.")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_credentials(item, f"{path}[{index}].")


def build_production_config(
    reports: Sequence[Mapping[str, Any]],
    *,
    model_base_url: str,
    model_name: str,
    reranker: Mapping[str, Any],
    trace_dir: str,
    source_root: str,
    generation_max_tokens: int | None = None,
) -> dict[str, Any]:
    """Render a ``rag-production.json`` from the two successful route reports."""

    if [report.get("route") for report in reports] != ["e5", "qwen3"]:
        raise BuildInputError("index reports must be ordered e5 then qwen3")
    if [report.get("model_name") for report in reports] != [
        E5_MODEL_NAME,
        QWEN_MODEL_NAME,
    ]:
        raise BuildInputError("index reports do not use the frozen model order")
    for value, key in (
        (model_name, "model_name"),
        (trace_dir, "trace_dir"),
        (source_root, "source_root"),
    ):
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise BuildInputError(f"{key} must be a nonempty trimmed string")
    config: dict[str, Any] = {
        "model_base_url": _check_model_base_url(model_base_url),
        "model_name": model_name,
        "indexes": [_index_entry(report) for report in reports],
        "reranker": _clean_reranker(reranker),
    }
    if generation_max_tokens is not None:
        if (
            type(generation_max_tokens) is not int
            or not 1 <= generation_max_tokens <= 4096
        ):
            raise BuildInputError("generation_max_tokens must be an integer in 1..4096")
        config["generation_max_tokens"] = generation_max_tokens
    config["trace_dir"] = trace_dir
    config["source_root"] = source_root
    _reject_credentials(config)
    return config


def _write_json(path: Path, value: Any, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise BuildSafetyError(
            f"refusing to overwrite existing report {path}; use --overwrite"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_config(path: Path, config: Mapping[str, Any], *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise BuildSafetyError(
            f"refusing to overwrite existing config {path}; use --overwrite"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _preflight(
    args: argparse.Namespace,
    selected_plans: Sequence[Mapping[str, Any]],
    config_path: Path,
) -> None:
    output_root = args.output_root
    if output_root.exists() and not output_root.is_dir():
        raise BuildSafetyError(f"--output-root is not a directory: {output_root}")
    for plan in selected_plans:
        target = plan["index_root"]
        if target.exists() and not target.is_dir():
            raise BuildSafetyError(f"index target is not a directory: {target}")
        reusable_report = (target / INDEX_REPORT_NAME).is_file()
        allowed = args.overwrite or (args.resume and reusable_report)
        if target.exists() and any(target.iterdir()) and not allowed:
            raise BuildSafetyError(
                f"refusing to overwrite existing index directory {target}; "
                "use --overwrite, or --resume with an existing index-report.json"
            )
    build_report = output_root / BUILD_REPORT_NAME
    if build_report.exists() and not (args.overwrite or args.resume):
        raise BuildSafetyError(
            f"refusing to overwrite existing build report {build_report}; "
            "use --overwrite or --resume"
        )
    if config_path.exists() and not args.overwrite:
        raise BuildSafetyError(
            f"refusing to overwrite existing config {config_path}; use --overwrite"
        )


def _plan_routes(args: argparse.Namespace, build_id: str) -> list[dict[str, Any]]:
    plans = []
    for spec in ROUTE_SPECS:
        value = getattr(args, spec["argument"])
        model_path = (
            _resolve_model_path(args.model_root, value) if value is not None else None
        )
        index_root = args.output_root / spec["key"]
        plans.append(
            {
                "route": spec["key"],
                "model_name": spec["model_name"],
                "model_path": str(model_path) if model_path is not None else None,
                "index_root": index_root,
                "index_path": index_root / "qdrant",
                "collection": _collection_name(build_id, spec["suffix"]),
            }
        )
    return plans


def load_embedding_model(
    *,
    model_name: str,
    model_path: str,
    device: str,
    dtype: str,
    batch_size: int,
):
    """Production model loader; kept injectable so tests never load weights."""

    from accelerator_rag.embedding import EmbeddingModel

    path = Path(model_path)
    if not path.is_dir():
        raise BuildInputError(f"model directory not found: {path}")
    return EmbeddingModel(
        model_name,
        model_path=str(path),
        device=device,
        dtype=dtype,
        batch_size=batch_size,
    )


def _selected_specs(route_mode: str) -> tuple[Mapping[str, Any], ...]:
    if route_mode == "both":
        return ROUTE_SPECS
    return tuple(spec for spec in ROUTE_SPECS if spec["key"] == route_mode)


def _read_route_report(plan: Mapping[str, Any]) -> dict[str, Any] | None:
    path = plan["index_root"] / INDEX_REPORT_NAME
    if not path.is_file():
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildInputError(f"unreadable existing report {path}: {exc}") from exc
    if not isinstance(report, dict):
        raise BuildInputError(f"existing report must be a JSON object: {path}")
    return report


def _load_route_identity(
    plan: Mapping[str, Any],
    *,
    device: str,
    dtype: str,
    batch_size: int,
    embedder_factory: EmbedderFactory,
) -> dict[str, Any]:
    from accelerator_rag.retrieval.passages import PassageBuilder

    started = perf_counter()
    embedder = embedder_factory(
        model_name=plan["model_name"],
        model_path=plan["model_path"],
        device=device,
        dtype=dtype,
        batch_size=batch_size,
    )
    model_load_seconds = perf_counter() - started
    builder = PassageBuilder(embedder)
    fingerprint = embedder.fingerprint()
    contract = DenseIndexContract.from_fingerprint(fingerprint, builder.contract)
    if contract.requested_model_name != plan["model_name"]:
        raise BuildInputError(
            f"loaded embedder identity {contract.requested_model_name!r} differs "
            f"from route model {plan['model_name']!r}"
        )
    return {
        "embedder": embedder,
        "builder": builder,
        "fingerprint": fingerprint,
        "contract": contract,
        "started": started,
        "model_load_seconds": model_load_seconds,
    }


def _verify_reused_index(
    plan: Mapping[str, Any], report: Mapping[str, Any]
) -> set[str]:
    """Read-only check that the reported index still holds the reported points."""

    from qdrant_client import QdrantClient

    from accelerator_rag.retrieval.passages import PASSAGE_ALGORITHM

    path = plan["index_path"]
    if not (path / "meta.json").is_file():
        raise BuildInputError(
            f"cannot reuse {plan['route']}: local index is missing at {path}; "
            "rerun with --overwrite to rebuild this route"
        )
    contract_id = report["dense_index_contract_id"]
    point_count = report["point_count"]
    parent_ids: set[str] = set()
    client = QdrantClient(path=str(path))
    try:
        if not client.collection_exists(plan["collection"]):
            raise BuildInputError(
                f"cannot reuse {plan['route']}: collection "
                f"{plan['collection']!r} is missing; rerun with --overwrite"
            )
        count = client.count(plan["collection"], exact=True).count
        offset = None
        while True:
            records, offset = client.scroll(
                plan["collection"],
                limit=256,
                offset=offset,
                with_payload=[
                    "parent_chunk_id",
                    "payload_type",
                    "dense_index_contract_id",
                ],
                with_vectors=False,
            )
            for record in records:
                payload = record.payload or {}
                parent_id = payload.get("parent_chunk_id")
                if (
                    not isinstance(parent_id, str)
                    or payload.get("payload_type") != PASSAGE_ALGORITHM
                    or payload.get("dense_index_contract_id") != contract_id
                ):
                    raise BuildInputError(
                        f"cannot reuse {plan['route']}: index payloads are "
                        "unsigned, use another contract, or are not passages; "
                        "rerun with --overwrite"
                    )
                parent_ids.add(parent_id)
            if offset is None:
                break
    finally:
        client.close()
    if count != point_count:
        raise BuildInputError(
            f"cannot reuse {plan['route']}: Qdrant point count {count} differs "
            f"from report point_count {point_count}; rerun with --overwrite"
        )
    return parent_ids


def _validate_reused_report(
    report: Mapping[str, Any],
    *,
    corpus: Corpus,
    plan: Mapping[str, Any],
    build_id: str,
    contract: DenseIndexContract | None = None,
) -> None:
    missing = [field for field in REUSE_REPORT_FIELDS if field not in report]
    if missing:
        raise BuildInputError(
            f"cannot reuse {plan['route']}: index report lacks {missing}; "
            "rerun with --overwrite to rebuild this route"
        )
    expected = {
        "build_id": build_id,
        "route": plan["route"],
        "model_name": plan["model_name"],
        "collection": plan["collection"],
        "index_path": str(plan["index_path"]),
        "parent_count": corpus.indexable_chunks,
        "parent_set_sha256": corpus.parent_set_sha256,
        "parent_text_sha256": corpus.parent_text_sha256,
        "parent_evidence_sha256": corpus.parent_evidence_sha256,
    }
    mismatched = [
        field for field, value in expected.items() if report.get(field) != value
    ]
    if contract is not None:
        for field, value in (
            ("dense_index_contract_id", contract.contract_id),
            ("passage_contract_id", contract.passage_contract_id),
            ("model_name", contract.requested_model_name),
        ):
            if report.get(field) != value:
                mismatched.append(field)
    if mismatched:
        raise BuildInputError(
            f"{plan['route']} index report does not match the current "
            f"corpus/model ({', '.join(sorted(set(mismatched)))}); rerun with "
            f"--overwrite to rebuild {plan['route']} explicitly"
        )
    point_count = report["point_count"]
    embedded = report["embedded_passage_count"]
    if type(point_count) is not int or point_count <= 0 or point_count != embedded:
        raise BuildInputError(
            f"cannot reuse {plan['route']}: invalid point/embedded counts; "
            "rerun with --overwrite to rebuild this route"
        )
    for field in ("dense_index_contract_id", "passage_contract_id"):
        if not isinstance(report[field], str) or not re.fullmatch(
            r"[0-9a-f]{64}", report[field]
        ):
            raise BuildInputError(
                f"cannot reuse {plan['route']}: invalid {field}; rerun with "
                "--overwrite to rebuild this route"
            )
    if not isinstance(report["model_path"], str) or not report["model_path"].strip():
        raise BuildInputError(f"cannot reuse {plan['route']}: invalid model_path")
    if not isinstance(report["device"], str) or not report["device"].strip():
        raise BuildInputError(f"cannot reuse {plan['route']}: invalid device")
    if report["dtype"] not in {"float32", "float16", "bfloat16"}:
        raise BuildInputError(f"cannot reuse {plan['route']}: invalid dtype")
    if type(report["batch_size"]) is not int or report["batch_size"] <= 0:
        raise BuildInputError(f"cannot reuse {plan['route']}: invalid batch_size")
    parent_ids = _verify_reused_index(plan, report)
    expected_ids = {chunk.chunk_id for chunk in corpus.parents}
    if parent_ids != expected_ids:
        missing_ids = sorted(expected_ids - parent_ids)[:5]
        extra_ids = sorted(parent_ids - expected_ids)[:5]
        raise BuildInputError(
            f"cannot reuse {plan['route']}: indexed parent set differs from the "
            f"current corpus; missing={missing_ids} extra={extra_ids}; rerun "
            "with --overwrite to rebuild this route"
        )


def _normalized_reused_report(
    report: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    contract_rechecked: bool,
    model_path: str | None = None,
    device: str | None = None,
    dtype: str | None = None,
) -> dict[str, Any]:
    normalized = dict(report)
    if model_path is not None:
        normalized["model_path"] = model_path
    normalized["index_path"] = str(plan["index_path"])
    normalized["collection"] = plan["collection"]
    if device is not None:
        normalized["device"] = device
    if dtype is not None:
        normalized["dtype"] = dtype
    normalized["reused"] = True
    normalized["contract_rechecked"] = contract_rechecked
    return normalized


def _is_oom_error(exc: BaseException) -> bool:
    try:
        import torch

        oom_type = getattr(torch, "OutOfMemoryError", None)
        if oom_type is not None and isinstance(exc, oom_type):
            return True
    except ImportError:
        pass
    # Historical torch releases raised RuntimeError("CUDA out of memory").
    return isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower()


def _clear_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        # Cache cleanup must never mask the original OOM error.
        pass


def _oom_error(
    route: str, device: str, batch_size: int, exc: BaseException
) -> BuildOOMError:
    return BuildOOMError(
        f"out of memory while building {route} on device {device!r} with "
        f"batch_size={batch_size}. Completed route reports were kept and "
        "rag-production.json was not written. Lower --batch-size (Qwen3 "
        "production: 1 or 2), use a GPU with free memory (for example "
        "--device cuda:1), or use --device cpu (supported but slow, float32). "
        f"Rerun with --route {route} --batch-size 2 --overwrite. "
        f"Original error: {exc}"
    )


def _build_route(
    corpus: Corpus,
    *,
    plan: Mapping[str, Any],
    identity: Mapping[str, Any],
    device: str,
    dtype: str,
    batch_size: int,
    overwrite: bool,
    build_id: str,
) -> dict[str, Any]:
    from qdrant_client import QdrantClient

    from accelerator_rag.retrieval.dense import DenseRetriever
    from accelerator_rag.storage.qdrant_passages import QdrantPassageStore

    started = identity["started"]
    model_load_seconds = identity["model_load_seconds"]
    embedder = identity["embedder"]
    builder = identity["builder"]
    fingerprint = identity["fingerprint"]
    contract = identity["contract"]

    # Build every passage before opening the collection so a token-budget
    # failure cannot leave a half-written candidate index.
    passages = builder.build(corpus.parents)
    plan["index_root"].mkdir(parents=True, exist_ok=True)
    qdrant_path = plan["index_path"]
    qdrant_path.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(qdrant_path))
    try:
        if client.collection_exists(plan["collection"]):
            if not overwrite:
                raise BuildSafetyError(
                    f"refusing to overwrite existing collection "
                    f"{plan['collection']!r} in {qdrant_path}; use --overwrite"
                )
            client.delete_collection(plan["collection"])
        store = QdrantPassageStore(client, plan["collection"], contract)
        dense = DenseRetriever(embedder, store, passage_builder=builder)
        result = dense.index_corpus(
            corpus.parents,
            document_ids=list(corpus.document_ids),
            batch_size=batch_size,
            passages=passages,
        )
        if result["embedded_passage_count"] != len(passages):
            raise RuntimeError(
                "embedded passage count differs from built passages: "
                f"{result['embedded_passage_count']} != {len(passages)}"
            )
        if result["point_count"] != result["embedded_passage_count"]:
            raise RuntimeError(
                "Qdrant point count differs from embedded passages: "
                f"{result['point_count']} != {result['embedded_passage_count']}"
            )
        store.freeze_read_only()
        point_count = store.point_count()
        verification_started = perf_counter()
        written = list(store.all_passages())
        verification_seconds = perf_counter() - verification_started
        expected_ids = {chunk.chunk_id for chunk in corpus.parents}
        if len(written) != len(passages):
            raise RuntimeError(
                f"written passage count {len(written)} differs from "
                f"built passages {len(passages)}"
            )
        written_ids = {passage.parent_chunk_id for passage in written}
        if written_ids != expected_ids:
            missing = sorted(expected_ids - written_ids)[:5]
            extra = sorted(written_ids - expected_ids)[:5]
            raise RuntimeError(
                f"indexed parent set differs from input; missing={missing} "
                f"extra={extra}"
            )
        parents_by_id = {chunk.chunk_id: chunk for chunk in corpus.parents}
        for passage in written:
            if passage.parent != parents_by_id[passage.parent_chunk_id]:
                raise RuntimeError(
                    "indexed parent evidence differs from input: "
                    f"{passage.parent_chunk_id}"
                )
        if point_count != len(passages):
            raise RuntimeError(
                f"Qdrant point count {point_count} differs from "
                f"built passages {len(passages)}"
            )
    finally:
        client.close()
    if not (qdrant_path / "meta.json").is_file():
        raise RuntimeError(f"Qdrant did not create a local index at {qdrant_path}")

    return {
        "schema": REPORT_SCHEMA,
        "route": plan["route"],
        "build_id": build_id,
        "reused": False,
        "contract_rechecked": True,
        "model_name": plan["model_name"],
        "model_path": plan["model_path"],
        "index_path": str(qdrant_path),
        "collection": plan["collection"],
        "dense_index_contract_id": contract.contract_id,
        "passage_contract_id": contract.passage_contract_id,
        "parent_count": len(corpus.parents),
        "document_count": len(corpus.document_ids),
        "indexable_chunk_count": corpus.indexable_chunks,
        "passage_count": len(passages),
        "embedded_passage_count": result["embedded_passage_count"],
        "point_count": point_count,
        "parent_set_sha256": corpus.parent_set_sha256,
        "parent_text_sha256": corpus.parent_text_sha256,
        "parent_evidence_sha256": corpus.parent_evidence_sha256,
        "build_seconds": round(perf_counter() - started, 3),
        "model_load_seconds": round(model_load_seconds, 3),
        "embedding_seconds": round(result["embedding_seconds"], 3),
        "qdrant_indexing_seconds": round(result["qdrant_indexing_seconds"], 3),
        "verification_seconds": round(verification_seconds, 3),
        "device": device,
        "dtype": dtype,
        "batch_size": batch_size,
        "model_fingerprint": {
            "requested_model_name": fingerprint["requested_model_name"],
            "weights_manifest_sha256": fingerprint["weights_manifest_sha256"],
            "model_config_sha256": fingerprint["model_config_sha256"],
            "tokenizer_sha256": fingerprint["tokenizer_sha256"],
            "dimension": fingerprint["dimension"],
            "max_seq_length": fingerprint["max_seq_length"],
        },
        "created_at": _now(),
    }


def _assert_consistency(
    corpus: Corpus, reports: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    if [report["route"] for report in reports] != ["e5", "qwen3"]:
        raise RuntimeError("index reports are not ordered e5 then qwen3")
    for field in (
        "parent_set_sha256",
        "parent_text_sha256",
        "parent_evidence_sha256",
    ):
        values = {report[field] for report in reports}
        if len(values) != 1 or values.pop() != getattr(corpus, field):
            raise RuntimeError(f"index routes disagree on {field}")
    for report in reports:
        if report["parent_count"] != corpus.indexable_chunks:
            raise RuntimeError(
                f"{report['route']} parent count {report['parent_count']} "
                f"differs from corpus {corpus.indexable_chunks}"
            )
        if report["point_count"] != report["embedded_passage_count"]:
            raise RuntimeError(f"{report['route']} point count mismatch")
    return {
        "same_parent_set": True,
        "same_parent_text": True,
        "same_parent_evidence": True,
        "parent_count": corpus.indexable_chunks,
        "parent_set_sha256": corpus.parent_set_sha256,
        "parent_text_sha256": corpus.parent_text_sha256,
        "parent_evidence_sha256": corpus.parent_evidence_sha256,
        "point_counts_match_embedded": True,
    }


def _corpus_summary(corpus: Corpus) -> dict[str, Any]:
    return {
        "chunk_files": len(corpus.chunk_files),
        "total_chunks": corpus.total_chunks,
        "eligible_chunks": corpus.eligible_chunks,
        "indexable_chunks": corpus.indexable_chunks,
        "document_count": len(corpus.document_ids),
        "by_document": dict(corpus.by_document),
        "parent_set_sha256": corpus.parent_set_sha256,
        "parent_text_sha256": corpus.parent_text_sha256,
        "parent_evidence_sha256": corpus.parent_evidence_sha256,
    }


def _reuse_parents_summary(args: argparse.Namespace) -> dict[str, Any]:
    if not args.reuse_parents:
        return {"requested": False, "applied": False}
    return {
        "requested": True,
        "applied": False,
        "reason": ("not implemented in this version; every parent passage was rebuilt"),
    }


def _validate_args(args: argparse.Namespace) -> None:
    if not isinstance(args.device, str) or not args.device.strip():
        raise BuildInputError("--device must be a nonempty string")
    if type(args.batch_size) is not int or args.batch_size <= 0:
        raise BuildInputError("--batch-size must be a positive integer")
    if args.dtype not in {"float32", "float16", "bfloat16"}:
        raise BuildInputError(f"unsupported dtype: {args.dtype!r}")
    if args.resume and args.overwrite:
        raise BuildInputError(
            "--resume reuses valid reports; --overwrite rebuilds selected "
            "routes. Choose one"
        )
    if args.dry_run:
        return
    for spec in _selected_specs(args.route):
        if getattr(args, spec["argument"]) is None:
            raise BuildInputError(
                f"--{spec['argument'].replace('_', '-')} is required for "
                f"--route {args.route}"
            )
    if args.write_config is None:
        raise BuildInputError("--write-config is required for a real build")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument(
        "--model-root",
        type=Path,
        default=None,
        help="base directory for relative --e5-model/--qwen-model paths",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--route",
        choices=("e5", "qwen3", "both"),
        default="both",
        help="build one route or both; a single route reuses the other report",
    )
    parser.add_argument("--e5-model", default=None)
    parser.add_argument("--qwen-model", default=None)
    parser.add_argument(
        "--device",
        default="cpu",
        help=(
            "torch device such as cpu or cuda:0; cpu is supported for both "
            "models (Qwen3 uses float32) but is much slower"
        ),
    )
    parser.add_argument(
        "--dtype", choices=("float32", "float16", "bfloat16"), default="float32"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="passages per embedding batch; Qwen3 on a busy GPU uses 1 or 2",
    )
    parser.add_argument("--write-config", type=Path, default=None)
    parser.add_argument("--config-template", type=Path, default=DEFAULT_CONFIG_TEMPLATE)
    parser.add_argument("--reranker-config", type=Path, default=None)
    parser.add_argument("--model-base-url", default=None)
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--trace-dir", default=None)
    parser.add_argument("--source-root", default=None)
    parser.add_argument("--generation-max-tokens", type=int, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print corpus statistics; write nothing",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "rebuild selected routes, replacing only their candidate "
            "collections/directories under --output-root"
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "reuse a selected route's existing index-report.json after "
            "validating build ID, corpus hashes, passage/vector contracts and "
            "the local index; never re-embeds a reused route"
        ),
    )
    parser.add_argument(
        "--reuse-parents",
        action="store_true",
        help="accepted for forward compatibility; this version rebuilds all passages",
    )
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    *,
    embedder_factory: EmbedderFactory | None = None,
) -> int:
    args = parse_args(argv)
    _validate_args(args)
    build_dir = args.build_dir
    if not build_dir.is_dir():
        raise BuildInputError(f"build directory not found: {build_dir}")
    build_id = build_dir.name
    if not build_id:
        raise BuildInputError(f"cannot derive a build ID from {build_dir}")
    corpus = load_corpus(build_dir)
    plans = _plan_routes(args, build_id)
    selected_keys = {spec["key"] for spec in _selected_specs(args.route)}
    selected_plans = [plan for plan in plans if plan["route"] in selected_keys]

    if args.dry_run:
        existing = [
            str(plan["index_root"]) for plan in plans if plan["index_root"].exists()
        ]
        if args.write_config is not None and args.write_config.exists():
            existing.append(str(args.write_config))
        summary = {
            "dry_run": True,
            "writes": False,
            "build_id": build_id,
            "build_dir": str(build_dir),
            "output_root": str(args.output_root),
            "route": args.route,
            "resume": args.resume,
            "corpus": _corpus_summary(corpus),
            "planned_routes": [
                {
                    "route": plan["route"],
                    "selected": plan["route"] in selected_keys,
                    "model_name": plan["model_name"],
                    "model_path": plan["model_path"],
                    "collection": plan["collection"],
                    "index_path": str(plan["index_path"]),
                    "report_present": (
                        plan["index_root"] / INDEX_REPORT_NAME
                    ).is_file(),
                }
                for plan in plans
            ],
            "existing_outputs": existing,
            "reuse_parents": _reuse_parents_summary(args),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    template = _load_template(args.config_template)
    settings = _resolve_settings(args, template)
    _preflight(args, selected_plans, args.write_config)
    factory = embedder_factory or load_embedding_model
    reports: dict[str, dict[str, Any]] = {}
    reuse_notes: dict[str, dict[str, Any]] = {}
    companion_errors: list[str] = []

    # Unselected routes are never built or rewritten.  Their reports are
    # validated against the current corpus and local index so a single-route
    # rebuild can still produce a complete two-route configuration.
    for plan in plans:
        if plan["route"] in selected_keys:
            continue
        try:
            existing = _read_route_report(plan)
            if existing is None:
                raise BuildInputError(
                    f"no reusable report for {plan['route']}: "
                    f"{plan['index_root'] / INDEX_REPORT_NAME} is missing"
                )
            _validate_reused_report(
                existing, corpus=corpus, plan=plan, build_id=build_id
            )
        except BuildInputError as exc:
            companion_errors.append(str(exc))
            continue
        reports[plan["route"]] = _normalized_reused_report(
            existing, plan, contract_rechecked=False
        )
        reuse_notes[plan["route"]] = {
            "reused": True,
            "contract_rechecked": False,
            "source": INDEX_REPORT_NAME,
        }

    for plan in selected_plans:
        route = plan["route"]
        try:
            identity = _load_route_identity(
                plan,
                device=args.device,
                dtype=args.dtype,
                batch_size=args.batch_size,
                embedder_factory=factory,
            )
            existing = _read_route_report(plan) if args.resume else None
            if existing is not None:
                _validate_reused_report(
                    existing,
                    corpus=corpus,
                    plan=plan,
                    build_id=build_id,
                    contract=identity["contract"],
                )
                report = _normalized_reused_report(
                    existing,
                    plan,
                    contract_rechecked=True,
                    model_path=plan["model_path"],
                    device=args.device,
                    dtype=args.dtype,
                )
                reuse_notes[route] = {
                    "reused": True,
                    "contract_rechecked": True,
                    "source": INDEX_REPORT_NAME,
                }
            else:
                report = _build_route(
                    corpus,
                    plan=plan,
                    identity=identity,
                    device=args.device,
                    dtype=args.dtype,
                    batch_size=args.batch_size,
                    overwrite=args.overwrite,
                    build_id=build_id,
                )
                _write_json(
                    plan["index_root"] / INDEX_REPORT_NAME,
                    report,
                    overwrite=args.overwrite,
                )
                reuse_notes[route] = {
                    "reused": False,
                    "contract_rechecked": True,
                    "source": "built",
                }
        except Exception as exc:
            if not _is_oom_error(exc):
                raise
            _clear_cuda_cache()
            raise _oom_error(route, args.device, args.batch_size, exc) from exc
        reports[route] = report
        # Release this route's model before the next route loads; otherwise the
        # previous embedder can still occupy GPU memory during the second load.
        del identity
        if args.device.lower().startswith("cuda"):
            _clear_cuda_cache()

    missing = [route for route in ("e5", "qwen3") if route not in reports]
    if missing:
        print(
            json.dumps(
                {
                    "build_id": build_id,
                    "output_root": str(args.output_root),
                    "config_written": False,
                    "selected_routes": [plan["route"] for plan in selected_plans],
                    "available_routes": sorted(reports),
                    "missing_routes": missing,
                    "errors": companion_errors,
                    "next": (
                        "Both route reports must exist and match this build "
                        "before rag-production.json can be written. Build the "
                        "missing route with --route <route> and rerun."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    ordered_reports = [reports["e5"], reports["qwen3"]]
    consistency = _assert_consistency(corpus, ordered_reports)
    config = build_production_config(
        ordered_reports,
        model_base_url=settings["model_base_url"],
        model_name=settings["model_name"],
        reranker=settings["reranker"],
        trace_dir=settings["trace_dir"],
        source_root=settings["source_root"],
        generation_max_tokens=settings["generation_max_tokens"],
    )
    _write_config(args.write_config, config, overwrite=args.overwrite)

    warnings: list[str] = []
    if args.reuse_parents:
        warnings.append(
            "--reuse-parents is not implemented in this version; every parent "
            "passage was rebuilt"
        )
    route_summaries = [
        {
            key: report.get(key)
            for key in (
                "route",
                "model_name",
                "model_path",
                "index_path",
                "collection",
                "dense_index_contract_id",
                "parent_count",
                "passage_count",
                "point_count",
                "build_seconds",
            )
        }
        | {
            "reused": reuse_notes[report["route"]]["reused"],
            "contract_rechecked": reuse_notes[report["route"]]["contract_rechecked"],
        }
        for report in ordered_reports
    ]
    build_report = {
        "schema": BUILD_REPORT_SCHEMA,
        "build_id": build_id,
        "build_dir": str(build_dir),
        "output_root": str(args.output_root),
        "config_path": str(args.write_config),
        "created_at": _now(),
        "route": args.route,
        "resume": args.resume,
        "device": args.device,
        "dtype": args.dtype,
        "batch_size": args.batch_size,
        "model_root": str(args.model_root) if args.model_root is not None else None,
        "corpus": _corpus_summary(corpus),
        "routes": route_summaries,
        "reuse_notes": reuse_notes,
        "consistency": consistency,
        "reuse_parents": _reuse_parents_summary(args),
        "warnings": warnings,
    }
    _write_json(
        args.output_root / BUILD_REPORT_NAME,
        build_report,
        overwrite=args.overwrite or args.resume,
    )
    print(
        json.dumps(
            {
                "build_id": build_id,
                "output_root": str(args.output_root),
                "config_path": str(args.write_config),
                "route": args.route,
                "resume": args.resume,
                "routes": route_summaries,
                "consistency": consistency,
                "warnings": warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildOOMError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(3) from exc
