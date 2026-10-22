"""Install prerequisites and merge Messenger settings into a Hermes home.

Invoked with the Hermes runtime by setup.sh or setup.ps1. Does not restart Hermes.
"""
import argparse
from datetime import datetime, timezone
import importlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile


def default_home(environ=None, platform=None, user_home=None):
    environ = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    user_home = Path.home() if user_home is None else Path(user_home)
    if environ.get("HERMES_HOME"):
        return Path(environ["HERMES_HOME"]).expanduser()
    if platform == "win32":
        return Path(environ.get("LOCALAPPDATA", user_home / "AppData" / "Local")) / "hermes"
    return user_home / ".hermes"


def ensure_dependencies():
    for module, requirement in (("aiohttp", "aiohttp>=3.9,<4"), ("ruamel.yaml", "ruamel.yaml>=0.18,<0.20")):
        try:
            importlib.import_module(module)
        except ModuleNotFoundError:
            print(f"Installing {requirement} into {sys.executable}")
            subprocess.run([sys.executable, "-m", "pip", "install", requirement], check=True)
            importlib.invalidate_caches()
            importlib.import_module(module)


def _mapping(parent, key):
    from collections.abc import MutableMapping
    if key not in parent or parent[key] is None:
        from ruamel.yaml.comments import CommentedMap
        parent[key] = CommentedMap()
    if not isinstance(parent[key], MutableMapping):
        raise ValueError(f"config.yaml: {key} must be a mapping; no files changed")
    return parent[key]


def _config_content(original):
    from collections.abc import MutableMapping, MutableSequence
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap, CommentedSeq
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.allow_duplicate_keys = False
    try:
        config = yaml.load(original.decode("utf-8-sig"))
    except Exception as exc:
        raise ValueError("config.yaml is invalid YAML; no files changed") from exc
    if config is None:
        config = CommentedMap()
    if not isinstance(config, MutableMapping):
        raise ValueError("config.yaml must be a mapping; no files changed")
    before = io.StringIO()
    yaml.dump(config, before)
    plugins = _mapping(config, "plugins")
    if "enabled" not in plugins or plugins["enabled"] is None:
        plugins["enabled"] = CommentedSeq()
    if not isinstance(plugins["enabled"], MutableSequence):
        raise ValueError("config.yaml: plugins.enabled must be a list; no files changed")
    if "messenger" not in plugins["enabled"]:
        plugins["enabled"].append("messenger")
    messenger = _mapping(_mapping(config, "platforms"), "messenger")
    messenger.setdefault("enabled", True)
    extra = _mapping(messenger, "extra")
    for key, value in {"host": "0.0.0.0", "port": 8788, "capacity": 1000,
                       "retention_seconds": 604800, "timeout": 20, "processing_timeout": 600}.items():
        if key not in messenger:
            extra.setdefault(key, value)
    output = io.StringIO()
    yaml.dump(config, output)
    # Do not rewrite merely to normalize YAML formatting on a second run.
    content = original if before.getvalue() == output.getvalue() else output.getvalue().encode("utf-8")
    return content, {**messenger, **extra}


def _env_content(original, environ, platform_values):
    text = original.decode("utf-8-sig")
    keys = set(re.findall(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", text, re.MULTILINE))
    defaults = {
        "MANYCHAT_API_TOKEN": "",
        "MESSENGER_WEBHOOK_SECRET": None,
        "MESSENGER_ALLOWED_USERS": "",
        "MESSENGER_ALLOW_ALL_USERS": "false",
        "MESSENGER_HOST": "0.0.0.0",
        "MESSENGER_PORT": "8788",
        "MESSENGER_CAPACITY": "1000",
        "MESSENGER_RETENTION_SECONDS": "604800",
        "MESSENGER_API_TIMEOUT": "20",
        "MESSENGER_PROCESSING_TIMEOUT": "600",
        "MESSENGER_DATABASE": "",
    }
    lines = []
    config_keys = {"MANYCHAT_API_TOKEN": "token", "MESSENGER_WEBHOOK_SECRET": "webhook_secret",
                   "MESSENGER_HOST": "host", "MESSENGER_PORT": "port", "MESSENGER_CAPACITY": "capacity",
                   "MESSENGER_RETENTION_SECONDS": "retention_seconds", "MESSENGER_API_TIMEOUT": "timeout",
                   "MESSENGER_PROCESSING_TIMEOUT": "processing_timeout", "MESSENGER_DATABASE": "database"}
    for key, default in defaults.items():
        if key in keys:
            continue
        configured = platform_values.get(config_keys.get(key))
        value = environ.get(key, configured if configured is not None else default)
        if value is None:
            value = secrets.token_urlsafe(32)
        lines.append(f"{key}={json.dumps(str(value), ensure_ascii=False)}")
    if not lines:
        return original
    newline = "\r\n" if b"\r\n" in original else "\n"
    suffix = ("" if not text or text.endswith(("\n", "\r")) else newline)
    suffix += newline + "# Messenger plugin (generated by setup)" + newline + newline.join(lines) + newline
    return original + suffix.encode("utf-8")


def _atomic_write(path, content):
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def configure(home, environ=None):
    environ = os.environ if environ is None else environ
    home = Path(home).expanduser().resolve()
    env_path, config_path = home / ".env", home / "config.yaml"
    for path in (env_path, config_path):
        if path.is_symlink():
            raise ValueError(f"Refusing to replace symlink: {path}")
    env_before = env_path.read_bytes() if env_path.exists() else b""
    config_before = config_path.read_bytes() if config_path.exists() else b""
    # Validate both files before creating backups or changing either file.
    config_after, platform_values = _config_content(config_before)
    env_after = _env_content(env_before, environ, platform_values)
    edits = [(path, before, after) for path, before, after in (
        (env_path, env_before, env_after), (config_path, config_before, config_after)
    ) if before != after]
    result = {"changed": [], "backups": []}
    if not edits:
        return result
    home.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for path, before, after in edits:
        if path.exists():
            backup = path.with_name(path.name + ".bak." + stamp)
            # Exclusive creation and owner-only mode also protect secret backups.
            descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(before)
            result["backups"].append(str(backup))
    written = []
    try:
        for path, before, after in edits:
            existed = path.exists()
            _atomic_write(path, after)
            written.append((path, before, existed))
            result["changed"].append(str(path))
    except OSError:
        for path, before, existed in reversed(written):
            if existed:
                _atomic_write(path, before)
            else:
                path.unlink()
        raise
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", type=Path, default=None)
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("Python 3.11+ from the Hermes runtime is required")
    home = args.hermes_home or default_home()
    print(f"Hermes Python: {sys.executable}")
    print(f"Hermes home: {home}")
    try:
        ensure_dependencies()
        result = configure(home)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        # Do not echo YAML errors or values containing credentials.
        print(f"Setup failed ({type(exc).__name__}); check file permissions, YAML structure and Python dependencies. No credential values are printed.", file=sys.stderr)
        return 1
    for backup in result["backups"]:
        print(f"Backup: {backup}")
    for path in result["changed"]:
        print(f"Updated: {path}")
    if not result["changed"]:
        print("Settings already present; no file changes.")
    print("Fill MANYCHAT_API_TOKEN and allowed users in .env; copy the webhook secret into ManyChat. Existing values are preserved. Restart Hermes when ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
