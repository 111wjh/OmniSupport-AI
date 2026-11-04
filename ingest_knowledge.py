"""导入单个知识文件或目录；支持独立、可复用的评测快照集合。"""

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import selectors
import sys
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import AsyncQdrantClient

from app.core.config import get_settings
from app.services.embedding_service import embed_texts
from app.services.knowledge_service import split_markdown_sections
from app.services.qdrant_initializer import (
    COLLECTION_NAME,
    VECTOR_SIZE,
    init_qdrant_collection,
)
from app.services.qdrant_service import upsert_knowledge_chunks


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class KnowledgeDocument:
    source: str
    content_sha256: str
    chunks: tuple[str, ...]


def collect_documents(input_path: Path) -> list[KnowledgeDocument]:
    """稳定排序读取仓库内 Markdown，保留可移植的相对来源路径。"""
    target = input_path.resolve()
    if not target.is_relative_to(PROJECT_ROOT):
        raise ValueError("知识文件必须位于项目目录内")

    if target.is_dir():
        paths = sorted(
            (p for p in target.rglob("*.md") if p.is_file()),
            key=lambda p: p.relative_to(PROJECT_ROOT).as_posix(),
        )
    elif target.is_file() and target.suffix.lower() == ".md":
        paths = [target]
    else:
        raise ValueError("输入必须是存在的 Markdown 文件或目录")

    if not paths:
        raise ValueError("没有找到 Markdown 知识文件")

    documents = []
    for path in paths:
        if not path.resolve().is_relative_to(PROJECT_ROOT):
            raise ValueError("知识文件不能链接到项目目录之外")
        content = path.read_text(encoding="utf-8-sig")
        chunks = split_markdown_sections(content)
        if not chunks or any(not chunk.strip() for chunk in chunks):
            raise ValueError(f"知识文件为空：{path.name}")
        documents.append(
            KnowledgeDocument(
                source=path.relative_to(PROJECT_ROOT).as_posix(),
                content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                chunks=tuple(chunks),
            )
        )
    return documents


def describe_corpus(documents: list[KnowledgeDocument]) -> dict:
    """指纹覆盖来源、正文、切分数量和模型，供评测固定数据版本。"""
    settings = get_settings()
    description = {
        "embedding_model": settings.EMBEDDING_MODEL,
        "vector_size": VECTOR_SIZE,
        "chunker": "markdown_h2_v1",
        "documents": [
            {
                "source": document.source,
                "content_sha256": document.content_sha256,
                "chunks": len(document.chunks),
            }
            for document in documents
        ],
    }
    serialized = json.dumps(
        description, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {
        **description,
        "corpus_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "document_count": len(documents),
        "chunk_count": sum(len(document.chunks) for document in documents),
    }


def expected_payloads(documents: list[KnowledgeDocument]) -> dict[str, dict]:
    return {
        str(uuid5(NAMESPACE_URL, f"{document.source}:{index}")): {
            "text": chunk,
            "source": document.source,
            "chunk_index": index,
        }
        for document in documents
        for index, chunk in enumerate(document.chunks)
    }


async def read_payloads(client: AsyncQdrantClient, collection: str) -> dict[str, dict]:
    result = {}
    offset = None
    while True:
        records, offset = await client.scroll(
            collection_name=collection,
            offset=offset,
            limit=256,
            with_payload=True,
            with_vectors=False,
        )
        for point in records:
            result[str(point.id)] = point.payload or {}
        if offset is None:
            return result


async def import_documents(
    documents: list[KnowledgeDocument],
    collection: str,
    batch_size: int,
) -> tuple[int, bool]:
    """仅 upsert 明确计划的点；不删除集合或任何额外记录。"""
    settings = get_settings()
    expected = expected_payloads(documents)

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=20,
    )
    try:
        exists = await client.collection_exists(collection)
        existing = await read_payloads(client, collection) if exists else {}
        if set(existing) - set(expected):
            raise ValueError("目标集合包含本轮语料之外的记录，请使用独立快照集合")
        reusable = bool(existing) and existing == expected
    finally:
        await client.close()

    if reusable:
        await init_qdrant_collection(collection_name=collection)
        print("目标快照内容已完整匹配，复用已有向量，不再调用 Embedding。", flush=True)
        return len(expected), True

    if not settings.LLM_API_KEY or not settings.LLM_BASE_URL:
        raise ValueError("Embedding 配置不完整")

    texts = [chunk for document in documents for chunk in document.chunks]
    vectors = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        async with asyncio.timeout(90):
            batch_vectors = await embed_texts(batch)
        if len(batch_vectors) != len(batch):
            raise ValueError("Embedding 返回数量与输入不一致")
        for vector in batch_vectors:
            if len(vector) != VECTOR_SIZE or not all(math.isfinite(x) for x in vector):
                raise ValueError("Embedding 向量维度或数值不符合要求")
        vectors.extend(batch_vectors)
        print(f"Embedding: {len(vectors)}/{len(texts)}", flush=True)

    # 全部向量校验通过后，才创建集合及写入数据。
    await init_qdrant_collection(collection_name=collection)
    offset = 0
    for document in documents:
        size = len(document.chunks)
        await upsert_knowledge_chunks(
            chunks=list(document.chunks),
            vectors=vectors[offset:offset + size],
            source=document.source,
            collection_name=collection,
        )
        offset += size
        print(f"已写入：{document.source} ({size} 片段)", flush=True)

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=20,
    )
    try:
        actual = await read_payloads(client, collection)
        if actual != expected:
            raise RuntimeError("导入后的点 ID 或正文、来源、片段编号校验失败")
        count = await client.count(collection_name=collection, exact=True)
        if count.count != len(expected):
            raise RuntimeError("导入后实际数量与计划不一致")
    finally:
        await client.close()
    return count.count, False


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
    documents = collect_documents(args.path)
    summary = describe_corpus(documents)
    collection = (
        f"omnisupport_rag_eval_{summary['corpus_sha256'][:12]}"
        if args.snapshot else args.collection or COLLECTION_NAME
    )
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
