"""Native Hermes webhook route and shared ingress payload validation. No HTTP listener."""
import re


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


def manychat_route():
    """Hermes core authenticates and renders fields without JSON interpolation."""
    return {
        "prompt": "{message}",
        "deliver_only": True,
        "deliver": "messenger_ingress",
        "deliver_extra": {"chat_id": "{contact_id}", "thread_id": "{message_id}"},
        "filters": [
            {"field": "is_echo", "not_equals": True},
            {"field": "contact_id", "regex": "^[1-9][0-9]{0,29}$"},
            {"field": "message", "regex": r"\S"},
        ],
    }
