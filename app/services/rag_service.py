
from app.services.embedding_service import embed_texts
from app.services.qdrant_service import search_hybrid_knowledge
from app.services.rerank_service import rerank_documents


async def retrieve_relevant_knowledge(
    question: str,
    recall_k: int = 5,
    top_n: int = 3,
) -> list[dict]:
    """通过混合检索、RRF 融合和 Rerank 获取相关企业知识。"""

    if not question.strip():
        return []

    # 1. 将用户问题转换成向量，供向量检索使用
    query_vectors = await embed_texts([question])
    query_vector = query_vectors[0]

    # 2. 同时执行 BM25 和向量检索，并通过 RRF 融合结果
    candidates = await search_hybrid_knowledge(
        query_text=question,
        query_vector=query_vector,
        recall_k=recall_k,
        top_k=recall_k,
    )

    if not candidates:
        return []

    # 3. 提取融合检索得到的候选知识正文
    documents = [
        candidate["text"]
        for candidate in candidates
    ]

    # 4. 使用 Reranker 对候选知识重新排序
    ranked = await rerank_documents(
        query=question,
        documents=documents,
        top_n=top_n,
    )

    # 5. 根据 Reranker 返回的原始索引找回知识信息
    results = []

    for item in ranked:
        original = candidates[item["index"]]

        results.append({
            "text": original["text"],
            "source": original["source"],
            "chunk_index": original["chunk_index"],
            "hybrid_score": original["score"],
            "rerank_score": item["score"],
        })

    return results
