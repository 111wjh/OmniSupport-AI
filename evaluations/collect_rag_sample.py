import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.rag_service import retrieve_relevant_knowledge


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "evaluations/datasets/rag_cases.json"
OUTPUT_PATH = PROJECT_ROOT / "reports/rag_sample_retrieval.json"

CASE_ID = "rag-001"
RECALL_K = 5
TOP_N = 3


async def main() -> None:
    # 读取题目和人工准备的参考答案
    dataset = json.loads(
        DATASET_PATH.read_text(encoding="utf-8-sig")
    )
    case = next(
        item for item in dataset["cases"]
        if item["id"] == CASE_ID
    )

    # 只把问题交给检索函数，不传参考答案
    chunks = await retrieve_relevant_knowledge(
        question=case["query"],
        recall_k=RECALL_K,
        top_n=TOP_N,
        collection_name=dataset["collection"],
    )

    if not chunks:
        raise RuntimeError("未检索到知识片段，请先检查知识库和检索配置。")

    sample = {
        "schema_version": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "case_id": case["id"],
        "collection": dataset["collection"],
        "retrieval": {
            "method": "hybrid_rrf_rerank",
            "recall_k": RECALL_K,
            "top_n": TOP_N,
        },
        "user_input": case["query"],
        "reference": case["reference"],
        "retrieved_contexts": [item["text"] for item in chunks],
        "retrieved_chunks": chunks,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(sample, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"问题：{case['query']}")
    for rank, item in enumerate(chunks, start=1):
        print(
            f"{rank}. {item['source']} "
            f"| chunk_index={item['chunk_index']} "
            f"| rerank_score={item['rerank_score']:.4f}"
        )
    print(f"结果已保存：{OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())