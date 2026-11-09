"""Ported upstream test_core.py: technical kit behavior on the fictional package vault.

Ported 1:1 from the upstream Spanish suite (obsidian-business-brain/tests/test_core.py);
imports point to the native English engine (hermes_business_brain.engine.*) and
Spanish message assertions are replaced with the engine's English equivalents.

Manifest-import tests run against the vendored synthetic handoff fixture
(fixtures/traspaso_sintetico, copied byte-for-byte from the upstream
ejemplos/traspaso_sintetico) through the vendored vNext-0.9 contract validator
(engine/validador_de_traspaso.py) and canvas generator (engine/lib_canvas.py).
"""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine import crear_instancia, importar_traspaso, validar_boveda
from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.validar_boveda import validate

TEMPLATE_MAP = (
    Path(importar_traspaso.__file__).resolve().parents[1]
    / "data" / "plantilla_boveda" / "00_Mapas" / "Relaciones_de_conocimiento.md"
)

# Vendored byte-verbatim copy of the upstream synthetic handoff package.
MANIFEST = Path(__file__).resolve().parent / "fixtures" / "traspaso_sintetico" / "manifest.json"


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name) / "brisa"
        create('BRISA-SINTETICA', 'Brisa Modular FICTICIA', self.vault)

    def test_vault_template_validates(self):
        result = validate(self.vault)
        self.assertEqual(result['errores'], [])
        self.assertEqual(result['traspasos'], 0)

    def test_importer_rejects_modified_map_even_with_old_phrase(self):
        from hermes_business_brain.engine.importar_traspaso import (
            LEGACY_RELATION_PLACEHOLDER,
            _intact_relation_placeholder,
        )
        template = TEMPLATE_MAP.read_text(encoding='utf8')
        self.assertTrue(_intact_relation_placeholder(template))
        self.assertTrue(_intact_relation_placeholder(LEGACY_RELATION_PLACEHOLDER))
        self.assertFalse(_intact_relation_placeholder(template + '\n# Important manual change\n'))
        self.assertFalse(_intact_relation_placeholder(LEGACY_RELATION_PLACEHOLDER + '\n# Manual change\n'))

    def test_import_and_graph(self):
        from hermes_business_brain.engine.exportar_grafo import graph
        from hermes_business_brain.engine.importar_traspaso import import_package
        stats = import_package(MANIFEST, self.vault)
        self.assertEqual(stats['documentos'], 4)
        self.assertEqual(stats['bloques'], 5)
        self.assertEqual(stats['pruebas_semanticas_pendientes'], 3)
        result = validate(self.vault)
        self.assertEqual(result['errores'], [])
        self.assertEqual(result['traspasos'], 1)
        self.assertEqual(result['bloques'], 5)
        canvas = json.loads((self.vault / '00_Mapas' / 'Mapa_de_relaciones.canvas').read_text(encoding='utf-8'))
        self.assertEqual(len(canvas['nodes']), 6)
        self.assertGreaterEqual(len(canvas['edges']), 4)
        g = graph(self.vault)
        preds = {x['predicado'] for x in g['aristas'] if x['capa'] == 'contrato'}
        self.assertIn('refiere_oferta', preds)
        self.assertIn('sustentado_por', preds)
        self.assertIn('pertenece_a', preds)
        self.assertIn('autoridad_en_precio_modulo_estandar', preds)
        self.assertIn('no_ejecutada', (self.vault / '90_Sistema' / 'Pruebas_de_recuperacion.md').read_text(encoding='utf-8'))

    def test_non_destructive(self):
        from hermes_business_brain.engine.importar_traspaso import import_package
        import_package(MANIFEST, self.vault)
        with self.assertRaises(FileExistsError):
            import_package(MANIFEST, self.vault)
        with self.assertRaises(FileExistsError):
            create('BRISA-SINTETICA', 'Ficticia', self.vault)

    def test_broken_link_detected(self):
        note = self.vault / '00_Mapas' / 'Mapa_de_empresa.md'
        note.write_text(note.read_text(encoding='utf-8') + '\n[[No_existe_este_documento]]\n',
                        encoding='utf-8', newline='\n')
        self.assertTrue(any('broken or ambiguous link' in e for e in validate(self.vault)['errores']))

    def test_company_isolation(self):
        with self.assertRaises(ValueError):
            create('mal id', 'Name', Path(self.temp.name) / 'invalida')
        other = Path(self.temp.name) / 'otra'
        create('OTRA-SINTETICA', 'Otra', other)
        # The two vaults carry distinct company identities (no shared state).
        import yaml
        cfg_a = yaml.safe_load((self.vault / '90_Sistema' / 'config_empresa.yaml').read_text(encoding='utf-8'))
        cfg_b = yaml.safe_load((other / '90_Sistema' / 'config_empresa.yaml').read_text(encoding='utf-8'))
        self.assertEqual(cfg_a['company_id'], 'BRISA-SINTETICA')
        self.assertEqual(cfg_b['company_id'], 'OTRA-SINTETICA')
        # fresh second vault validates clean too
        self.assertEqual(validate(other)['errores'], [])

    def test_contract_rejects_tampered_document(self):
        # The original package stays intact; a copy gets one test file altered.
        import shutil
        from hermes_business_brain.engine.importar_traspaso import import_package
        base = Path(self.temp.name) / 'tampered'
        shutil.copytree(MANIFEST.parent, base)
        (base / 'Ejemplo_sintetico' / 'D03_Portafolio.md').write_text('alterado', encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError) as ctx:
            import_package(base / 'manifest.json', self.vault)
        self.assertIn('HASH document', str(ctx.exception))
        self.assertEqual(list((self.vault / '10_Conocimiento').glob('*.md')), [])

    def test_sensitive_material_is_refused(self):
        import shutil
        from hermes_business_brain.engine.importar_traspaso import import_package
        base = Path(self.temp.name) / 'sensitive'
        shutil.copytree(MANIFEST.parent, base)
        manifest = base / 'manifest.json'
        obj = json.loads(manifest.read_text(encoding='utf-8'))
        obj['sources'][0]['access'] = 'restringido'
        manifest.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError) as ctx:
            import_package(manifest, self.vault)
        self.assertIn('has no ACL', str(ctx.exception))
        self.assertEqual(list((self.vault / '10_Conocimiento').glob('*.md')), [])

    def test_name_with_apostrophe_yaml_safe(self):
        other = Path(self.temp.name) / 'name'
        create('ACME-TEST', "Company O'Connor", other)
        from hermes_business_brain.engine import lib_ce
        import yaml
        company = yaml.safe_load((other / '90_Sistema' / 'config_empresa.yaml').read_text(encoding='utf-8'))
        self.assertEqual(company['company_name'], "Company O'Connor")
        self.assertEqual(validate(other)['errores'], [])


if __name__ == '__main__':
    unittest.main()
