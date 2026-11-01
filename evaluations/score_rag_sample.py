import asyncio
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

# 在导入 Ragas 前关闭其使用情况统计
os.environ["RAGAS_DO_NOT_TRACK"] = "true"

from dotenv import load_dotenv
from openai import AsyncOpenAI
import argparse
from evaluations.faithfulness import AuditedFaithfulness
from ragas.embeddings.base import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "reports/rag_sample.json"
OUTPUT_PATH = PROJECT_ROOT / "reports/rag_sample_evaluation.json"

async def add_incremental_metric(
    judge,
    client,
    sample: dict,
    sample_sha256: str,
    model: str,
    metric_name: str,
) -> None:
    """复用已有结果，只计算指定的新增指标。"""

    precision_path = OUTPUT_PATH.with_name(
        "rag_sample_evaluation_with_precision.json"
    )

    if metric_name == "context_precision":
        input_path = OUTPUT_PATH
        output_path = precision_path
    elif metric_name == "answer_relevancy":
        input_path = precision_path
        output_path = OUTPUT_PATH.with_name(
            "rag_sample_evaluation_complete.json"
        )
    else:
        raise ValueError(f"不支持的指标：{metric_name}")

    if output_path.exists():
        raise FileExistsError(
            f"报告已存在，请先查看，避免重复评分：{output_path}"
        )

    report = json.loads(
        input_path.read_text(encoding="utf-8-sig")
    )

    if report["sample_sha256"] != sample_sha256:
        raise ValueError("样例已改变，不能复用原报告。")

    embedding_model = "qwen3.7-text-embedding-flash"

    if metric_name == "context_precision":
        scorer = ContextPrecision(llm=judge)
        inputs = {
            "user_input": sample["user_input"],
            "reference": sample["reference"],
            "retrieved_contexts": sample["retrieved_contexts"],
        }
    else:
        embeddings = embedding_factory(
            "openai",
            model=embedding_model,
            client=client,
        )
        scorer = AnswerRelevancy(
            llm=judge,
            embeddings=embeddings,
            strictness=3,
        )
        inputs = {
            "user_input": sample["user_input"],
            "response": sample["response"],
        }

    started = perf_counter()

    async with asyncio.timeout(180):
        result = await scorer.ascore(**inputs)

    score = float(result.value)

    # 回答相关性使用余弦相似度，理论上可能出现负值
    lower_bound = -1 if metric_name == "answer_relevancy" else 0

    if (
        not math.isfinite(score)
        or score < lower_bound - 1e-9
        or score > 1 + 1e-9
    ):
        raise ValueError(f"{metric_name} 未返回有效分数：{score}")

    report["metrics"][metric_name] = score

    details = {
        "judge_model": model,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(perf_counter() - started, 3),
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

    if metric_name == "answer_relevancy":
        details["embedding_model"] = embedding_model
        details["strictness"] = 3

    report.setdefault(
        "incremental_evaluations", {}
    )[metric_name] = details

    output_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    print(f"样例：{sample['case_id']}")
    print(f"{metric_name}：{score:.4f}")
    print(f"报告已保存：{output_path}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metric",
        choices=(
            "base",
            "context_precision",
            "answer_relevancy",
        ),
        default="base",
    )
    args = parser.parse_args()
    # 评测环境独立读取配置，不导入业务项目的 Settings
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")

    if not api_key or not base_url or not model:
        raise ValueError("请检查 .env 中的模型密钥、地址和名称。")

    # 保存输入文件指纹，方便追溯本次评分对应的样例
    raw = INPUT_PATH.read_bytes()
    sample = json.loads(raw.decode("utf-8-sig"))

    started = perf_counter()

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
        if args.metric != "base":
            await add_incremental_metric(
                judge=judge,
                client=client,
                sample=sample,
                sample_sha256=hashlib.sha256(raw).hexdigest(),
                model=model,
                metric_name=args.metric,
            )
            return
        scorer = AuditedFaithfulness(llm=judge)

        async with asyncio.timeout(180):
            result = await scorer.ascore(
                user_input=sample["user_input"],
                response=sample["response"],
                retrieved_contexts=sample["retrieved_contexts"],
            )
            recall_result = await ContextRecall(llm=judge).ascore(
                user_input=sample["user_input"],
                retrieved_contexts=sample["retrieved_contexts"],
                reference=sample["reference"],
            )

    score = float(result.value)
    recall_score = float(recall_result.value)

    for name, value in (
        ("faithfulness", score),
        ("context_recall", recall_score),
    ):
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} 未返回有效分数：{value}")

    report = {
        "schema_version": 1,
        "case_id": sample["case_id"],
        "sample_sha256": hashlib.sha256(raw).hexdigest(),
        "judge_model": model,
        "generator_model": sample["generation"]["model"],
        "metrics": {
        "faithfulness": score,
        "context_recall": recall_score,
        },
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(perf_counter() - started, 3),
        "judgments": scorer.judgments,
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

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    for index, item in enumerate(scorer.judgments, start=1):
        label = "有支持" if item["verdict"] else "缺少支持"
        print(f"\n{index}. [{label}] {item['statement']}")
        print(f"理由：{item['reason']}")

    print(f"样例：{sample['case_id']}")
    print(f"评审模型：{model}")
    print(f"Faithfulness：{score:.4f}")
    print(f"Context Recall：{recall_score:.4f}")
    print(f"报告已保存：{OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())