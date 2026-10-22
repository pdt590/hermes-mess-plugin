"""ManyChat External Request ingress. Payload is our explicit contract."""
import hmac
import json
import re
import sqlite3
from aiohttp import web

try:
    from .store import Conflict, Full
except ImportError:  # standalone unit tests
    from store import Conflict, Full


def normalize_payload(data):
    if not isinstance(data, dict):
        raise ValueError()
    contact = data.get("contact_id")
    if type(contact) is int:
        contact = str(contact)
    if not isinstance(contact, str) or not re.fullmatch(r"[1-9][0-9]{0,29}", contact):
        raise ValueError()
    message = data.get("message")
    if not isinstance(message, str) or not message.strip() or len(message) > 10000:
        raise ValueError()
    if data.get("channel", "facebook") != "facebook" or type(data.get("is_echo", False)) is not bool:
        raise ValueError()
    identifier = data.get("message_id")
    if identifier is not None and (not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 256):
        raise ValueError()
    message.encode("utf-8")
    if identifier is not None:
        identifier.encode("utf-8")
    return {"contact_id": contact, "message": message, "message_id": identifier,
            "channel": "facebook", "is_echo": data.get("is_echo", False)}


def create_app(settings, inbox, wake_worker, ready=lambda: True):
    app = web.Application(client_max_size=65536)

    async def receive(request):
        supplied = request.headers.get("X-Webhook-Secret", "").encode("utf-8")
        if not hmac.compare_digest(supplied, settings.secret.encode("utf-8")):
            return web.json_response({"error": "unauthorized"}, status=401)
        if not ready():
            return web.json_response({"error": "unavailable"}, status=503, headers={"Retry-After": "5"})
        try:
            payload = normalize_payload(await request.json())
        except (ValueError, UnicodeError, json.JSONDecodeError):
            return web.json_response({"error": "invalid_payload"}, status=400)
        if payload["is_echo"]:
            return web.json_response({"status": "ignored"})
        try:
            receipt = inbox.enqueue(payload)
        except Conflict:
            return web.json_response({"error": "id_conflict"}, status=409)
        except (Full, sqlite3.Error):
            return web.json_response({"error": "unavailable"}, status=503, headers={"Retry-After": "5"})
        wake_worker()
        return web.json_response({"status": "accepted", "id": receipt.id, "duplicate": receipt.duplicate}, status=202)

    async def health(request):
        return web.json_response({"status": "ok" if ready() else "unavailable"}, status=200 if ready() else 503)

    app.router.add_post("/webhooks/manychat", receive)
    app.router.add_get("/healthz", health)
    return app
