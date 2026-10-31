from app.schemas.agent_ticket import CreateSupportTicketArguments

ORDER_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_order_status",
        "description": (
            "查询当前已认证客户自己的订单状态。"
            "当用户要求查询订单、最近一笔订单或订单详情时使用。"
            "如果用户提供了订单编号，将 order_number 设置为该编号。"
            "如果用户没有提供订单编号，查询当前客户最近一笔订单，"
            "此时可以不传 order_number。"
            "必须由后端验证客户身份及订单归属。"
            "不能向未认证用户泄露订单信息。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_number": {
                    "type": "string",
                    "description": (
                        "可选的订单编号。用户提供编号时查询指定订单；"
                        "未提供时查询当前客户最近一笔订单。"
                    ),
                }
            },
            "additionalProperties": False,
        },
    },
}



KNOWLEDGE_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": (
            "检索企业知识库中的产品信息、保修政策、"
            "退换货规则、物流说明及售后服务规定。"
            "当用户咨询这些知识时使用。"
            "不要使用此工具查询客户个人订单的实时状态；"
            "订单状态应使用 get_order_status 工具查询。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要检索的企业知识问题",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


LIST_MY_REFUNDS_TOOL = {
    "type": "function",
    "function": {
        "name": "list_my_refunds",
        "description": (
            "查询当前已认证客户自己的退款申请列表。"
            "当客户询问退款申请进度、历史退款申请或审核状态时使用。"
            "必须由后端根据已认证的客户 ID 限定查询范围。"
            "不得查询其他客户的退款申请。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "最多返回的记录数，范围为 1 到 100，默认 20。",
                    "minimum": 1,
                    "maximum": 100,
                },
                "offset": {
                    "type": "integer",
                    "description": "分页跳过的记录数，默认 0。",
                    "minimum": 0,
                },
            },
            "additionalProperties": False,
        },
    },
}


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

GET_REFUND_EXECUTION_TOOL = {
    "type": "function",
    "function": {
        "name": "get_refund_execution",
        "description": (
            "查询当前已认证客户自己的退款执行结果。"
            "当客户询问退款是否执行成功时使用。"
            "需要退款申请编号，可先通过 list_my_refunds 获取。"
            "审核通过不代表退款执行成功。"
            "当前系统执行的是模拟退款，"
            "即使返回 succeeded，也不能声称真实资金已经到账。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "refund_request_id": {
                    "type": "string",
                    "description": (
                        "退款申请的 UUID，"
                        "不是订单编号，也不是退款执行记录编号。"
                    ),
                },
            },
            "required": ["refund_request_id"],
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
    ORDER_STATUS_TOOL,
    KNOWLEDGE_SEARCH_TOOL,
    LIST_MY_REFUNDS_TOOL,
    SUBMIT_REFUND_REQUEST_TOOL,
    GET_REFUND_EXECUTION_TOOL,
    CREATE_SUPPORT_TICKET_TOOL,
]
