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
    for module, requirement in (("aiohttp", "aiohttp>=3.9,<4"), ("ruamel.yaml", "ruamel.yaml>=0.18,<0.20"), ("dotenv", "python-dotenv>=1,<2")):
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


def _config_content(original, environ):
    from collections.abc import MutableMapping, MutableSequence
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap, CommentedSeq
    import importlib.util
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
    if plugins.get("enabled") is None:
        plugins["enabled"] = CommentedSeq()
    if not isinstance(plugins["enabled"], MutableSequence):
        raise ValueError("config.yaml: plugins.enabled must be a list")
    if "messenger" not in plugins["enabled"]:
        plugins["enabled"].append("messenger")
    platforms = _mapping(config, "platforms")
    messenger = _mapping(platforms, "messenger")
    messenger.setdefault("enabled", True)
    extra = _mapping(messenger, "extra")
    for container in (messenger, extra):
        for key in ("host", "port", "webhook_secret"):
            container.pop(key, None)
    for key,value in {"capacity":1000,"retention_seconds":604800,"timeout":20,"processing_timeout":600}.items():
        if key not in messenger:
            extra.setdefault(key,value)
    ingress = _mapping(platforms,"messenger_ingress")
    ingress["enabled"] = True
    webhook = _mapping(platforms,"webhook")
    webhook["enabled"] = True
    web_extra = _mapping(webhook,"extra")
    web_extra["port"] = int(environ["WEBHOOK_PORT"])
    web_extra.setdefault("host","0.0.0.0")
    routes = _mapping(web_extra,"routes")
    existing_route = routes.get("manychat",{})
    if not isinstance(existing_route,MutableMapping):
        raise ValueError("Existing manychat route must be a mapping")
    if existing_route and existing_route.get("deliver") != "messenger_ingress":
        raise ValueError("Existing manychat route conflicts; migrate or rename it first")
    secret = environ["MESSENGER_HERMES_WEBHOOK_SECRET"]
    spec = importlib.util.spec_from_file_location("messenger_route_configuration",Path(__file__).resolve().parents[1]/"webhook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    route = module.manychat_route()
    route["secret"] = str(secret)
    routes["manychat"] = route
    output = io.StringIO()
    yaml.dump(config,output)
    content = original if before.getvalue()==output.getvalue() else output.getvalue().encode("utf-8")
    return content,{**messenger,**extra,"hermes_webhook_secret":str(secret)}


def parse_env(content):
    from dotenv.parser import parse_stream
    bindings = list(parse_stream(io.StringIO(content.decode("utf-8-sig"))))
    if any(binding.error for binding in bindings):
        raise ValueError("Invalid dotenv syntax")
    return bindings


def read_template(path):
    values = {}
    for binding in parse_env(Path(path).read_bytes()):
        if binding.key is None:
            continue
        if binding.value is None or binding.key in values:
            raise ValueError("Template needs unique KEY=value assignments")
        values[binding.key] = binding.value
    if not values.get("MESSENGER_HERMES_WEBHOOK_SECRET"):
        raise ValueError("Set the route secret in .env.example")
    if not 1 <= int(values.get("WEBHOOK_PORT", "0")) <= 65535:
        raise ValueError("Set WEBHOOK_PORT in .env.example")
    return values


def _env_content(original, values, platform_values=None):
    bindings = parse_env(original)
    newline = "\r\n" if b"\r\n" in original else "\n"
    seen = set()
    chunks = []
    retired = {"MESSENGER_HOST", "MESSENGER_PORT", "MESSENGER_WEBHOOK_SECRET"}
    for binding in bindings:
        key = binding.key
        if key in values:
            if key not in seen:
                chunks.append(f"{key}={json.dumps(values[key],ensure_ascii=False)}"+newline)
                seen.add(key)
        elif key not in retired:
            chunks.append(binding.original.string)
    text = "".join(chunks)
    missing = [key for key in values if key not in seen]
    if missing:
        if text and not text.endswith(("\n","\r")):
            text += newline
        text += newline + "# Messenger settings from .env.example" + newline
        text += "".join(f"{key}={json.dumps(values[key],ensure_ascii=False)}"+newline for key in missing)
    return text.encode("utf-8")


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


def configure(home, template_path=None):
    home = Path(home).expanduser().resolve()
    template_path = Path(template_path) if template_path else Path(__file__).resolve().parents[1] / ".env.example"
    values = read_template(template_path)
    env_path, config_path = home / ".env", home / "config.yaml"
    for path in (env_path, config_path):
        if path.is_symlink():
            raise ValueError(f"Refusing to replace symlink: {path}")
    env_before = env_path.read_bytes() if env_path.exists() else b""
    config_before = config_path.read_bytes() if config_path.exists() else b""
    config_after, _ = _config_content(config_before, values)
    env_after = _env_content(env_before, values)
    from ruamel.yaml import YAML
    state_path = home / "plugin-data" / "messenger" / "setup-state.json"
    if state_path.is_symlink() or not state_path.resolve().is_relative_to(home):
        raise ValueError("Setup state must not be a symlink")
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        old = YAML().load(config_before.decode("utf-8-sig")) or {}
        webhook = (old.get("platforms") or {}).get("webhook") or {}
        env_old = {b.key:b.value for b in parse_env(env_before) if b.key}
        state = {"version":1,"webhook_existed":bool(webhook),"shared_before":{},
                 "webhook_port_env_before":{"exists":"WEBHOOK_PORT" in env_old,"value":env_old.get("WEBHOOK_PORT")},"env_keys":[]}
        for key in ("enabled","extra.host","extra.port"):
            parent = webhook if key=="enabled" else webhook.get("extra",{})
            leaf = key.split(".")[-1]
            state["shared_before"][key] = {"exists":leaf in parent,"value":parent.get(leaf)}
    installed = YAML().load(config_after.decode("utf-8"))["platforms"]["webhook"]
    state["shared_installed"] = {"enabled":installed.get("enabled"),"extra.host":installed["extra"].get("host"),"extra.port":installed["extra"]["port"]}
    state["env_keys"] = sorted(set(state["env_keys"]) | set(values))
    state["webhook_port_env_installed"] = values["WEBHOOK_PORT"]
    state_bytes = (json.dumps(state,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
    state_before = state_path.read_bytes() if state_path.exists() else b""
    return commit_changes(home,[(env_path,env_before,env_after),(config_path,config_before,config_after),(state_path,state_before,state_bytes)])


def commit_changes(home, candidates):
    edits = [(path,before,after) for path,before,after in candidates if before != after]
    result = {"changed": [], "backups": []}
    if not edits:
        return result
    home.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for path, before, after in edits:
        path.parent.mkdir(parents=True, exist_ok=True)
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
    except (OSError, ValueError, ImportError, subprocess.CalledProcessError) as exc:
        # Do not echo YAML errors or values containing credentials.
        print(f"Setup failed ({type(exc).__name__}); check file permissions, YAML structure and Python dependencies. No credential values are printed.", file=sys.stderr)
        return 1
    for backup in result["backups"]:
        print(f"Backup: {backup}")
    for path in result["changed"]:
        print(f"Updated: {path}")
    if not result["changed"]:
        print("Settings already present; no file changes.")
    print("Settings synchronized from .env.example. Edit that file and rerun setup to change values. Configure the same route secret in ManyChat. Restart Hermes when ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
