"""Ported upstream test_continuidad_temporal.py: temporal ordering of continuity

records with random IDs. Ported 1:1; imports point to the native English engine
(hermes_business_brain.engine.*). No Spanish string assertions: the test only
checks JSON keys and relative paths.
"""
from __future__ import annotations
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.lib_ce import make_note
from hermes_business_brain.engine.operacion import summary
from hermes_business_brain.engine.validar_boveda import validate


class UltimaContinuidadTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.vault = create("EMPRESA-SINTETICA", "Temporal test", Path(t.name) / "boveda")
        self.folder = self.vault / "90_Sistema" / "Continuidad"
        self.folder.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, nid: str, timestamp: str):
        path = self.folder / name
        path.write_text(make_note({
            "id": nid, "tipo": "continuidad", "empresa_id": "EMPRESA-SINTETICA",
            "estado_editorial": "borrador", "sensibilidad": "interno",
            "registrado_en": timestamp,
        }, f"# Synthetic session {nid}\n"), encoding="utf8", newline='\n')
        return path

    def test_second_same_day_does_not_use_lexicographic_id(self):
        old = self.write("2026-10-28_SES-ZZZZ.md", "SES-ZZZZ", "2026-10-28T13:00:00-06:00")
        later = self.write("2026-10-28_SES-AAAA.md", "SES-AAAA", "2026-10-28T14:00:00-06:00")
        result = summary(self.vault)
        self.assertEqual(result["ultima_continuidad"], later.relative_to(self.vault).as_posix())
        self.assertEqual(result["continuidades_fecha_invalida"], [])
        self.assertEqual(validate(self.vault)["errores"], [])
        self.assertTrue(old.is_file())

    def test_offset_comparison_and_stable_tiebreaker(self):
        first = self.write("2026-10-28_SES-111.md", "SES-111", "2026-10-28T18:00:00+00:00")
        second = self.write("2026-10-28_SES-222.md", "SES-222", "2026-10-28T13:00:00-05:00")
        self.assertEqual(summary(self.vault)["ultima_continuidad"],
                         second.relative_to(self.vault).as_posix())
        self.assertTrue(first.exists())

    def test_invalid_timestamp_is_reported_not_selected(self):
        bad = self.write("2026-10-28_SES-ZZZ.md", "SES-ZZZ", "sin_fecha")
        good = self.write("2026-10-28_SES-AAA.md", "SES-AAA", "2026-10-28T14:00:00-06:00")
        result = summary(self.vault)
        self.assertEqual(result["ultima_continuidad"], good.relative_to(self.vault).as_posix())
        self.assertEqual(result["continuidades_fecha_invalida"],
                         [bad.relative_to(self.vault).as_posix()])

    def test_missing_timezone_is_reported(self):
        self.write("2026-10-28_SES-AAA.md", "SES-AAA", "2026-10-28T15:00:00")
        result = summary(self.vault)
        self.assertIsNone(result["ultima_continuidad"])
        self.assertEqual(len(result["continuidades_fecha_invalida"]), 1)

    def test_empty_vault_has_no_last_continuity(self):
        result = summary(self.vault)
        self.assertIsNone(result["ultima_continuidad"])
        self.assertEqual(result["continuidades_fecha_invalida"], [])


if __name__ == "__main__":
    unittest.main()
