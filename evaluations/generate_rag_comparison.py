import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.core.config import get_settings
from app.services.rag_answer_service import generate_answer_from_knowledge


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = PROJECT_ROOT / "reports/rag_comparison/pilot_v1"
INPUT_PATH = RUN_DIR / "retrieval.json"
OUTPUT_PATH = RUN_DIR / "responses.json"
GENERATOR_PATH = PROJECT_ROOT / "app/services/rag_answer_service.py"


def save_report(report: dict) -> None:
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
    raw = INPUT_PATH.read_bytes()
    retrieval = json.loads(raw.decode("utf-8-sig"))

    if retrieval["status"] != "retrieval_complete":
        raise ValueError("请先完成本轮检索采集。")

    settings = get_settings()

    config = {
        "retrieval_sha256": hashlib.sha256(raw).hexdigest(),
        "model": settings.LLM_MODEL,
        "generator_sha256": hashlib.sha256(
            GENERATOR_PATH.read_bytes()
        ).hexdigest(),
        "endpoint_sha256": hashlib.sha256(
            (settings.LLM_BASE_URL or "").encode("utf-8")
        ).hexdigest(),
        "temperature": "provider_default",
    }

    if OUTPUT_PATH.exists():
        report = json.loads(
            OUTPUT_PATH.read_text(encoding="utf-8-sig")
        )

        if report["config"] != config:
            raise ValueError(
                "输入、模型或回答代码已改变，不能混入本轮结果。"
            )

        if report["status"] == "generation_complete":
            print(f"本轮回答已全部生成：{OUTPUT_PATH}")
            return
    else:
        report = {
            "schema_version": 1,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "generating",
            "config": config,
            "retrieval_config": retrieval["config"],
            "dataset_snapshot": retrieval["dataset_snapshot"],
            "cases": retrieval["cases"],
        }
        save_report(report)

    total = sum(
        len(case["variants"])
        for case in report["cases"]
    )
    current = 0

    for case in report["cases"]:
        for method, variant in case["variants"].items():
            current += 1
            label = f"{case['case_id']} / {method}"

            if "response" in variant:
                print(f"[{current}/{total}] {label} 已完成，跳过")
                continue

            chunks = variant["retrieved_chunks"]

            if variant["retrieved_contexts"] != [
                item["text"] for item in chunks
            ]:
                raise ValueError(f"{label} 的知识正文不一致。")

            started = perf_counter()

            async with asyncio.timeout(120):
                response = await generate_answer_from_knowledge(
                    question=case["user_input"],
                    knowledge=chunks,
                )

            if not response.strip():
                raise ValueError(f"{label} 返回了空回答。")

            variant["response"] = response
            variant["generation"] = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(
                    perf_counter() - started, 3
                ),
            }
            save_report(report)

            print(f"[{current}/{total}] {label} 完成")

    report["status"] = "generation_complete"
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    save_report(report)

    print(f"\n共完成 {total} 组回答")
    print(f"报告位置：{OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())