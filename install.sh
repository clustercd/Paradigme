#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'
if [ ! -x paradigme_venv/bin/python ]; then
  python3 -m venv paradigme_venv
fi
paradigme_venv/bin/python -m pip install -r requirements.txt
if [ ! -f config.json ]; then cp config.example.json config.json; fi
printf '%s\n' 'Installation ready. Run bash start.sh.'
