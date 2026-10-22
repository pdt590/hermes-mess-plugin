import asyncio
import importlib
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
import pytest


def make_adapter(plugin, tmp_path):
    from gateway.config import PlatformConfig
    module = importlib.import_module(plugin.__name__ + ".adapter")
    return module.MessengerAdapter(PlatformConfig(extra={"token": "token", "webhook_secret": "secret", "database": str(tmp_path / "db"), "port": 0}))


async def test_gateway_fifo_completion_and_routing(plugin, tmp_path):
    adapter = make_adapter(plugin, tmp_path)
    entered = asyncio.Event()
    release = asyncio.Event()
    observed = []
    delivered = []
    async def api(request):
        delivered.append(await request.json())
        return web.json_response({"status": "success"})
    app = web.Application()
    app.router.add_post("/fb/sending/sendContent", api)
    async with TestServer(app) as server:
        async def handler(event):
            observed.append(event)
            entered.set()
            await release.wait()
            return "reply to " + event.text
        adapter.set_message_handler(handler)
        assert await adapter.connect()
        adapter.client.url = str(server.make_url("/fb/sending/sendContent"))
        try:
            if True:
                from types import SimpleNamespace
                from gateway.config import PlatformConfig
                bridge = importlib.import_module(plugin.__name__ + ".adapter").MessengerIngressAdapter(PlatformConfig())
                bridge.gateway_runner = SimpleNamespace(_authorization_adapter=lambda platform, profile: adapter)
                for contact in ("123", "456"):
                    result = await bridge.send(contact, "hi", metadata={"thread_id": "a"})
                    assert result.success
                await asyncio.wait_for(entered.wait(), 3)
                assert len(observed) == 1
                states = dict(adapter.inbox.db.execute("SELECT state,count(*) FROM inbox GROUP BY state"))
                assert states == {"pending": 1, "processing": 1}
                release.set()
                for _ in range(300):
                    states = dict(adapter.inbox.db.execute("SELECT state,count(*) FROM inbox GROUP BY state"))
                    if states == {"complete": 2}:
                        break
                    await asyncio.sleep(0.01)
                assert states == {"complete": 2}
                assert [x["subscriber_id"] for x in delivered] == [123, 456]
                assert [x.source.chat_id for x in observed] == ["123", "456"]
                assert all(not x.allow_gateway_control and not x.internal and not x.source.role_authorized for x in observed)
        finally:
            await adapter.disconnect()
            await adapter.disconnect()


async def test_recovery_and_disconnect_preserves_accepted_message(plugin, tmp_path):
    from store import Inbox
    db = Inbox(tmp_path / "db")
    db.enqueue({"contact_id": "123", "message": "pending", "message_id": "a"})
    db.claim()
    db.close()
    adapter = make_adapter(plugin, tmp_path)
    entered = asyncio.Event()
    async def handler(event):
        entered.set()
        await asyncio.Event().wait()
    adapter.set_message_handler(handler)
    assert await adapter.connect()
    await asyncio.wait_for(entered.wait(), 3)
    await adapter.disconnect()
    db = Inbox(tmp_path / "db")
    db.recover()
    assert db.claim()[1]["message"] == "pending"
    db.close()


def test_register_platform(plugin):
    from gateway.platforms.base import BasePlatformAdapter
    from gateway.config import PlatformConfig
    # Registration context captures no behavior; the real registry is checked in smoke script.
    class Context:
        def register_platform(self, **kwargs):
            self.registration = kwargs
    ctx = Context()
    plugin.register(ctx)
    assert ctx.registration["name"] == "messenger"
    assert issubclass(ctx.registration["adapter_factory"], BasePlatformAdapter)
    assert ctx.registration["validate_config"](PlatformConfig(extra={"token": "t", "webhook_secret": "s"}))


async def test_no_plugin_listener_and_database_failure_cleans_resources(plugin, tmp_path):
    adapter = make_adapter(plugin, tmp_path)
    assert await adapter.connect()
    assert adapter.bound_port is None
    await adapter.disconnect()
    from dataclasses import replace
    adapter.settings = replace(adapter.settings, database=tmp_path)
    assert await adapter.connect() is False
    assert adapter.inbox is None and adapter.client is None and adapter._http is None


async def test_watchdog_pauses_ingress_without_losing_event(plugin, tmp_path):
    from dataclasses import replace
    adapter = make_adapter(plugin, tmp_path)
    adapter.settings = replace(adapter.settings, processing_timeout=0.05)
    async def handler(event):
        await asyncio.Event().wait()
    adapter.set_message_handler(handler)
    assert await adapter.connect()
    try:
        adapter.inbox.enqueue({"contact_id": "123", "message": "hi"})
        adapter._wake.set()
        for _ in range(100):
            if not adapter._ready:
                break
            await asyncio.sleep(0.01)
        assert not adapter._ready
        from types import SimpleNamespace
        from gateway.config import PlatformConfig
        bridge = importlib.import_module(plugin.__name__ + ".adapter").MessengerIngressAdapter(PlatformConfig())
        bridge.gateway_runner = SimpleNamespace(_authorization_adapter=lambda platform, profile: adapter)
        assert not (await bridge.send("123", "another")).success
        assert adapter.inbox.db.execute("SELECT state FROM inbox").fetchone()[0] == "processing"
    finally:
        await adapter.disconnect()


async def test_send_failure_no_gateway_retry(plugin, tmp_path):
    adapter = make_adapter(plugin, tmp_path)
    calls = []
    async def api(request):
        calls.append(1)
        return web.json_response({}, status=503)
    app = web.Application()
    app.router.add_post("/fb/sending/sendContent", api)
    async with TestServer(app) as server:
        assert await adapter.connect()
        adapter.client.url = str(server.make_url("/fb/sending/sendContent"))
        try:
            result = await adapter._send_with_retry("123", "hello")
            assert not result.success and result.raw_response["uncertain"]
            assert len(calls) == 1
        finally:
            await adapter.disconnect()


async def test_uncertain_final_not_added_to_gateway_boot_redelivery(plugin, tmp_path, monkeypatch):
    from gateway import delivery_ledger
    from gateway.platforms.event import MessageEvent
    monkeypatch.setattr(delivery_ledger, "_db_path", lambda: tmp_path / "ledger.sqlite")
    monkeypatch.setattr(delivery_ledger, "ledger_enabled", lambda: True)
    # Simulate the next boot discovering rows whose prior owner has exited.
    monkeypatch.setattr(delivery_ledger, "_owner_alive", lambda *args: False)
    adapter = make_adapter(plugin, tmp_path)
    calls = []
    async def api(request):
        calls.append(await request.json())
        if len(calls) == 1:
            return web.json_response({"status": "success"})
        return web.Response(status=503)
    app = web.Application()
    app.router.add_post("/fb/sending/sendContent", api)
    async with TestServer(app) as server:
        assert await adapter.connect()
        adapter.client.url = str(server.make_url("/fb/sending/sendContent"))
        try:
            event = MessageEvent(text="question", source=adapter.build_source(chat_id="123", user_id="123"), message_id="inbound", allow_gateway_control=False)
            result, _ = await adapter.send_final_ledgered(event, "messenger:123", "a" * 2100, {}, reply_to=None)
            assert not result.success and result.raw_response["sent_chunks"] == 1
            assert len(calls) == 2
            assert delivery_ledger.sweep_recoverable() == []
        finally:
            await adapter.disconnect()
