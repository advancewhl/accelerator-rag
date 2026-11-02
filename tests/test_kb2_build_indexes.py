"""Contract tests for the Schema v2 dual-index build script.

The real E5/Qwen3 models are never loaded: a deterministic character-level
embedder exercises the full passage, Qdrant write, verification and config
paths.  Qdrant runs in embedded directory mode under ``tmp_path``.
"""

from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import re
import sys

import pytest
from qdrant_client import QdrantClient

from conftest import PassageFixtureEmbedder

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "kb2_build_indexes.py"


def _load_build_module():
    name = "kb2_build_indexes_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load_build_module()
REQUIRED_REPORT_FIELDS = {
    "model_name",
    "model_path",
    "index_path",
    "collection",
    "dense_index_contract_id",
    "parent_count",
    "point_count",
    "embedded_passage_count",
    "passage_count",
    "build_seconds",
    "device",
    "dtype",
    "batch_size",
    "parent_set_sha256",
    "parent_text_sha256",
    "parent_evidence_sha256",
}


def make_chunk(document_id, suffix, text, **overrides):
    values = {
        "chunk_id": f"{document_id}:{suffix}",
        "document_id": document_id,
        "document_title": f"Title {document_id}",
        "text": text,
        "source_path": f"data/l0_raw/test/{document_id}.pdf",
        "document_version": "1",
        "language": "en",
        "category": "control_system",
        "topic": "test",
        "page_start": 1,
        "page_end": 1,
    }
    values.update(overrides)
    return MODULE.KnowledgeChunk(**values)


def corpus_file(document_id, chunks, *, eligible, indexable):
    return {
        "revision_id": document_id,
        "document_id": document_id,
        "chunks": [asdict(chunk) for chunk in chunks],
        "eligible_chunk_ids": [chunk.chunk_id for chunk in eligible],
        "indexable_chunk_ids": [chunk.chunk_id for chunk in indexable],
    }


