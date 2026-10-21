from functools import lru_cache
from pydantic_settings import BaseSettings,SettingsConfigDict

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
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore",)

@lru_cache
def get_settings() -> Settings:
    return Settings()