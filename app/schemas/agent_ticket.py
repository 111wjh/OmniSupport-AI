from pydantic import BaseModel, ConfigDict, Field


class CreateSupportTicketArguments(BaseModel):
    """Agent 创建人工服务工单时允许提交的参数。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    subject: str = Field(
        min_length=1,
        max_length=200,
        description="根据客户实际诉求整理的工单标题。",
    )

    description: str = Field(
        min_length=5,
        max_length=4000,
        description="根据客户已提供的信息整理的问题说明，不得编造。",
    )

    order_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="与本次问题相关的订单编号；未提供时留空。",
    )