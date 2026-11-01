"""工单创建请求的幂等辅助逻辑。"""

import hashlib
import json

from app.schemas.ticket import TicketCreateRequest


def build_ticket_request_fingerprint(
    data: TicketCreateRequest,
) -> str:
    """将经过校验的工单创建参数转换为稳定的请求摘要。"""

    payload = data.model_dump(mode="json")

    canonical_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()