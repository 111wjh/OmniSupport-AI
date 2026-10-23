
ORDER_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_order_status",
        "description": (
            "查询当前已认证客户自己的订单状态。"
            "当用户明确要求查询订单时使用。"
            "必须先由后端验证客户身份及订单归属。"
            "不能凭订单编号直接向未认证用户泄露订单信息。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_number": {
                    "type": "string",
                    "description": "订单编号，例如 OMNI20260001",
                }
            },
            "required": ["order_number"],
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

AGENT_TOOLS = [
    ORDER_STATUS_TOOL,
    KNOWLEDGE_SEARCH_TOOL,
]
