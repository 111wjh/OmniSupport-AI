
from uuid import UUID

from app.agent.graph import agent_graph
from app.core.langfuse_client import get_langfuse_client
from app.core.request_context import get_request_id
from app.llm.client import build_llm_messages


async def generate_agent_reply(
    message: str,
    history: list[dict[str, str]] | None = None,
    customer_id: UUID | None = None,
    image_observation: str | None = None,
) -> str:
    """通过 LangGraph 生成最终客服回复，并记录 Langfuse Trace。"""

    # 1. 复用原有的消息构造逻辑
    messages = build_llm_messages(
        message=message,
        history=history,
        image_observation=image_observation,
    )

    # 2. 获取已经缓存的 Langfuse 客户端
    langfuse = get_langfuse_client()

    # 3. 为本次 Agent 执行创建追踪 Span
    with langfuse.start_as_current_observation(
        as_type="span",
        name="OmniSupport-AI Agent",
        metadata={
            "request_id": get_request_id() or "local",
            "modality": "multimodal" if image_observation else "text",
        },
    ) as span:

        # 4. 保留原有 LangGraph 执行逻辑
        result = await agent_graph.ainvoke(
            {
                "messages": messages,
                "customer_id": customer_id,
                "model_calls": 0,
            },
            config={"recursion_limit": 12},
        )

        # 5. 读取工作流返回的最后一条消息
        final_message = result["messages"][-1]
        reply = final_message.get("content")

        # 6. 检查最终回复是否有效
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("LangGraph 没有返回有效文本")

        # 7. 记录本次执行结果
        span.update(
            output={
                "status": "success",
                "model_calls": result["model_calls"],
            }
        )

    return reply