def write_build(tmp_path, files):
    build_dir = tmp_path / "build-kb2-test"
    chunks_dir = build_dir / "chunks"
    chunks_dir.mkdir(parents=True)
    for name, payload in files.items():
        (chunks_dir / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    return build_dir


@pytest.fixture
def corpus_build(tmp_path):
    a1 = make_chunk("doc-a", "a1", "startup evidence alpha")
    a2 = make_chunk("doc-a", "a2", "short eligible but not indexable")
    a3 = make_chunk("doc-a", "a3", "ineligible audit-only text")
    b1 = make_chunk("doc-b", "b1", "startup evidence beta")
    b2 = make_chunk("doc-b", "b2", "eligible but not indexable")
    build_dir = write_build(
        tmp_path,
        {
            "doc-a": corpus_file(
                "doc-a", [a1, a2, a3], eligible=[a1, a2], indexable=[a1]
            ),
            "doc-b": corpus_file("doc-b", [b1, b2], eligible=[b1, b2], indexable=[b1]),
        },
    )
    return {
        "build_dir": build_dir,
        "a1": a1.chunk_id,
        "a2": a2.chunk_id,
        "a3": a3.chunk_id,
        "b1": b1.chunk_id,
        "b2": b2.chunk_id,
    }


@pytest.fixture
def template_path(tmp_path):
    path = tmp_path / "rag-production.template.json"
    path.write_text(
        json.dumps(
            {
                "model_base_url": "http://127.0.0.1:8000/v1",
                "model_name": "ds-1017",
                "indexes": [
                    {
                        "model_name": "stale/model",
                        "model_path": "/stale/model",
                        "index_path": "/stale/index",
                        "collection": "stale_collection",
                        "dense_index_contract_id": "0" * 64,
                        "point_count": 1,
                        "device": "cpu",
                        "dtype": "float32",
                    }
                ],
                "reranker": {
                    "model_path": "/workspace/models/Qwen3-Reranker",
                    "device": "cuda:0",
                    "dtype": "auto",
                    "batch_size": 4,
                },
                "generation_max_tokens": 4096,
                "trace_dir": "tmp/rag-request-traces",
                "source_root": "/workspace/data/l0_raw",
                "api_key": "MUST-NOT-LEAK",
            }
        ),
        encoding="utf-8",
    )
    return path


def fake_embedder_factory(*, model_name, model_path, device, dtype, batch_size):
    embedder = PassageFixtureEmbedder(limit=512)
    embedder.model_name = model_name
    embedder.model_path = model_path
    embedder.dimension = 2
    return embedder


def run_build(
    *,
    build_dir,
    output_root,
    config_path,
    template_path,
    extra=(),
    factory=fake_embedder_factory,
):
    argv = [
        "--build-dir",
        str(build_dir),
        "--output-root",
        str(output_root),
        "--model-root",
        str(build_dir.parent / "models"),
        "--e5-model",
        "intfloat--multilingual-e5-base",
        "--qwen-model",
        "Qwen--Qwen3-Embedding-0.6B",
        "--write-config",
        str(config_path),
        "--config-template",
        str(template_path),
        "--device",
        "cpu",
        "--batch-size",
        "2",
        *extra,
    ]
    return MODULE.main(argv, embedder_factory=factory)


def test_build_only_indexable_routes_agree_and_config_is_written(
    corpus_build, template_path, tmp_path, monkeypatch
):
    build_dir = corpus_build["build_dir"]
    output_root = tmp_path / "indexes"
    config_path = tmp_path / "rag-production.json"
    calls = []
    original = MODULE.load_corpus

    def counting_load(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(MODULE, "load_corpus", counting_load)
    assert (
        run_build(
            build_dir=build_dir,
            output_root=output_root,
            config_path=config_path,
            template_path=template_path,
        )
        == 0
    )
    # The corpus is read once and the same parents feed both routes.
    assert calls == [build_dir]

    e5 = json.loads((output_root / "e5" / "index-report.json").read_text())
    qwen = json.loads((output_root / "qwen3" / "index-report.json").read_text())
    build_report = json.loads((output_root / "index-build-report.json").read_text())
    for report in (e5, qwen):
        assert REQUIRED_REPORT_FIELDS <= set(report)
        assert report["parent_count"] == 2
        assert report["point_count"] == report["embedded_passage_count"] == 2
        assert report["passage_count"] == 2
        assert report["device"] == "cpu"
        assert report["dtype"] == "float32"
        assert report["batch_size"] == 2
        assert re.fullmatch(r"[0-9a-f]{64}", report["dense_index_contract_id"])
    assert e5["route"] == "e5"
    assert qwen["route"] == "qwen3"
    assert e5["model_name"] == MODULE.E5_MODEL_NAME
    assert qwen["model_name"] == MODULE.QWEN_MODEL_NAME
    assert e5["dense_index_contract_id"] != qwen["dense_index_contract_id"]

    for field in (
        "parent_set_sha256",
        "parent_text_sha256",
        "parent_evidence_sha256",
    ):
        assert e5[field] == qwen[field] == build_report["corpus"][field]
    consistency = build_report["consistency"]
    assert consistency["same_parent_set"] is True
    assert consistency["same_parent_text"] is True
    assert consistency["same_parent_evidence"] is True
    assert consistency["parent_count"] == 2
    assert build_report["config_path"] == str(config_path)

    config = json.loads(config_path.read_text())
    assert set(config) == {
        "model_base_url",
        "model_name",
        "indexes",
        "reranker",
        "generation_max_tokens",
        "trace_dir",
        "source_root",
    }
    assert "api_key" not in config_path.read_text()
    assert [entry["model_name"] for entry in config["indexes"]] == [
        MODULE.E5_MODEL_NAME,
        MODULE.QWEN_MODEL_NAME,
    ]
    assert config["model_base_url"] == "http://127.0.0.1:8000/v1"
    assert config["model_name"] == "ds-1017"
    assert config["trace_dir"] == "tmp/rag-request-traces"
    assert config["source_root"] == "/workspace/data/l0_raw"
    assert config["generation_max_tokens"] == 4096
    assert config["reranker"] == {
        "model_path": "/workspace/models/Qwen3-Reranker",
        "device": "cuda:0",
        "dtype": "auto",
        "batch_size": 4,
    }
    assert config["indexes"][0]["index_path"] == str(output_root / "e5" / "qdrant")
    assert config["indexes"][1]["index_path"] == str(output_root / "qwen3" / "qdrant")
    assert config["indexes"][0]["point_count"] == 2
    assert config["indexes"][1]["point_count"] == 2

    expected_parents = {corpus_build["a1"], corpus_build["b1"]}
    for entry in config["indexes"]:
        client = QdrantClient(path=entry["index_path"])
        try:
            records, _ = client.scroll(
                entry["collection"], limit=100, with_payload=True
            )
        finally:
            client.close()
        assert {record.payload["parent_chunk_id"] for record in records} == (
            expected_parents
        )
    # Audit-only and eligible-but-not-indexable chunks never enter Qdrant.
    assert corpus_build["a2"] not in expected_parents
    assert corpus_build["a3"] not in expected_parents


def test_duplicate_chunk_ids_across_corpus_rejected(tmp_path):
    first = make_chunk("doc-a", "dup", "startup first")
    second = make_chunk("doc-b", "dup", "startup second", chunk_id=first.chunk_id)
    build_dir = write_build(
        tmp_path,
        {
            "doc-a": corpus_file("doc-a", [first], eligible=[first], indexable=[first]),
            "doc-b": corpus_file(
                "doc-b", [second], eligible=[second], indexable=[second]
            ),
        },
    )
    with pytest.raises(MODULE.BuildInputError, match="duplicate chunk ID"):
        MODULE.load_corpus(build_dir)


def test_empty_corpus_rejected(tmp_path):
    missing = tmp_path / "missing-build"
    with pytest.raises(MODULE.BuildInputError, match="chunk directory not found"):
        MODULE.load_corpus(missing)

    empty = tmp_path / "empty-build"
    (empty / "chunks").mkdir(parents=True)
    with pytest.raises(MODULE.BuildInputError, match="no chunk files"):
        MODULE.load_corpus(empty)

    chunk = make_chunk("doc-a", "a1", "startup evidence")
    no_indexable = write_build(
        tmp_path,
        {"doc-a": corpus_file("doc-a", [chunk], eligible=[chunk], indexable=[])},
    )
    with pytest.raises(MODULE.BuildInputError, match="no indexable chunks"):
        MODULE.load_corpus(no_indexable)


def test_document_id_mismatch_rejected(tmp_path):
    chunk = make_chunk("doc-other", "a1", "startup evidence")
    build_dir = write_build(
        tmp_path,
        {"doc-a": corpus_file("doc-a", [chunk], eligible=[chunk], indexable=[chunk])},
    )
    with pytest.raises(MODULE.BuildInputError, match="document_id"):
        MODULE.load_corpus(build_dir)


def test_restricted_or_ineligible_indexable_rejected(tmp_path):
    restricted = make_chunk(
        "doc-a", "restricted", "startup restricted", access_scope="restricted"
    )
    build_dir = write_build(
        tmp_path,
        {
            "doc-a": corpus_file(
                "doc-a",
                [restricted],
                eligible=[restricted],
                indexable=[restricted],
            )
        },
    )
    with pytest.raises(MODULE.BuildInputError, match="restricted"):
        MODULE.load_corpus(build_dir)

    chunk = make_chunk("doc-a", "a1", "startup evidence")
    ignored = make_chunk("doc-a", "a2", "audit only")
    ineligible = write_build(
        tmp_path / "ineligible",
        {
            "doc-a": corpus_file(
                "doc-a", [chunk, ignored], eligible=[chunk], indexable=[ignored]
            )
        },
    )
    with pytest.raises(MODULE.BuildInputError, match="not eligible"):
        MODULE.load_corpus(ineligible)


def test_existing_output_requires_explicit_overwrite(
    corpus_build, template_path, tmp_path
):
    build_dir = corpus_build["build_dir"]
    output_root = tmp_path / "indexes"
    config_path = tmp_path / "rag-production.json"
    kwargs = {
        "build_dir": build_dir,
        "output_root": output_root,
        "config_path": config_path,
        "template_path": template_path,
    }
    assert run_build(**kwargs) == 0
    with pytest.raises(MODULE.BuildSafetyError, match="--overwrite"):
        run_build(**kwargs)
    assert run_build(**kwargs, extra=("--overwrite",)) == 0
    config = json.loads(config_path.read_text())
    assert config["indexes"][0]["point_count"] == 2


def test_cli_settings_override_template(corpus_build, template_path, tmp_path):
    config_path = tmp_path / "cli-rag-production.json"
    assert (
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=tmp_path / "cli-indexes",
            config_path=config_path,
            template_path=template_path,
            extra=(
                "--model-base-url",
                "http://localhost:9000/v1",
                "--model-name",
                "cli-model",
                "--trace-dir",
                "tmp/cli-traces",
                "--source-root",
                "/workspace/cli-l0",
                "--generation-max-tokens",
                "1024",
            ),
        )
        == 0
    )
    config = json.loads(config_path.read_text())
    assert config["model_base_url"] == "http://localhost:9000/v1"
    assert config["model_name"] == "cli-model"
    assert config["trace_dir"] == "tmp/cli-traces"
    assert config["source_root"] == "/workspace/cli-l0"
    assert config["generation_max_tokens"] == 1024


def test_dry_run_writes_nothing_and_loads_no_model(corpus_build, tmp_path, capsys):
    output_root = tmp_path / "dry-run-indexes"

    def exploding_factory(**kwargs):
        raise AssertionError("dry run must not load an embedding model")

    code = MODULE.main(
        [
            "--dry-run",
            "--build-dir",
            str(corpus_build["build_dir"]),
            "--output-root",
            str(output_root),
        ],
        embedder_factory=exploding_factory,
    )
    assert code == 0
    assert not output_root.exists()
    summary = json.loads(capsys.readouterr().out)
    assert summary["dry_run"] is True
    assert summary["writes"] is False
    assert summary["corpus"]["indexable_chunks"] == 2
    assert [route["route"] for route in summary["planned_routes"]] == [
        "e5",
        "qwen3",
    ]


def test_config_refuses_credentials(corpus_build, template_path, tmp_path):
    template = json.loads(template_path.read_text())
    template["model_base_url"] = "http://user:password@127.0.0.1:8000/v1"
    bad_url = tmp_path / "bad-url.json"
    bad_url.write_text(json.dumps(template), encoding="utf-8")
    with pytest.raises(MODULE.BuildInputError, match="credentials"):
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=tmp_path / "indexes",
            config_path=tmp_path / "config.json",
            template_path=bad_url,
            factory=lambda **kwargs: pytest.fail("model must not load"),
        )

    template = json.loads(template_path.read_text())
    template["reranker"] = {
        "model_path": "/workspace/models/Qwen3-Reranker",
        "api_key": "MUST-NOT-LEAK",
    }
    bad_reranker = tmp_path / "bad-reranker.json"
    bad_reranker.write_text(json.dumps(template), encoding="utf-8")
    with pytest.raises(MODULE.BuildInputError, match="reranker"):
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=tmp_path / "indexes",
            config_path=tmp_path / "config.json",
            template_path=bad_reranker,
            factory=lambda **kwargs: pytest.fail("model must not load"),
        )


