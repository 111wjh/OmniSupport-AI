from functools import lru_cache
from pydantic_settings import BaseSettings,SettingsConfigDict

#Settings 继承 BaseSettings 后，就能从环境变量读取同名配置，并自动校验数据类型。
class Settings(BaseSettings):
    APP_NAME: str = "OmniSupport AI"
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore",)

@lru_cache
def get_settings() -> Settings:
    return Settings()