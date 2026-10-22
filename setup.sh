#!/bin/sh
# Linux, macOS, or Git Bash on Windows. Always use the Hermes runtime.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${HERMES_HOME:-}" ]; then
    installer_home=$HERMES_HOME
else
    case "$(uname -s)" in
        MINGW*|MSYS*|CYGWIN*)
            installer_home="${LOCALAPPDATA:?LOCALAPPDATA is required}/hermes"
            ;;
        *) installer_home="$HOME/.hermes" ;;
    esac
fi
if command -v cygpath >/dev/null 2>&1; then
    installer_home=$(cygpath -u "$installer_home")
fi
installer_python=${HERMES_PYTHON:-}
if [ -z "$installer_python" ]; then
    for candidate in \
        "$installer_home/hermes-agent/venv/bin/python" \
        "$installer_home/hermes-agent/.venv/bin/python" \
        "$installer_home/venv/bin/python" \
        "$installer_home/.venv/bin/python" \
        "$installer_home/hermes-agent/venv/Scripts/python.exe" \
        "$installer_home/hermes-agent/.venv/Scripts/python.exe" \
        "$installer_home/venv/Scripts/python.exe"; do
        if [ -x "$candidate" ]; then
            installer_python=$candidate
            break
        fi
    done
fi
if [ -z "$installer_python" ]; then
    echo 'Hermes Python not found. Set HERMES_PYTHON to the Python executable used by Hermes.' >&2
    exit 1
fi
if command -v cygpath >/dev/null 2>&1; then
    installer_python=$(cygpath -u "$installer_python")
fi
exec "$installer_python" "$SCRIPT_DIR/scripts/install.py" --hermes-home "$installer_home" "$@"
