"""Historical measurements are preserved; rejudging cached rankings is explicit."""

from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.evaluation.retrieval import evaluate


def compare_stage_two(history, current, queries):
    output = {
        "comparability_note": "Stage 2 original page-level scores were mislabeled Recall; displayed here as historical Hit. They are not directly comparable to stricter complete-evidence Stage 2.5. Rejudged historical Top-5 below isolates judgment changes from ranking/index changes; no search or GT selection uses historical scores.",
        "stage_two_total_chunks": history["index"]["chunk_count"],
        "stage_two_eligible_chunks": history["index"]["chunk_count"],
        "stage_two_five_total_chunks": current["retrieval_eligibility"]["total_chunks"],
        "stage_two_five_eligible_chunks": current["index"]["point_count"],
    }
    for name in ("bm25", "dense"):
        old = history[name]
        cases = {c["id"]: c for c in old["cases"]}
        subset = [q for q in queries if q.id in cases]

        class Cached:
            def search(self, query, *, top_k):
                case = next(c for c in cases.values() if c["query"] == query)
                return [
                    RetrievalResult(
                        r["rank"],
                        r["score"],
                        KnowledgeChunk(**r["chunk"]),
                        r["retriever"],
                    )
                    for r in case["results"][:top_k]
                ]

        judged = evaluate(Cached(), subset)
        old_ranks = {
            c["id"]: c["first_relevant_rank"] for c in old["cases"] if c["answerable"]
        }
        rejudged_ranks = {
            c["id"]: c["first_complete_rank"]
            for c in judged["cases"]
            if c["answerable"]
        }
        new_ranks = {
            c["id"]: c["first_complete_rank"]
            for c in current[name]["cases"]
            if c["answerable"]
        }

        def changes(before, after):
            return {
                "fail_to_hit": [
                    q for q in before if before[q] is None and after[q] is not None
                ],
                "hit_to_fail": [
                    q for q in before if before[q] is not None and after[q] is None
                ],
            }

        output[name] = {
            "stage_two_historical_page_judgment": {
                **{f"Hit@{k}": old["metrics"][f"Recall@{k}"] for k in (1, 3, 5)},
                "MRR@5": old["metrics"]["MRR"],
            },
            "stage_two_cached_top5_new_contract": judged["metrics"],
            "stage_two_five": current[name]["metrics"],
            "historical_to_current": changes(old_ranks, new_ranks),
            "contract_change_on_same_rankings": changes(old_ranks, rejudged_ranks),
            "ranking_change_under_same_contract": changes(rejudged_ranks, new_ranks),
        }
    return output
