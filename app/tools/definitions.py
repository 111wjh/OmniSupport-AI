

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

AGENT_TOOLS = [
    ORDER_STATUS_TOOL,
    KNOWLEDGE_SEARCH_TOOL,
]
