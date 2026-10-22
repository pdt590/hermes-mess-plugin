from pathlib import Path
import pytest


@pytest.fixture
def template(tmp_path):
    path = tmp_path / 'template.env'
    path.write_text('MANYCHAT_API_TOKEN="template-token"\nMESSENGER_HERMES_WEBHOOK_SECRET="template-secret"\nWEBHOOK_PORT=8644\nMESSENGER_ALLOWED_USERS=""\nMESSENGER_ALLOW_ALL_USERS=false\nMESSENGER_API_TIMEOUT=20\n', encoding='utf-8')
    return path


def test_install_merges_without_overwriting_unrelated_settings(tmp_path, template):
    from scripts.install import configure
    from ruamel.yaml import YAML
    home = tmp_path / 'home'
    home.mkdir()
    original_env = '# keep me\nOTHER_TOKEN="keep"\nMANYCHAT_API_TOKEN="old"\nMESSENGER_PORT=9999\n'
    original_config = '# owner comment\nmodel: existing-model\nplugins:\n  enabled: [other]\nplatforms:\n  telegram:\n    enabled: true\n'
    (home/'.env').write_text(original_env)
    (home/'config.yaml').write_text(original_config)
    result = configure(home, template_path=template)
    text = (home/'.env').read_text()
    assert 'OTHER_TOKEN="keep"' in text and '# keep me' in text
    assert 'MANYCHAT_API_TOKEN="template-token"' in text
    assert 'MESSENGER_PORT=' not in text
    config = YAML().load((home/'config.yaml').read_text())
    assert config['plugins']['enabled'] == ['other','messenger']
    assert config['platforms']['telegram']['enabled']
    assert config['model'] == 'existing-model'
    assert '# owner comment' in (home/'config.yaml').read_text()
    assert len(result['backups']) == 2
    assert sorted(Path(p).read_text() for p in result['backups']) == sorted([original_env,original_config])
    assert configure(home,template_path=template)['changed'] == []


@pytest.mark.parametrize('yaml', ['plugins: []','plugins:\n  enabled: nope','platforms: []','platforms:\n  messenger:\n    extra: wrong','plugins: [invalid','false','model: x\nmodel: y'])
def test_invalid_config_never_modifies_files(tmp_path, template, yaml):
    from scripts.install import configure
    (tmp_path/'.env').write_bytes(b'KEEP=1\r\n')
    (tmp_path/'config.yaml').write_text(yaml)
    with pytest.raises(ValueError):
        configure(tmp_path, template_path=template)
    assert (tmp_path/'.env').read_bytes() == b'KEEP=1\r\n'
    assert (tmp_path/'config.yaml').read_text() == yaml
    assert not list(tmp_path.glob('*.bak.*'))


def test_home_detection(tmp_path):
    from scripts.install import default_home
    assert default_home({'LOCALAPPDATA':str(tmp_path)},'win32',tmp_path/'user') == tmp_path/'hermes'
    assert default_home({},'linux',tmp_path/'user') == tmp_path/'user'/'.hermes'
    assert default_home({'HERMES_HOME':str(tmp_path/'override')},'linux',tmp_path) == tmp_path/'override'


def test_dependencies_install_only_missing(monkeypatch):
    from scripts import install
    attempts=[]
    def importer(name):
        if name=='aiohttp' and not attempts:
            raise ModuleNotFoundError(name)
    monkeypatch.setattr(install.importlib,'import_module',importer)
    monkeypatch.setattr(install.subprocess,'run',lambda args,**kw:attempts.append(args))
    install.ensure_dependencies()
    assert len(attempts)==1
    assert attempts[0][1:4]==['-m','pip','install']
    assert 'aiohttp>=3.9,<4' in attempts[0]
    install.ensure_dependencies()
    assert len(attempts)==1


def test_native_route_preserves_other_routes_and_uses_template(tmp_path,template):
    from scripts.install import configure
    from ruamel.yaml import YAML
    (tmp_path/'config.yaml').write_text('platforms:\n  webhook:\n    extra:\n      secret: other-global-secret\n      routes:\n        github: {prompt: keep}\n')
    configure(tmp_path,template_path=template)
    extra=YAML().load((tmp_path/'config.yaml').read_text())['platforms']['webhook']['extra']
    assert extra['secret']=='other-global-secret'
    assert extra['routes']['github']['prompt']=='keep'
    assert extra['routes']['manychat']['secret']=='template-secret'
    assert extra['port']==8644


def test_write_failure_restores_first_file(tmp_path,template,monkeypatch):
    from scripts import install
    (tmp_path/'.env').write_bytes(b'KEEP=1\n')
    (tmp_path/'config.yaml').write_bytes(b'model: existing\n')
    original=install._atomic_write
    def write(path,content):
        if path.name=='config.yaml':
            raise OSError('simulated failure')
        original(path,content)
    monkeypatch.setattr(install,'_atomic_write',write)
    with pytest.raises(OSError):
        install.configure(tmp_path,template_path=template)
    assert (tmp_path/'.env').read_bytes()==b'KEEP=1\n'
    assert (tmp_path/'config.yaml').read_bytes()==b'model: existing\n'
