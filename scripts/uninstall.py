"""Permanently remove the Messenger plugin, its configuration and conversation database."""
import argparse
import io
import json
import os
from pathlib import Path
import sys
import contextlib
import shutil
import sqlite3

try:
    from .install import default_home, parse_env, commit_changes, _atomic_write
except ImportError:
    from install import default_home, parse_env, commit_changes, _atomic_write


def _archive_plugin(plugin, destination):
    """Archive a checked directory, including Windows' locked-working-directory case."""
    try:
        plugin.rename(destination)
        return
    except PermissionError:
        pass
    # The caller already verified both absolute roots stay inside Hermes home.
    # Move directory entries themselves, never follow links into another tree.
    destination.mkdir()
    moved = []
    try:
        for entry in list(plugin.iterdir()):
            target = destination / entry.name
            if entry.parent.resolve() != plugin.resolve() or target.parent.resolve() != destination.resolve():
                raise ValueError('Archive entry leaves checked roots')
            entry.rename(target)
            moved.append(entry.name)
    except Exception:
        for name in reversed(moved):
            (destination / name).rename(plugin / name)
        destination.rmdir()
        raise
    with contextlib.suppress(OSError):
        plugin.rmdir()  # a locked empty directory may remain, with no plugin manifest


def _restore_plugin(plugin, backup):
    if not plugin.exists():
        backup.rename(plugin)
        return
    if any(plugin.iterdir()):
        raise OSError('Cannot restore archive into a nonempty plugin directory')
    for entry in list(backup.iterdir()):
        entry.rename(plugin / entry.name)
    backup.rmdir()


