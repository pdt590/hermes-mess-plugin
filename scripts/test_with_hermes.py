"""Run tests using an installed Hermes Python, with an isolated home.

Example: <hermes-venv-python> scripts/test_with_hermes.py <hermes-source>
Install requirements-dev.txt into that runtime, or use this project's .venv
as a fallback for pure Python test dependencies (not compiled extensions).
"""
import os
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root.parents[1] / "hermes-agent"
if not (source / "gateway" / "platforms" / "base.py").is_file():
    raise SystemExit("Provide the Hermes source directory as the first argument")
sys.path[:0] = [str(root), str(source)]
# Existing runtime dependencies take priority over fallback test packages.
fallback = root / ".venv" / "Lib" / "site-packages"
if fallback.is_dir():
    sys.path.append(str(fallback))
os.chdir(root)
with tempfile.TemporaryDirectory(prefix="messenger-hermes-test-") as home:
    os.environ["HERMES_HOME"] = home
    # Ignore production credentials/config in the caller's shell.
    for key in list(os.environ):
        if key.startswith("MESSENGER_") or key == "MANYCHAT_API_TOKEN":
            os.environ.pop(key)
    import gateway.platforms.base  # fail loudly if runtime is unavailable
    import pytest
    raise SystemExit(pytest.main(["-q", "--tb=short", *sys.argv[2:]]))
