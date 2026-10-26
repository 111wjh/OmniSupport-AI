
from uuid import UUID

from app.agent.graph import agent_graph
from app.core.langfuse_client import get_langfuse_client
from app.core.request_context import get_request_id
from app.llm.client import build_llm_messages
from typing import Callable


async def generate_agent_reply(
    message: str,
    history: list[dict[str, str]] | None = None,
    customer_id: UUID | None = None,
    image_observation: str | None = None,
    on_text_delta: Callable[[str], None] | None = None,
) -> str:
    """通过 LangGraph 生成客服回复，支持可选的流式文本回调。"""

    messages = build_llm_messages(
        message=message,
        history=history,
        image_observation=image_observation,
    )

    langfuse = get_langfuse_client()

    with langfuse.start_as_current_observation(
        as_type="span",
        name="OmniSupport-AI Agent",
        metadata={
            "request_id": get_request_id() or "local",
            "modality": "multimodal" if image_observation else "text",
            "stream_enabled": on_text_delta is not None,
        },
    ) as span:

        initial_state = {
            "messages": messages,
            "customer_id": customer_id,
            "model_calls": 0,
        }

        if on_text_delta is None:
            # 普通模式：保持原有执行方式
            result = await agent_graph.ainvoke(
                initial_state,
                config={"recursion_limit": 12},
            )

            final_message = result["messages"][-1]
            model_calls = result["model_calls"]

        else:
            # 流式模式：监听文本事件和节点更新
            final_message = None
            model_calls = 0

            async for mode, data in agent_graph.astream(
                {
                    **initial_state,
                    "stream_enabled": True,
                },
                config={"recursion_limit": 12},
                stream_mode=["custom", "updates"],
            ):
                if mode == "custom":
                    if data.get("type") == "token":
                        on_text_delta(data["content"])

                elif mode == "updates":
                    for node_update in data.values():
                        updated_messages = (
                            node_update.get("messages") or []
                        )

                        if updated_messages:
                            final_message = updated_messages[-1]

                        if "model_calls" in node_update:
                            model_calls = node_update["model_calls"]

            if final_message is None:
                raise ValueError(
                    "LangGraph 没有返回最终助手消息"
                )

        reply = final_message.get("content")

        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("LangGraph 没有返回有效文本")

        span.update(
            output={
                "status": "success",
                "model_calls": model_calls,
            }
        )

    return reply
