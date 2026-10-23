
from openai import AsyncOpenAI

from app.core.config import get_settings


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量将文本转换为 Embedding 向量。"""

    if not texts:
        return []

    settings = get_settings()

    async with AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    ) as client:
        response = await client.embeddings.create(
            model="qwen3.7-text-embedding-flash",
            input=texts,
        )

    # 按输入顺序整理返回的向量
    sorted_data = sorted(
        response.data,
        key=lambda item: item.index,
    )

    return [item.embedding for item in sorted_data]
