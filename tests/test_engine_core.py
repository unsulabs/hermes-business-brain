"""Proving tests for the native English engine core (in-process, no subprocess).

Covers: (a) engine importability + doctor(), (b) create_vault -> validate_vault
-> status lifecycle on a temp dir with upstream key parity, (c) English-only
user-facing strings (no Spanish accents) in the adapted modules' help/errors.
"""
from __future__ import annotations

import io
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from hermes_business_brain.engine import (
    api,
    cerebro,
    ops_vault,
    resolver_boveda_codex,
)

ENGINE_DIR = Path(api.__file__).resolve().parent

# Spanish accented characters that must not appear in user-facing strings.
SPANISH_ACCENTS = set("áéíóúñ")

# Every module owned by the engine-core worker, checked for accent-free strings.
CORE_MODULES = [
    "__init__.py",
    "api.py",
    "ops_vault.py",
    "cerebro.py",
    "crear_instancia.py",
    "doctor_preflight.py",
    "lib_ce.py",
    "operacion.py",
    "platform_fs.py",
    "resolver_boveda_codex.py",
    "registrar_boveda_codex.py",
    "validar_boveda.py",
    "windows_fs.py",
]

# Upstream JSON output keys that MUST be preserved verbatim.
VALIDATE_KEYS = {"notas", "ids", "bloques", "traspasos", "errores", "advertencias", "tipos"}
STATUS_KEYS = {
    "empresa", "id_empresa", "version_instancia", "total_notas", "por_tipo",
    "editorial", "conocimiento", "capas", "plantillas_instaladas",
    "vistas_bases_instaladas", "fuentes_resumen", "documentos_dx",
    "ultima_continuidad", "continuidades_fecha_invalida", "advertencia",
}


class TestEngineImportable(unittest.TestCase):
    """(a) The engine is a real in-process engine: importable, no subprocess."""

    def test_api_imports_and_doctor_runs(self):
        self.assertTrue(callable(api.doctor))
        result = api.doctor()
        self.assertIsInstance(result, dict)
        # Dependency introspection is present (modules inspected, not installed).
        self.assertIn("dependencias_python", result)
        self.assertIn("yaml", result["dependencias_python"])
        self.assertIn("jsonschema", result["dependencias_python"])
        self.assertIn("python", result)
        self.assertIn("so", result)

    def test_doctor_accepts_vault(self):
        result = api.doctor(vault=ENGINE_DIR)
        self.assertIsInstance(result, dict)
        self.assertIn("boveda_solicitada", result)

    def test_brain_error_type_is_exposed(self):
        self.assertTrue(issubclass(api.BrainError, Exception))
        self.assertIs(api.BrainError, ops_vault.BrainError)

    def test_vault_ops_all_exposed(self):
        for name in ("create_vault", "validate_vault", "status", "register_vault", "resolve_vault"):
            self.assertTrue(callable(getattr(api, name)), name)

    def test_sibling_ops_raise_clear_error_when_missing(self):
        # Tolerance contract: absent sibling modules must not break the import,
        # and their ops must raise a clear, helpful AttributeError.
        if api.ops_knowledge is None:
            with self.assertRaises(AttributeError) as ctx:
                _ = api.query
            self.assertIn("ops_knowledge", str(ctx.exception))
        if api.ops_transcripts is None:
            with self.assertRaises(AttributeError) as ctx:
                _ = api.transcript_cycle
            self.assertIn("ops_transcripts", str(ctx.exception))


