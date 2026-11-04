"""导入单个知识文件或目录；支持独立、可复用的评测快照集合。"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import selectors
import sys

from app.core.config import get_settings
from app.rag.corpus import collect_documents, describe_corpus
from app.rag.ingestion import import_documents
from app.services.qdrant_initializer import VECTOR_SIZE


PROJECT_ROOT = Path(__file__).resolve().parent







def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        default=PROJECT_ROOT / "knowledge/after_sales_policy.md",
        help="Markdown 文件或目录；目录模式递归读取所有 .md 文件",
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--collection", help="显式指定目标集合")
    target.add_argument(
        "--snapshot", action="store_true",
        help="使用语料指纹创建独立的 omnisupport_rag_eval_* 集合",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true", help="只检查文件与切分，不调用外部服务")
    parser.add_argument("--manifest", type=Path, help="将导入结果保存为项目内的 JSON 清单")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 32:
        parser.error("--batch-size 必须在 1 到 32 之间")
    if args.manifest and not args.manifest.resolve().is_relative_to(PROJECT_ROOT):
        parser.error("--manifest 必须保存在项目目录内")
    return args


async def main(args: argparse.Namespace) -> None:
    settings = get_settings()

    documents = collect_documents(args.path, project_root=PROJECT_ROOT)
    summary = describe_corpus(
        documents,
        embedding_model=settings.EMBEDDING_MODEL,
        vector_size=VECTOR_SIZE,
    )
    if args.snapshot:
        collection = f"omnisupport_rag_eval_{summary['corpus_sha256'][:12]}"
    elif args.collection:
        collection = args.collection
    else:
        collection = settings.KNOWLEDGE_COLLECTION
    print(f"文档：{summary['document_count']}，片段：{summary['chunk_count']}", flush=True)
    print(f"目标集合：{collection}", flush=True)
    for document in documents:
        print(f"  {document.source}: {len(document.chunks)}", flush=True)

    if args.dry_run:
        print("检查完成，未调用 Embedding 或写入 Qdrant。", flush=True)
        return

    count, reused = await import_documents(documents, collection, args.batch_size)
    manifest = {
        "schema_version": 1,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        **summary,
        "collection": collection,
        "actual_point_count": count,
        "reused_existing_vectors": reused,
        "verification": "exact_point_ids_and_payloads",
        "corpus_kind": "synthetic_demo_enterprise_knowledge",
    }
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"导入核对完成：{count} 条，集合 {collection}", flush=True)


if __name__ == "__main__":
    arguments = parse_args()
    try:
        if sys.platform == "win32":
            asyncio.run(
                main(arguments),
                loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
            )
        else:
            asyncio.run(main(arguments))
    except Exception as exc:
        # 外部服务异常仅输出类型与状态码，避免打印配置、密钥或请求正文。
        status = getattr(exc, "status_code", None)
        print(f"导入未完成：{type(exc).__name__}" + (f" (HTTP {status})" if status else ""), file=sys.stderr)
        if isinstance(exc, (ValueError, RuntimeError)):
            print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
