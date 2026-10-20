
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.db.base import Base


# 注册所有 ORM 模型
import app.models  # noqa: F401


# 获取 Alembic 配置
config = context.config

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# 读取项目数据库配置
settings = get_settings()

if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL 未配置，请检查 .env 文件")


# 告诉 Alembic 使用哪些 ORM 模型
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：不连接数据库，生成 SQL。"""

    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接 PostgreSQL 执行迁移。"""

    # 使用同步引擎运行 Alembic
    connectable = create_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
