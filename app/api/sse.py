
import json
from typing import Any, AsyncIterator

from fastapi.responses import StreamingResponse


def format_sse_event(
    event: str,
    data: dict[str, Any],
) -> str:
    """将事件和数据转换为 SSE 标准格式。"""

    payload = json.dumps(
        data,
        ensure_ascii=False,
    )

    return f"event: {event}\ndata: {payload}\n\n"


def create_sse_response(
    event_stream: AsyncIterator[str],
) -> StreamingResponse:
    """创建 FastAPI SSE 流式响应。"""

    return StreamingResponse(
        content=event_stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
