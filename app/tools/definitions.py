from app.schemas.agent_ticket import CreateSupportTicketArguments
from app.tools.registry import registered_tool_definitions



CREATE_SUPPORT_TICKET_TOOL = {
    "type": "function",
    "function": {
        "name": "create_support_ticket",
        "description": (
            "为当前已认证客户创建人工服务工单，并关联当前聊天会话。"
            "仅当客户明确要求创建工单或转人工协助时使用。"
            "必须根据客户已提供的信息整理标题和问题说明，不得编造。"
            "如果尚不清楚需要人工处理的问题，应先询问。"
            "订单编号为可选项，客户未提供时可以省略，不得猜测。"
            "客户身份和当前会话由后端提供，不接受模型指定。"
            "创建成功仅代表进入待处理队列，不代表人工客服已经接入。"
            "结果无法确认时，不得自动重复调用，应先核对工单列表。"
        ),
        "parameters": (
            CreateSupportTicketArguments.model_json_schema()
        ),
    },
}
AGENT_TOOLS = [
    *registered_tool_definitions(),
    CREATE_SUPPORT_TICKET_TOOL,
]
