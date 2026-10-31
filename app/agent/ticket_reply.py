"""根据工单创建工具的实际结果生成回复。"""

from typing import Any
from uuid import UUID


UNCONFIRMED_REPLY = (
    "暂时无法确认本次人工服务工单是否创建成功。\n"
    "请先查询工单列表核对，确认前请勿重复创建。"
)

STATUS_LABELS = {
    "open": "待领取",
    "in_progress": "处理中",
    "closed": "已关闭",
}

REJECTION_REPLIES = {
    "authentication_required": (
        "本次未创建工单：请先登录，再申请人工服务。"
    ),
    "conversation_required": (
        "本次未创建工单：缺少当前聊天会话。"
    ),
    "invalid_arguments": (
        "本次未创建工单：标题、问题说明或订单编号不符合要求。\n"
        "请补充或核对相关信息。"
    ),
    "related_resource_not_found": (
        "本次未创建工单：关联的订单或会话不存在，"
        "或当前账号无权关联。\n"
        "请核对订单编号和登录账号。"
    ),
}


def build_ticket_creation_reply(
    tool_result: dict[str, Any],
) -> str:
    """区分创建成功、明确拒绝和结果无法确认。"""

    if tool_result.get("success") is True:
        data = tool_result.get("data")

        if not isinstance(data, dict):
            return UNCONFIRMED_REPLY

        ticket_id = data.get("id")
        status = data.get("status")

        if (
            not isinstance(ticket_id, str)
            or not isinstance(status, str)
            or status not in STATUS_LABELS
        ):
            return UNCONFIRMED_REPLY

        # 成功回复必须包含格式合法的工单编号。
        try:
            ticket_id = str(UUID(ticket_id))
        except ValueError:
            return UNCONFIRMED_REPLY

        status_label = STATUS_LABELS[status]

        return (
            "人工服务工单已创建。\n"
            f"工单编号：{ticket_id}\n"
            f"本次读取的状态：{status_label}。\n"
            "创建工单不代表人工客服已实时接入聊天，"
            "后续通过工单沟通记录查看工作人员回复。"
        )

    if tool_result.get("success") is False:
        error = tool_result.get("error")

        if isinstance(error, str) and error in REJECTION_REPLIES:
            return REJECTION_REPLIES[error]

    return UNCONFIRMED_REPLY