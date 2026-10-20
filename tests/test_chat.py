
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
import httpx
from openai import APITimeoutError, APIConnectionError
from app.services.chat_service import (
    ConversationBusyError,
    ConversationLockExpiredError,
)

client = TestClient(app)


def test_chat_creates_conversation():
    """首次聊天：自动创建会话。"""

    conversation_id = uuid4()

    with (
        patch(
            "app.api.v1.chat.resolve_conversation_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.api.v1.chat.generate_reply_and_save",
            new_callable=AsyncMock,
        ) as mock_chat,
    ):
        mock_resolve.return_value = conversation_id
        mock_chat.return_value = "您好，请问有什么需要帮助？"

        response = client.post(
            "/api/v1/chat",
            json={"message": "你好"},
        )

        assert response.status_code == 200
        assert response.json()["reply"] == "您好，请问有什么需要帮助？"
        assert response.json()["conversation_id"] == str(conversation_id)

        mock_resolve.assert_awaited_once_with(None)
        mock_chat.assert_awaited_once_with(
            message="你好",
            conversation_id=conversation_id,
        )


def test_chat_reuses_conversation():
    """继续聊天：复用已有会话 ID。"""

    conversation_id = uuid4()

    with (
        patch(
            "app.api.v1.chat.resolve_conversation_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.api.v1.chat.generate_reply_and_save",
            new_callable=AsyncMock,
        ) as mock_chat,
    ):
        mock_resolve.return_value = conversation_id
        mock_chat.return_value = "可以继续描述耳机故障。"

        response = client.post(
            "/api/v1/chat",
            json={
                "message": "我的耳机坏了",
                "conversation_id": str(conversation_id),
            },
        )

        assert response.status_code == 200
        assert response.json()["conversation_id"] == str(conversation_id)

        mock_resolve.assert_awaited_once_with(conversation_id)
        mock_chat.assert_awaited_once_with(
            message="我的耳机坏了",
            conversation_id=conversation_id,
        )


def test_chat_conversation_not_found():
    """会话不存在：返回 404。"""

    conversation_id = uuid4()

    with (
        patch(
            "app.api.v1.chat.resolve_conversation_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.api.v1.chat.generate_reply_and_save",
            new_callable=AsyncMock,
        ) as mock_chat,
    ):
        mock_resolve.side_effect = ValueError("会话不存在")

        response = client.post(
            "/api/v1/chat",
            json={
                "message": "继续聊天",
                "conversation_id": str(conversation_id),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "会话不存在"
        mock_chat.assert_not_awaited()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": "a" * 2001},
        {"message": "你好", "conversation_id": "invalid-uuid"},
    ],
)
def test_chat_invalid_request(payload):
    """非法输入应返回 422。"""

    response = client.post(
        "/api/v1/chat",
        json=payload,
    )

    assert response.status_code == 422


def test_chat_llm_timeout():
    """Qwen 请求超时应返回 HTTP 504。"""

    conversation_id = uuid4()

    request = httpx.Request(
        "POST",
        "https://example.com/chat/completions",
    )

    with (
        patch(
            "app.api.v1.chat.resolve_conversation_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.api.v1.chat.generate_reply_and_save",
            new_callable=AsyncMock,
        ) as mock_chat,
    ):
        mock_resolve.return_value = conversation_id

        mock_chat.side_effect = APITimeoutError(
            request=request,
        )

        response = client.post(
            "/api/v1/chat",
            json={"message": "你好"},
        )

        assert response.status_code == 504
        assert response.json()["detail"] == (
            "AI 服务响应超时，请稍后重试"
        )


def test_chat_llm_connection_error():
    """Qwen 网络连接失败应返回 HTTP 502。"""

    conversation_id = uuid4()

    request = httpx.Request(
        "POST",
        "https://example.com/chat/completions",
    )

    with (
        patch(
            "app.api.v1.chat.resolve_conversation_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.api.v1.chat.generate_reply_and_save",
            new_callable=AsyncMock,
        ) as mock_chat,
    ):
        mock_resolve.return_value = conversation_id

        mock_chat.side_effect = APIConnectionError(
            request=request,
        )

        response = client.post(
            "/api/v1/chat",
            json={"message": "你好"},
        )

        assert response.status_code == 502
        assert response.json()["detail"] == (
            "AI 服务暂时不可用，请稍后重试"
        )


def test_new_conversation_cleanup_on_timeout():
    """首次聊天超时，应清理新创建的空会话。"""

    conversation_id = uuid4()

    request = httpx.Request(
        "POST",
        "https://example.com/chat/completions",
    )

    with (
        patch(
            "app.api.v1.chat.resolve_conversation_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.api.v1.chat.generate_reply_and_save",
            new_callable=AsyncMock,
        ) as mock_chat,
        patch(
            "app.api.v1.chat.delete_empty_conversation",
            new_callable=AsyncMock,
        ) as mock_cleanup,
    ):
        mock_resolve.return_value = conversation_id
        mock_chat.side_effect = APITimeoutError(request=request)
        mock_cleanup.return_value = True

        response = client.post(
            "/api/v1/chat",
            json={"message": "你好"},
        )

        assert response.status_code == 504

        mock_cleanup.assert_awaited_once_with(
            conversation_id
        )

    print("New conversation cleanup test passed!")


def test_existing_conversation_not_cleaned_on_timeout():
    """已有会话超时，不应触发清理。"""

    conversation_id = uuid4()

    request = httpx.Request(
        "POST",
        "https://example.com/chat/completions",
    )

    with (
        patch(
            "app.api.v1.chat.resolve_conversation_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.api.v1.chat.generate_reply_and_save",
            new_callable=AsyncMock,
        ) as mock_chat,
        patch(
            "app.api.v1.chat.delete_empty_conversation",
            new_callable=AsyncMock,
        ) as mock_cleanup,
    ):
        mock_resolve.return_value = conversation_id
        mock_chat.side_effect = APITimeoutError(request=request)

        response = client.post(
            "/api/v1/chat",
            json={
                "message": "继续聊天",
                "conversation_id": str(conversation_id),
            },
        )

        assert response.status_code == 504

        mock_cleanup.assert_not_awaited()

    print("Existing conversation protection test passed!")

@pytest.mark.parametrize(
    "exception_type, expected_detail",
    [
        (
            ConversationBusyError,
            "会话正在处理中，请稍后重试",
        ),
        (
            ConversationLockExpiredError,
            "会话处理权已失效，请重新发送消息",
        ),
    ],
)
def test_chat_concurrency_errors_return_409(
    exception_type,
    expected_detail,
):
    """并发冲突和处理权失效应返回 HTTP 409。"""

    conversation_id = uuid4()

    with (
        patch(
            "app.api.v1.chat.resolve_conversation_id",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.api.v1.chat.generate_reply_and_save",
            new_callable=AsyncMock,
        ) as mock_chat,
    ):
        mock_resolve.return_value = conversation_id
        mock_chat.side_effect = exception_type(expected_detail)

        response = client.post(
            "/api/v1/chat",
            json={
                "message": "我的耳机没有声音",
                "conversation_id": str(conversation_id),
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"] == expected_detail

        mock_chat.assert_awaited_once_with(
            message="我的耳机没有声音",
            conversation_id=conversation_id,
        )

    print(f"{exception_type.__name__}: HTTP 409 passed!")