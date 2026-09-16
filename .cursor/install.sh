#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for zuper-wop-notify.
# Ensures the venv toolchain, then builds the project virtualenv.
set -euo pipefail

# The default image ships Python 3.12 but not the venv/ensurepip module.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv
fi

cd "$(dirname "$0")/../zuper-wop-notify"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

echo "zuper-wop-notify install complete:"
.venv/bin/python --version
