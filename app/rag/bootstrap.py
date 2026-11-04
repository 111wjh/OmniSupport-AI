"""组装知识检索器及其依赖。"""

from app.rag.contracts import KnowledgeRetriever
from app.rag.pipeline import HybridRerankRetriever
from app.rag.adapters.embedding import embed_texts
from app.rag.adapters.qdrant import search_hybrid_knowledge
from app.rag.adapters.reranker import rerank_documents


def build_knowledge_retriever() -> KnowledgeRetriever:
    return HybridRerankRetriever(
        embed=embed_texts,
        search=search_hybrid_knowledge,
        rerank=rerank_documents,
    )