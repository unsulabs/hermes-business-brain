"""Ported upstream test_resolver_boveda_codex.py: synthetic-only routing and

clean-install failure regressions (selectors, project association, malformed
registries fail closed, symlink and traversal rejection, native-mismatch
precedence). Spanish names in fixtures are translated; English error regexes
come from the v2 modules; JSON keys stay verbatim. The two cerebro/resolver
CLI tests are exercised in-process.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.registrar_boveda_codex import (
    canonical, native_registry_path, register,
)
from hermes_business_brain.engine.resolver_boveda_codex import resolve
from hermes_business_brain.engine.validar_boveda import validate

REGISTER_MOD = 'hermes_business_brain.engine.registrar_boveda_codex'


class RoutingTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = canonical(tmp.name)
        self.vault = self.root / 'Company A with spaces'
        (self.vault / '90_Sistema').mkdir(parents=True)
        (self.vault / '90_Sistema/Como_usar.md').write_text('# Synthetic instructions',
                                                            encoding='utf-8', newline='\n')
        (self.vault / 'Inicio.md').write_text('# Synthetic home', encoding='utf-8',
                                              newline='\n')
        self.native = self.root / 'obsidian.json'
        self.registry = self.root / 'vaults.json'
        self.native.write_text(json.dumps({'vaults': {'abc': {'path': str(self.vault)}}}),
                               encoding='utf-8', newline='\n')
        register(self.vault, 'Company A', 'EMP-A', self.registry, self.native,
                 '90_Sistema/Como_usar.md', 'Inicio.md', self.root)

    def run_resolve(self, **kwargs):
        return resolve(self.registry, self.native, **(kwargs or {'selector': 'EMP-A'}))

    def change_entry(self, **kwargs):
        obj = json.loads(self.registry.read_text(encoding='utf-8'))
        obj['vaults'][0].update(kwargs)
        self.registry.write_text(json.dumps(obj), encoding='utf-8', newline='\n')

    def test_selectors_project_and_read_only(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for selector in ('EMP-A', 'abc', 'company a', str(self.vault)):
            result = self.run_resolve(selector=selector)
            self.assertEqual(result['status'], 'selected')
            self.assertTrue(result['native_registry_verified'])
        self.assertEqual(self.run_resolve(project=self.root / 'child')['path'], str(self.vault))
        self.assertEqual(before,
                         {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_missing_ambiguous_malformed(self):
        with self.assertRaises(ValueError):
            self.run_resolve(selector='unknown')
        obj = json.loads(self.registry.read_text(encoding='utf-8'))
        obj['vaults'].append(dict(obj['vaults'][0]))
        self.registry.write_text(json.dumps(obj), encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            self.run_resolve()
        with self.assertRaises(ValueError):
            self.run_resolve(project=self.root)
        self.registry.write_text('{', encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            self.run_resolve()
        self.registry.unlink()
        with self.assertRaises(ValueError):
            self.run_resolve()

    def test_native_mismatch_precedes_instruction_lookup(self):
        self.native.write_text(json.dumps({'vaults': {'different': {'path': str(self.vault)}}}),
                               encoding='utf-8', newline='\n')
        self.change_entry(instructions='../secret.md')
        with self.assertRaisesRegex(ValueError, 'Native Obsidian'):
            self.run_resolve()

    def test_malformed_fields_fail_closed(self):
        original = self.registry.read_bytes()
        for change in ({'id': None}, {'aliases': 'EMP-A'}, {'projects': [None]},
                       {'instructions': ''}, {'path': 'relative'}):
            self.registry.write_bytes(original)
            self.change_entry(**change)
            with self.assertRaises(ValueError):
                self.run_resolve()

    def test_traversal_and_drive_relative_rejected(self):
        for value in ('../secret.md', '/secret.md', 'C:secret.md', 'folder\\secret.md'):
            self.change_entry(instructions=value)
            with self.assertRaises(ValueError):
                self.run_resolve()

    def test_symlinks_rejected(self):
        secret = self.root / 'outside.md'
        secret.write_text('not read', encoding='utf-8', newline='\n')
        start = self.vault / 'Inicio.md'
        start.unlink()
        start.symlink_to(secret)
        with self.assertRaises(ValueError):
            self.run_resolve()
        start.unlink()
        start.write_text('# Home', encoding='utf-8', newline='\n')
        alias = self.root / 'linked'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            resolve(alias / 'vaults.json', self.native, selector='EMP-A')
        with self.assertRaises(ValueError):
            resolve(self.registry, alias / 'obsidian.json', selector='EMP-A')

    def test_cli_missing_native_returns_error(self):
        # Upstream ran scripts/resolver_boveda_codex.py (exit 2, status error).
        # In-process equivalent: a missing native registry fails closed.
        self.native.unlink()
        with self.assertRaises(ValueError):
            self.run_resolve()

    def test_invalid_vault_validation_fails_cli(self):
        # In-process adaptation of the cerebro validar CLI (nonzero exit <-> errors).
        for path in (self.root / 'missing', self.native):
            self.assertTrue(validate(path)['errores'])

    def test_platform_defaults_are_mocked_not_os_acceptance(self):
        with patch(f'{REGISTER_MOD}.sys.platform', 'darwin'):
            self.assertEqual(native_registry_path(),
                             Path.home() / 'Library/Application Support/obsidian/obsidian.json')
        with patch(f'{REGISTER_MOD}.sys.platform', 'linux'), \
             patch.dict(os.environ, {'XDG_CONFIG_HOME': '/synthetic/config'}):
            self.assertEqual(native_registry_path(),
                             Path('/synthetic/config/obsidian/obsidian.json'))
        with patch(f'{REGISTER_MOD}.sys.platform', 'win32'), \
             patch.dict(os.environ, {'APPDATA': '/synthetic/roaming'}):
            self.assertEqual(native_registry_path(),
                             Path('/synthetic/roaming/obsidian/obsidian.json'))
        with patch(f'{REGISTER_MOD}.sys.platform', 'linux'), \
             patch.dict(os.environ, {}, clear=True), \
             patch(f'{REGISTER_MOD}.Path.home', return_value=self.root):
            self.assertEqual(native_registry_path(),
                             self.root / '.config/obsidian/obsidian.json')


if __name__ == '__main__':
    unittest.main()
