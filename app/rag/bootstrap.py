"""组装知识检索器及其依赖。"""

from app.rag.contracts import KnowledgeRetriever
from app.rag.pipeline import HybridRerankRetriever
from app.services.embedding_service import embed_texts
from app.rag.adapters.qdrant import search_hybrid_knowledge
from app.services.rerank_service import rerank_documents


def build_knowledge_retriever() -> KnowledgeRetriever:
    return HybridRerankRetriever(
        embed=embed_texts,
        search=search_hybrid_knowledge,
        rerank=rerank_documents,
    )