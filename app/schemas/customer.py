
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class CustomerRegisterRequest(BaseModel):
    """客户注册请求。"""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    display_name: str = Field(
        min_length=1,
        max_length=100,
    )


class CustomerResponse(BaseModel):
    """返回给前端的客户信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str
    is_active: bool
