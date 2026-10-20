
import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError
import logging

logger = logging.getLogger(__name__)

class OrderStatusArguments(BaseModel):
    """订单查询工具的参数。"""

    model_config = ConfigDict(extra="forbid")

    order_number: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9-]+$",
    )


async def execute_tool(
    tool_name: str,
    arguments: str,
) -> dict:
    """统一执行 Agent 工具。"""

    logger.info(
    "Agent tool requested: %s",
    tool_name,
    )
    # 1. 只允许执行已注册的工具
    if tool_name != "get_order_status":
        return {
            "success": False,
            "error": "unknown_tool",
            "message": "不支持的工具",
        }

    # 2. 验证模型传来的 JSON 参数
    try:
        args = OrderStatusArguments.model_validate_json(
            arguments
        )
    except ValidationError:
        return {
            "success": False,
            "error": "invalid_arguments",
            "message": "订单查询参数不合法",
        }

    # 3. 当前尚未实现客户身份认证，因此拒绝查询
    return {
        "success": False,
        "error": "authentication_required",
        "message": (
            "订单查询需要先验证客户身份。"
            "当前系统尚未接入身份认证，无法查询订单。"
        ),
    }
