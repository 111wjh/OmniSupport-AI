from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ToolContext:
    """由后端传给工具的请求信息。"""

    customer_id: UUID | None = None