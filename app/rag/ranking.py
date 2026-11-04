"""把重排索引还原成带正文和来源的知识片段。"""

from app.rag.contracts import KnowledgeHit


def build_ranked_hits(
    candidates: list[dict],
    ranked: list[dict],
) -> list[KnowledgeHit]:
    hits: list[KnowledgeHit] = []

    for item in ranked:
        original = candidates[item["index"]]

        hits.append(
            KnowledgeHit(
                text=original["text"],
                source=original["source"],
                chunk_index=original["chunk_index"],
                retrieval_score=original["score"],
                rerank_score=item["score"],
            )
        )

    return hits

def serialize_hybrid_hits(hits: list[KnowledgeHit]) -> list[dict]:
    """把知识片段转换成现有接口和评测报告使用的字典。"""
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