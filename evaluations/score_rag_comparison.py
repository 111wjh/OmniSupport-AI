import argparse
import asyncio
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

os.environ["RAGAS_DO_NOT_TRACK"] = "true"

from dotenv import load_dotenv
from openai import AsyncOpenAI
from ragas.embeddings.base import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
)

from evaluations.faithfulness import AuditedFaithfulness


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = PROJECT_ROOT / "reports/rag_comparison/pilot_v1"
INPUT_PATH = RUN_DIR / "responses.json"
OUTPUT_PATH = RUN_DIR / "scores.json"

EMBEDDING_MODEL = "qwen3.7-text-embedding-flash"

METRIC_FIELDS = {
    "faithfulness": (
        "user_input", "response", "retrieved_contexts"
    ),
    "context_recall": (
        "user_input", "reference", "retrieved_contexts"
    ),
    "context_precision": (
        "user_input", "reference", "retrieved_contexts"
    ),
    "answer_relevancy": (
        "user_input", "response"
    ),
}


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


def build_scorer(metric: str, judge, client):
    """根据指标名创建对应的评分器。"""
    if metric == "faithfulness":
        return AuditedFaithfulness(llm=judge)

    if metric == "context_recall":
        return ContextRecall(llm=judge)

    if metric == "context_precision":
        return ContextPrecision(llm=judge)

    embeddings = embedding_factory(
        "openai",
        model=EMBEDDING_MODEL,
        client=client,
    )
    return AnswerRelevancy(
        llm=judge,
        embeddings=embeddings,
        strictness=3,
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metric",
        choices=list(METRIC_FIELDS),
        required=True,
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")

    if not api_key or not base_url or not model:
        raise ValueError("请检查模型密钥、地址和名称。")

    raw = INPUT_PATH.read_bytes()
    responses = json.loads(raw.decode("utf-8-sig"))

    if responses["status"] != "generation_complete":
        raise ValueError("请先完成全部回答生成。")

    config = {
        "responses_sha256": hashlib.sha256(raw).hexdigest(),
        "judge_model": model,
        "endpoint_sha256": hashlib.sha256(
            base_url.encode("utf-8")
        ).hexdigest(),
        "embedding_model": EMBEDDING_MODEL,
        "temperature": 0,
        "strictness": 3,
        "versions": {
            name: version(name)
            for name in (
                "ragas",
                "langchain-community",
                "openai",
                "instructor",
            )
        },
    }

    if OUTPUT_PATH.exists():
        report = json.loads(
            OUTPUT_PATH.read_text(encoding="utf-8-sig")
        )
        if report["config"] != config:
            raise ValueError(
                "输入或评测环境发生变化，不能混入原报告。"
            )
    else:
        report = {
            "schema_version": 1,
            "config": config,
            "completed_metrics": [],
            "results": {},
        }
        save_report(report)

    total = sum(
        len(case["variants"])
        for case in responses["cases"]
    )
    current = 0

    async with AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=60.0,
        max_retries=1,
    ) as client:
        judge = llm_factory(
            model=model,
            client=client,
            temperature=0,
            max_tokens=4096,
            max_retries=2,
            extra_body={"enable_thinking": False},
        )
        scorer = build_scorer(args.metric, judge, client)

        for case in responses["cases"]:
            for method, variant in case["variants"].items():
                current += 1
                key = f"{case['case_id']}/{method}"

                record = report["results"].setdefault(
                    key,
                    {
                        "case_id": case["case_id"],
                        "method": method,
                        "metrics": {},
                    },
                )

                if args.metric in record["metrics"]:
                    print(f"[{current}/{total}] {key} 已评分，跳过")
                    continue

                values = {
                    "user_input": case["user_input"],
                    "reference": case["reference"],
                    "response": variant["response"],
                    "retrieved_contexts": variant["retrieved_contexts"],
                }
                inputs = {
                    name: values[name]
                    for name in METRIC_FIELDS[args.metric]
                }

                started = perf_counter()

                async with asyncio.timeout(180):
                    result = await scorer.ascore(**inputs)

                score = float(result.value)
                lower = (
                    -1 if args.metric == "answer_relevancy" else 0
                )

                if (
                    not math.isfinite(score)
                    or score < lower - 1e-9
                    or score > 1 + 1e-9
                ):
                    raise ValueError(
                        f"{key} / {args.metric} 分数无效：{score}"
                    )

                measurement = {
                    "score": score,
                    "evaluated_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "duration_seconds": round(
                        perf_counter() - started, 3
                    ),
                }

                if args.metric == "faithfulness":
                    measurement["judgments"] = scorer.judgments

                record["metrics"][args.metric] = measurement
                save_report(report)

                print(
                    f"[{current}/{total}] {key} "
                    f"{args.metric}={score:.4f}"
                )

    if args.metric not in report["completed_metrics"]:
        report["completed_metrics"].append(args.metric)

    save_report(report)

    print(f"\n{args.metric} 已完成：{total}/{total}")
    print(f"报告位置：{OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())