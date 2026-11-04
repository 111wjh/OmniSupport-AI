import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.core.config import get_settings
from evaluations.retrievers import retrieve_for_comparison


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "evaluations/datasets/rag_cases.json"
CORPUS_PATH = PROJECT_ROOT / "reports/rag_corpus_import.json"
OUTPUT_PATH = (
    PROJECT_ROOT / "reports/rag_comparison/pilot_v1/retrieval.json"
)

RECALL_K = 5
TOP_K = 3
METHODS = ["bm25", "dense", "hybrid", "hybrid_rerank"]


def save_report(report: dict) -> None:
    """先写临时文件，写完后再替换正式文件。"""
    temporary_path = OUTPUT_PATH.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    temporary_path.replace(OUTPUT_PATH)


async def main() -> None:
    settings = get_settings()
    raw = DATASET_PATH.read_bytes()
    dataset = json.loads(raw.decode("utf-8-sig"))
    corpus = json.loads(
        CORPUS_PATH.read_text(encoding="utf-8-sig")
    )

    if dataset["collection"] != corpus["collection"]:
        raise ValueError("题目指定的知识库与导入记录不一致。")

    config = {
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "corpus_sha256": corpus["corpus_sha256"],
        "collection": dataset["collection"],
        "embedding_model": settings.EMBEDDING_MODEL,
        "rerank_model": settings.RERANK_MODEL,
        "recall_k": settings.RAG_RECALL_K,
        "top_k": settings.RAG_TOP_N,
        "methods": METHODS,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_PATH.exists():
        report = json.loads(
            OUTPUT_PATH.read_text(encoding="utf-8-sig")
        )
        if report["config"] != config:
            raise ValueError(
                "题目或实验配置已改变，请使用新的实验目录。"
            )
    else:
        report = {
            "schema_version": 1,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "collecting",
            "config": config,
            "dataset_snapshot": dataset,
            "cases": [],
        }
        save_report(report)

    completed_ids = {
        item["case_id"]
        for item in report["cases"]
    }

    total = len(dataset["cases"])

    for index, case in enumerate(dataset["cases"], start=1):
        case_id = case["id"]

        if case_id in completed_ids:
            print(f"[{index}/{total}] {case_id} 已完成，跳过")
            continue

        started = perf_counter()

        async with asyncio.timeout(180):
            results = await retrieve_for_comparison(
                question=case["query"],
                collection_name=dataset["collection"],
                recall_k=RECALL_K,
                top_k=TOP_K,
            )

        record = {
            "case_id": case_id,
            "category": case["category"],
            "user_input": case["query"],
            "reference": case["reference"],
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "retrieval_batch_seconds": round(
                perf_counter() - started, 3
            ),
            "variants": {
                method: {
                    "retrieved_contexts": [
                        item["text"] for item in chunks
                    ],
                    "retrieved_chunks": chunks,
                }
                for method, chunks in results.items()
            },
        }

        report["cases"].append(record)
        save_report(report)

        counts = ", ".join(
            f"{method}={len(chunks)}"
            for method, chunks in results.items()
        )
        print(f"[{index}/{total}] {case_id} 完成：{counts}")

    report["status"] = "retrieval_complete"
    save_report(report)

    print(f"\n已保存 {len(report['cases'])} 道题的检索结果")
    print(f"报告位置：{OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())