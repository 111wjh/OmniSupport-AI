
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.chat_service import generate_reply_and_save
import pytest

from app.services.chat_service import (
    generate_reply_and_save,
    ConversationBusyError,
    ConversationLockExpiredError,
    _renew_conversation_periodically,
)
def test_generate_reply_and_save_success():
    """正常聊天：获取处理权、读取历史、生成回复、安全保存并释放处理权。"""

    conversation_id = uuid4()
    token = uuid4()

    history_messages = [object()]
    formatted_history = [
        {"role": "user", "content": "之前的问题"}
    ]
    expected_reply = "请检查耳机连接状态。"

    # 模拟异步数据库会话
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False

    # 模拟数据库事务
    transaction = AsyncMock()
    transaction.__aenter__.return_value = session
    transaction.__aexit__.return_value = False

    with (
        patch(
            "app.services.chat_service.acquire_conversation",
            new_callable=AsyncMock,
        ) as mock_acquire,
        patch(
            "app.services.chat_service.release_conversation",
            new_callable=AsyncMock,
        ) as mock_release,
        patch(
            "app.services.chat_service.get_conversation_messages",
            new_callable=AsyncMock,
        ) as mock_get_history,
        patch(
            "app.services.chat_service.format_history_for_llm",
        ) as mock_format,
        patch(
            "app.services.chat_service.generate_llm_reply",
            new_callable=AsyncMock,
        ) as mock_llm,
        patch(
            "app.services.chat_service.save_chat_turn_with_token",
            new_callable=AsyncMock,
        ) as mock_save,
        patch(
            "app.services.chat_service.AsyncSessionLocal",
        ) as mock_session_factory,
    ):
        # 配置所有模拟对象
        mock_acquire.return_value = token
        mock_get_history.return_value = history_messages
        mock_format.return_value = formatted_history
        mock_llm.return_value = expected_reply

        mock_session_factory.return_value = session
        mock_session_factory.begin.return_value = transaction

        # 执行真正的 ChatService 业务函数
        reply = asyncio.run(
            generate_reply_and_save(
                message="你好",
                conversation_id=conversation_id,
            )
        )

        # 1. 成功获取会话处理权
        mock_acquire.assert_awaited_once_with(
            conversation_id
        )

        # 2. 查询当前会话的历史消息
        mock_get_history.assert_awaited_once_with(
            session=session,
            conversation_id=conversation_id,
        )

        # 3. 格式化历史并调用模型
        mock_format.assert_called_once_with(
            history_messages
        )
        mock_llm.assert_awaited_once_with(
            message="你好",
            history=formatted_history,
        )

        # 4. 使用 Token 保存用户消息和 AI 回复
        mock_save.assert_awaited_once_with(
            session=session,
            conversation_id=conversation_id,
            token=token,
            user_content="你好",
            assistant_content=expected_reply,
        )

        # 5. 返回正确的 AI 回复
        assert reply == expected_reply

        # 6. 释放自己获取的处理权
        mock_release.assert_awaited_once_with(
            conversation_id,
            token,
        )

    print("ChatService success flow test passed!")

def test_generate_reply_and_save_rejects_busy_conversation():
    """会话正在处理时，拒绝新的聊天请求。"""

    conversation_id = uuid4()

    with (
        patch(
            "app.services.chat_service.acquire_conversation",
            new_callable=AsyncMock,
        ) as mock_acquire,
        patch(
            "app.services.chat_service.generate_llm_reply",
            new_callable=AsyncMock,
        ) as mock_llm,
        patch(
            "app.services.chat_service.release_conversation",
            new_callable=AsyncMock,
        ) as mock_release,
    ):
        # 模拟会话已经被其他请求占用
        mock_acquire.return_value = None

        # 验证当前请求被拒绝
        with pytest.raises(ConversationBusyError):
            asyncio.run(
                generate_reply_and_save(
                    message="我的耳机没有声音",
                    conversation_id=conversation_id,
                )
            )

        # 确认尝试获取处理权
        mock_acquire.assert_awaited_once_with(
            conversation_id
        )

        # 被拒绝后不能调用 Qwen
        mock_llm.assert_not_awaited()

        # 不能释放其他请求的处理权
        mock_release.assert_not_awaited()

    print("ChatService busy conversation test passed!")


