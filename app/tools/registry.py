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
from app.tools.refund_tools import (
    GetRefundExecutionArguments,
    ListMyRefundsArguments,
    execute_get_refund_execution,
    execute_list_my_refunds,
)

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
    "list_my_refunds": ToolSpec(
        description=(
            "查询当前已认证客户自己的退款申请列表。"
            "当客户询问退款申请进度、历史退款申请或审核状态时使用。"
            "必须由后端根据已认证的客户 ID 限定查询范围。"
            "不得查询其他客户的退款申请。"
        ),
        arguments_model=ListMyRefundsArguments,
        handler=execute_list_my_refunds,
    ),
    "get_refund_execution": ToolSpec(
        description=(
            "查询当前已认证客户自己的退款执行结果。"
            "需要退款申请编号，可先通过 list_my_refunds 获取。"
            "审核通过不代表退款已执行。执行结果为模拟退款，"
            "即使返回 succeeded，也不能声称真实资金已经到账。"
        ),
        arguments_model=GetRefundExecutionArguments,
        handler=execute_get_refund_execution,
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