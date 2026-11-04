"""读取知识文档并生成可复现的语料指纹。"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.services.knowledge_service import split_markdown_sections


@dataclass(frozen=True)
class KnowledgeDocument:
    source: str
    content_sha256: str
    chunks: tuple[str, ...]


def collect_documents(
    input_path: Path,
    *,
    project_root: Path,
) -> list[KnowledgeDocument]:
    """稳定排序读取仓库内 Markdown，保留可移植的相对来源路径。"""
    target = input_path.resolve()
    if not target.is_relative_to(project_root):
        raise ValueError("知识文件必须位于项目目录内")

    if target.is_dir():
        paths = sorted(
            (p for p in target.rglob("*.md") if p.is_file()),
            key=lambda p: p.relative_to(project_root).as_posix(),
        )
    elif target.is_file() and target.suffix.lower() == ".md":
        paths = [target]
    else:
        raise ValueError("输入必须是存在的 Markdown 文件或目录")

    if not paths:
        raise ValueError("没有找到 Markdown 知识文件")

    documents = []
    for path in paths:
        if not path.resolve().is_relative_to(project_root):
            raise ValueError("知识文件不能链接到项目目录之外")
        content = path.read_text(encoding="utf-8-sig")
        chunks = split_markdown_sections(content)
        if not chunks or any(not chunk.strip() for chunk in chunks):
            raise ValueError(f"知识文件为空：{path.name}")
        documents.append(
            KnowledgeDocument(
                source=path.relative_to(project_root).as_posix(),
                content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                chunks=tuple(chunks),
            )
        )
    return documents


def describe_corpus(
    documents: list[KnowledgeDocument],
    *,
    embedding_model: str,
    vector_size: int,
) -> dict:
    """指纹覆盖来源、正文、切分数量和模型，供评测固定数据版本。"""
    description = {
        "embedding_model": embedding_model,
        "vector_size": vector_size,
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