class TestVaultLifecycle(unittest.TestCase):
    """(b) create_vault -> validate_vault -> status on a temp dir."""

    def _fresh_vault(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        vid = "TEST-" + re.sub(r"[^A-Za-z0-9_-]", "", Path(tmp.name).name)[:16] or "TESTVAULT"
        self.assertRegex(vid, r"[A-Za-z0-9][A-Za-z0-9_-]{1,63}")
        dest = Path(tmp.name) / "vault"
        created = api.create_vault(id=vid, name="Test Company", dest=dest)
        return dest, vid, created

    def test_create_vault_returns_upstream_keys(self):
        dest, _vid, created = self._fresh_vault()
        self.assertEqual(
            {"creada", "estado", "nota"},
            set(created),
            "create_vault must return the upstream 'crear' output keys",
        )
        self.assertEqual(str(dest.resolve()), created["creada"])
        self.assertEqual("infraestructura_sin_conocimiento", created["estado"])
        self.assertTrue(dest.is_dir())
        self.assertTrue((dest / "90_Sistema" / "config_empresa.yaml").is_file())
        # Company identity was stamped into the template.
        cfg = (dest / "90_Sistema" / "config_empresa.yaml").read_text(encoding="utf8")
        self.assertIn("Test Company", cfg)

    def test_create_vault_rejects_existing_dest(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name) / "vault"
        api.create_vault(id="TESTVAULT1", name="Test Company", dest=dest)
        with self.assertRaises(api.BrainError):
            api.create_vault(id="TESTVAULT2", name="Test Company", dest=dest)

    def test_validate_vault_returns_upstream_keys_and_clean(self):
        dest, _vid, _created = self._fresh_vault()
        result = api.validate_vault(vault=dest)
        self.assertEqual(VALIDATE_KEYS, set(result))
        self.assertEqual([], result["errores"], "fresh template vault must validate clean")
        self.assertEqual([], result["advertencias"])
        self.assertGreater(result["notas"], 0)

    def test_validate_vault_non_vault_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        result = api.validate_vault(vault=Path(tmp.name) / "missing")
        self.assertEqual(set(result), VALIDATE_KEYS)
        self.assertEqual(0, result["notas"])
        self.assertTrue(result["errores"])

    def test_status_returns_upstream_keys(self):
        dest, _vid, _created = self._fresh_vault()
        result = api.status(vault=dest)
        self.assertEqual(STATUS_KEYS, set(result))
        self.assertGreater(result["total_notas"], 0)
        self.assertEqual(0, result["documentos_dx"]["total"])
        self.assertGreater(result["capas"]["infraestructura"], 0)


class TestEnglishOnly(unittest.TestCase):
    """(c) User-facing strings of the owned modules carry no Spanish accents."""

    def _user_facing_text(self, module_file) -> str:
        text = (ENGINE_DIR / module_file).read_text(encoding="utf8")
        # Skip non-user-facing definitions: regex patterns, enum sets, and
        # enums/JSON keys (which must be preserved verbatim by contract).
        text = re.sub(r"(?m)^\s*[A-Z_]+\s*=\s*[\{\[\"]", "", text)
        text = re.sub(r"(?m)^\s*#.*$", "", text)  # comments are not user-facing
        return text

    def test_no_spanish_accents_in_owned_modules(self):
        found = {}
        for module in CORE_MODULES:
            offending = sorted(set(SPANISH_ACCENTS) & set(self._user_facing_text(module)))
            if offending:
                found[module] = offending
        self.assertEqual({}, found, f"Spanish accents found in user-facing strings: {found}")

    def test_cerebro_help_is_english(self):
        # Parse the cerebro help output; descriptions must be English.
        # argparse prints the usage/error to stderr and exits when a required
        # subcommand is missing; assert the error output carries no accents.
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit):
            cerebro.parse_args()  # required subcommand -> prints help, exits 2
        help_text = out.getvalue() + err.getvalue()
        self.assertTrue(help_text.strip(), "help text must be printed")
        self.assertEqual(set(SPANISH_ACCENTS) & set(help_text), set())

    def test_resolver_missing_selector_error_is_english(self):
        # The first validation in resolve() runs before any registry read.
        with self.assertRaises(ValueError) as ctx:
            resolver_boveda_codex.resolve(Path("/nonexistent/registry.json"), Path("/nonexistent/native.json"))
        message = str(ctx.exception)
        self.assertNotIn("á", message)
        self.assertIn("selector", message)


if __name__ == "__main__":
    unittest.main()
