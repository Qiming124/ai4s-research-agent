# Embedding 工厂：sentence-transformers、OpenAI 兼容 API 或测试用确定性向量。

from __future__ import annotations

import hashlib
import logging
from typing import Any

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from server.config import Settings, get_settings

logger = logging.getLogger(__name__)


class TestEmbeddingFunction(EmbeddingFunction):
    """确定性伪向量，供 pytest 使用（无需下载模型）。"""

    def __call__(self, input: Documents) -> Embeddings:
        dim = 8
        vectors: list[list[float]] = []
        for text in input:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vec = [float(digest[i % len(digest)]) / 255.0 for i in range(dim)]
            vectors.append(vec)
        return vectors


class OpenAICompatibleEmbeddingFunction(EmbeddingFunction):
    """通过 langchain-openai OpenAIEmbeddings 调用兼容 API。"""

    def __init__(self, settings: Settings) -> None:
        from langchain_openai import OpenAIEmbeddings

        base_url = settings.rag_embedding_base_url.strip() or settings.deepseek_base_url
        self._embeddings = OpenAIEmbeddings(
            model=settings.rag_embedding_model,
            api_key=settings.deepseek_api_key,
            base_url=base_url,
        )

    def __call__(self, input: Documents) -> Embeddings:
        return self._embeddings.embed_documents(list(input))


def get_embedding_function(
    settings: Settings | None = None,
    *,
    provider: str | None = None,
) -> EmbeddingFunction[Documents]:
    cfg = settings or get_settings()
    chosen = (provider or cfg.rag_embedding_provider).strip().lower()

    if chosen == "test":
        return TestEmbeddingFunction()

    if chosen == "openai":
        return OpenAICompatibleEmbeddingFunction(cfg)

    if chosen == "chroma_default":
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        logger.info("RAG embedding: chromadb DefaultEmbeddingFunction")
        return DefaultEmbeddingFunction()

    if chosen == "sentence_transformers":
        try:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers 未安装。请运行: pip install 'ai4s-research-agent[rag]'"
            ) from exc

        logger.info("RAG embedding: sentence-transformers %s", cfg.rag_embedding_model)
        return SentenceTransformerEmbeddingFunction(model_name=cfg.rag_embedding_model)

    raise ValueError(f"未知 RAG_EMBEDDING_PROVIDER: {chosen}")
