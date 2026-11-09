"""Ported upstream test_captura_progresiva.py: discovery captures as isolated

tests with fully fictitious data (never approved knowledge). Spanish strings
translated to the engine's English equivalents; JSON keys stay verbatim. The
private-key draft marker is assembled from fragments at runtime (repo PEM-scan
rule).
"""
from __future__ import annotations
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.operacion import create_source, summary
from hermes_business_brain.engine.registro_descubrimiento import capture_discovery
from hermes_business_brain.engine.validar_boveda import validate
from hermes_business_brain.engine.lib_ce import split_frontmatter


class CaptureTest(unittest.TestCase):
    def setUp(self):
        context = tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        self.tmp = Path(context.name)
        self.vault = create("EMP-PRUEBA", "Fictitious Company", self.tmp / "boveda")
        self.note = self.tmp / "authorized_capture.md"
        self.note.write_text(
            "## Documented observation\nA synthetic sample document exists.\n\n"
            "## Provisional interpretation\nIt is unknown which company did the work.\n\n"
            "## Pending\nConfirm the attribution before using it in an offer.",
            encoding="utf8", newline='\n')

    def test_provisional_record_with_no_fake_case(self):
        result = capture_discovery(self.vault, "Initial exploration", self.note)
        self.assertFalse(result["aprobado"])
        dest = Path(result["ruta"])
        self.assertEqual(dest.parent.name, "Descubrimiento")
        props, body = split_frontmatter(dest.read_text(encoding="utf8"))
        self.assertEqual(props["tipo"], "registro_descubrimiento")
        self.assertEqual(props["estado_editorial"], "borrador")
        self.assertEqual(props["estado_conocimiento"], "pendiente")
        self.assertEqual(props["autoridad"], "ninguna")
        self.assertIn("It is unknown which company", body)
        self.assertEqual(validate(self.vault)["errores"], [])
        self.assertEqual(summary(self.vault)["por_tipo"]["registro_descubrimiento"], 1)
        self.assertFalse(list((self.vault / "20_Entidades").glob("*.md")))

    def test_source_link_must_exist(self):
        create_source(self.vault, "F-DEMO-01", "Synthetic original",
                      "urn:synthetic:ejemplo", "prueba")
        result = capture_discovery(self.vault, "Reading", self.note, sources=["F-DEMO-01"])
        props, _ = split_frontmatter(Path(result["ruta"]).read_text(encoding="utf8"))
        self.assertIn("[[50_Fuentes/Synthetic original]]", props["fuentes"])
        with self.assertRaises(ValueError):
            capture_discovery(self.vault, "Bad", self.note, sources=["F-DESCONOCIDA"])

    def test_empty_and_secret_rejected(self):
        self.note.write_text("   ", encoding="utf8", newline='\n')
        with self.assertRaises(ValueError):
            capture_discovery(self.vault, "Empty", self.note)
        marker = "-----" + "BEGIN PRIVATE " + "KEY-----"
        self.note.write_text(marker + "\nInvalid example", encoding="utf8", newline='\n')
        with self.assertRaises(ValueError):
            capture_discovery(self.vault, "Secret", self.note)

    def test_non_destructive_multiple_captures(self):
        first = capture_discovery(self.vault, "One", self.note)
        original = Path(first["ruta"]).read_bytes()
        second = capture_discovery(self.vault, "Two", self.note)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(Path(first["ruta"]).read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
