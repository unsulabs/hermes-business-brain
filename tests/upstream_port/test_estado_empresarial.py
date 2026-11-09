"""Ported upstream test_estado_empresarial.py: templates and continuity notes

must never be confused with business knowledge. Ported 1:1; imports point to
the native English engine. Assertions are structural (JSON keys + counts),
with the upstream Spanish display names replaced by English ones.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.operacion import create_ficha, create_source, save_continuity, summary
from hermes_business_brain.engine.documentos import create_document


class EstadoEmpresarialTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.vault = create('ACME-FICTICIA', 'Synthetic company', self.folder / 'boveda')
        self.body = self.folder / 'borrador.md'
        self.body.write_text('# Synthetic laboratory\n\n## Activity\n\n'
                             'We design a way to represent work with criteria, '
                             'without asserting undocumented results.\n\n'
                             '## CONTROL\n\nThis is a fictitious test for the product.\n',
                             encoding='utf8', newline='\n')

    def test_empty_vault_has_infrastructure_not_business(self):
        r = summary(self.vault)
        self.assertEqual(r['capas']['documentos_dx'], 0)
        self.assertEqual(r['capas']['entidades_operativas'], 0)
        self.assertEqual(r['capas']['fuentes'], 0)
        self.assertGreater(r['capas']['infraestructura'], 0)
        self.assertEqual(r['documentos_dx']['registros'], [])
        self.assertEqual(r['vistas_bases_instaladas'], 16)
        self.assertGreater(r['plantillas_instaladas'], 20)
        self.assertEqual(r['total_notas'], r['capas']['infraestructura'])

    def test_sources_and_continuity_are_not_document_or_approved_company(self):
        create_source(self.vault, 'F-DEMO-011', 'Synthetic source', 'urn:synthetic:011', 'nota',
                      read_status='leida_parcial')
        save_continuity(self.vault, summary='First synthetic capture.', next_step='Review sample data')
        r = summary(self.vault)
        self.assertEqual(r['fuentes_resumen']['por_lectura'], {'leida_parcial': 1})
        self.assertEqual(r['capas']['fuentes'], 1)
        self.assertEqual(r['capas']['trabajo_provisional'], 1)
        self.assertEqual(r['documentos_dx']['total'], 0)
        self.assertEqual(r['capas']['entidades_operativas'], 0)
        self.assertEqual(r['total_notas'], r['capas']['infraestructura'] + 2)

    def test_D01_draft_is_visible_separately_from_infrastructure(self):
        create_source(self.vault, 'F-DEMO-011', 'Synthetic source', 'urn:synthetic:011', 'nota')
        create_document(self.vault, 'D01', 'Synthetic identity', self.body,
                        editorial='en_revision', sources=['F-DEMO-011'])
        create_ficha(self.vault, 'proyecto', 'Synthetic project')
        r = summary(self.vault)
        self.assertEqual(r['documentos_dx']['total'], 1)
        self.assertEqual(r['documentos_dx']['por_clase'], {'D01': 1})
        self.assertEqual(r['documentos_dx']['por_estado_editorial'], {'en_revision': 1})
        self.assertEqual(r['documentos_dx']['registros'][0]['ruta'],
                         '10_Conocimiento/Synthetic identity.md')
        self.assertEqual(r['documentos_dx']['registros'][0]['fuentes_referenciadas'], 1)
        self.assertEqual(r['capas']['entidades_operativas'], 1)
        self.assertEqual(r['por_tipo']['documento'], 1)


if __name__ == '__main__':
    unittest.main()
