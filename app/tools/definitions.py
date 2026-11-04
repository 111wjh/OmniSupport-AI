from app.schemas.agent_ticket import CreateSupportTicketArguments
from app.tools.registry import registered_tool_definitions










SUBMIT_REFUND_REQUEST_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_refund_request",
        "description": (
            "为当前已认证客户提交退款申请。"
            "仅当客户明确要求申请退款时使用，"
            "不能仅因客户询问退款政策或退款资格就自动提交。"
            "必须提供真实订单编号和退款原因。"
            "后端负责验证客户身份、订单归属和退款资格。"
            "本工具只创建待审核申请，不批准退款，也不执行退款。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_number": {
                    "type": "string",
                    "description": "客户本人订单的完整订单编号。",
                    "minLength": 1,
                    "maxLength": 50,
                },
                "reason": {
                    "type": "string",
                    "description": "客户填写的退款原因，长度为 5 到 2000 个字符。",
                    "minLength": 5,
                    "maxLength": 2000,
                },
            },
            "required": [
                "order_number",
                "reason",
            ],
            "additionalProperties": False,
        },
    },
}



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
    SUBMIT_REFUND_REQUEST_TOOL,
    CREATE_SUPPORT_TICKET_TOOL,
]
