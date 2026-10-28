#make_url()解析现有数据库连接配置。
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def get_checkpointer_conninfo() -> str:
    """获取 LangGraph PostgreSQL Checkpointer 使用的连接字符串。"""

    database_url = get_settings().DATABASE_URL

    if not database_url:
        raise ValueError(
            "DATABASE_URL 未配置，无法初始化 LangGraph Checkpointer"
        )

    url = make_url(database_url)

    # 目前项目使用 psycopg 驱动
    if url.drivername not in {
        "postgresql+psycopg",
        "postgresql",
    }:
        raise ValueError(
            f"不支持的 Checkpointer 数据库驱动：{url.drivername}"
        )

    # 将 SQLAlchemy 驱动形式转换为 Psycopg 使用的 URL 形式
    return url.set(
        drivername="postgresql"
    ).render_as_string(hide_password=False)