def test_resume_and_overwrite_are_exclusive(corpus_build, template_path, tmp_path):
    with pytest.raises(MODULE.BuildInputError, match="Choose one"):
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=tmp_path / "indexes",
            config_path=tmp_path / "config.json",
            template_path=template_path,
            extra=("--resume", "--overwrite"),
        )


@pytest.mark.parametrize("route", ["e5", "qwen3"])
def test_single_route_reuses_companion_report(
    route, corpus_build, template_path, tmp_path
):
    output_root = tmp_path / f"indexes-{route}"
    full_config = tmp_path / f"config-{route}-full.json"
    assert (
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=output_root,
            config_path=full_config,
            template_path=template_path,
        )
        == 0
    )
    companion = "qwen3" if route == "e5" else "e5"
    companion_report = output_root / companion / "index-report.json"
    companion_before = companion_report.read_bytes()

    config_path = tmp_path / f"config-{route}-single.json"
    assert (
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=output_root,
            config_path=config_path,
            template_path=template_path,
            extra=("--route", route, "--overwrite"),
        )
        == 0
    )
    assert companion_report.read_bytes() == companion_before
    config = json.loads(config_path.read_text())
    assert [entry["model_name"] for entry in config["indexes"]] == [
        MODULE.E5_MODEL_NAME,
        MODULE.QWEN_MODEL_NAME,
    ]
    build_report = json.loads((output_root / "index-build-report.json").read_text())
    assert build_report["route"] == route
    assert {item["route"]: item["reused"] for item in build_report["routes"]} == {
        route: False,
        companion: True,
    }


