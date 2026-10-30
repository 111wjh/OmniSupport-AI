from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DemoOrderCreate(BaseModel):
    """本地创建演示订单时使用的输入数据。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    customer_email: EmailStr

    product_name: str = Field(
        default="联调演示商品",
        min_length=1,
        max_length=180,
    )

    total_amount: Decimal = Field(
        default=Decimal("99.00"),
        gt=0,
        max_digits=12,
        decimal_places=2,
    )