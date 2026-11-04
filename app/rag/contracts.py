"""RAG 模块对外使用的请求、结果和检索接口。"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RetrievalRequest:
    """一次知识检索所需的参数。"""

    query: str
    collection_name: str
    recall_k: int
    top_n: int

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("检索问题不能为空")

        if not self.collection_name.strip():
            raise ValueError("知识集合名称不能为空")

        if not 1 <= self.top_n <= self.recall_k:
            raise ValueError(
                "检索数量必须满足 1 <= top_n <= recall_k"
            )


@dataclass(frozen=True)
class KnowledgeHit:
    """统一的知识检索结果，不暴露具体 SDK 对象。"""

    text: str
    source: str
    chunk_index: int | None

    # 原始召回或融合阶段的分数。
    retrieval_score: float | None = None

    # 使用重排时的分数；未重排时可以没有。
    rerank_score: float | None = None


class KnowledgeRetriever(Protocol):
    """知识检索实现应遵守的接口。"""

    async def retrieve(
        self,
        request: RetrievalRequest,
    ) -> list[KnowledgeHit]:
        ...