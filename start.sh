#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [ ! -x paradigme_venv/bin/python ]; then bash install.sh; fi
printf '%s\n' 'Open http://127.0.0.1:8765 unless you changed the port.' 'Stop with Ctrl+C.'
exec paradigme_venv/bin/python "$PWD/app.py"