def test_single_route_missing_companion_writes_no_config(
    corpus_build, template_path, tmp_path, capsys
):
    output_root = tmp_path / "single-missing"
    config_path = tmp_path / "single-missing-config.json"
    assert (
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=output_root,
            config_path=config_path,
            template_path=template_path,
            extra=("--route", "e5"),
        )
        == 2
    )
    assert (output_root / "e5" / "index-report.json").is_file()
    assert not (output_root / "qwen3").exists()
    assert not config_path.exists()
    summary = json.loads(capsys.readouterr().out)
    assert summary["config_written"] is False
    assert summary["available_routes"] == ["e5"]
    assert summary["missing_routes"] == ["qwen3"]
    assert summary["errors"]


def test_sequential_single_route_builds_complete_config(
    corpus_build, template_path, tmp_path
):
    output_root = tmp_path / "sequential"
    config_path = tmp_path / "sequential-config.json"
    kwargs = {
        "build_dir": corpus_build["build_dir"],
        "output_root": output_root,
        "config_path": config_path,
        "template_path": template_path,
    }
    assert run_build(**kwargs, extra=("--route", "e5")) == 2
    assert not config_path.exists()
    e5_before = (output_root / "e5" / "index-report.json").read_bytes()
    assert run_build(**kwargs, extra=("--route", "qwen3")) == 0
    assert (output_root / "e5" / "index-report.json").read_bytes() == e5_before
    config = json.loads(config_path.read_text())
    assert [entry["model_name"] for entry in config["indexes"]] == [
        MODULE.E5_MODEL_NAME,
        MODULE.QWEN_MODEL_NAME,
    ]
    build_report = json.loads((output_root / "index-build-report.json").read_text())
    assert {item["route"]: item["reused"] for item in build_report["routes"]} == {
        "e5": True,
        "qwen3": False,
    }


