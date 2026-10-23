
from app.services.embedding_service import embed_texts
from app.services.qdrant_service import search_knowledge
from app.services.rerank_service import rerank_documents


async def retrieve_relevant_knowledge(
    question: str,
    recall_k: int = 5,
    top_n: int = 3,
) -> list[dict]:
    """通过向量检索和 Rerank 获取相关企业知识。"""

    if not question.strip():
        return []

    # 1. 将用户问题转换为向量
    query_vectors = await embed_texts([question])
    query_vector = query_vectors[0]

    # 2. 使用 Qdrant 召回候选知识
    candidates = await search_knowledge(
        query_vector=query_vector,
        top_k=recall_k,
    )

    if not candidates:
        return []

    # 3. 提取候选知识正文
    documents = [
        candidate["text"]
        for candidate in candidates
    ]

    # 4. 调用 Rerank 模型重新排序
    ranked = await rerank_documents(
        query=question,
        documents=documents,
        top_n=top_n,
    )

    # 5. 根据原始索引找回知识来源等信息
    results = []

    for item in ranked:
        original = candidates[item["index"]]

        results.append({
            "text": original["text"],
            "source": original["source"],
            "chunk_index": original["chunk_index"],
            "vector_score": original["score"],
            "rerank_score": item["score"],
        })

    return results