def test_generate_reply_and_save_releases_lock_on_llm_error():
    """Qwen 调用失败时，仍然释放会话处理权。"""

    conversation_id = uuid4()
    token = uuid4()

    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False

    with (
        patch(
            "app.services.chat_service.acquire_conversation",
            new_callable=AsyncMock,
        ) as mock_acquire,
        patch(
            "app.services.chat_service.release_conversation",
            new_callable=AsyncMock,
        ) as mock_release,
        patch(
            "app.services.chat_service.get_conversation_messages",
            new_callable=AsyncMock,
        ) as mock_history,
        patch(
            "app.services.chat_service.format_history_for_llm",
        ) as mock_format,
        patch(
            "app.services.chat_service.generate_llm_reply",
            new_callable=AsyncMock,
        ) as mock_llm,
        patch(
            "app.services.chat_service.save_chat_turn_with_token",
            new_callable=AsyncMock,
        ) as mock_save,
        patch(
            "app.services.chat_service.AsyncSessionLocal",
        ) as mock_session_factory,
    ):
        mock_acquire.return_value = token
        mock_history.return_value = []
        mock_format.return_value = []
        mock_llm.side_effect = RuntimeError("模拟 Qwen 调用失败")
        mock_session_factory.return_value = session

        with pytest.raises(RuntimeError, match="模拟 Qwen 调用失败"):
            asyncio.run(
                generate_reply_and_save(
                    message="我的耳机没有声音",
                    conversation_id=conversation_id,
                )
            )

        # 即使模型调用失败，也必须释放自己的处理权
        mock_release.assert_awaited_once_with(
            conversation_id,
            token,
        )

        # 模型没有生成回复，因此不能保存聊天记录
        mock_save.assert_not_awaited()

    print("ChatService lock release on error test passed!")


def test_generate_reply_and_save_handles_expired_token():
    """保存时 Token 失效，应转换异常并释放处理权。"""

    conversation_id = uuid4()
    token = uuid4()

    session = AsyncMock()
    transaction = AsyncMock()
    transaction.__aenter__.return_value = session
    transaction.__aexit__.return_value = False

    with (
        patch(
            "app.services.chat_service.acquire_conversation",
            new_callable=AsyncMock,
        ) as mock_acquire,
        patch(
            "app.services.chat_service.release_conversation",
            new_callable=AsyncMock,
        ) as mock_release,
        patch(
            "app.services.chat_service.get_conversation_messages",
            new_callable=AsyncMock,
        ) as mock_history,
        patch(
            "app.services.chat_service.format_history_for_llm",
        ) as mock_format,
        patch(
            "app.services.chat_service.generate_llm_reply",
            new_callable=AsyncMock,
        ) as mock_llm,
        patch(
            "app.services.chat_service.save_chat_turn_with_token",
            new_callable=AsyncMock,
        ) as mock_save,
        patch(
            "app.services.chat_service.AsyncSessionLocal",
        ) as mock_session_factory,
    ):
        mock_acquire.return_value = token
        mock_history.return_value = []
        mock_format.return_value = []
        mock_llm.return_value = "请检查耳机连接状态。"
        mock_session_factory.return_value = session
        mock_session_factory.begin.return_value = transaction

        mock_save.side_effect = ValueError("会话处理权已失效")

        with pytest.raises(
            ConversationLockExpiredError,
            match="会话处理权已失效",
        ):
            asyncio.run(
                generate_reply_and_save(
                    message="我的耳机没有声音",
                    conversation_id=conversation_id,
                )
            )

        # 保存失败时，应当已经调用安全保存函数
        mock_save.assert_awaited_once_with(
            session=session,
            conversation_id=conversation_id,
            token=token,
            user_content="我的耳机没有声音",
            assistant_content="请检查耳机连接状态。",
        )

        # 异常退出时仍应尝试释放自己的处理权
        mock_release.assert_awaited_once_with(
            conversation_id,
            token,
        )

    print("ChatService expired token test passed!")

