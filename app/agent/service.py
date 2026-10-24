
from uuid import UUID

from app.agent.graph import agent_graph
from app.llm.client import build_llm_messages


async def generate_agent_reply(
    message: str,
    history: list[dict[str, str]] | None = None,
    customer_id: UUID | None = None,
    image_observation: str | None = None,
) -> str:
    """通过 LangGraph 生成最终客服回复。"""

    # 1. 复用原有的消息构造逻辑
    messages = build_llm_messages(
        message=message,
        history=history,
        image_observation=image_observation,
    )

    # 2. 初始化状态并运行 LangGraph
    result = await agent_graph.ainvoke(
        {
            "messages": messages,
            "customer_id": customer_id,
            "model_calls": 0,
        },
        #LangGraph 最多执行多12个工作流步骤
        config={"recursion_limit": 12},
    )

    # 3. 读取工作流返回的最后一条消息
    final_message = result["messages"][-1]
    reply = final_message.get("content")

    # 4. 检查最终回复是否有效
    if not isinstance(reply, str) or not reply.strip():
        raise ValueError("LangGraph 没有返回有效文本")

    return reply
