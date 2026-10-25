
from functools import lru_cache

from langfuse import Langfuse

from app.core.config import get_settings


@lru_cache
def get_langfuse_client() -> Langfuse:
    """获取全局复用的 Langfuse 客户端。"""

    settings = get_settings()

    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        base_url=settings.LANGFUSE_BASE_URL,
    )
