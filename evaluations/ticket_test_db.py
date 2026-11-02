import asyncio
import selectors
import sys
from contextlib import asynccontextmanager
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import get_settings
from app.db.base import Base
from app.models import (
    Conversation,
    Customer,
    Order,
    Staff,
    Ticket,
    TicketMessage,
    Message,
    ChatOperation,
)


TEST_DATABASE = "omnisupport_concurrency_test"

TEST_TABLES = [
    Customer.__table__,
    Staff.__table__,
    Order.__table__,
    Conversation.__table__,
    Ticket.__table__,
    TicketMessage.__table__,
    Message.__table__,
    ChatOperation.__table__,
]


def run_async(coroutine):
    """在 Windows 下使用 Psycopg 支持的事件循环。"""
    if sys.platform == "win32":
        return asyncio.run(
            coroutine,
            loop_factory=lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector()
            ),
        )

    return asyncio.run(coroutine)


@asynccontextmanager
async def ticket_test_database():
    """创建隔离测试表，提供 Session 工厂，并负责清理。"""
    configured_url = get_settings().DATABASE_URL

    if not configured_url:
        raise ValueError("DATABASE_URL 未配置。")

    test_url = make_url(configured_url).set(
        database=TEST_DATABASE
    )
    schema_name = f"ticket_test_{uuid4().hex}"

    engine = create_async_engine(
        test_url,
        isolation_level="READ COMMITTED",
        execution_options={
            "schema_translate_map": {None: schema_name}
        },
        connect_args={
            "options": (
                "-c statement_timeout=15000 "
                "-c lock_timeout=10000"
            )
        },
    )

    sessions = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    created = False

    try:
        async with engine.begin() as connection:
            actual_database = await connection.scalar(
                text("SELECT current_database()")
            )

            if actual_database != TEST_DATABASE:
                raise RuntimeError("连接目标不是指定的测试库。")

            await connection.execute(
                CreateSchema(schema_name)
            )
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=TEST_TABLES,
                )
            )

        created = True
        yield sessions

    finally:
        try:
            if created:
                async with engine.begin() as connection:
                    await connection.execute(
                        DropSchema(schema_name, cascade=True)
                    )
        finally:
            await engine.dispose()


async def main() -> None:
    async with ticket_test_database() as sessions:
        async with sessions() as session:
            count = await session.scalar(
                select(func.count()).select_from(Ticket)
            )

            print("专用测试库连接成功")
            print(f"隔离表已创建，工单数量：{count}")

    print("本轮测试 schema 已清理")


if __name__ == "__main__":
    run_async(main())