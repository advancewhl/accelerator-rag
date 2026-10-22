"""Local Qwen3 reranker, following the downloaded official Transformers example."""

from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


class Qwen3Reranker:
    model_name = "Qwen/Qwen3-Reranker-0.6B"
    instruction = "Given a web search query, retrieve relevant passages that answer the query"
    prefix = ('<|im_start|>system\nJudge whether the Document meets the requirements '
              'based on the Query and the Instruct provided. Note that the answer '
              'can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
    suffix = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'

    def __init__(self, model_path, *, batch_size=4):
        started = perf_counter()
        self.path = Path(model_path).resolve()
        self.batch_size = batch_size
        self.max_length = 8192  # Official Transformers example; no input is silently truncated.
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.path, local_files_only=True, padding_side="left"
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            self.path, local_files_only=True, dtype=torch.float32,
            attn_implementation="sdpa",
        ).eval().to("cpu")
        self.prefix_ids = self.tokenizer.encode(self.prefix, add_special_tokens=False)
        self.suffix_ids = self.tokenizer.encode(self.suffix, add_special_tokens=False)
        self.no_id = self.tokenizer.convert_tokens_to_ids("no")
        self.yes_id = self.tokenizer.convert_tokens_to_ids("yes")
        assert self.no_id != self.yes_id
        assert self.tokenizer.encode("yes", add_special_tokens=False) == [self.yes_id]
        assert self.tokenizer.encode("no", add_special_tokens=False) == [self.no_id]
        self.load_seconds = perf_counter() - started
        self.max_observed_tokens = 0
        self.scored_pairs = 0

    @torch.inference_mode()
    def score(self, query: str, passages: list[str]) -> list[float]:
        scores = []
        for start in range(0, len(passages), self.batch_size):
            sequences = []
            for passage in passages[start:start + self.batch_size]:
                text = f"<Instruct>: {self.instruction}\n<Query>: {query}\n<Document>: {passage}"
                ids = self.prefix_ids + self.tokenizer.encode(text) + self.suffix_ids
                if len(ids) > self.max_length:
                    raise ValueError("retrieved passage pair exceeds official example max_length")
                self.max_observed_tokens = max(self.max_observed_tokens, len(ids))
                sequences.append(ids)
            inputs = self.tokenizer.pad(
                {"input_ids": sequences}, padding=True, return_tensors="pt"
            )
            # Same final-token logits as the official example; skip unused vocabulary logits.
            logits = self.model(**inputs, logits_to_keep=1, use_cache=False).logits[:, -1, :]
            yes_no = torch.stack([logits[:, self.no_id], logits[:, self.yes_id]], dim=1)
            scores.extend(torch.nn.functional.log_softmax(yes_no, dim=1)[:, 1].exp().tolist())
        self.scored_pairs += len(passages)
        return scores

    def fingerprint(self):
        # Same bounded hashing and sorted weight-manifest scheme as EmbeddingModel.
        def digest(path):
            h = sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            return h.hexdigest()
        files = [p for p in sorted(self.path.rglob("*"))
                 if p.is_file() and ".cache" not in p.relative_to(self.path).parts]
        weights = {p.relative_to(self.path).as_posix(): digest(p) for p in files
                   if p.suffix in {".safetensors", ".bin"}}
        assert weights
        tokenizer = json.loads(self.tokenizer.backend_tokenizer.to_str())
        tokenizer.pop("truncation", None)
        tokenizer.pop("padding", None)
        return {
            "requested_model_name": self.model_name,
            "resolved_local_model_path": str(self.path),
            "weights_files": weights,
            "weights_manifest_sha256": sha256(json.dumps(weights, sort_keys=True).encode()).hexdigest(),
            "model_config_sha256": digest(self.path / "config.json"),
            "config_files": {p.relative_to(self.path).as_posix(): digest(p) for p in files if p.suffix == ".json"},
            "tokenizer_sha256": sha256(json.dumps(tokenizer, sort_keys=True).encode()).hexdigest(),
            "model_card_sha256": digest(self.path / "README.md"),
            "local_model_bytes": sum(p.stat().st_size for p in files),
            "instruction": self.instruction, "prefix": self.prefix, "suffix": self.suffix,
            "max_length": self.max_length, "batch_size": self.batch_size,
            "dtype": "float32", "device": "cpu", "attention": "sdpa",
            "score": "P(yes | yes/no final-token logits)",
        }
