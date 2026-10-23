
import re


def split_markdown_sections(content: str) -> list[str]:
    """按照二级标题切分文档，并为每个片段保留文档主标题。"""

    sections = re.split(
        r"(?=^##\s+)",
        content,
        flags=re.MULTILINE,
    )

    # 没有二级标题时，将非空文档作为一个片段
    if len(sections) == 1:
        return [content.strip()] if content.strip() else []

    # 第一个部分是文档主标题
    document_title = sections[0].strip()

    # 从第二个部分开始，才是真正的章节内容
    chunks = [
        f"{document_title}\n\n{section.strip()}"
        for section in sections[1:]
        if section.strip()
    ]

    return chunks
