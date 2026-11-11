"""Multi-route recall with fusion, revision-side probes and atom generation."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .index import CorpusIndex, entity_terms, query_terms
from .schema import Atom, Candidate, Needs, dedupe_atoms

_FUSION_K = 60
_CANDIDATE_LIMIT = 48
_SENTENCE_CANDIDATES = 28


class DenseChannel:
    """Optional E5/Qwen3 adapter; offline runs record it as unavailable."""

    name = "dense"
    available = False

    def search(self, query: str, chunk_ids, top_k: int):  # pragma: no cover - interface
        raise NotImplementedError("dense channel is not configured for this run")


@dataclass(frozen=True)
class RecallResult:
    candidates: tuple[Candidate, ...]
    atoms: tuple[Atom, ...]
    trace: dict

    def to_dict(self) -> dict:
        return {
            "candidates": [item.to_dict() for item in self.candidates],
            "atoms": [atom.to_dict() for atom in self.atoms],
            "trace": self.trace,
        }


def allowed_revisions(
    index: CorpusIndex, needs: Needs, family_ids: set[str]
) -> set[str]:
    if needs.version_pair:
        return set(needs.version_pair)
    if needs.revision_ids:
        return set(needs.revision_ids)
    return index.revision_ids_for_families(family_ids)


def derive_queries(query: str, needs: Needs, limit: int = 5) -> tuple[str, ...]:
    texts = [query.strip()]
    entities = entity_terms(needs.entities)
    if entities:
        joined = " ".join(
            item.raw for item in needs.entities if item.kind in {"cabinet", "device"}
        ).strip()
        if joined:
            texts.append(joined)
    role_words = []
    for name in needs.required_names():
        role_words.append(
            {
                "requirement": "要求 指标",
                "design": "设计 指标",
                "test_result": "测试 结果 实测",
                "test_scope": "测试条件 测量范围",
                "acceptance": "验收 结论",
                "condition": "条件 适用",
                "version_left": "第一版",
                "version_right": "第二版",
            }.get(name, "")
        )
    role_text = " ".join(word for word in role_words if word).strip()
    if role_text:
        texts.append(f"{query.strip()} {role_text}")
    version = [item for item in needs.relations if item.name.startswith("version_")]
    if version:
        terms = sorted(query_terms(query))
        texts.append(" ".join(terms) if terms else query)
    ordered: list[str] = []
    for text in texts:
        text = unicodedata.normalize("NFKC", text).strip()
        if text and text not in ordered:
            ordered.append(text)
    return tuple(ordered[:limit])


def _add_candidate(
    bucket: dict[str, dict], chunk_id: str, *, score: float, route: dict
) -> None:
    item = bucket.setdefault(chunk_id, {"score": 0.0, "routes": []})
    item["score"] += score
    item["routes"].append(route)


def recall(
    index: CorpusIndex,
    needs: Needs,
    query: str,
    *,
    family_ids: set[str],
    round_no: int = 1,
    focus: tuple[str, ...] = (),
    dense: DenseChannel | None = None,
    archiver_atoms: tuple[Atom, ...] = (),
) -> RecallResult:
    revisions = allowed_revisions(index, needs, family_ids)
    terms = query_terms(query)
    entities = entity_terms(needs.entities)
    entity_kinds = {item.normalized: item.kind for item in needs.entities}
    queries = derive_queries(query, needs)
    if focus:
        queries = tuple(
            dict.fromkeys(f"{query} {name}" for name in focus)
        )[:4] or (query,)
    bucket: dict[str, dict] = {}
    channels: dict[str, dict] = {}

    def count(channel: str) -> dict:
        return channels.setdefault(channel, {"calls": 0, "candidates": 0})

    # 1. lexical recall over the allowed revision set.
    bm25_chunks: list[str] = []
    queries_used: list[str] = []
    for text in queries:
        hits = index.bm25_search(
            text,
            top_k=20 if round_no == 1 else 12,
            revision_ids=revisions,
        )
        queries_used.append(text)
        count("bm25")["calls"] += 1
        for rank, (chunk_id, score) in enumerate(hits, 1):
            bm25_chunks.append(chunk_id)
            _add_candidate(
                bucket,
                chunk_id,
                score=1.0 / (_FUSION_K + rank),
                route={
                    "channel": "bm25",
                    "query": text,
                    "rank": rank,
                    "score": round(score, 6),
                },
            )
    count("bm25")["candidates"] = len(set(bm25_chunks))

    # 2. exact structured rows.
    row_hits = index.rows_matching(
        entity_terms=entities,
        entity_kinds=entity_kinds,
        text_terms=terms,
        family_ids=family_ids,
        revision_ids=revisions,
        limit=80,
    )
    rows_by_chunk: dict[str, list] = {}
    for row, score in row_hits:
        rows_by_chunk.setdefault(row.chunk_id, []).append((row, score))
    for rank, (chunk_id, rows) in enumerate(
        sorted(rows_by_chunk.items(), key=lambda item: (-max(s for _, s in item[1]), item[0])),
        1,
    ):
        _add_candidate(
            bucket,
            chunk_id,
            score=1.0 / (_FUSION_K + rank),
            route={
                "channel": "row_exact",
                "rank": rank,
                "rows": len(rows),
                "top_score": round(max(score for _, score in rows), 6),
            },
        )
    count("row_exact")["calls"] = 1
    count("row_exact")["candidates"] = len(rows_by_chunk)

    # 3. fact index.
    fact_hits = index.facts_matching(
        entity_terms=entities,
        entity_kinds=entity_kinds,
        text_terms=terms,
        revision_ids=revisions,
        limit=120,
    )
    fact_chunks: dict[str, list] = {}
    for fact, score in fact_hits:
        fact_chunks.setdefault(fact.citation.chunk_id, []).append((fact, score))
    for rank, (chunk_id, facts) in enumerate(
        sorted(
            fact_chunks.items(),
            key=lambda item: (-max(score for _, score in item[1]), item[0]),
        ),
        1,
    ):
        _add_candidate(
            bucket,
            chunk_id,
            score=1.0 / (_FUSION_K + rank),
            route={
                "channel": "fact",
                "rank": rank,
                "facts": len(facts),
                "top_score": round(max(score for _, score in facts), 6),
            },
        )
    count("fact")["calls"] = 1
    count("fact")["candidates"] = len(fact_chunks)

    # 4. revision-side probes.
    if needs.version_pair and not focus:
        for side, revision_id in zip(
            ("version_left", "version_right"), needs.version_pair, strict=True
        ):
            side_hits = index.bm25_search(
                query, top_k=8, revision_ids={revision_id}
            )
            count("revision")["calls"] += 1
            for rank, (chunk_id, score) in enumerate(side_hits, 1):
                _add_candidate(
                    bucket,
                    chunk_id,
                    score=1.0 / (_FUSION_K + rank),
                    route={
                        "channel": "revision",
                        "side": side,
                        "revision_id": revision_id,
                        "rank": rank,
                        "score": round(score, 6),
                    },
                )
        count("revision")["candidates"] = len(
            [cid for cid in bucket if index.revision_of(cid) in needs.version_pair]
        )

    # 4b. literal scan for numbers, port ranges and rare identifiers.
    literal_tokens = set()
    for entity in needs.entities:
        if entity.kind not in {"number", "port"}:
            continue
        raw = unicodedata.normalize("NFKC", entity.raw).casefold()
        literal_tokens.add(raw)
        core = raw.split("-")[0].strip()
        if core and any(ch.isdigit() for ch in core):
            literal_tokens.add(core)
    literal_tokens.update(
        token
        for token in terms
        if any(ch.isdigit() for ch in token) and len(token) >= 3
    )
    literal_tokens = sorted(literal_tokens)[:16]
    literal_hits: list[tuple[str, int]] = []
    if literal_tokens and not focus:
        patterns = []
        for token in literal_tokens:
            if token.isdigit() or re.fullmatch(r"\d+(?:\.\d+)?", token):
                patterns.append(re.compile(rf"(?<![\d.]){re.escape(token)}(?![\d.])"))
            else:
                patterns.append(re.compile(re.escape(token)))
        for revision_id in sorted(revisions):
            for chunk_id in index.document_order.get(revision_id, ()):
                folded = index.chunks[chunk_id].text.casefold()
                hits = sum(1 for pattern in patterns if pattern.search(folded))
                if hits:
                    literal_hits.append((chunk_id, hits))
    literal_hits.sort(key=lambda item: (-item[1], item[0]))
    count("literal")["calls"] = 1 if literal_tokens else 0
    count("literal")["candidates"] = len(literal_hits)
    for rank, (chunk_id, hits) in enumerate(literal_hits[:16], 1):
        _add_candidate(
            bucket,
            chunk_id,
            score=0.7 / (_FUSION_K + rank),
            route={"channel": "literal", "rank": rank, "hits": hits},
        )

    # 4c. table-structure scan for "column empty / not filled" questions.
    role_words = {
        "test_result": ("测试结果", "实测结果", "测试项", "结果"),
        "acceptance": ("结论", "验收", "评审", "符合性"),
        "requirement": ("要求", "指标", "验收指标", "技术指标"),
        "design": ("设计",),
    }
    wanted = [
        word
        for name in needs.required_names()
        for word in role_words.get(name, ())
    ]
    structure_enabled = bool(
        wanted
        and not focus
        and any(
            word in query
            for word in ("栏", "表", "列", "填写", "结果", "结论", "空")
        )
    )
    structure_hits: list[tuple[str, int]] = []
    if structure_enabled:
        for revision_id in sorted(revisions):
            for chunk_id in index.document_order.get(revision_id, ()):
                headers = index.chunk_headers.get(chunk_id, ())
                if not headers:
                    continue
                matched = {
                    word for word in wanted if any(word in header for header in headers)
                }
                if matched:
                    structure_hits.append((chunk_id, len(matched)))
    structure_hits.sort(key=lambda item: (-item[1], item[0]))
    count("structure")["calls"] = 1 if structure_enabled else 0
    count("structure")["candidates"] = len(structure_hits)
    for rank, (chunk_id, hits) in enumerate(structure_hits[:16], 1):
        _add_candidate(
            bucket,
            chunk_id,
            score=0.8 / (_FUSION_K + rank),
            route={"channel": "structure", "rank": rank, "hits": hits},
        )

    # 5. optional dense adapter.
    if dense is not None and getattr(dense, "available", False) and not focus:
        dense_hits = dense.search(
            query, sorted(index.chunks), top_k=20
        )
        count("dense")["calls"] += 1
        count("dense")["candidates"] = len(dense_hits)
        for rank, (chunk_id, score) in enumerate(dense_hits, 1):
            if chunk_id not in index.chunks:
                continue
            if index.revision_of(chunk_id) not in revisions:
                continue
            _add_candidate(
                bucket,
                chunk_id,
                score=1.0 / (_FUSION_K + rank),
                route={
                    "channel": "dense",
                    "rank": rank,
                    "score": round(float(score), 6),
                },
            )
    else:
        count("dense")["available"] = False

    # 6. reading-order neighbours of the strongest candidates.
    ordered = sorted(
        bucket.items(), key=lambda item: (-item[1]["score"], item[0])
    )[:_SENTENCE_CANDIDATES]
    if not focus:
        for chunk_id, _ in ordered:
            for rank, neighbor in enumerate(
                index.neighbor_chunks(chunk_id, limit=2), 1
            ):
                if index.revision_of(neighbor) not in revisions:
                    continue
                _add_candidate(
                    bucket,
                    neighbor,
                    score=0.5 / (_FUSION_K + rank),
                    route={"channel": "neighbor", "anchor": chunk_id, "rank": rank},
                )
    count("neighbor")["calls"] = 0 if focus else len(ordered)
    count("neighbor")["candidates"] = len(
        [1 for item in bucket.values() if any(r["channel"] == "neighbor" for r in item["routes"])]
    )

    candidates = tuple(
        Candidate(
            chunk_id=chunk_id,
            score=item["score"],
            routes=tuple(item["routes"]),
            revision_id=index.revision_of(chunk_id),
            source_role=index.chunks[chunk_id].evidence_role,
        )
        for chunk_id, item in sorted(
            bucket.items(), key=lambda item: (-item[1]["score"], item[0])
        )[:_CANDIDATE_LIMIT]
    )

    # 7. atoms.
    atoms: list[Atom] = []
    for fact, score in fact_hits:
        if index.revision_of(fact.citation.chunk_id) not in revisions:
            continue
        atoms.append(index.fact_atom(fact, score=1.0 + 0.1 * score))
    for row, score in row_hits:
        atoms.append(row.to_atom(score=1.0 + 0.1 * score))
    for candidate in candidates[:_SENTENCE_CANDIDATES]:
        chunk = index.chunk(candidate.chunk_id)
        primary = candidate.routes[0]["channel"] if candidate.routes else "bm25"
        rows = index.rows_of(candidate.chunk_id)
        if rows:
            routes = {route["channel"] for route in candidate.routes}
            if routes & {"structure", "literal", "row_exact"}:
                for row in rows[:60]:
                    atoms.append(
                        row.to_atom(score=max(0.5, candidate.score * 10.0))
                    )
            continue
        atoms.extend(
            index.sentence_atoms(
                chunk.chunk_id,
                score=max(0.1, candidate.score * 10.0),
                route=primary,
                query_terms=terms,
            )
        )
    # 8. version sides always contribute their best-matching paragraphs.
    if needs.version_pair and not focus:
        for revision_id in needs.version_pair:
            side_atoms = [
                atom
                for atom in index.all_paragraphs(revision_id)
                if atom.score >= 0
            ]
            scored = sorted(
                side_atoms,
                key=lambda atom: (
                    -sum(1 for term in terms if term and term in atom.excerpt.casefold()),
                    atom.atom_id,
                ),
            )[:14]
            atoms.extend(scored)
    atoms.extend(archiver_atoms)
    atoms_tuple = dedupe_atoms(atoms)
    counts = {name: dict(values) for name, values in sorted(channels.items())}
    trace = {
        "round": round_no,
        "route": needs.route,
        "queries": list(dict.fromkeys(queries_used)),
        "focus": list(focus),
        "allowed_revisions": sorted(revisions),
        "channels": counts,
        "candidate_count": len(bucket),
        "selected_candidates": len(candidates),
        "atom_count": len(atoms_tuple),
    }
    return RecallResult(candidates=candidates, atoms=atoms_tuple, trace=trace)
