import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.core.config import get_settings
from app.services.rag_answer_service import generate_answer_from_knowledge


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "reports/rag_sample_retrieval.json"
OUTPUT_PATH = PROJECT_ROOT / "reports/rag_sample.json"


async def main() -> None:
    sample = json.loads(
        INPUT_PATH.read_text(encoding="utf-8-sig")
    )
    chunks = sample["retrieved_chunks"]

    # 确认生成回答与后续评分使用的是同一组资料
    if not chunks:
        raise ValueError("检索结果为空，请先完成检索采集。")

    if sample["retrieved_contexts"] != [
        item["text"] for item in chunks
    ]:
        raise ValueError("知识正文与片段记录不一致，请检查采集文件。")

    started = perf_counter()

    # 只传入问题和实际检索结果，不传参考答案
    async with asyncio.timeout(120):
        response = await generate_answer_from_knowledge(
            question=sample["user_input"],
            knowledge=chunks,
        )

    if not response.strip():
        raise ValueError("模型返回了空回答。")

    result = {
        **sample,
        "response": response,
        "generation": {
            "model": get_settings().LLM_MODEL,
            "duration_seconds": round(perf_counter() - started, 3),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"问题：{sample['user_input']}")
    print(f"\n模型回答：\n{response}")
    print(f"\n样例已保存：{OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())