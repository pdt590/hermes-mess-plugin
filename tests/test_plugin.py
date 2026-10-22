import importlib
from pathlib import Path


def test_real_plugin_context_and_registry(plugin):
    from hermes_cli.plugins import PluginContext, PluginManager
    from hermes_cli.plugins_manifest import parse_manifest_file
    from gateway.platform_registry import platform_registry
    root = Path(__file__).resolve().parents[1]
    manifest = parse_manifest_file(root / "plugin.yaml", root, "user", "")
    manager = PluginManager()
    ctx = PluginContext(manifest, manager)
    plugin.register(ctx)
    entry = platform_registry.get("messenger")
    assert entry.plugin_name == "messenger"
    assert entry.trusted_inbound is False
    assert entry.allow_all_env == "MESSENGER_ALLOW_ALL_USERS"


def test_profile_scoped_settings(plugin, monkeypatch, tmp_path):
    from gateway.config import PlatformConfig
    from gateway.platforms import _shared
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    settings_class = importlib.import_module(plugin.__name__ + ".config").Settings
    monkeypatch.setenv("MANYCHAT_API_TOKEN", "other-profile-token")
    # Model the scoped secret boundary, retaining actual Settings and resolver code.
    monkeypatch.setattr(_shared, "get_scoped_secret", lambda name, default=None: default)
    handle = set_hermes_home_override(tmp_path)
    try:
        settings = settings_class.from_platform(PlatformConfig(extra={"token": "own-token", "webhook_secret": "own-secret"}))
        assert settings.token == "own-token"
        assert settings.database == tmp_path / "plugin-data" / "messenger" / "inbox.sqlite"
        monkeypatch.setattr(_shared, "get_scoped_secret", lambda name, default=None: "explicit-token" if name == "MANYCHAT_API_TOKEN" else default)
        assert settings_class.from_platform(PlatformConfig(extra={"token": "own-token", "webhook_secret": "s"})).token == "explicit-token"
    finally:
        reset_hermes_home_override(handle)


def test_real_plugin_manager_load(plugin):
    from hermes_cli.plugins import PluginManager
    from hermes_cli.plugins_manifest import parse_manifest_file
    from gateway.platform_registry import platform_registry
    root = Path(__file__).resolve().parents[1]
    manifest = parse_manifest_file(root / "plugin.yaml", root, "user", "")
    manager = PluginManager()
    manager._load_plugin(manifest)
    loaded = manager._plugins["messenger"]
    assert loaded.enabled and not loaded.error
    assert platform_registry.get("messenger").plugin_name == "messenger"


def test_registry_creates_adapter_with_yaml_only_secrets(plugin, tmp_path):
    from gateway.platform_registry import platform_registry
    from gateway.config import PlatformConfig
    adapter = platform_registry.create_adapter("messenger", PlatformConfig(extra={"token": "yaml-token", "webhook_secret": "yaml-secret", "database": str(tmp_path / "db")}))
    assert adapter is not None
