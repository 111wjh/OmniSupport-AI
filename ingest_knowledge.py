
import asyncio
from pathlib import Path

from app.services.knowledge_service import split_markdown_sections
from app.services.embedding_service import embed_texts
from app.services.qdrant_service import upsert_knowledge_chunks


async def main():
    # 1. 读取企业知识文档
    source = "knowledge/after_sales_policy.md"

    content = Path(source).read_text(
        encoding="utf-8"
    )

    # 2. 将文档切分为知识片段
    chunks = split_markdown_sections(content)

    print("Chunks:", len(chunks))

    # 3. 调用 Embedding 模型生成向量
    vectors = await embed_texts(chunks)

    print("Vectors:", len(vectors))

    # 4. 将知识片段和向量写入 Qdrant
    count = await upsert_knowledge_chunks(
        chunks=chunks,
        vectors=vectors,
        source=source,
    )

    print("Upserted points:", count)


if __name__ == "__main__":
    asyncio.run(main())
