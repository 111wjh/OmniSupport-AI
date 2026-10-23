
import httpx

from app.core.config import get_settings


async def rerank_documents(
    query: str,
    documents: list[str],
    top_n: int = 3,
) -> list[dict]:
    """使用 Rerank 模型重新排列候选知识。"""

    if not query.strip() or not documents:
        return []

    settings = get_settings()

    if not settings.LLM_API_KEY:
        raise ValueError("未配置大模型 API Key")

    if not settings.RERANK_API_URL:
        raise ValueError("未配置 Rerank API 地址")

    # 限制返回数量，不能超过候选文档数量
    top_n = max(1, min(top_n, len(documents)))

    payload = {
        "model": "qwen3.7-text-rerank",
        "input": {
            "query": query,
            "documents": documents,
        },
        "parameters": {
            "top_n": top_n,
            "instruct": (
                "Given a user question, retrieve "
                "relevant passages that answer the question."
            ),
        },
    }

    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            settings.RERANK_API_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    # 获取模型排序后的结果
    ranked_results = data["output"]["results"]

    results = []

    for item in ranked_results:
        index = item["index"]

        results.append({
            "index": index,
            "score": item["relevance_score"],
            "text": documents[index],
        })

    return results
