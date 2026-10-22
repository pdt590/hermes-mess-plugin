import json
import contextlib
from pathlib import Path
import pytest


@pytest.fixture
def template(tmp_path):
    path = tmp_path / '.env.example'
    path.write_text('MANYCHAT_API_TOKEN="template-token"\nMESSENGER_HERMES_WEBHOOK_SECRET="template-secret"\nWEBHOOK_PORT=8644\nMESSENGER_ALLOW_ALL_USERS=false\n', encoding='utf-8')
    return path


def test_only_template_values_and_idempotency(tmp_path, template, monkeypatch):
    from scripts.install import configure
    home = tmp_path / 'home'
    home.mkdir()
    (home / '.env').write_text('OTHER=preserve\nMANYCHAT_API_TOKEN=old\n', encoding='utf-8')
    monkeypatch.setenv('MANYCHAT_API_TOKEN', 'process-token-must-not-be-used')
    configure(home, template_path=template)
    text = (home / '.env').read_text()
    assert 'MANYCHAT_API_TOKEN="template-token"' in text
    assert 'OTHER=preserve' in text and 'process-token' not in text
    assert 'MESSENGER_ALLOWED_USERS=' not in text
    assert configure(home, template_path=template)['changed'] == []


def test_uninstall_removes_plugin_but_preserves_shared_settings(tmp_path, template):
    from scripts.install import configure
    from scripts.uninstall import uninstall
    from ruamel.yaml import YAML
    home = tmp_path / 'home'
    home.mkdir()
    (home / '.env').write_text('OTHER=keep\nWEBHOOK_PORT=9999\n', encoding='utf-8')
    (home / 'config.yaml').write_text('plugins:\n  enabled: [other]\nplatforms:\n  webhook:\n    enabled: true\n    extra:\n      port: 9999\n      routes:\n        github: {prompt: keep}\n', encoding='utf-8')
    plugin = home / 'plugins' / 'messenger'
    plugin.mkdir(parents=True)
    (plugin / 'plugin.yaml').write_text('name: messenger\n')
    configure(home, template_path=template)
    data = home / 'plugin-data' / 'messenger'
    for name in ('inbox.sqlite', 'inbox.sqlite-wal', 'inbox.sqlite-shm'):
        (data / name).write_bytes(b'conversation')
    result = uninstall(home, template_path=template)
    config = YAML().load((home / 'config.yaml').read_text())
    assert config['plugins']['enabled'] == ['other']
    assert 'messenger' not in config['platforms'] and 'messenger_ingress' not in config['platforms']
    assert config['platforms']['webhook']['extra']['routes'] == {'github': {'prompt': 'keep'}}
    assert config['platforms']['webhook']['extra']['port'] == 9999
    assert 'WEBHOOK_PORT="9999"' in (home / '.env').read_text()
    assert 'MANYCHAT_API_TOKEN=' not in (home / '.env').read_text()
    assert not plugin.exists() and result['plugin_removed']
    assert not (home / 'plugin-data' / 'messenger').exists()
    assert not list((home / 'plugin-backups').iterdir())
    assert uninstall(home, template_path=template)['changed'] == []


def test_invalid_yaml_does_not_change_env(tmp_path, template):
    from scripts.install import configure
    (tmp_path / 'config.yaml').write_text('plugins: []')
    (tmp_path / '.env').write_bytes(b'OTHER=keep\r\n')
    with pytest.raises(ValueError):
        configure(tmp_path, template_path=template)
    assert (tmp_path / '.env').read_bytes() == b'OTHER=keep\r\n'


def test_uninstall_retains_new_shared_overrides(tmp_path, template):
    from scripts.install import configure
    from scripts.uninstall import uninstall
    from ruamel.yaml import YAML
    configure(tmp_path, template_path=template)
    yaml = YAML()
    config = yaml.load((tmp_path / 'config.yaml').read_text())
    config['platforms']['webhook']['extra']['port'] = 9000
    config['platforms']['webhook']['extra']['routes']['other'] = {'prompt':'keep'}
    with (tmp_path / 'config.yaml').open('w') as stream:
        yaml.dump(config, stream)
    uninstall(tmp_path, template_path=template)
    config = yaml.load((tmp_path / 'config.yaml').read_text())
    assert config['platforms']['webhook']['extra']['port'] == 9000
    assert config['platforms']['webhook']['enabled'] is True


def test_template_does_not_expand_process_environment(tmp_path, template, monkeypatch):
    from scripts.install import configure
    monkeypatch.setenv('PRIVATE_VALUE', 'must-not-expand')
    template.write_text(template.read_text()+'MESSENGER_CUSTOM="${PRIVATE_VALUE}"\n')
    configure(tmp_path / 'home', template_path=template)
    assert '${PRIVATE_VALUE}' in (tmp_path / 'home' / '.env').read_text()


