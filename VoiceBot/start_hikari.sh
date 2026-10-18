#!/usr/bin/env bash
set -euo pipefail

# Resolve relative to this file, so launching from another folder also works.
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if [[ ! -x .venv/bin/python ]]; then
    printf '%s\n' \
        'Hikari Linux virtual environment is missing.' \
        'Create it with: python3.12 -m venv .venv' \
        'Then install: .venv/bin/python -m pip install -r requirements.txt' >&2
    exit 1
fi

# Replace the shell so Ctrl+C and exit status reach the normal supervisor.
exec .venv/bin/python run_hikari.py "$@"
