import pytest
from aiohttp.test_utils import TestClient, TestServer


@pytest.fixture
async def client(tmp_path):
    from webhook import create_app
    from store import Inbox
    from config import Settings
    inbox = Inbox(tmp_path / "db", 1)
    settings = Settings(token="t", secret="secret")
    async with TestClient(TestServer(create_app(settings, inbox, lambda: None))) as client:
        yield client, inbox
    inbox.close()


async def test_http_auth_admission_duplicate_conflict_and_full(client):
    http, inbox = client
    url = "/webhooks/manychat"
    data = {"contact_id": "123", "message": "hello", "message_id": "a"}
    assert (await http.post(url, json=data)).status == 401
    headers = {"X-Webhook-Secret": "secret"}
    first = await http.post(url, json=data, headers=headers)
    assert first.status == 202
    identifier = (await first.json())["id"]
    duplicate = await http.post(url, json=data, headers=headers)
    assert (await duplicate.json())["duplicate"] is True
    assert (await http.post(url, json={**data, "message": "other"}, headers=headers)).status == 409
    assert (await http.post(url, json={**data, "message_id": "b"}, headers=headers)).status == 503
    assert inbox.claim()[0] == identifier


@pytest.mark.parametrize("patch", [{"contact_id": True}, {"contact_id": 1.2}, {"contact_id": "１２３"}, {"message": " "}, {"message": "\ud800"}, {"channel": "instagram"}, {"is_echo": "false"}, {"message_id": []}])
async def test_validation(client, patch):
    http, _ = client
    response = await http.post("/webhooks/manychat", json={"contact_id": "123", "message": "hello", **patch}, headers={"X-Webhook-Secret": "secret"})
    assert response.status == 400


async def test_echo_bad_json_and_size(client):
    http, inbox = client
    headers = {"X-Webhook-Secret": "secret"}
    response = await http.post("/webhooks/manychat", json={"contact_id": "1", "message": "hi", "is_echo": True}, headers=headers)
    assert (await response.json())["status"] == "ignored"
    assert inbox.claim() is None
    assert (await http.post("/webhooks/manychat", data="{", headers=headers)).status == 400
    assert (await http.post("/webhooks/manychat", data="x" * 70000, headers=headers)).status == 413
    assert (await http.get("/healthz")).status == 200
