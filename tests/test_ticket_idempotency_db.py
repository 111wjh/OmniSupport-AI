"""显式启用的 PostgreSQL 集成测试；模型节点替换，真实走 Graph、工具和事务。"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import Request
from PIL import Image
from sqlalchemy import func, select

from app.core.auth import get_current_customer
from app.db.session import get_db
from app.main import app, fastapi_app
from app.models import ChatOperation, Conversation, Customer, Message, Ticket
from app.schemas.ticket import TicketCreateRequest
from app.services import chat_idempotency, chat_service, conversation_service, multimodal_service, ticket_service
from app.services.ticket_service import TicketIdempotencyConflictError
from app.tools import ticket_tools
from app.tools.context import ToolContext
from app.agent import graph, nodes, service as agent_service
from evaluations.ticket_test_db import run_async, ticket_test_database

pytestmark = pytest.mark.skipif(
    os.getenv("OMNISUPPORT_DB_TESTS") != "1",
    reason="设置 OMNISUPPORT_DB_TESTS=1，在专用测试库中运行",
)

ARGS = {"subject": "幂等测试工单", "description": "测试耳机连接问题，请人工协助排查。"}
BODY = {"message": "请创建人工工单，帮助排查耳机连接。", "conversation_id": None}


@asynccontextmanager
async def environment(monkeypatch):
    async with ticket_test_database() as sessions:
        async with sessions.begin() as session:
            customers = [
                Customer(email=f"idempotency-{uuid4().hex}@example.com",
                         display_name="集成测试", password_hash="unused-test-hash")
                for _ in range(2)
            ]
            session.add_all(customers)
        for module in (chat_idempotency, chat_service, conversation_service, ticket_tools):
            monkeypatch.setattr(module, "AsyncSessionLocal", sessions)

        calls = []
        async def model_node(state):
            calls.append(state)
            return {
                "model_calls": state["model_calls"] + 1,
                "messages": [{
                    "role": "assistant", "content": "",
                    "tool_calls": [{
                        "id": str(uuid4()), "type": "function",
                        "function": {"name": "create_support_ticket", "arguments": json.dumps(ARGS)},
                    }],
                }],
            }

        monkeypatch.setattr(graph, "call_model", model_node)
        monkeypatch.setattr(graph, "agent_graph", graph.build_agent_graph())
        for module in (nodes, agent_service):
            monkeypatch.setattr(module, "get_langfuse_client", lambda: MagicMock())
        observations = []
        async def vision(**kwargs):
            observations.append(kwargs)
            return "图片中是一副白色耳机，未见明显裂纹。"
        monkeypatch.setattr(multimodal_service, "analyze_image", vision)

        async def current_customer(request: Request):
            customer_id = UUID(request.headers.get("X-Test-Customer", str(customers[0].id)))
            return next(customer for customer in customers if customer.id == customer_id)
        async def database_session():
            async with sessions() as session:
                yield session
        previous = fastapi_app.dependency_overrides.copy()
        fastapi_app.dependency_overrides[get_current_customer] = current_customer
        fastapi_app.dependency_overrides[get_db] = database_session
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                yield SimpleNamespace(sessions=sessions, client=client, customers=customers,
                                      calls=calls, observations=observations)
        finally:
            fastapi_app.dependency_overrides.clear()
            fastapi_app.dependency_overrides.update(previous)


async def counts(env):
    async with env.sessions() as session:
        return tuple([
            await session.scalar(select(func.count()).select_from(model))
            for model in (Conversation, ChatOperation, Ticket, Message)
        ])


@pytest.mark.parametrize("different_payload", [False, True])
@pytest.mark.parametrize("repeat", range(3))
def test_direct_creation_database_race(monkeypatch, different_payload, repeat):
    async def check():
        async with environment(monkeypatch) as env:
            barrier = asyncio.Barrier(2)
            original = ticket_service._get_idempotent_ticket
            async def both_miss(*args, **kwargs):
                result = await original(*args, **kwargs)
                if result is None:
                    await barrier.wait()
                return result
            monkeypatch.setattr(ticket_service, "_get_idempotent_ticket", both_miss)
            async def create(subject):
                async with env.sessions() as session:
                    return await ticket_service.create_customer_ticket(
                        session, env.customers[0].id,
                        TicketCreateRequest(**{**ARGS, "subject": subject}),
                        idempotency_key=f"race-{repeat}",
                    )
            results = await asyncio.gather(
                create(ARGS["subject"]),
                create("不同的标题" if different_payload else ARGS["subject"]),
                return_exceptions=True,
            )
            if different_payload:
                assert sum(isinstance(item, Ticket) for item in results) == 1
                assert sum(isinstance(item, TicketIdempotencyConflictError) for item in results) == 1
            else:
                assert all(isinstance(item, Ticket) for item in results), results
                assert results[0].id == results[1].id
            assert (await counts(env))[2] == 1
    run_async(check())


def test_direct_api_key_contracts_and_owner_checks(monkeypatch):
    async def check():
        async with environment(monkeypatch) as env:
            headers = {"Idempotency-Key": "demo-key"}
            first = await env.client.post("/api/v1/tickets", json=ARGS, headers=headers)
            second = await env.client.post("/api/v1/tickets", json=ARGS, headers=headers)
            assert first.status_code == second.status_code == 201
            assert first.json()["id"] == second.json()["id"]
            conflict = await env.client.post("/api/v1/tickets", json={**ARGS, "subject": "新标题"}, headers=headers)
            assert conflict.status_code == 409
            other = await env.client.post("/api/v1/tickets", json=ARGS, headers={
                **headers, "X-Test-Customer": str(env.customers[1].id),
            })
            assert other.status_code == 201 and other.json()["id"] != first.json()["id"]
            for invalid in ("", "white space", "x" * 129, "chat-operation:fake", "agent-run:fake"):
                response = await env.client.post("/api/v1/tickets", json=ARGS, headers={"Idempotency-Key": invalid})
                assert response.status_code == 422
            no_key = [await env.client.post("/api/v1/tickets", json=ARGS) for _ in range(2)]
            assert no_key[0].json()["id"] != no_key[1].json()["id"]
            async with env.sessions.begin() as session:
                foreign = await conversation_service.create_conversation(session, customer_id=env.customers[1].id)
            denied = await env.client.post("/api/v1/tickets", json={
                **ARGS, "conversation_id": str(foreign.id),
            }, headers={"Idempotency-Key": "foreign"})
            assert denied.status_code == 404
    run_async(check())


@pytest.mark.parametrize("changed", [False, True])
def test_first_turn_mapping_race_rolls_back_losing_conversation(monkeypatch, changed):
    async def check():
        async with environment(monkeypatch) as env:
            barrier = asyncio.Barrier(2)
            original = chat_idempotency.create_conversation
            async def create_together(*args, **kwargs):
                result = await original(*args, **kwargs)
                await barrier.wait()
                return result
            monkeypatch.setattr(chat_idempotency, "create_conversation", create_together)
            request_id = uuid4()
            async def prepare(message):
                return await chat_idempotency.prepare_chat_operation(
                    env.customers[0].id, request_id, message, None,
                )
            results = await asyncio.gather(
                prepare("原请求"), prepare("改变的请求" if changed else "原请求"),
                return_exceptions=True,
            )
            if changed:
                assert sum(isinstance(item, chat_idempotency.ChatIdempotencyConflictError) for item in results) == 1
            else:
                assert results[0].id == results[1].id
            assert await counts(env) == (1, 1, 0, 0)
    run_async(check())


@pytest.mark.parametrize("first_path", ["/api/v1/chat", "/api/v1/chat/stream"])
def test_chat_replay_across_transports_and_changed_input(monkeypatch, first_path):
    async def check():
        async with environment(monkeypatch) as env:
            body = {**BODY, "client_request_id": str(uuid4())}
            first = await env.client.post(first_path, json=body)
            assert first.status_code == 200
            assert "人工服务工单已创建" in first.text
            replay = await env.client.post("/api/v1/chat", json=body)
            streamed = await env.client.post("/api/v1/chat/stream", json=body)
            assert replay.status_code == streamed.status_code == 200
            assert replay.json()["reply"] in streamed.text.replace("\\n", "\n")
            assert "event: done" in streamed.text
            assert len(env.calls) == 1
            assert await counts(env) == (1, 1, 1, 2)
            changed = await env.client.post("/api/v1/chat", json={**body, "message": "换了内容"})
            assert changed.status_code == 409
            changed_conversation = await env.client.post("/api/v1/chat", json={
                **body, "conversation_id": replay.json()["conversation_id"],
            })
            assert changed_conversation.status_code == 409
            assert len(env.calls) == 1
            other = await env.client.post("/api/v1/chat", json=body, headers={
                "X-Test-Customer": str(env.customers[1].id),
            })
            assert other.status_code == 200
            assert other.json()["conversation_id"] != replay.json()["conversation_id"]
            assert await counts(env) == (2, 2, 2, 4)
    run_async(check())


def test_parallel_same_chat_operation_is_busy_then_replays(monkeypatch):
    async def check():
        async with environment(monkeypatch) as env:
            started, finish = asyncio.Event(), asyncio.Event()
            original = chat_service.generate_agent_reply
            async def wait_in_model(**kwargs):
                started.set()
                await finish.wait()
                return await original(**kwargs)
            monkeypatch.setattr(chat_service, "generate_agent_reply", wait_in_model)
            body = {**BODY, "client_request_id": str(uuid4())}
            task = asyncio.create_task(env.client.post("/api/v1/chat", json=body))
            await asyncio.wait_for(started.wait(), 10)
            try:
                competing = await env.client.post("/api/v1/chat", json=body)
                assert competing.status_code == 409
            finally:
                finish.set()
            assert (await task).status_code == 200
            assert (await env.client.post("/api/v1/chat", json=body)).status_code == 200
            assert len(env.calls) == 1
            assert await counts(env) == (1, 1, 1, 2)
    run_async(check())


@pytest.mark.parametrize("retry_path", ["/api/v1/chat", "/api/v1/chat/stream"])
def test_ticket_commit_then_history_failure_recovers_without_model(monkeypatch, retry_path):
    async def check():
        async with environment(monkeypatch) as env:
            original = chat_service.save_chat_turn_with_token
            failures = 1
            async def fail_after_save(**kwargs):
                nonlocal failures
                await original(**kwargs)
                if failures:
                    failures -= 1
                    raise RuntimeError("injected failure: roll back both messages")
            monkeypatch.setattr(chat_service, "save_chat_turn_with_token", fail_after_save)
            body = {**BODY, "client_request_id": str(uuid4())}
            failed = await env.client.post("/api/v1/chat", json=body)
            assert failed.status_code == 500
            assert await counts(env) == (1, 1, 1, 0)
            async with env.sessions() as session:
                operation = await session.scalar(select(ChatOperation))
                assert operation.reply is None and operation.completed_at is None
            response = await env.client.post(retry_path, json=body)
            assert response.status_code == 200 and "人工服务工单已创建" in response.text
            assert len(env.calls) == 1
            assert await counts(env) == (1, 1, 1, 2)
            async with env.sessions() as session:
                operation = await session.scalar(select(ChatOperation))
                assert operation.reply is not None and operation.completed_at is not None
    run_async(check())


def test_image_retry_reuses_original_bytes_and_observation(monkeypatch):
    async def check():
        async with environment(monkeypatch) as env:
            def image(color):
                output = BytesIO()
                Image.new("RGB", (2, 2), color).save(output, format="PNG")
                return output.getvalue()
            image_bytes = image("white")
            data = {"question": BODY["message"], "client_request_id": str(uuid4())}
            async def send(content):
                return await env.client.post("/api/v1/images/upload", data=data,
                    files={"file": ("test.png", content, "image/png")})
            original = chat_service.save_chat_turn_with_token
            async def fail(**kwargs):
                raise RuntimeError("injected failure before chat commit")
            monkeypatch.setattr(chat_service, "save_chat_turn_with_token", fail)
            assert (await send(image_bytes)).status_code == 500
            assert await counts(env) == (1, 1, 1, 0)
            monkeypatch.setattr(chat_service, "save_chat_turn_with_token", original)
            recovered = await send(image_bytes)
            replay = await send(image_bytes)
            assert recovered.status_code == replay.status_code == 200
            assert recovered.json() == replay.json()
            assert len(env.calls) == len(env.observations) == 1
            assert (await send(image("black"))).status_code == 409
            assert await counts(env) == (1, 1, 1, 2)
    run_async(check())


def test_same_operation_repeated_tool_arguments_cannot_create_second_ticket(monkeypatch):
    async def check():
        async with environment(monkeypatch) as env:
            operation = await chat_idempotency.prepare_chat_operation(env.customers[0].id, uuid4(), "建单", None)
            context = ToolContext(
                customer_id=env.customers[0].id,
                conversation_id=operation.conversation_id,
                ticket_idempotency_key=chat_idempotency.ticket_key(operation.id),
            )
            first = await ticket_tools.execute_create_support_ticket(json.dumps(ARGS), context)
            repeated = await ticket_tools.execute_create_support_ticket(json.dumps(ARGS), context)
            changed = await ticket_tools.execute_create_support_ticket(
                json.dumps({**ARGS, "subject": "改写标题"}),
                context,
            )
            assert first["success"] is repeated["success"] is True
            assert first["data"]["id"] == repeated["data"]["id"]
            assert changed["error"] == "ticket_idempotency_conflict"
            assert (await counts(env))[2] == 1
    run_async(check())
