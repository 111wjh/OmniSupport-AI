
from contextvars import ContextVar


# 保存当前 HTTP 请求的 Request ID
request_id_var: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)


def get_request_id() -> str | None:
    """获取当前请求的 Request ID。"""
    return request_id_var.get()