def test_uninstall_refuses_another_plugin_before_writing(tmp_path, template):
    from scripts.install import configure
    from scripts.uninstall import uninstall
    configure(tmp_path,template_path=template)
    plugin=tmp_path/'plugins'/'messenger'
    plugin.mkdir(parents=True)
    (plugin/'plugin.yaml').write_text('name: another-plugin\n')
    before=(tmp_path/'.env').read_bytes(),(tmp_path/'config.yaml').read_bytes()
    with pytest.raises(ValueError):
        uninstall(tmp_path,template_path=template)
    assert ((tmp_path/'.env').read_bytes(),(tmp_path/'config.yaml').read_bytes())==before
    assert plugin.exists()


def test_uninstall_archive_failure_rolls_back_configuration(tmp_path,template,monkeypatch):
    from scripts.install import configure
    from scripts.uninstall import uninstall
    configure(tmp_path,template_path=template)
    plugin=tmp_path/'plugins'/'messenger'
    plugin.mkdir(parents=True)
    (plugin/'plugin.yaml').write_text('name: messenger\n')
    before=(tmp_path/'.env').read_bytes(),(tmp_path/'config.yaml').read_bytes()
    rename=Path.rename
    def fail_move(path,target):
        if path==plugin or path.is_relative_to(plugin):
            raise PermissionError('simulated locked plugin')
        return rename(path,target)
    monkeypatch.setattr(Path,'rename',fail_move)
    with pytest.raises(PermissionError):
        uninstall(tmp_path,template_path=template)
    assert ((tmp_path/'.env').read_bytes(),(tmp_path/'config.yaml').read_bytes())==before
    assert plugin.exists()


def test_uninstall_removes_fresh_shared_listener_settings(tmp_path,template):
    from scripts.install import configure
    from scripts.uninstall import uninstall
    from ruamel.yaml import YAML
    configure(tmp_path,template_path=template)
    uninstall(tmp_path,template_path=template)
    config=YAML().load((tmp_path/'config.yaml').read_text())
    assert 'webhook' not in config['platforms']
    assert 'WEBHOOK_PORT=' not in (tmp_path/'.env').read_text()


def test_uninstall_deletes_contents_if_root_rename_is_locked(tmp_path,template,monkeypatch):
    from scripts.install import configure
    from scripts.uninstall import uninstall
    configure(tmp_path,template_path=template)
    plugin=tmp_path/'plugins'/'messenger'
    plugin.mkdir(parents=True)
    (plugin/'plugin.yaml').write_text('name: messenger\n')
    (plugin/'adapter.py').write_text('# plugin source\n')
    rename=Path.rename
    def locked_root(path,target):
        if path==plugin:
            raise PermissionError('simulated active working directory')
        return rename(path,target)
    monkeypatch.setattr(Path,'rename',locked_root)
    result=uninstall(tmp_path,template_path=template)
    assert result['plugin_removed']
    assert not plugin.exists()
    assert not list((tmp_path/'plugin-backups').iterdir())


def test_uninstall_deletes_verified_custom_database(tmp_path, template):
    import sqlite3
    from scripts.install import configure
    from scripts.uninstall import uninstall
    home = tmp_path / 'home'
    configure(home, template_path=template)
    database = tmp_path / 'custom.sqlite'
    with contextlib.closing(sqlite3.connect(database)) as db:
        db.execute('CREATE TABLE inbox (id, upstream_key, digest, payload, state, created, updated, error)')
    with (home / '.env').open('a') as stream:
        stream.write('MESSENGER_DATABASE='+str(database)+'\n')
    Path(str(database)+'-journal').write_bytes(b'')
    unrelated = tmp_path / 'state.db'
    unrelated.write_bytes(b'preserve')
    uninstall(home, template_path=template)
    assert not database.exists()
    assert not Path(str(database)+'-journal').exists()
    assert unrelated.read_bytes() == b'preserve'


def test_uninstall_refuses_unrelated_database_before_changes(tmp_path, template):
    import sqlite3
    from scripts.install import configure
    from scripts.uninstall import uninstall
    configure(tmp_path, template_path=template)
    database = tmp_path / 'state.db'
    with contextlib.closing(sqlite3.connect(database)) as db:
        db.execute('CREATE TABLE sessions (id)')
    with (tmp_path / '.env').open('a') as stream:
        stream.write('MESSENGER_DATABASE='+str(database)+'\n')
    before = (tmp_path / '.env').read_bytes(), (tmp_path / 'config.yaml').read_bytes()
    with pytest.raises(ValueError):
        uninstall(tmp_path, template_path=template)
    assert database.exists()
    assert before == ((tmp_path / '.env').read_bytes(), (tmp_path / 'config.yaml').read_bytes())
