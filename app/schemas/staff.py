
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StaffLoginRequest(BaseModel):
    """员工登录请求。"""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(
        min_length=1,
        max_length=128,
    )


class StaffResponse(BaseModel):
    """返回给前端的员工信息，不包含密码哈希。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str
    role: Literal[
        "admin",
        "customer_support",
        "refund_reviewer",
    ]
    is_active: bool


class StaffTokenResponse(BaseModel):
    """员工登录成功后返回的访问令牌。"""

    access_token: str
    token_type: str = "bearer"
