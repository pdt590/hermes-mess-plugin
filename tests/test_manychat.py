import asyncio
import pytest
from aiohttp import web, ClientSession
from aiohttp.test_utils import TestServer


async def make_client(handler, **kwargs):
    from manychat import ManyChatClient
    app = web.Application()
    app.router.add_post("/fb/sending/sendContent", handler)
    server = TestServer(app)
    await server.start_server()
    session = ClientSession()
    return ManyChatClient(session, "secret-token", base_url=str(server.make_url("/")).rstrip("/"), **kwargs), session, server


async def test_send_contract():
    received = []
    async def handler(request):
        received.append((request.headers.get("Authorization"), await request.json()))
        return web.json_response({"status": "success"})
    client, session, server = await make_client(handler)
    try:
        result = await client.send_text("123", "Xin chào")
        assert result.success
        assert result.sent_chunks == 1
        assert received == [("Bearer secret-token", {"subscriber_id": 123, "data": {"version": "v2", "content": {"messages": [{"type": "text", "text": "Xin chào"}]}}})]
    finally:
        await session.close()
        await server.close()


@pytest.mark.parametrize("status,body,uncertain", [(200, {"status": "error", "message": "secret-token"}, False), (401, {}, False), (503, {}, True), (200, [], True)])
async def test_failures_are_not_retried_or_leaked(status, body, uncertain):
    calls = []
    async def handler(request):
        calls.append(1)
        return web.json_response(body, status=status)
    client, session, server = await make_client(handler)
    try:
        result = await client.send_text("123", "hi")
        assert not result.success and result.uncertain == uncertain
        assert len(calls) == 1
        assert "secret-token" not in result.error
    finally:
        await session.close()
        await server.close()


async def test_rate_limit_then_success():
    calls = []
    async def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return web.json_response({}, status=429, headers={"Retry-After": "0"})
        return web.json_response({"status": "success"})
    client, session, server = await make_client(handler)
    try:
        assert (await client.send_text("1", "hi")).success
        assert len(calls) == 3
    finally:
        await session.close()
        await server.close()


async def test_partial_chunks_and_timeout():
    calls = []
    async def handler(request):
        calls.append(await request.json())
        if len(calls) == 2:
            await asyncio.sleep(0.4)
        return web.json_response({"status": "success"})
    client, session, server = await make_client(handler, timeout=0.2)
    try:
        result = await client.send_text("1", "a" * 2100)
        assert not result.success and result.uncertain
        assert result.sent_chunks == 1 and len(calls) == 2
    finally:
        await session.close()
        await server.close()


async def test_fragmented_json_success():
    async def handler(request):
        response = web.StreamResponse(headers={"Content-Type": "application/json"})
        await response.prepare(request)
        await response.write(b'{"status":')
        await asyncio.sleep(0.02)
        await response.write(b'"success"}')
        await response.write_eof()
        return response
    client, session, server = await make_client(handler)
    try:
        assert (await client.send_text("1", "hi")).success
    finally:
        await session.close()
        await server.close()


async def test_unicode_chunks_and_rate_limit_cap():
    from manychat import text_chunks
    parts = list(text_chunks("😀" * 1001))
    assert [len(p.encode("utf-16-le")) // 2 for p in parts] == [2000, 2]
    assert "".join(parts) == "😀" * 1001
    calls = []
    async def handler(request):
        calls.append(1)
        return web.Response(status=429, headers={"Retry-After": "60"})
    client, session, server = await make_client(handler)
    try:
        result = await client.send_text("1", "hi")
        assert not result.success and not result.uncertain and result.error == "rate_limited"
        assert len(calls) == 1
    finally:
        await session.close()
        await server.close()
