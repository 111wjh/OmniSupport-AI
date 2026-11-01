import hashlib
import json
import math
from pathlib import Path
from statistics import fmean


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = PROJECT_ROOT / "reports/rag_comparison/pilot_v1"

METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


def main() -> None:
    raw = (RUN_DIR / "responses.json").read_bytes()
    responses = json.loads(raw.decode("utf-8-sig"))
    scores = json.loads(
        (RUN_DIR / "scores.json").read_text(
            encoding="utf-8-sig"
        )
    )

    if scores["config"]["responses_sha256"] != (
        hashlib.sha256(raw).hexdigest()
    ):
        raise ValueError("评分与回答文件不匹配。")

    cases = responses["cases"]
    methods = responses["retrieval_config"]["methods"]

    expected_keys = {
        f"{case['case_id']}/{method}"
        for case in cases
        for method in methods
    }

    if set(scores["results"]) != expected_keys:
        raise ValueError("评分组存在缺失或多余记录。")

    table = [
        "| 方案 | Faithfulness | Answer Relevancy | "
        "Context Precision | Context Recall |",
        "|---|---:|---:|---:|---:|",
    ]

    for method in methods:
        averages = []

        for metric in METRICS:
            values = []

            for case in cases:
                key = f"{case['case_id']}/{method}"
                measurement = scores["results"][key]["metrics"]

                if metric not in measurement:
                    raise ValueError(f"{key} 缺少指标：{metric}")

                value = measurement[metric]["score"]

                if (
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                ):
                    raise ValueError(f"{key} / {metric} 分数无效")

                values.append(value)

            averages.append(fmean(values))

        cells = " | ".join(
            f"{value:.4f}" for value in averages
        )
        table.append(f"| {method} | {cells} |")

    retrieval_config = responses["retrieval_config"]

    content = [
        "# RAG 检索方案对照实验",
        "",
        "本报告为小样本、单轮流程验证，不代表生产效果。",
        "",
        "## 实验配置",
        "",
        f"- 题目数量：{len(cases)}",
        f"- 检索方案数量：{len(methods)}",
        f"- 候选数量参数：{retrieval_config['recall_k']}",
        f"- 最终返回数量：{retrieval_config['top_k']}",
        f"- 知识库：{retrieval_config['collection']}",
        f"- 回答模型：{responses['config']['model']}",
        f"- 评审模型：{scores['config']['judge_model']}",
        "- 四种方案共用回答函数，各自使用已保存的检索资料。",
        "- 回答模型未接收参考答案。",
        "",
        "## 评分均值",
        "",
        *table,
        "",
        "每列均对该方案的全部题目取算术平均。",
        "四项指标分别展示，不合成总分。",
        "",
        "## 结果解释与限制",
        "",
        "- 各方案存在不同指标之间的取舍。",
        "- 当前上下文召回率均为 1，未区分出方案差异。",
        "- 上下文精确度不等于无关片段占比。",
        "- 忠实度需要结合逐条判断人工复核。",
        "- 客户自述、系统要求及合理建议可能被判为缺少检索依据。",
        "- 生成与评审使用同一模型，存在共同偏差风险。",
        "- 样本少且每组只生成一次，尚未验证重复运行的稳定性。",
        "- 尚未完成人工复核全部回答，不能据此确定最优生产方案。",
        "",
        "## 复现依据",
        "",
        "- retrieval.json：固定的检索结果。",
        "- responses.json：固定的模型回答。",
        "- scores.json：逐组评分、环境版本及忠实度判断。",
        "- 后续应扩大题目覆盖范围，并保留独立评测样本。",
    ]

    output_path = RUN_DIR / "summary.md"
    output_path.write_text(
        "\n".join(content) + "\n",
        encoding="utf-8",
    )

    print("\n".join(table))
    print(f"\n报告已保存：{output_path}")


if __name__ == "__main__":
    main()