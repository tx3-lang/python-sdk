"""Render-fixture test for the .trix/client-lib codegen plugin."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def _resolve_tx3c() -> str:
    """Locates the tx3c binary: TX3_TX3C_PATH first, then $PATH."""
    from_env = os.environ.get("TX3_TX3C_PATH")
    if from_env and Path(from_env).is_file():
        return from_env
    found = shutil.which("tx3c")
    if found:
        return found
    raise RuntimeError("tx3c not found; set TX3_TX3C_PATH or install tx3c")


@pytest.mark.codegen
def test_codegen_client_lib_renders_and_imports() -> None:
    """Renders the plugin against the shared fixture and imports the result.

    A successful render that produces an unloadable module is a failure.
    """
    sdk_dir = Path(__file__).resolve().parent.parent
    repo_root = sdk_dir.parent
    template_dir = repo_root / ".trix" / "client-lib"
    tii_path = sdk_dir / "tests" / "fixtures" / "transfer.tii"

    assert tii_path.is_file(), f"missing TII fixture: {tii_path}"
    assert template_dir.is_dir(), f"missing template directory: {template_dir}"

    with tempfile.TemporaryDirectory() as out_dir:
        subprocess.run(
            [
                _resolve_tx3c(),
                "codegen",
                "--tii",
                str(tii_path),
                "--template",
                str(template_dir),
                "--output",
                out_dir,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        generated = Path(out_dir) / "__init__.py"
        assert generated.is_file(), "expected generated __init__.py"

        spec = importlib.util.spec_from_file_location("tx3_generated_protocol", generated)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)

    assert module.TARGET_TII_VERSION == "v1beta0"
    assert set(module.PROFILES) == {"local", "preprod"}
    assert module.TRANSFER_TIR.version == "v1beta0"
    params = module.TransferParams(quantity=1_000_000)
    assert params.quantity == 1_000_000
    assert hasattr(module.Client, "transfer")
    assert hasattr(module.Client, "submit")
