
from langgraph.graph import END, START, StateGraph

from app.agent.state import AgentState
from app.agent.nodes import (
    call_model,
    execute_tools,
    route_after_model,
    handle_call_limit,
)


def build_agent_graph():
    """构建并编译 LangGraph Agent 工作流。"""

    workflow = StateGraph(AgentState)

    # 注册三个业务节点
    workflow.add_node("model", call_model)
    workflow.add_node("tools", execute_tools)
    workflow.add_node("limit", handle_call_limit)

    # 工作流入口
    workflow.add_edge(START, "model")

    # 根据模型输出选择执行工具、结束或返回兜底消息
    workflow.add_conditional_edges(
        "model",
        route_after_model,
        {
            "tools": "tools",
            "end": END,
            "limit": "limit",
        },
    )

    # 工具执行完成后，再次调用模型
    workflow.add_edge("tools", "model")

    # 达到调用上限后，直接结束
    workflow.add_edge("limit", END)

    return workflow.compile()


agent_graph = build_agent_graph()
