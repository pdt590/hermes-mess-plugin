import pytest


@pytest.mark.parametrize("patch", [{"contact_id": True}, {"contact_id": 1.2}, {"contact_id": "bad"}, {"message": " "}, {"channel": "instagram"}, {"is_echo": "false"}, {"message_id": []}])
def test_payload_validation(patch):
    from webhook import normalize_payload
    with pytest.raises(ValueError):
        normalize_payload({"contact_id": "123", "message": "hello", **patch})