def test_resume_reuses_valid_reports_without_rebuild(
    corpus_build, template_path, tmp_path, monkeypatch
):
    output_root = tmp_path / "resume"
    first_config = tmp_path / "config-first.json"
    assert (
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=output_root,
            config_path=first_config,
            template_path=template_path,
        )
        == 0
    )
    before = {
        route: (output_root / route / "index-report.json").read_bytes()
        for route in ("e5", "qwen3")
    }

    def must_not_rebuild(*args, **kwargs):
        raise AssertionError("resume must not rebuild a validated route")

    monkeypatch.setattr(MODULE, "_build_route", must_not_rebuild)

    def no_embed_factory(*, model_name, model_path, device, dtype, batch_size):
        embedder = fake_embedder_factory(
            model_name=model_name,
            model_path=model_path,
            device=device,
            dtype=dtype,
            batch_size=batch_size,
        )

        def must_not_embed(*args, **kwargs):
            raise AssertionError("resume must not embed passages")

        embedder.embed_documents = must_not_embed
        embedder.embed_token_safe_documents = must_not_embed
        return embedder

    config_path = tmp_path / "config-resume.json"
    assert (
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=output_root,
            config_path=config_path,
            template_path=template_path,
            extra=("--resume",),
            factory=no_embed_factory,
        )
        == 0
    )
    for route, content in before.items():
        assert (output_root / route / "index-report.json").read_bytes() == content
    assert config_path.is_file()
    build_report = json.loads((output_root / "index-build-report.json").read_text())
    assert build_report["resume"] is True
    assert {item["route"]: item["reused"] for item in build_report["routes"]} == {
        "e5": True,
        "qwen3": True,
    }
    assert {
        item["route"]: item["contract_rechecked"] for item in build_report["routes"]
    } == {"e5": True, "qwen3": True}


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("parent_text_sha256", "0" * 64),
        ("dense_index_contract_id", "1" * 64),
    ),
)
def test_resume_mismatch_requires_explicit_rebuild(
    field, value, corpus_build, template_path, tmp_path, monkeypatch
):
    output_root = tmp_path / f"resume-mismatch-{field}"
    config_path = tmp_path / f"config-{field}.json"
    assert (
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=output_root,
            config_path=config_path,
            template_path=template_path,
        )
        == 0
    )
    report_path = output_root / "e5" / "index-report.json"
    report = json.loads(report_path.read_text())
    report[field] = value
    report_path.write_text(json.dumps(report), encoding="utf-8")

    monkeypatch.setattr(
        MODULE,
        "_build_route",
        lambda *args, **kwargs: pytest.fail("must not rebuild on mismatch"),
    )
    resumed_config = tmp_path / f"config-{field}-resumed.json"
    with pytest.raises(MODULE.BuildInputError, match="--overwrite"):
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=output_root,
            config_path=resumed_config,
            template_path=template_path,
            extra=("--route", "e5", "--resume"),
        )
    assert not resumed_config.exists()


