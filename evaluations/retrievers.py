from app.rag.adapters.embedding import embed_texts
from app.rag.adapters.qdrant import (
    search_bm25_knowledge,
    search_hybrid_knowledge,
    search_knowledge,
)
from app.rag.adapters.reranker import rerank_documents
from app.rag.ranking import build_ranked_hits, serialize_hybrid_hits

async def retrieve_for_comparison(
    question: str,
    collection_name: str,
    *,
    recall_k: int = 5,
    top_k: int = 3,
) -> dict[str, list[dict]]:
    """对同一个问题执行四种检索方案。"""

    if not question.strip():
        raise ValueError("问题不能为空。")

    if not 1 <= top_k <= recall_k:
        raise ValueError("需要满足 1 <= top_k <= recall_k。")

    # 1. BM25：直接用问题文本检索
    bm25_candidates = await search_bm25_knowledge(
        query_text=question,
        top_k=recall_k,
        collection_name=collection_name,
    )

    # 同一个问题只生成一次向量，供后面的方案共用
    vectors = await embed_texts([question])
    query_vector = vectors[0]

    # 2. Dense：只使用向量检索
    dense_candidates = await search_knowledge(
        query_vector=query_vector,
        top_k=recall_k,
        collection_name=collection_name,
    )

    # 3. Hybrid：BM25 与向量检索融合
    hybrid_candidates = await search_hybrid_knowledge(
        query_text=question,
        query_vector=query_vector,
        recall_k=recall_k,
        top_k=recall_k,
        collection_name=collection_name,
    )

    # 4. 在同一批混合检索候选上执行重排
    ranked = await rerank_documents(
        query=question,
        documents=[
            item["text"]
            for item in hybrid_candidates
        ],
        top_n=top_k,
    )

    hits = build_ranked_hits(hybrid_candidates, ranked)
    reranked = serialize_hybrid_hits(hits)
    return {
        "bm25": bm25_candidates[:top_k],
        "dense": dense_candidates[:top_k],
        "hybrid": hybrid_candidates[:top_k],
        "hybrid_rerank": reranked,
    }