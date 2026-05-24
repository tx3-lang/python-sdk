#!/usr/bin/env bash
#
# CI artifact — not part of the SDK.
#
# Renders the .trix/client-lib codegen plugin against the shared transfer
# fixture and verifies the result the way a consumer would: the rendered module
# is imported in a fresh venv with the dependencies its generated
# requirements.txt pins installed — no editable install of the SDK source tree.
#
# Requires `tx3c` and `python` on PATH.
# Last verified against fleet v0.12.0 (unified Tx3ClientBuilder).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
gen="$(mktemp -d)"
trap 'rm -rf "$gen"' EXIT

tx3c codegen \
  --tii "$repo_root/sdk/tests/fixtures/transfer.tii" \
  --template "$repo_root/.trix/client-lib" \
  --output "$gen"

for f in __init__.py requirements.txt; do
  test -f "$gen/$f" || { echo "missing generated file: $f"; exit 1; }
done

for sym in \
  'TARGET_TII_VERSION' \
  'PROFILES' \
  'TRANSFER_TIR' \
  'class TransferParams' \
  'class Client'; do
  grep -qF "$sym" "$gen/__init__.py" || { echo "generated __init__.py missing: $sym"; exit 1; }
done

# Import the rendered module in a fresh venv with the dependencies its generated
# requirements.txt pins, exactly as an end user would consume it.
python -m venv "$gen/venv"
"$gen/venv/bin/pip" install --quiet --upgrade pip
"$gen/venv/bin/pip" install --quiet -r "$gen/requirements.txt"
"$gen/venv/bin/python" -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('tx3_generated_protocol', '$gen/__init__.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
assert module.TARGET_TII_VERSION == 'v1beta0', module.TARGET_TII_VERSION
assert set(module.PROFILES) == {'local', 'preprod'}, module.PROFILES
assert module.TRANSFER_TIR.version == 'v1beta0'
assert module.TransferParams(quantity=1).quantity == 1
print('generated module imported OK')
"

echo "codegen check passed"
