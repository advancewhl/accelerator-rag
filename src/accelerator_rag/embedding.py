from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer

FloatArray = NDArray[np.float32]


class BgeSmallZhEmbedder:
    """使用BGE中文模型生成归一化文本向量"""

    QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章"

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device

        self._model = SentenceTransformer(
            model_name,
            device=device,
        )

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> FloatArray:
        """将多个文档文本转换为二维向量矩阵"""

        if not texts:
            raise ValueError("文档文本列表不能为空")

        embeddings = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return np.asarray(
            embeddings,
            dtype=np.float32,
        )

    def embed_query(
        self,
        text: str,
    ) -> FloatArray:
        """将单个查询转换为一维向量"""

        query = text.strip()

        if not query:
            raise ValueError("查询文本不能为空")

        query_with_instruction = self.QUERY_INSTRUCTION + query

        embedding = self._model.encode(
            query_with_instruction,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return np.asarray(
            embedding,
            dtype=np.float32,
        )
