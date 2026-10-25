
from qdrant_client import AsyncQdrantClient, models
import asyncio
from app.core.config import get_settings


COLLECTION_NAME = "omnisupport_knowledge"
VECTOR_SIZE = 1024


async def init_qdrant_collection() -> None:
    """初始化 Qdrant 集合和 BM25 全文索引。"""

    settings = get_settings()

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )

    try:
        # 1. 检查 Collection 是否存在
        exists = await client.collection_exists(
            collection_name=COLLECTION_NAME,
        )

        # 2. 不存在时，创建稠密向量集合
        if not exists:
            await client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                ),
            )
            print(f"Collection 创建成功：{COLLECTION_NAME}")
        else:
            print(f"Collection 已存在：{COLLECTION_NAME}")

        # 3. 检查 text 字段是否已有索引
        info = await client.get_collection(
            collection_name=COLLECTION_NAME,
        )
        # 检查现有 Collection 的稠密向量配置
        vector_config = info.config.params.vectors

        if not isinstance(vector_config, models.VectorParams):
            raise ValueError("Collection 向量配置不是预期的单向量结构")

        if vector_config.size != VECTOR_SIZE:
            raise ValueError(
                f"Collection 向量维度错误："
                f"预期 {VECTOR_SIZE}，实际 {vector_config.size}"
            )

        if vector_config.distance != models.Distance.COSINE:
            raise ValueError(
                "Collection 距离算法错误：预期 COSINE"
            )

        print("Collection 向量配置正确")

        payload_schema = info.payload_schema or {}

        if "text" in payload_schema:
            index_info = payload_schema["text"]
            params = index_info.params

            valid = (
                isinstance(params, models.TextIndexParams)
                and params.tokenizer == models.TokenizerType.MULTILINGUAL
                and params.lowercase is True
                and params.scoring is not None
                and params.scoring.type == models.TextScoringType.BM25
            )

            if not valid:
                raise ValueError(
                    "text 索引配置不符合要求："
                    "需要 MULTILINGUAL 分词器和 BM25 评分"
                )

            print("BM25 索引配置正确，跳过创建")
        else:
            # 4. 为知识正文创建 BM25 全文索引
            await client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="text",
                field_schema=models.TextIndexParams(
                    type=models.TextIndexType.TEXT,
                    tokenizer=models.TokenizerType.MULTILINGUAL,
                    lowercase=True,
                    scoring=models.TextScoringParams(
                        type=models.TextScoringType.BM25,
                    ),
                ),
                wait=True,
            )

            print("BM25 全文索引创建成功")

    finally:
        # 5. 释放 Qdrant 客户端连接
        await client.close()

if __name__ == "__main__":
    asyncio.run(init_qdrant_collection())