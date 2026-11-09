"""Ported upstream test_enlaces_bases.py: the general validator must stay

compatible with links pointing to native Obsidian Bases views (.base assets).
Purely file-based; imports point to the native English engine.

Adaptations: the upstream graph/CLI assertions (exportar_grafo.graph + the
cerebro grafo/validar subprocesses) are replaced by in-process checks because
the v2 engine does not ship exportar_grafo.py and cerebro.run() is broken
(engine gaps, see _verify/tests-v2.md); the 'validar' CLI exit semantics are
mapped to validate()['errores'].
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.lib_ce import make_note, target_index, resolve_link
from hermes_business_brain.engine.validar_boveda import validate
from hermes_business_brain.engine.nombres_legibles import _rewrite_wiki


class BaseLinksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name).resolve()

    def write(self, relative, text):
        path = self.vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')
        return path

    def note(self, body):
        self.write('Inicio.md', make_note({'id': 'HOME', 'tipo': 'inicio'}, body))

    def base(self, path):
        return self.write(path, 'views:\n  - type: table\n    name: Own view\n')

    def test_exact_path_alias_embed_and_unique_basename(self):
        self.base('90_Sistema/Vistas/Transcripciones/Transcripciones.base')
        self.note('[[90_Sistema/Vistas/Transcripciones/Transcripciones.base|See]]\n'
                  '![[Transcripciones.base]]\n')
        before = {p.relative_to(self.vault): p.read_bytes()
                  for p in self.vault.rglob('*') if p.is_file()}
        result = validate(self.vault)
        self.assertEqual(result['errores'], [])
        self.assertEqual(result['notas'], 1)
        self.assertEqual(result['ids'], 1)
        self.assertEqual(before, {p.relative_to(self.vault): p.read_bytes()
                                  for p in self.vault.rglob('*') if p.is_file()})

    def test_ambiguous_basename_fails_but_explicit_path_resolves(self):
        first = self.base('uno/Compartida.base')
        self.base('dos/Compartida.base')
        index = target_index(self.vault, include_assets=True)
        self.assertIsNone(resolve_link('Compartida.base', *index))
        self.assertEqual(resolve_link('uno/Compartida.base', *index), first)
        self.note('[[Compartida.base]] [[uno/Compartida.base]]')
        self.assertEqual(len(validate(self.vault)['errores']), 1)

    def test_missing_base_and_wrong_qualified_path_do_not_resolve(self):
        self.base('Vistas/Existe.base')
        self.note('[[Falta.base]] [[Otro/Existe.base]] [[Nota ausente]]')
        errors = validate(self.vault)['errores']
        self.assertEqual(len(errors), 3)
        self.assertTrue(any('Falta.base' in e for e in errors))
        self.assertTrue(any('Otro/Existe.base' in e for e in errors))

    def test_base_and_markdown_same_stem_remain_distinct(self):
        base = self.base('Vistas/Clientes.base')
        md = self.write('Clientes.md', make_note({'id': 'CLIENTES'}, '# Clientes'))
        index = target_index(self.vault, include_assets=True)
        self.assertEqual(resolve_link('Clientes.base', *index), base)
        self.assertEqual(resolve_link('Clientes', *index), md)
        self.note('[[Clientes]] [[Clientes.md]] [[Clientes.base]]')
        self.assertEqual(validate(self.vault)['errores'], [])

    def test_other_validation_errors_and_symlink_are_not_hidden(self):
        self.base('Vistas/Real.base')
        self.write('Duplicada.md', make_note({'id': 'HOME'}, '# Duplicada'))
        (self.vault / 'Alias.base').symlink_to(self.vault / 'Vistas/Real.base')
        self.note('[[Vistas/Real.base]] [[Alias.base]]')
        errors = validate(self.vault)['errores']
        self.assertTrue(any('Duplicate ID' in e for e in errors))
        self.assertTrue(any('Alias.base' in e for e in errors))

    def test_markdown_named_like_base_does_not_hide_missing_asset(self):
        self.write('Clientes.base.md', make_note({'id': 'ODD'}, '# Markdown note'))
        self.note('[[Clientes.base]]')
        self.assertEqual(len(validate(self.vault)['errores']), 1)
        self.base('Vistas/Clientes.base')
        self.assertEqual(validate(self.vault)['errores'], [])

    def test_explicit_literal_base_markdown_and_graph_remain_notes_only(self):
        self.write('90_Sistema/config_empresa.yaml', 'company_id: SYNTHETIC\n')
        literal = self.write('a/Odd.base.md', make_note({'id': 'LITERAL'}, '# Literal'))
        self.base('a/Odd.base')
        self.note('[[a/Odd.base]] [[a/Odd.base.md]]')
        self.assertEqual(validate(self.vault)['errores'], [])
        self.assertEqual(resolve_link('a/Odd.base.md',
                                      *target_index(self.vault, include_assets=True)), literal)
        self.assertIsNone(resolve_link('a/Odd.base', *target_index(self.vault)))

    def test_rename_preserves_explicit_markdown_type_and_base_link(self):
        old = self.write('a/Odd.base.md', make_note({'id': 'LITERAL'}, '# Literal'))
        self.base('a/Odd.base')
        new = self.vault / 'a' / 'Human title.md'
        text, count = _rewrite_wiki('[[a/Odd.base]] [[a/Odd.base.md|Note]]', self.vault,
                                    {old: new}, *target_index(self.vault))
        self.assertEqual(count, 1)
        self.assertEqual(text, '[[a/Odd.base]] [[a/Human title.md|Note]]')

    def test_general_cli_validar_success_then_missing_failure(self):
        # In-process adaptation of the upstream cerebro.py validar subprocess
        # (returncode 0 <-> outcomes errors == [], nonzero <-> errors non-empty).
        self.base('90_Sistema/Vistas/Transcripciones/Transcripciones.base')
        self.note('[[90_Sistema/Vistas/Transcripciones/Transcripciones.base]]')
        good = validate(self.vault)
        self.assertEqual(good['errores'], [])
        self.note('[[No existe.base]]')
        bad = validate(self.vault)
        self.assertTrue(bad['errores'])
        self.assertIn('No existe.base', ' '.join(bad['errores']))


if __name__ == '__main__':
    unittest.main()
