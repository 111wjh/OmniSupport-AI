import asyncio
import selectors
import sys

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import AsyncSessionLocal, engine
from app.schemas.demo_order import DemoOrderCreate
from app.services.demo_order_service import create_demo_order


def read_input() -> DemoOrderCreate:
    """读取终端输入，空白的可选项使用 Schema 默认值。"""

    values = {
        "customer_email": input("客户邮箱: ").strip(),
    }

    product_name = input(
        "商品名称 [联调演示商品]: "
    ).strip()

    if product_name:
        values["product_name"] = product_name

    total_amount = input("订单金额 [99.00]: ").strip()

    if total_amount:
        values["total_amount"] = total_amount

    return DemoOrderCreate.model_validate(values)


async def main(data: DemoOrderCreate) -> None:
    """在一个事务中创建演示订单，并释放数据库资源。"""

    try:
        async with AsyncSessionLocal.begin() as session:
            order = await create_demo_order(
                session=session,
                data=data,
            )

        # 离开事务上下文且没有异常，才说明提交成功。
        print("模拟演示订单创建成功")
        print(f"订单号: {order.order_number}")
        print(f"客户邮箱: {str(data.customer_email).lower()}")
        print(f"商品名称: {order.product_name}")
        print(f"金额: {order.total_amount:.2f}")
        print(f"状态: {order.status}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        data = read_input()

        if sys.platform == "win32":
            asyncio.run(
                main(data),
                loop_factory=lambda: asyncio.SelectorEventLoop(
                    selectors.SelectSelector()
                ),
            )
        else:
            asyncio.run(main(data))

    except (ValidationError, ValueError) as exc:
        print(f"创建失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    except SQLAlchemyError:
        print(
            "数据库操作发生异常，暂时无法确认创建结果。"
            "请先查询该客户的订单列表，确认后再决定是否重试。",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    except (KeyboardInterrupt, EOFError):
        print("\n已退出创建命令。", file=sys.stderr)
        raise SystemExit(130) from None