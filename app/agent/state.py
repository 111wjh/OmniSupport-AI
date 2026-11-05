
from operator import add
from typing import Annotated, Any, TypedDict, NotRequired
from uuid import UUID


class AgentState(TypedDict):
    """LangGraph Agent 工作流共享状态。"""

    # 保存系统提示词、历史消息、模型回复和工具结果。
    # add 表示节点返回的新消息会追加到现有列表。
    messages: Annotated[list[dict[str, Any]], add]

    # 当前经过身份认证的客户 ID。
    # 工具执行时使用它限制订单查询范围。
    customer_id: UUID | None
    # 当前工作流已经调用大模型的次数
    model_calls: int
    # 是否启用流式输出；未提供时默认为 False
    stream_enabled: NotRequired[bool]
    # 当前聊天会话，由后端传入，供工单关联使用。
    conversation_id: NotRequired[UUID | None]
    # 根据本轮业务工具的实际结果生成的固定回复。
    business_reply: NotRequired[str | None]
    # 服务端生成，绝不从模型参数读取。
    ticket_idempotency_key: NotRequired[str | None]
