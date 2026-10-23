
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct
from app.core.config import get_settings

async def upsert_knowledge_chunks(
    chunks: list[str],
    vectors: list[list[float]],
    source: str,
    qdrant_url: str | None = None,
    collection_name: str = "omnisupport_knowledge",
) -> int:
    """将知识片段及其向量写入 Qdrant。"""

    # 确保每个知识片段都有对应的向量
    if len(chunks) != len(vectors):
        raise ValueError("知识片段数量与向量数量不一致")

    if not chunks:
        return 0

    # 将知识片段转换成 Qdrant 数据点
    points = [
        PointStruct(
            id=str(uuid5(NAMESPACE_URL, f"{source}:{index}")),
            vector=vector,
            payload={
                "text": chunk,
                "source": source,
                "chunk_index": index,
            },
        )
        for index, (chunk, vector) in enumerate(
            zip(chunks, vectors)
        )
    ]

    settings = get_settings()

    client = AsyncQdrantClient(
        url=qdrant_url or settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )

    try:
        await client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
        )
    finally:
        await client.close()

    return len(points)




async def search_knowledge(
    query_vector: list[float],
    top_k: int = 3,
    qdrant_url: str | None = None,
    collection_name: str = "omnisupport_knowledge",
) -> list[dict]:
    """根据问题向量，检索最相关的企业知识。"""

    settings = get_settings()

    client = AsyncQdrantClient(
        url=qdrant_url or settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )

    try:
        response = await client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )
    finally:
        await client.close()

    results = []

    for point in response.points:
        payload = point.payload or {}

        results.append({
            "score": point.score,
            "text": payload.get("text", ""),
            "source": payload.get("source", ""),
            "chunk_index": payload.get("chunk_index"),
        })

    return results