def test_release_error_does_not_mask_llm_error():
    """释放处理权失败时，不覆盖原始的 Qwen 异常。"""

    conversation_id = uuid4()
    token = uuid4()

    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False

    with (
        patch(
            "app.services.chat_service.acquire_conversation",
            new_callable=AsyncMock,
        ) as mock_acquire,
        patch(
            "app.services.chat_service.release_conversation",
            new_callable=AsyncMock,
        ) as mock_release,
        patch(
            "app.services.chat_service.get_conversation_messages",
            new_callable=AsyncMock,
        ) as mock_history,
        patch(
            "app.services.chat_service.format_history_for_llm",
        ) as mock_format,
        patch(
            "app.services.chat_service.generate_llm_reply",
            new_callable=AsyncMock,
        ) as mock_llm,
        patch(
            "app.services.chat_service.save_chat_turn_with_token",
            new_callable=AsyncMock,
        ) as mock_save,
        patch(
            "app.services.chat_service.AsyncSessionLocal",
        ) as mock_session_factory,
    ):
        mock_acquire.return_value = token
        mock_history.return_value = []
        mock_format.return_value = []

        # 第一个异常：Qwen 调用失败
        mock_llm.side_effect = RuntimeError(
            "模拟 Qwen 调用失败"
        )

        # 第二个异常：释放处理权失败
        mock_release.side_effect = RuntimeError(
            "模拟释放处理权失败"
        )

        mock_session_factory.return_value = session

        with pytest.raises(
            RuntimeError,
            match="模拟 Qwen 调用失败",
        ):
            asyncio.run(
                generate_reply_and_save(
                    message="你好",
                    conversation_id=conversation_id,
                )
            )

        # 释放操作确实被尝试执行
        mock_release.assert_awaited_once_with(
            conversation_id,
            token,
        )

        # 模型调用失败，不能保存聊天记录
        mock_save.assert_not_awaited()

    print("ChatService release error protection test passed!")


def test_periodic_renewal_stops_when_requested():
    """续期协程能够重复续期，并响应停止信号。"""

    conversation_id = uuid4()
    token = uuid4()

    async def run_test():
        stop_event = asyncio.Event()
        lease_lost_event = asyncio.Event()
        renewal_count = 0

        async def renew_side_effect(*args):
            nonlocal renewal_count
            renewal_count += 1

            # 模拟成功续期两次后，主流程要求停止
            if renewal_count == 2:
                stop_event.set()

            return True

        with patch(
            "app.services.chat_service.renew_conversation",
            new_callable=AsyncMock,
            side_effect=renew_side_effect,
        ) as mock_renew:
            await _renew_conversation_periodically(
                conversation_id=conversation_id,
                token=token,
                stop_event=stop_event,
                lease_lost_event=lease_lost_event,
                interval_seconds=0.01,
            )

            assert mock_renew.await_count == 2
            assert not lease_lost_event.is_set()

    asyncio.run(run_test())

    print("Periodic renewal stop test passed!")


def test_periodic_renewal_signals_lost_lease():
    """续期失败时，设置处理权失效事件并退出。"""

    conversation_id = uuid4()
    token = uuid4()

    async def run_test():
        stop_event = asyncio.Event()
        lease_lost_event = asyncio.Event()

        with patch(
            "app.services.chat_service.renew_conversation",
            new_callable=AsyncMock,
            return_value=False,
        ) as mock_renew:
            await _renew_conversation_periodically(
                conversation_id=conversation_id,
                token=token,
                stop_event=stop_event,
                lease_lost_event=lease_lost_event,
                interval_seconds=0.01,
            )

            mock_renew.assert_awaited_once_with(
                conversation_id,
                token,
            )
            assert lease_lost_event.is_set()

    asyncio.run(run_test())

    print("Periodic renewal failure test passed!")
