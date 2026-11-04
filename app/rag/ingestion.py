"""将知识文档转换为向量并写入 Qdrant。"""

import asyncio
import math
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import AsyncQdrantClient

from app.core.config import get_settings
from app.rag.corpus import KnowledgeDocument
from app.services.embedding_service import embed_texts
from app.services.qdrant_initializer import VECTOR_SIZE, init_qdrant_collection
from app.rag.adapters.qdrant import upsert_knowledge_chunks

def expected_payloads(documents: list[KnowledgeDocument]) -> dict[str, dict]:
    return {
        str(uuid5(NAMESPACE_URL, f"{document.source}:{index}")): {
            "text": chunk,
            "source": document.source,
            "chunk_index": index,
        }
        for document in documents
        for index, chunk in enumerate(document.chunks)
    }


async def read_payloads(client: AsyncQdrantClient, collection: str) -> dict[str, dict]:
    result = {}
    offset = None
    while True:
        records, offset = await client.scroll(
            collection_name=collection,
            offset=offset,
            limit=256,
            with_payload=True,
            with_vectors=False,
        )
        for point in records:
            result[str(point.id)] = point.payload or {}
        if offset is None:
            return result


async def import_documents(
    documents: list[KnowledgeDocument],
    collection: str,
    batch_size: int,
) -> tuple[int, bool]:
    """仅 upsert 明确计划的点；不删除集合或任何额外记录。"""
    settings = get_settings()
    expected = expected_payloads(documents)

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=20,
    )
    try:
        exists = await client.collection_exists(collection)
        existing = await read_payloads(client, collection) if exists else {}
        if set(existing) - set(expected):
            raise ValueError("目标集合包含本轮语料之外的记录，请使用独立快照集合")
        reusable = bool(existing) and existing == expected
    finally:
        await client.close()

    if reusable:
        await init_qdrant_collection(collection_name=collection)
        print("目标快照内容已完整匹配，复用已有向量，不再调用 Embedding。", flush=True)
        return len(expected), True

    if not settings.LLM_API_KEY or not settings.LLM_BASE_URL:
        raise ValueError("Embedding 配置不完整")

    texts = [chunk for document in documents for chunk in document.chunks]
    vectors = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        async with asyncio.timeout(90):
            batch_vectors = await embed_texts(batch)
        if len(batch_vectors) != len(batch):
            raise ValueError("Embedding 返回数量与输入不一致")
        for vector in batch_vectors:
            if len(vector) != VECTOR_SIZE or not all(math.isfinite(x) for x in vector):
                raise ValueError("Embedding 向量维度或数值不符合要求")
        vectors.extend(batch_vectors)
        print(f"Embedding: {len(vectors)}/{len(texts)}", flush=True)

    # 全部向量校验通过后，才创建集合及写入数据。
    await init_qdrant_collection(collection_name=collection)
    offset = 0
    for document in documents:
        size = len(document.chunks)
        await upsert_knowledge_chunks(
            chunks=list(document.chunks),
            vectors=vectors[offset:offset + size],
            source=document.source,
            collection_name=collection,
        )
        offset += size
        print(f"已写入：{document.source} ({size} 片段)", flush=True)

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=20,
    )
    try:
        actual = await read_payloads(client, collection)
        if actual != expected:
            raise RuntimeError("导入后的点 ID 或正文、来源、片段编号校验失败")
        count = await client.count(collection_name=collection, exact=True)
        if count.count != len(expected):
            raise RuntimeError("导入后实际数量与计划不一致")
    finally:
        await client.close()
    return count.count, False