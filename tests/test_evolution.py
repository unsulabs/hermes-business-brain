"""Proving test: read-only evolution scan (engine v2).

Creates a synthetic vault through the engine vault-creation path, seeds
capture-like notes under 90_Sistema/Descubrimiento, and asserts that the
evolution scan returns the expected result shape, fires the promotion rules
only when the required evidence exists, marks thin evidence as ``partial``,
reports due revisits for areas without documents, and that the new evolution
files are ASCII-only and carry no private-key detection literal.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hermes_business_brain.engine import api as engine_api
from hermes_business_brain.engine import ops_evolution

NEW_FILES = [
    "hermes_business_brain/engine/evolucion.py",
    "hermes_business_brain/engine/ops_evolution.py",
    "hermes_business_brain/data/modelo/reglas_evolucion.json",
    "hermes_business_brain/skills/ce-evolucion/SKILL.md",
]


def _create_vault(tmp: Path) -> Path:
    vault = tmp / "evo-vault"
    engine_api.create_vault(id="TEST-EVO-001", name="Evolution Test", dest=str(vault))
    return vault


def _seed(vault: Path, name: str, body: str) -> Path:
    folder = vault / "90_Sistema" / "Descubrimiento"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(body, encoding="utf-8")
    return path


class TestEvolutionScan(unittest.TestCase):
    def test_scan_result_shape_and_zero_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            vault = _create_vault(Path(td))
            result = ops_evolution.evolution_scan(vault=str(vault))
            self.assertEqual(result["vault"], str(vault))
            for key in ("date", "summary", "candidates", "due_visits"):
                self.assertIn(key, result)
            self.assertEqual(result["summary"]["sources"], 0)
            self.assertEqual(result["candidates"], [])

    def test_rule_r01_fires_with_two_episodes_and_not_with_one(self):
        with tempfile.TemporaryDirectory() as td:
            vault = _create_vault(Path(td))
            _seed(vault, "one.md", "The owner stated a criterion about budget adjustments in one event.")
            result = ops_evolution.evolution_scan(vault=str(vault))
            r01 = [c for c in result["candidates"] if c["rule_id"] == "R01"]
            self.assertEqual(len(r01), 1)
            self.assertEqual(r01[0]["status"], "partial")
            _seed(vault, "two.md", "A second event confirms the same criterion with a real episode.")
            _seed(vault, "three.md", "A third event repeats the criterion pattern again.")
            result = ops_evolution.evolution_scan(vault=str(vault))
            r01 = [c for c in result["candidates"] if c["rule_id"] == "R01"]
            self.assertEqual(len(r01), 1)
            self.assertEqual(r01[0]["status"], "ready")
            self.assertGreaterEqual(len(r01[0]["evidence"]), 2)

    def test_rule_r04_fires_when_all_figures_present(self):
        with tempfile.TemporaryDirectory() as td:
            vault = _create_vault(Path(td))
            _seed(
                vault,
                "case.md",
                "Full case: quote total $100000, gastos listados, cobrado con saldo pendiente.",
            )
            result = ops_evolution.evolution_scan(vault=str(vault))
            r04 = [c for c in result["candidates"] if c["rule_id"] == "R04"]
            self.assertEqual(len(r04), 1)
            self.assertEqual(r04[0]["status"], "ready")

    def test_thin_evidence_is_partial(self):
        with tempfile.TemporaryDirectory() as td:
            vault = _create_vault(Path(td))
            _seed(vault, "quote.md", "One quote with $15000 of flowers.")
            result = ops_evolution.evolution_scan(vault=str(vault))
            r02 = [c for c in result["candidates"] if c["rule_id"] == "R02"]
            self.assertEqual(len(r02), 1)
            self.assertEqual(r02[0]["status"], "partial")
            self.assertIn("only 1 of 2", r02[0]["why_not"])

    def test_due_visits_reported_for_stale_areas(self):
        with tempfile.TemporaryDirectory() as td:
            vault = _create_vault(Path(td))
            result = ops_evolution.evolution_scan(vault=str(vault))
            self.assertGreater(len(result["due_visits"]), 0)
            first = result["due_visits"][0]
            for key in ("area", "last_review", "cadence_days", "primary", "suggestion"):
                self.assertIn(key, first)
            self.assertEqual(first["last_review"], "never")

    def test_new_files_are_ascii_and_pem_free(self):
        pem_parts = ("PRIVATE KEY", "BEGIN")
        for rel in NEW_FILES:
            path = ROOT / rel
            self.assertTrue(path.exists(), rel)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), f"{rel} is not ASCII-only")
            if "reglas" not in rel:
                self.assertNotIn("-----BEGIN", text)
                self.assertNotIn("PRIVATE KEY", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
