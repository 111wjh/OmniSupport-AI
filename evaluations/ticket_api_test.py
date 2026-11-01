import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from evaluations.ticket_test_db import (
    TEST_DATABASE,
    run_async,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def configure_test_database():
    """在导入后端应用之前，切换当前进程的数据库配置。"""
    database_url = get_settings().DATABASE_URL

    if not database_url:
        raise ValueError("DATABASE_URL 未配置。")

    test_url = make_url(database_url).set(
        database=TEST_DATABASE
    )

    os.environ["DATABASE_URL"] = test_url.render_as_string(
        hide_password=False
    )

    # 清除旧配置缓存，让后续模块读取新的数据库地址
    get_settings.cache_clear()

    return test_url


def initialize_database(test_url) -> None:
    """确认连接目标，再通过 Alembic 初始化测试库。"""
    engine = create_engine(test_url)

    try:
        with engine.connect() as connection:
            actual_database = connection.scalar(
                text("SELECT current_database()")
            )

            if actual_database != TEST_DATABASE:
                raise RuntimeError("连接目标不是指定测试库。")
    finally:
        engine.dispose()

    from alembic import command
    from alembic.config import Config

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    print(f"测试库迁移完成：{TEST_DATABASE}")


def start_server() -> None:
    import uvicorn

    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=8001,
        log_level="info",
    )
    server = uvicorn.Server(config)

    run_async(server.serve())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("init", "serve"),
    )
    args = parser.parse_args()

    test_url = configure_test_database()
    print(f"当前目标数据库：{TEST_DATABASE}")

    if args.action == "init":
        initialize_database(test_url)
    else:
        start_server()


if __name__ == "__main__":
    main()