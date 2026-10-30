"""根据退款提交工具的真实结果生成回复。"""

from typing import Any
from uuid import UUID


UNCONFIRMED_REPLY = (
    "暂时无法确认本次退款申请是否提交成功。\n"
    "请先查询退款申请列表，核对是否已有对应记录，"
    "确认前请勿重复提交。"
)


REJECTION_REPLIES = {
    "refund_already_exists": (
        "本次没有新建退款申请：该订单已存在有效的退款申请。\n"
        "请查询已有申请的审核状态或退款执行结果。"
    ),
    "order_not_found": (
        "本次退款申请未提交：未找到该订单，"
        "或当前账号无权申请退款。\n"
        "请核对订单编号和登录账号。"
    ),
    "refund_not_allowed": (
        "本次退款申请未提交：当前订单状态不允许申请退款。"
    ),
    "invalid_arguments": (
        "本次退款申请未提交：订单编号或退款原因不符合要求。\n"
        "请提供订单编号，以及至少 5 个字符的退款原因。"
    ),
    "authentication_required": (
        "本次退款申请未提交：请先登录，再申请退款。"
    ),
}


def build_refund_submission_reply(
    tool_result: dict[str, Any],
) -> str:
    """区分提交成功、明确拒绝和结果无法确认。"""

    if tool_result.get("success") is True:
        data = tool_result.get("data")

        if not isinstance(data, dict):
            return UNCONFIRMED_REPLY

        refund_id = data.get("id")

        if (
            data.get("status") != "pending"
            or not isinstance(refund_id, str)
        ):
            return UNCONFIRMED_REPLY

        # 成功回复必须包含格式合法的申请编号。
        try:
            refund_id = str(UUID(refund_id))
        except ValueError:
            return UNCONFIRMED_REPLY

        return (
            "退款申请已成功提交，提交时状态为待审核。\n"
            f"申请编号：{refund_id}\n"
            "后续由有权限的工作人员审核；"
            "审核通过后，还需单独执行模拟退款。\n"
            "你可以稍后询问审核进度或退款执行结果。"
        )

    if tool_result.get("success") is False:
        error = tool_result.get("error")

        if isinstance(error, str) and error in REJECTION_REPLIES:
            return REJECTION_REPLIES[error]

    return UNCONFIRMED_REPLY