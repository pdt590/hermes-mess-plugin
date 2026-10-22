import pytest


def test_settings_validate_and_hide_secrets(tmp_path):
    from config import Settings
    with pytest.raises(ValueError):
        Settings(token="")
    for kw in ({"capacity": 0}, {"timeout": 0}):
        with pytest.raises(ValueError):
            Settings(token="token-value", **kw)
    settings = Settings(token="token-value", database=tmp_path / "db")
    assert "token-value" not in repr(settings)
    assert "secret-value" not in repr(settings)
