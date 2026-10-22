"""One immutable vector space and passage representation per Dense collection."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json


def canonical_sha256(value) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class DenseIndexContract:
    requested_model_name: str
    weights_manifest_sha256: str
    model_config_sha256: str
    encoding_config_sha256: str
    tokenizer_sha256: str
    query_template: str
    document_prefix: str
    dimension: int
    max_seq_length: int
    passage_contract_id: str
    passage_algorithm: str
    normalize_embeddings: bool = True
    distance: str = "cosine"
    document_template: str = 'document_title + "\\n" + passage.text'

    def __post_init__(self):
        if (
            type(self.dimension) is not int
            or self.dimension <= 0
            or type(self.max_seq_length) is not int
            or self.max_seq_length <= 0
        ):
            raise ValueError("positive dimension/max_seq_length required")
        if any(
            not isinstance(getattr(self, key), str) or not getattr(self, key).strip()
            for key in [
                "requested_model_name",
                "weights_manifest_sha256",
                "model_config_sha256",
                "encoding_config_sha256",
                "tokenizer_sha256",
                "query_template",
                "passage_contract_id",
                "passage_algorithm",
                "distance",
            ]
        ):
            raise ValueError("incomplete Dense index identity")
        if type(self.normalize_embeddings) is not bool:
            raise ValueError("normalize_embeddings must be boolean")

    @property
    def contract_id(self) -> str:
        return canonical_sha256(asdict(self))

    @classmethod
    def from_fingerprint(cls, identity, passage_contract):
        return cls(
            requested_model_name=identity["requested_model_name"],
            weights_manifest_sha256=identity["weights_manifest_sha256"],
            model_config_sha256=identity["model_config_sha256"],
            encoding_config_sha256=canonical_sha256(identity["config_files"]),
            tokenizer_sha256=identity["tokenizer_sha256"],
            query_template=identity["query_template"],
            document_prefix=identity["document_prefix"],
            dimension=identity["dimension"],
            max_seq_length=identity["max_seq_length"],
            passage_contract_id=canonical_passage_id(passage_contract),
            passage_algorithm=passage_contract["algorithm"],
        )


def canonical_passage_id(contract):
    # Preserve dense-passages-v1 identity exactly (its existing canonicalization).
    return sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
