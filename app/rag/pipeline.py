"""当前使用的混合检索与重排流程。"""

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.rag.contracts import KnowledgeHit, RetrievalRequest
from app.rag.ranking import build_ranked_hits
class HybridSearch(Protocol):
    async def __call__(
        self,
        *,
        query_text: str,
        query_vector: list[float],
        recall_k: int,
        top_k: int,
        collection_name: str,
    ) -> list[dict]:
        ...


class Rerank(Protocol):
    async def __call__(
        self,
        *,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[dict]:
        ...


class HybridRerankRetriever:
    """通过混合检索和重排获取知识片段。"""
    def __init__(
        self,
        *,
        embed: Callable[[list[str]], Awaitable[list[list[float]]]],
        search: HybridSearch,
        rerank: Rerank,
    ) -> None:
        self._embed = embed
        self._search = search
        self._rerank = rerank
    async def retrieve(
        self,
        request: RetrievalRequest,
    ) -> list[KnowledgeHit]:
        # 1. 为检索问题生成向量。
        vectors = await self._embed([request.query])
        query_vector = vectors[0]

        # 2. 获取融合后的候选片段。
        candidates = await self._search(
            query_text=request.query,
            query_vector=query_vector,
            recall_k=request.recall_k,
            top_k=request.recall_k,
            collection_name=request.collection_name,
        )

        if not candidates:
            return []

        # 3. 对候选片段重新排序。
        ranked = await self._rerank(
            query=request.query,
            documents=[item["text"] for item in candidates],
            top_n=request.top_n,
        )

        # 4. 将底层返回的数据转换为统一结果。
        return build_ranked_hits(candidates, ranked)