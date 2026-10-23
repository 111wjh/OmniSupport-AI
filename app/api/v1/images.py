
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from openai import OpenAIError

from app.services.multimodal_service import handle_multimodal_question

from app.core.auth import get_current_customer
from app.models.customer import Customer
from io import BytesIO

from PIL import Image, UnidentifiedImageError
import logging
router = APIRouter(
    prefix="/api/v1",
    tags=["Images"],
)

# 最大允许上传 5MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024

# 支持的图片类型
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def detect_image_type(content: bytes) -> str | None:
    """根据文件签名识别常见图片格式。"""

    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if (
        len(content) >= 12
        and content[:4] == b"RIFF"
        and content[8:12] == b"WEBP"
    ):
        return "image/webp"

    return None



# 限制图片最大像素数量为 2000 万
MAX_IMAGE_PIXELS = 20_000_000


def validate_image_content(content: bytes) -> None:
    """使用 Pillow 验证图片完整性和像素大小。"""

    try:
        # 第一次打开：检查图片结构及尺寸
        with Image.open(BytesIO(content)) as image:
            width, height = image.size

            if width * height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=413,
                    detail="图片像素数量不能超过 2000 万",
                )

            image.verify()

        # 第二次打开：实际解码图片数据
        with Image.open(BytesIO(content)) as image:
            image.load()

    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
    ):
        raise HTTPException(
            status_code=400,
            detail="图片内容损坏或格式无效",
        )


@router.post("/images/upload")
async def upload_image(
    file: Annotated[UploadFile, File()],
    #Form() 表示这个参数来自 form-data
    question: Annotated[str, Form(min_length=1, max_length=1000)],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
):
    """接收并检查客户上传的图片。"""

    try:
        # 1. 检查文件类型
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail="只支持 JPG、PNG、WEBP 图片",
            )

        # 2. 读取文件，最多读取 5MB + 1 字节
        content = await file.read(MAX_IMAGE_SIZE + 1)

        # 3. 检查文件是否为空
        if not content:
            raise HTTPException(
                status_code=400,
                detail="上传文件不能为空",
            )

        # 4. 检查文件大小
        if len(content) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="图片大小不能超过 5MB",
            )

        # 检查文件内容的真实格式
        actual_type = detect_image_type(content)

        if actual_type is None:
            raise HTTPException(
                status_code=400,
                detail="无法识别图片格式",
            )
        if actual_type != file.content_type:
            raise HTTPException(
                status_code=400,
                detail="文件声明类型与实际图片格式不一致",
            )

        # 使用 Pillow 验证图片内容
        validate_image_content(content)

        # 5. 返回验证结果
        # 调用多模态业务编排服务
        try:

            result = await handle_multimodal_question(
                image_bytes=content,
                image_type=actual_type,
                question=question,
                customer_id=current_customer.id,
            )

        except OpenAIError:
            logging.getLogger(__name__).exception(
                "多模态 AI 模型调用失败"
            )
            raise HTTPException(
                status_code=502,
                detail="AI 模型调用失败，请稍后重试",
            ) from None



        return {
            "success": True,
            "filename": file.filename,
            "content_type": actual_type,
            "size": len(content),
            "image_observation": result["image_observation"],
            "answer": result["answer"],
        }



    finally:
        await file.close()
