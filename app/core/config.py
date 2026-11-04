from functools import lru_cache
from pydantic_settings import BaseSettings,SettingsConfigDict
from pydantic import Field
#Settings 继承 BaseSettings 后，就能从环境变量读取同名配置，并自动校验数据类型。
class Settings(BaseSettings):
     # FastAPI 基础配置
    APP_NAME: str = "OmniSupport AI"
    DEBUG: bool = False

    # 大语言模型配置
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = ""
    LLM_BASE_URL: str | None = None
    # PostgreSQL 数据库配置
    DATABASE_URL: str | None = None
    # JWT 身份认证配置
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    RERANK_API_URL: str = ""
    # Langfuse 可观测性配置
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_BASE_URL: str = "https://jp.cloud.langfuse.com"
    # Qdrant 向量数据库配置
    QDRANT_URL: str = "http://127.0.0.1:6333"
    QDRANT_API_KEY: str | None = None
    # 知识检索配置
    EMBEDDING_MODEL: str = "qwen3.7-text-embedding-flash"
    RERANK_MODEL: str = "qwen3.7-text-rerank"
    KNOWLEDGE_COLLECTION: str = "omnisupport_knowledge"

    # 融合检索的候选数量，以及重排后的返回数量
    RAG_RECALL_K: int = Field(default=5, ge=1)
    RAG_TOP_N: int = Field(default=3, ge=1)
    REDIS_URL: str | None = None
    RAG_EMBED_CACHE_TTL_SECONDS: int = Field(default=3600, ge=1)
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore",)

@lru_cache
def get_settings() -> Settings:
    return Settings()