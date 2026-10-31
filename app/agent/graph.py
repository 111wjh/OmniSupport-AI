
from langgraph.graph import END, START, StateGraph

from app.agent.state import AgentState
from app.agent.nodes import (
    call_model,
    execute_tools,
    route_after_model,
    route_after_tools,
    handle_call_limit,
    handle_refund_submission_result,
    handle_ticket_creation_result,
)


def build_agent_graph(checkpointer=None):
    """构建并编译 LangGraph Agent 工作流。"""

    workflow = StateGraph(AgentState)

    # 注册业务节点。
    workflow.add_node("model", call_model)
    workflow.add_node("tools", execute_tools)
    workflow.add_node("limit", handle_call_limit)
    workflow.add_node(
        "refund_submission_result",
        handle_refund_submission_result)
    workflow.add_node(
        "ticket_creation_result",
        handle_ticket_creation_result,
    )
    # 工作流入口
    workflow.add_edge(START, "model")

    # 根据模型输出决定下一步
    workflow.add_conditional_edges(
        "model",
        route_after_model,
        {
            "tools": "tools",
            "end": END,
            "limit": "limit",
        },
    )

    # 工具执行完成后，根据提交结果选择下一步
    workflow.add_conditional_edges(
        "tools",
        route_after_tools,
        {
            "model": "model",
            "refund_submission_result": "refund_submission_result",
            "ticket_creation_result": "ticket_creation_result",
        },
    )

    # 退款提交回复完成后，结束本次工作流
    workflow.add_edge("refund_submission_result", END)

    # 达到调用上限后结束
    workflow.add_edge("limit", END)

    # 工单创建结果回复完成后，结束本次工作流。
    workflow.add_edge("ticket_creation_result", END)
    return workflow.compile(checkpointer=checkpointer)


# 保留默认实例，保证初始化阶段的模块导入兼容
agent_graph = build_agent_graph()


def configure_agent_graph(checkpointer):
    """使用指定的 Checkpointer 重新构建 Agent 工作流。"""

    global agent_graph

    agent_graph = build_agent_graph(
        checkpointer=checkpointer
    )
