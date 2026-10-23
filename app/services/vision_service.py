
import base64

from openai import AsyncOpenAI

from app.core.config import get_settings


async def analyze_image(
    image_bytes: bytes,
    image_type: str,
    question: str,
) -> str:
    """调用视觉模型，分析用户上传的图片。"""

    settings = get_settings()

    # 1. 将图片转换成 Base64
    encoded_image = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    # 2. 构建图片 Data URL
    image_url = (
        f"data:{image_type};base64,{encoded_image}"
    )

    # 3. 创建大模型客户端
    client = AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=60.0,
    )

    # 4. 同时发送文字和图片
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": question,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                        },
                    },
                ],
            }
        ],
    )

    # 5. 提取模型回答
    answer = response.choices[0].message.content

    if not answer:
        raise ValueError("视觉模型未返回文字回答")

    return answer
