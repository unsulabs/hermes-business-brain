"""Ported upstream test_registrar_boveda_obsidian.py: local registration of a new

vault after opening it in Obsidian (native registry), with idempotency,
collision protection and project association. Spanish error assertions are
replaced by the engine's English messages; status enums and JSON keys stay
verbatim.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.registrar_boveda_obsidian import canonical, register


class RegisterVaultTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = self.root / "Fictitious company"
        (self.vault / "90_Sistema").mkdir(parents=True)
        (self.vault / "90_Sistema" / "Como_usar.md").write_text("# Usage\n",
                                                                encoding='utf-8', newline='\n')
        (self.vault / "Inicio.md").write_text("# Home\n", encoding='utf-8', newline='\n')
        self.native = self.root / "obsidian.json"
        self.registry = self.root / "vaults.json"
        self.project = canonical(self.root / "Agent Project")
        self.project.mkdir()
        self.native.write_text(json.dumps({"vaults": {"abc123": {"path": str(self.vault)}}}),
                               encoding='utf-8', newline='\n')

    def call_register(self):
        return register(self.vault, "Fictitious company", "EMP-FIC", self.registry,
                        self.native, "90_Sistema/Como_usar.md", "Inicio.md")

    def test_register_and_repeat_without_rewriting(self):
        first = self.call_register()
        self.assertEqual(first["status"], "registrada")
        self.assertEqual(first["id"], "abc123")
        before = self.registry.read_bytes()
        second = self.call_register()
        self.assertEqual(second["status"], "ya_registrada")
        self.assertEqual(before, self.registry.read_bytes())
        self.assertEqual(json.loads(before)["vaults"][0]["aliases"], ["EMP-FIC"])

    def test_native_registration_required(self):
        self.native.write_text(json.dumps({"vaults": {}}), encoding='utf-8', newline='\n')
        with self.assertRaisesRegex(ValueError, "Open the folder"):
            self.call_register()
        self.assertFalse(self.registry.exists())

    def test_collision_preserves_existing_registry(self):
        self.registry.write_text(json.dumps({"format": "hermes-obsidian-vaults/1",
                                             "vaults": [{"name": "Other company", "id": "xyz",
                                                         "aliases": ["EMP-FIC"],
                                                         "path": str(self.root / "Other")}]}) + "\n",
                                 encoding='utf-8', newline='\n')
        before = self.registry.read_bytes()
        with self.assertRaisesRegex(ValueError, "collides"):
            self.call_register()
        self.assertEqual(before, self.registry.read_bytes())

    def test_existing_registry_is_backed_up(self):
        self.registry.write_text('{"format":"hermes-obsidian-vaults/1","vaults":[]}\n',
                                 encoding='utf-8', newline='\n')
        before = self.registry.read_bytes()
        result = self.call_register()
        self.assertEqual(Path(result["respaldo"]).read_bytes(), before)
        self.assertEqual(len(json.loads(self.registry.read_text(encoding='utf-8'))["vaults"]), 1)

    def test_new_vault_is_associated_with_exact_project(self):
        result = register(self.vault, "Fictitious company", "EMP-FIC", self.registry,
                          self.native, "90_Sistema/Como_usar.md", "Inicio.md", self.project)
        self.assertEqual(result["status"], "registrada")
        self.assertEqual(json.loads(self.registry.read_text(encoding='utf-8'))["vaults"][0]
                         ["projects"], [str(self.project)])
        before = self.registry.read_bytes()
        repeated = register(self.vault, "Fictitious company", "EMP-FIC", self.registry,
                            self.native, "90_Sistema/Como_usar.md", "Inicio.md", self.project)
        self.assertEqual(repeated["status"], "ya_registrada")
        self.assertEqual(self.registry.read_bytes(), before)

    def test_existing_vault_adds_project_with_backup(self):
        self.call_register()
        before = self.registry.read_bytes()
        result = register(self.vault, "Fictitious company", "EMP-FIC", self.registry,
                          self.native, "90_Sistema/Como_usar.md", "Inicio.md", self.project)
        self.assertEqual(result["status"], "proyecto_asociado")
        self.assertEqual(Path(result["respaldo"]).read_bytes(), before)
        self.assertEqual(json.loads(self.registry.read_text(encoding='utf-8'))["vaults"][0]
                         ["projects"], [str(self.project)])

    def test_project_collision_does_not_rewrite_registry(self):
        other = {"name": "Other company", "id": "xyz", "aliases": ["OTRA"],
                 "path": str(self.root / "Other"),
                 "projects": [str(self.project)]}
        self.registry.write_text(json.dumps({"format": "hermes-obsidian-vaults/1",
                                             "vaults": [other]}) + "\n",
                                 encoding='utf-8', newline='\n')
        before = self.registry.read_bytes()
        with self.assertRaisesRegex(ValueError, "collides"):
            register(self.vault, "Fictitious company", "EMP-FIC", self.registry,
                     self.native, "90_Sistema/Como_usar.md", "Inicio.md", self.project)
        self.assertEqual(self.registry.read_bytes(), before)

    def test_nonexistent_project_does_not_register(self):
        with self.assertRaisesRegex(ValueError, "Project does not exist"):
            register(self.vault, "Fictitious company", "EMP-FIC", self.registry,
                     self.native, "90_Sistema/Como_usar.md", "Inicio.md",
                     self.root / "Does not exist")
        self.assertFalse(self.registry.exists())


if __name__ == "__main__":
    unittest.main()
