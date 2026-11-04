"""组装知识检索器及其依赖。"""

from app.rag.contracts import KnowledgeRetriever
from app.rag.pipeline import HybridRerankRetriever
from app.rag.adapters.embedding_cache import embed_query_with_cache
from app.rag.adapters.qdrant import search_hybrid_knowledge
from app.rag.adapters.reranker import rerank_documents


def build_knowledge_retriever() -> KnowledgeRetriever:
    return HybridRerankRetriever(
        embed=embed_query_with_cache,
        search=search_hybrid_knowledge,
        rerank=rerank_documents,
    )