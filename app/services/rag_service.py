"""兼容现有调用方的知识检索入口。"""

from typing import Any

from app.core.config import get_settings
from app.rag.bootstrap import build_knowledge_retriever
from app.rag.contracts import RetrievalRequest


async def retrieve_relevant_knowledge(
    question: str,
    recall_k: int | None = None,
    top_n: int | None = None,
    *,
    collection_name: str | None = None,
) -> list[dict[str, Any]]:
    """调用新检索实现，暂时保持原有字典返回格式。"""

    # 保留旧入口对空问题的处理方式。
    if not question.strip():
        return []

    settings = get_settings()

    request = RetrievalRequest(
        query=question,
        collection_name=(
            settings.KNOWLEDGE_COLLECTION
            if collection_name is None
            else collection_name
        ),
        recall_k=(
            settings.RAG_RECALL_K
            if recall_k is None
            else recall_k
        ),
        top_n=(
            settings.RAG_TOP_N
            if top_n is None
            else top_n
        ),
    )

    retriever = build_knowledge_retriever()
    hits = await retriever.retrieve(request)

    # 旧调用方仍使用字典，因此在这个边界转换格式。
    return [
        {
            "text": hit.text,
            "source": hit.source,
            "chunk_index": hit.chunk_index,
            "hybrid_score": hit.retrieval_score,
            "rerank_score": hit.rerank_score,
        }
        for hit in hits
    ]