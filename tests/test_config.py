import pytest


def test_settings_validate_and_hide_secrets(tmp_path):
    from config import Settings
    with pytest.raises(ValueError):
        Settings(token="", secret="")
    for kw in ({"port": -1}, {"capacity": 0}, {"timeout": 0}):
        with pytest.raises(ValueError):
            Settings(token="token-value", secret="secret-value", **kw)
    settings = Settings(token="token-value", secret="secret-value", database=tmp_path / "db")
    assert "token-value" not in repr(settings)
    assert "secret-value" not in repr(settings)
