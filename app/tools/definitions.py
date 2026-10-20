
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

AGENT_TOOLS = [ORDER_STATUS_TOOL]
