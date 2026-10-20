#!/usr/bin/env bash
# Dispatches a RustDesk client build with the INNERbit branding (icon, logo,
# app name, company name) already filled in. Pass --platform and anything
# else rdgen_cli.py accepts (e.g. --dry-run, --version) through as-is.
#
# Usage:
#   ./scripts/build-innerbit.sh --platform windows
#   ./scripts/build-innerbit.sh --platform linux --dry-run
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec python3 "$SCRIPT_DIR/../rdgen_cli.py" \
  --repo INNERBIT-INFORMATICA/rustdesk-client \
  --server rustdesk.innerbit.com.br \
  --key "ZMLOYLzSTnPmfaWMds0RMWHtXApkfLY+wSk5K5QuKIo=" \
  --filename innerbit-rustdesk \
  --version 1.5.0 \
  --appname "INNERbit" \
  --compname "INNERbit Informatica Ltda" \
  --icon "$SCRIPT_DIR/../branding/innerbit/icon.png" \
  --logo "$SCRIPT_DIR/../branding/innerbit/logo.png" \
  "$@"
