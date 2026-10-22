import asyncio
import hashlib
import hmac
import importlib
import json
import time
from types import SimpleNamespace

from aiohttp import ClientSession
from aiohttp.test_utils import TestClient, TestServer
import pytest


@pytest.fixture
async def native(plugin, tmp_path):
    from gateway.config import Platform, PlatformConfig
    from gateway.platforms.webhook import WebhookAdapter
    module = importlib.import_module(plugin.__name__ + '.adapter')
    messenger = module.MessengerAdapter(PlatformConfig(extra={'token': 'test-token', 'database': str(tmp_path/'db')}))
    ingress = module.MessengerIngressAdapter(PlatformConfig())
    adapters = {Platform('messenger'): messenger, Platform('messenger_ingress'): ingress}
    runner = SimpleNamespace(_authorization_adapter=lambda platform, profile: adapters.get(platform))
    ingress.gateway_runner = runner
    webhook = WebhookAdapter(PlatformConfig(extra={'port':0, 'host':'0.0.0.0', 'secret': 'test-signing-secret', 'routes': {'manychat': module.manychat_route()}}))
    webhook.gateway_runner = runner
    seen = []
    async def handler(event):
        seen.append(event)
        return None
    messenger.set_message_handler(handler)
    assert await messenger.connect()
    assert await ingress.connect()
    assert await webhook.connect()
    port = webhook._runner.addresses[0][1]
    try:
        async with ClientSession(base_url=f'http://localhost:{port}') as http:
            yield http, messenger, seen
    finally:
        await webhook.disconnect()
    await ingress.disconnect()
    await messenger.disconnect()


def signed(body, timestamp=None):
    stamp = str(int(time.time() if timestamp is None else timestamp))
    digest = hmac.new(b'test-signing-secret', stamp.encode()+b'.'+body, hashlib.sha256).hexdigest()
    return {'Content-Type': 'application/json', 'X-Webhook-Timestamp': stamp, 'X-Webhook-Signature-V2': digest}


async def test_native_auth_queue_and_contact_session(native):
    http, messenger, seen = native
    body = json.dumps({'contact_id':'123','message':'hello "quoted"\nworld', 'message_id':'a','is_echo':False}).encode()
    assert (await http.post('/webhooks/manychat', data=body)).status == 401
    response = await http.post('/webhooks/manychat', data=body, headers=signed(body))
    assert response.status == 200
    assert (await response.json())['status'] == 'delivered'
    for _ in range(100):
        if seen:
            break
        await asyncio.sleep(.01)
    assert seen[0].source.chat_id == '123'
    assert seen[0].text == 'hello "quoted"\nworld'
    assert not seen[0].allow_gateway_control
    assert not hasattr(messenger, '_runner') or messenger._runner is None


async def test_native_tampered_stale_and_legacy_secret_rejected(native):
    http, messenger, seen = native
    body = b'{"contact_id":"123","message":"hello","message_id":"a"}'
    assert (await http.post('/webhooks/manychat', data=body+b' ', headers=signed(body))).status == 401
    assert (await http.post('/webhooks/manychat', data=body, headers=signed(body,time.time()-600))).status == 401
    assert (await http.post('/webhooks/manychat', data=body, headers={'X-Webhook-Secret':'test-signing-secret'})).status == 401
    assert not seen


async def test_native_static_token_echo_and_dedup(native):
    http, messenger, seen = native
    headers = {'X-Gitlab-Token':'test-signing-secret'}
    echo = {'contact_id':'123','message':'bot','message_id':'echo','is_echo':True}
    assert (await (await http.post('/webhooks/manychat', json=echo,headers=headers)).json())['status'] == 'ignored'
    data = {'contact_id':'123','message':'hello','message_id':'same','is_echo':False}
    for request_id in ('attempt1','attempt2'):
        assert (await http.post('/webhooks/manychat',json=data,headers={**headers,'X-Request-ID':request_id})).status == 200
    for _ in range(100):
        if seen:
            break
        await asyncio.sleep(.01)
    assert len(seen) == 1