def uninstall(home, template_path=None):
    from ruamel.yaml import YAML
    from collections.abc import MutableMapping
    home = Path(home).expanduser().resolve()
    env_path, config_path = home / '.env', home / 'config.yaml'
    state_path = home / 'plugin-data' / 'messenger' / 'setup-state.json'
    for path in (env_path, config_path, state_path):
        if path.is_symlink() or not path.resolve().is_relative_to(home):
            raise ValueError('Configuration path leaves the selected Hermes home')
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    env_before = env_path.read_bytes() if env_path.exists() else b''
    config_before = config_path.read_bytes() if config_path.exists() else b''
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.allow_duplicate_keys = False
    config = yaml.load(config_before.decode('utf-8-sig')) if config_before else {}
    if config is None:
        config = {}
    if not isinstance(config, MutableMapping):
        raise ValueError('config.yaml must be a mapping')
    # Validate the relevant shapes before any files are written or moved.
    plugins = config.get('plugins') or {}
    platforms = config.get('platforms') or {}
    if not isinstance(plugins, MutableMapping) or not isinstance(platforms, MutableMapping):
        raise ValueError('Invalid plugins/platforms mapping')
    data_dir = home / 'plugin-data' / 'messenger'
    messenger = platforms.get('messenger') or {}
    database_value = (messenger.get('extra') or {}).get('database')
    # Read the installed profile before removing its environment/configuration.
    for binding in parse_env(env_before):
        if binding.key == 'MESSENGER_DATABASE' and binding.value:
            database_value = binding.value
    database_files = []
    if database_value:
        database = Path(database_value).expanduser()
        if not database.is_absolute():
            raise ValueError('Custom database must use an absolute path for uninstall')
        if not database.resolve().is_relative_to(data_dir.resolve()):
            # Custom locations authorize one verified Messenger SQLite file only,
            # never a directory tree or the shared Hermes session database.
            database_files = [Path(str(database)+suffix) for suffix in ('','-wal','-shm','-journal')]
            if any(path.is_symlink() or path.is_dir() for path in database_files):
                raise ValueError('Custom database paths must be regular files')
            if database.is_file():
                with contextlib.closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True)) as db:
                    columns = {row[1] for row in db.execute('PRAGMA table_info(inbox)')}
                    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if tables != {'inbox'} or not {'id','upstream_key','digest','payload','state','created','updated','error'} <= columns:
                    raise ValueError('Custom database is not a Messenger inbox')
            elif any(path.exists() for path in database_files):
                raise ValueError('Cannot verify orphaned custom database sidecars')
    if data_dir.is_symlink() or not data_dir.resolve().is_relative_to(home):
        raise ValueError('Messenger data path leaves the selected Hermes home')
    for key in ('enabled', 'disabled'):
        if key in plugins:
            if not isinstance(plugins[key], list):
                raise ValueError('Invalid plugin enablement list')
            plugins[key][:] = [v for v in plugins[key] if v != 'messenger']
    entries = plugins.get('entries')
    if entries is not None:
        if not isinstance(entries, MutableMapping):
            raise ValueError('Invalid plugin entries')
        entries.pop('messenger', None)
    platforms.pop('messenger', None)
    platforms.pop('messenger_ingress', None)
    webhook = platforms.get('webhook') or {}
    if not isinstance(webhook, MutableMapping):
        raise ValueError('Invalid webhook config')
    extra = webhook.get('extra') or {}
    if not isinstance(extra, MutableMapping):
        raise ValueError('Invalid webhook extra config')
    routes = extra.get('routes') or {}
    if not isinstance(routes, MutableMapping):
        raise ValueError('Invalid webhook routes')
    if isinstance(routes.get('manychat'), dict) and routes['manychat'].get('deliver') == 'messenger_ingress':
        routes.pop('manychat')
    other_routes = bool(routes)
    for key, previous in state.get('shared_before', {}).items():
        parent = webhook if key == 'enabled' else extra
        leaf = key.split('.')[-1]
        if parent.get(leaf) != state.get('shared_installed', {}).get(key):
            continue  # an operator changed this after installation
        if previous['exists']:
            parent[leaf] = previous['value']
        elif not other_routes:
            parent.pop(leaf, None)
    if 'routes' in extra and not routes:
        extra.pop('routes')
    if 'extra' in webhook and not extra:
        webhook.pop('extra')
    if 'webhook' in platforms and not webhook:
        platforms.pop('webhook')
    out = io.StringIO()
    yaml.dump(config, out)
    # Compare normalized YAML to avoid formatting-only changes.
    original = yaml.load(config_before.decode('utf-8-sig')) if config_before else {}
    old_dump = io.StringIO()
    yaml.dump(original or {}, old_dump)
    config_after = config_before if old_dump.getvalue() == out.getvalue() else out.getvalue().encode('utf-8')
    keys = set(state.get('env_keys', []))
    if template_path is None:
        template_path = Path(__file__).resolve().parents[1] / '.env.example'
    if Path(template_path).is_file():
        keys.update(b.key for b in parse_env(Path(template_path).read_bytes()) if b.key)
    chunks = []
    newline = '\r\n' if b'\r\n' in env_before else '\n'
    for binding in parse_env(env_before):
        key = binding.key
        if key == 'WEBHOOK_PORT':
            before = state.get('webhook_port_env_before')
            if before is not None and binding.value == state.get('webhook_port_env_installed'):
                if before['exists']:
                    chunks.append('WEBHOOK_PORT='+json.dumps(before['value'])+newline)
                elif other_routes:
                    chunks.append(binding.original.string)
            else:
                chunks.append(binding.original.string)
        elif key not in keys and not (key and (key.startswith('MESSENGER_') or key == 'MANYCHAT_API_TOKEN')):
            chunks.append(binding.original.string)
    env_after = ''.join(chunks).encode('utf-8')
    plugin = home / 'plugins' / 'messenger'
    backup_root = home / 'plugin-backups'
    plugin_backup = backup_root / 'messenger-uninstalling'
    if not plugin_backup.resolve().is_relative_to(home) or plugin_backup.is_symlink():
        raise ValueError('Plugin staging path leaves the selected Hermes home')
    if plugin_backup.exists() and plugin.exists():
        raise ValueError('Previous uninstall staging directory needs cleanup before reinstall removal')
    if plugin_backup.exists():
        manifest = plugin_backup / 'plugin.yaml'
        if not manifest.is_file() or (yaml.load(manifest.read_text(encoding='utf-8-sig')) or {}).get('name') != 'messenger':
            raise ValueError('Uninstall staging directory is not the Messenger plugin')
    if plugin.exists() or plugin.is_symlink():
        if plugin.is_symlink() or not plugin.resolve().is_relative_to(home) or not backup_root.resolve().is_relative_to(home):
            raise ValueError('Plugin/archive path leaves the selected Hermes home')
        manifest = plugin / 'plugin.yaml'
        if not manifest.is_file() or (yaml.load(manifest.read_text(encoding='utf-8-sig')) or {}).get('name') != 'messenger':
            raise ValueError('Target directory is not the Messenger plugin')
    result = commit_changes(home, [(env_path,env_before,env_after),(config_path,config_before,config_after)])
    try:
        if plugin.exists():
            backup_root.mkdir(parents=True, exist_ok=True)
            if Path.cwd().resolve().is_relative_to(plugin.resolve()):
                os.chdir(home)  # do not keep Python's working directory inside the plugin
            _archive_plugin(plugin, plugin_backup)
    except OSError:
        # Restore settings if staging cannot finish, before destructive cleanup.
        for path, content in ((env_path,env_before),(config_path,config_before)):
            if str(path) in result['changed']:
                _atomic_write(path,content)
        if plugin_backup and plugin_backup.exists():
            _restore_plugin(plugin, plugin_backup)
        raise
    # Destructive phase: paths were validated before configuration changes.
    # Do not restore enabled settings after partial deletion.
    for path in database_files:
        path.unlink(missing_ok=True)
    if data_dir.exists():
        shutil.rmtree(data_dir)
    if plugin_backup and plugin_backup.exists():
        shutil.rmtree(plugin_backup)
    if plugin.exists() and not any(plugin.iterdir()):
        plugin.rmdir()
    result['plugin_removed'] = not plugin.exists()
    result['database_removed'] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hermes-home', type=Path)
    args = parser.parse_args()
    try:
        result = uninstall(args.hermes_home or default_home())
    except Exception:
        print('Uninstall incomplete. Stop Hermes, release file locks and inspect remaining files/staging and paths/YAML. Some files may already have been deleted. Credential values are not printed.', file=sys.stderr)
        return 1
    for backup in result['backups']:
        print('Config backup:',backup)
    print('Messenger plugin, settings and conversation database permanently deleted. Shared Python libraries retained. Restart Hermes to unload the running plugin.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
