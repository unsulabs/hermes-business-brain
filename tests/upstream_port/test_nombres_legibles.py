"""Ported upstream test_nombres_legibles.py: stable technical identity and

human-readable paths in a synthetic vault (plan + apply rename with SHA
guards, collisions, backup and wikilink rewrites). Imports point to the native
English engine; Spanish display names and message assertions are translated to
the engine's English equivalents; JSON keys stay verbatim.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.documentos import create_document
from hermes_business_brain.engine.lib_ce import path_by_id, split_frontmatter, visible_filename
from hermes_business_brain.engine.nombres_legibles import plan, apply
from hermes_business_brain.engine.operacion import create_source, save_continuity
from hermes_business_brain.engine.registro_descubrimiento import capture_discovery
from hermes_business_brain.engine.validar_boveda import validate


class ReadableNamesTest(unittest.TestCase):
    def test_visible_name_requires_subject(self):
        for code in ('D01', 'CAP-ABC123', 'SES-ABC123', 'F-DEMO-01'):
            with self.assertRaisesRegex(ValueError, 'needs words'):
                visible_filename(code)

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = create('FICTICIA-NOMBRES', 'Fictitious workshop', self.root / 'boveda')
        self.source = create_source(self.vault, 'F-DEMO-01', 'Workshop interview',
                                    'urn:synthetic:entrevista', 'conversacion')
        body = self.root / 'document.md'
        body.write_text('# Workshop direction\n\n## Activity\n\n'
                        'The fictitious workshop records needs and verifies decisions '
                        'before operating, using the interview as working source.\n',
                        encoding='utf-8', newline='\n')
        self.document = create_document(self.vault, 'D01', 'Workshop direction', body,
                                        sources=['F-DEMO-01'])
        capture = self.root / 'capture.md'
        capture.write_text('The owner said the schedule was Monday, then corrected it to '
                           'Tuesday. Keep the correction as primary source.',
                           encoding='utf8', newline='\n')
        self.capture = capture_discovery(self.vault, 'Schedule ambiguity', capture,
                                         sources=['F-DEMO-01'])
        self.continuity = save_continuity(self.vault,
            summary='Correct the schedule according to the owner later statement.',
            next_step='Re-read the source before proposing a decision.')
        self.spec = self.root / 'names.json'
        self.spec.write_text(json.dumps({'notas': [
            {'id': 'D01', 'nombre': 'How the workshop works'},
            {'id': self.capture['id'], 'nombre': 'Workshop schedule correction'},
            {'id': 'F-DEMO-01', 'nombre': 'Workshop interview log'},
            {'id': self.continuity['id'], 'nombre': '2026 - Schedule correction'},
        ]}), encoding='utf8', newline='\n')

    def test_plan_apply_preserves_ids_content_and_links(self):
        initial = {k: Path(v['ruta']).read_bytes() for k, v in
                   [('document', self.document), ('source', self.source),
                    ('capture', self.capture), ('continuity', self.continuity)]}
        proposal = plan(self.vault, self.spec)
        self.assertEqual(proposal['renombradas'], 4)
        result = apply(self.vault, self.spec, self.root / 'backup', proposal['sha_plan'])
        self.assertEqual(result['validacion'], 'PASS')
        self.assertEqual(validate(self.vault)['errores'], [])
        for key, nid in [('document', 'D01'), ('source', 'F-DEMO-01'),
                         ('capture', self.capture['id']), ('continuity', self.continuity['id'])]:
            p = path_by_id(self.vault, nid)
            self.assertIsNotNone(p)
            self.assertNotIn(nid, p.name)
            fm, body = split_frontmatter(p.read_text(encoding='utf-8'))
            self.assertEqual(fm['id'], nid)
            self.assertTrue(body.strip())
            old_fm, old_body = split_frontmatter(initial[key].decode())
            self.assertEqual(old_fm['id'], fm['id'])
            self.assertEqual(old_body, body)
        doc = path_by_id(self.vault, 'D01').read_text(encoding='utf-8')
        self.assertIn('[[50_Fuentes/Workshop interview log]]', doc)
        self.assertTrue((self.root / 'backup' / 'manifest.json').is_file())

    def test_collision_and_stale_plan_do_not_write(self):
        another = self.root / 'other.md'
        another.write_text('Second synthetic episode to test a title collision.',
                           encoding='utf-8', newline='\n')
        second = capture_discovery(self.vault, 'Another capture', another)
        rows = json.loads(self.spec.read_text(encoding='utf-8'))
        rows['notas'].append({'id': second['id'],
                              'nombre': 'Workshop schedule correction'})
        self.spec.write_text(json.dumps(rows), encoding='utf-8', newline='\n')
        with self.assertRaisesRegex(ValueError, 'collision'):
            plan(self.vault, self.spec)
        rows['notas'][-1]['nombre'] = 'A distinct second capture'
        self.spec.write_text(json.dumps(rows), encoding='utf-8', newline='\n')
        before = path_by_id(self.vault, 'D01').read_bytes()
        with self.assertRaisesRegex(ValueError, 'stale'):
            apply(self.vault, self.spec, self.root / 'backup', '0' * 64)
        self.assertEqual(before, path_by_id(self.vault, 'D01').read_bytes())
        self.assertFalse((self.root / 'backup').exists())

    def test_swap_of_existing_names_blocks_without_writing(self):
        second_input = self.root / 'other.md'
        second_input.write_text('Second fictitious capture to test name swapping.',
                                encoding='utf8', newline='\n')
        second = capture_discovery(self.vault, 'Second capture', second_input)
        first_path = Path(self.capture['ruta'])
        second_path = Path(second['ruta'])
        first_bytes, second_bytes = first_path.read_bytes(), second_path.read_bytes()
        spec = self.root / 'swap.json'
        spec.write_text(json.dumps({'notas': [
            {'id': self.capture['id'], 'nombre': second_path.stem},
            {'id': second['id'], 'nombre': first_path.stem},
        ]}), encoding='utf8', newline='\n')
        with self.assertRaisesRegex(ValueError, 'Destination occupied'):
            plan(self.vault, spec)
        self.assertEqual(first_path.read_bytes(), first_bytes)
        self.assertEqual(second_path.read_bytes(), second_bytes)
        self.assertEqual(validate(self.vault)['errores'], [])

    def test_broken_link_blocks_plan(self):
        p = Path(self.capture['ruta'])
        p.write_text(p.read_text(encoding='utf-8') + '\n[[Non existent note]]\n',
                     encoding='utf-8', newline='\n')
        with self.assertRaisesRegex(ValueError, 'Vault with previous errors'):
            plan(self.vault, self.spec)

    def test_markdown_link_to_old_path_blocks_plan(self):
        p = Path(self.capture['ruta'])
        old = Path(self.document['ruta']).relative_to(self.vault).as_posix()
        p.write_text(p.read_text(encoding='utf-8') + f'\n[Document]({old})\n',
                     encoding='utf-8', newline='\n')
        with self.assertRaisesRegex(ValueError, 'old path'):
            plan(self.vault, self.spec)


if __name__ == '__main__':
    unittest.main()
