"""Agent 的知识库检索工具。"""

import logging

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.rag_service import retrieve_relevant_knowledge
from app.tools.context import ToolContext

logger = logging.getLogger("uvicorn.error")


class KnowledgeSearchArguments(BaseModel):
    """模型传入的知识检索参数。"""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(
        min_length=1,
        max_length=500,
        description="需要检索的企业知识问题",
    )


async def execute_search_knowledge(
    arguments: str,
    _context: ToolContext,
) -> dict:
    """校验工具参数，然后检索企业知识。"""

    try:
        args = KnowledgeSearchArguments.model_validate_json(arguments)
    except ValidationError:
        return {
            "success": False,
            "error": "invalid_arguments",
            "message": "知识检索参数不合法",
        }

    try:
        results = await retrieve_relevant_knowledge(question=args.query)
    except Exception:
        logger.exception("Knowledge search failed")
        return {
            "success": False,
            "error": "knowledge_search_failed",
            "message": "知识库检索暂时不可用，请稍后再试。",
        }

    return {"success": True, "data": results}