def _oom_factory(message):
    def factory(*, model_name, model_path, device, dtype, batch_size):
        embedder = fake_embedder_factory(
            model_name=model_name,
            model_path=model_path,
            device=device,
            dtype=dtype,
            batch_size=batch_size,
        )
        if model_name == MODULE.QWEN_MODEL_NAME:

            def boom(*args, **kwargs):
                raise RuntimeError(message)

            embedder.embed_documents = boom
            embedder.embed_token_safe_documents = boom
        return embedder

    return factory


def test_oom_reports_advice_and_preserves_completed_route(
    corpus_build, template_path, tmp_path
):
    output_root = tmp_path / "oom"
    config_path = tmp_path / "config-oom.json"
    with pytest.raises(MODULE.BuildOOMError, match="batch_size=2") as exc:
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=output_root,
            config_path=config_path,
            template_path=template_path,
            factory=_oom_factory("CUDA out of memory. Tried to allocate 784.00 MiB"),
        )
    message = str(exc.value)
    assert "out of memory" in message.lower()
    assert "qwen3" in message
    assert "--batch-size" in message
    assert "--device cpu" in message
    assert "1 or 2" in message
    assert (output_root / "e5" / "index-report.json").is_file()
    assert not (output_root / "qwen3" / "index-report.json").exists()
    assert not config_path.exists()


def test_non_oom_runtime_error_is_not_converted(corpus_build, template_path, tmp_path):
    output_root = tmp_path / "non-oom"
    config_path = tmp_path / "config-non-oom.json"
    with pytest.raises(RuntimeError, match="tokenizer exploded") as exc:
        run_build(
            build_dir=corpus_build["build_dir"],
            output_root=output_root,
            config_path=config_path,
            template_path=template_path,
            factory=_oom_factory("tokenizer exploded"),
        )
    assert not isinstance(exc.value, MODULE.BuildOOMError)
    assert (output_root / "e5" / "index-report.json").is_file()
    assert not config_path.exists()


def test_torch_oom_class_is_recognized():
    torch = pytest.importorskip("torch")
    assert MODULE._is_oom_error(torch.OutOfMemoryError("CUDA out of memory"))
    assert not MODULE._is_oom_error(RuntimeError("tokenizer exploded"))


def test_help_documents_cpu_route_and_qwen_batch_advice(capsys):
    with pytest.raises(SystemExit):
        MODULE.parse_args(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--route" in text
    assert "--resume" in text
    assert "cpu is supported" in text
    assert "Qwen3 on a busy GPU uses 1 or 2" in text
