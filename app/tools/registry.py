"""已迁移到注册表的本地 Agent 工具。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel
from uuid import UUID
from app.tools.knowledge_tools import (
    KnowledgeSearchArguments,
    execute_search_knowledge,
)
from app.tools.context import ToolContext
from app.tools.order_tools import OrderStatusArguments, execute_get_order_status


@dataclass(frozen=True)
class ToolSpec:
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[str, ToolContext], Awaitable[dict]]

REGISTERED_TOOLS: dict[str, ToolSpec] = {
    "get_order_status": ToolSpec(
        description=(
            "查询当前已认证客户自己的订单状态。"
            "提供订单编号时查询指定订单，未提供时查询最近一笔订单。"
            "后端负责验证客户身份及订单归属。"
        ),
        arguments_model=OrderStatusArguments,
        handler=execute_get_order_status,
    ),
    "search_knowledge": ToolSpec(
        description=(
            "检索企业知识库中的产品信息、保修政策、"
            "退换货规则、物流说明及售后服务规定。"
            "当用户咨询这些知识时使用。"
            "不要使用此工具查询客户个人订单的实时状态；"
            "订单状态应使用 get_order_status 工具查询。"
        ),
        arguments_model=KnowledgeSearchArguments,
        handler=execute_search_knowledge,
    ),
}


def registered_tool_definitions() -> list[dict]:
    """生成模型能读取的工具定义。"""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": spec.description,
                "parameters": spec.arguments_model.model_json_schema(),
            },
        }
        for name, spec in REGISTERED_TOOLS.items()
    ]