"""为单条检索问题的 Embedding 提供 Redis 缓存。"""

import asyncio
import hashlib
import json
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.rag.adapters.embedding import embed_texts

logger = logging.getLogger("uvicorn.error")


async def embed_query_with_cache(texts: list[str]) -> list[list[float]]:
    settings = get_settings()

    # 在线检索每次传一条问题。其他输入交给原来的批量函数。
    if not settings.REDIS_URL or len(texts) != 1:
        return await embed_texts(texts)

    key_material = json.dumps(
        [settings.LLM_BASE_URL, settings.EMBEDDING_MODEL, texts[0]],
        ensure_ascii=False,
    )
    digest = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
    key = f"omnisupport:rag:embedding:v1:{digest}"

    async with Redis.from_url(settings.REDIS_URL) as client:
        try:
            async with asyncio.timeout(0.5):
                cached = await client.get(key)
        except (RedisError, TimeoutError):
            logger.warning("Embedding 缓存读取失败，直接调用模型")
            return await embed_texts(texts)

        if cached is not None:
            try:
                vector = json.loads(cached)
            except (ValueError, UnicodeError):
                vector = None

            if isinstance(vector, list) and vector:
                logger.info("Embedding 缓存命中")
                return [vector]

        logger.info("Embedding 缓存未命中，调用模型")
        vectors = await embed_texts(texts)

        if len(vectors) == 1 and vectors[0]:
            try:
                async with asyncio.timeout(0.5):
                    await client.set(
                        key,
                        json.dumps(vectors[0]),
                        ex=settings.RAG_EMBED_CACHE_TTL_SECONDS,
                    )
            except (RedisError, TimeoutError):
                logger.warning("Embedding 缓存写入失败，继续使用已生成的向量")

        return vectors