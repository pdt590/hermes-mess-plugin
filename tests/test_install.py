from pathlib import Path
import pytest


def test_install_merges_without_overwriting_and_is_idempotent(tmp_path):
    from scripts.install import configure
    home = tmp_path / "hermes"
    home.mkdir()
    original_env = '# keep me\nOTHER_TOKEN="keep"\nexport MANYCHAT_API_TOKEN="existing"\nMESSENGER_PORT=9999\n'
    original_config = '# owner comment\nmodel: existing-model\nplugins:\n  enabled: [other]\nplatforms:\n  telegram:\n    enabled: true\n  messenger:\n    extra:\n      port: 9999\n'
    (home / ".env").write_text(original_env, encoding="utf-8")
    (home / "config.yaml").write_text(original_config, encoding="utf-8")
    result = configure(home, environ={"MANYCHAT_API_TOKEN": "do-not-overwrite"})
    env = (home / ".env").read_text(encoding="utf-8")
    config = (home / "config.yaml").read_text(encoding="utf-8")
    assert env.startswith(original_env)
    assert env.count("MANYCHAT_API_TOKEN=") == 1
    assert 'MESSENGER_HOST="0.0.0.0"' in env
    assert "MESSENGER_ALLOWED_USERS=\"\"" in env
    assert "# owner comment" in config and "existing-model" in config
    from ruamel.yaml import YAML
    parsed = YAML().load(config)
    assert parsed["plugins"]["enabled"] == ["other", "messenger"]
    assert parsed["platforms"]["telegram"]["enabled"] is True
    assert parsed["platforms"]["messenger"]["extra"]["port"] == 9999
    assert parsed["platforms"]["messenger"]["extra"]["host"] == "0.0.0.0"
    assert len(result["backups"]) == 2
    assert sorted(Path(p).read_text(encoding="utf-8") for p in result["backups"]) == sorted([original_env, original_config])
    again = configure(home, environ={})
    assert again["changed"] == [] and again["backups"] == []
    assert (home / ".env").read_text(encoding="utf-8") == env
    assert (home / "config.yaml").read_text(encoding="utf-8") == config


@pytest.mark.parametrize("yaml", ["plugins: []", "plugins:\n  enabled: nope", "platforms: []", "platforms:\n  messenger:\n    extra: wrong", "plugins: [invalid", "false", "model: x\nmodel: y"])
def test_invalid_config_never_modifies_files(tmp_path, yaml):
    from scripts.install import configure
    (tmp_path / ".env").write_bytes(b"KEEP=1\r\n")
    (tmp_path / "config.yaml").write_text(yaml, encoding="utf-8")
    with pytest.raises(ValueError):
        configure(tmp_path, environ={})
    assert (tmp_path / ".env").read_bytes() == b"KEEP=1\r\n"
    assert (tmp_path / "config.yaml").read_text(encoding="utf-8") == yaml
    assert not list(tmp_path.glob("*.bak.*"))


def test_new_install_and_home_detection(tmp_path):
    from scripts.install import configure, default_home
    home = tmp_path / "new"
    result = configure(home, environ={"MANYCHAT_API_TOKEN": "token-with-#"})
    text = (home / ".env").read_text(encoding="utf-8")
    assert 'MANYCHAT_API_TOKEN="token-with-#"' in text
    secret = next(line.split("=", 1)[1] for line in text.splitlines() if line.startswith("MESSENGER_WEBHOOK_SECRET="))
    assert len(secret) >= 43 and "replace" not in secret
    assert result["backups"] == []
    assert default_home({"LOCALAPPDATA": str(tmp_path)}, "win32", tmp_path / "user") == tmp_path / "hermes"
    assert default_home({}, "linux", tmp_path / "user") == tmp_path / "user" / ".hermes"
    assert default_home({"HERMES_HOME": str(tmp_path / "override")}, "linux", tmp_path) == tmp_path / "override"


def test_dependencies_install_only_missing(monkeypatch):
    from scripts import install
    attempts = []
    def importer(name):
        if name == "aiohttp" and not attempts:
            raise ModuleNotFoundError(name)
    monkeypatch.setattr(install.importlib, "import_module", importer)
    monkeypatch.setattr(install.subprocess, "run", lambda args, **kw: attempts.append(args))
    install.ensure_dependencies()
    assert len(attempts) == 1
    assert attempts[0][1:4] == ["-m", "pip", "install"]
    assert "aiohttp>=3.9,<4" in attempts[0]
    install.ensure_dependencies()
    assert len(attempts) == 1


def test_yaml_values_are_not_shadowed_by_new_env_defaults(tmp_path):
    from scripts.install import configure
    from ruamel.yaml import YAML
    (tmp_path / "config.yaml").write_text('platforms:\n  messenger:\n    host: 192.0.2.10\n    port: 9999\n    extra:\n      webhook_secret: existing-secret\n', encoding="utf-8")
    configure(tmp_path, environ={})
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert 'MESSENGER_PORT="9999"' in env
    assert 'MESSENGER_HOST="192.0.2.10"' in env
    assert 'MESSENGER_WEBHOOK_SECRET="existing-secret"' in env
    config = YAML().load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert "host" not in config["platforms"]["messenger"]["extra"]


def test_write_failure_restores_first_file(tmp_path, monkeypatch):
    from scripts import install
    (tmp_path / ".env").write_bytes(b"KEEP=1\n")
    (tmp_path / "config.yaml").write_bytes(b"model: existing\n")
    original_write = install._atomic_write
    def write(path, content):
        if path.name == "config.yaml":
            raise OSError("simulated failure")
        original_write(path, content)
    monkeypatch.setattr(install, "_atomic_write", write)
    with pytest.raises(OSError):
        install.configure(tmp_path, environ={})
    assert (tmp_path / ".env").read_bytes() == b"KEEP=1\n"
    assert (tmp_path / "config.yaml").read_bytes() == b"model: existing\n"
