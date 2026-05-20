#!/usr/bin/env bash
#
# CI artifact — not part of the SDK.
#
# Renders the .trix/client-lib codegen plugin against the shared transfer
# fixture and verifies the result. The subject under test is the Handlebars
# templates + tx3c integration, not the SDK runtime.
#
# Steps: invoke `tx3c codegen`, assert the expected file exists, smoke-check
# the generated surface, and import the output against this repo's SDK.
#
# Requires `tx3c` and a `python` with this repo's SDK installed on PATH.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
gen="$(mktemp -d)"
trap 'rm -rf "$gen"' EXIT

tx3c codegen \
  --tii "$repo_root/sdk/tests/fixtures/transfer.tii" \
  --template "$repo_root/.trix/client-lib" \
  --output "$gen"

test -f "$gen/__init__.py" || { echo "missing generated file: __init__.py"; exit 1; }

for sym in \
  'TARGET_TII_VERSION' \
  'PROFILES' \
  'TRANSFER_TIR' \
  'class TransferParams' \
  'class Client'; do
  grep -qF "$sym" "$gen/__init__.py" || { echo "generated __init__.py missing: $sym"; exit 1; }
done

# Import the rendered module to confirm it loads against this repo's SDK.
python -c "
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
