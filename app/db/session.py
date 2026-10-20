from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL 未配置，请检查 .env 文件")


# 创建异步数据库引擎,负责建立和管理 PostgreSQL 连接池。
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

#Engine 管数据库连接，Session 管一次业务数据库操作。
# 创建异步数据库 Session 工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)