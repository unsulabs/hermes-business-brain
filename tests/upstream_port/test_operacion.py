"""Ported upstream test_operacion.py: MVP operation regression without real

company data. Imports point to the native English engine; Spanish display
strings inside assertions are replaced with the engine's English equivalents;
JSON keys and enums stay verbatim.

The imported-synthetic-price case runs against the vendored synthetic handoff
fixture (fixtures/traspaso_sintetico) via the vendored contract validator
(engine/validador_de_traspaso.py) and canvas generator (engine/lib_canvas.py).

Adapted: the two cerebro.py subprocess tests are exercised in-process because
engine cerebro.run() runs the engine ops directly (no external process).
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hermes_business_brain.engine import cerebro, crear_instancia
from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.lib_ce import split_frontmatter
from hermes_business_brain.engine.operacion import (authority_lookup, create_ficha,
                                                    create_source, exact_search,
                                                    load_registry, propose_change,
                                                    save_continuity, summary)
from hermes_business_brain.engine.validar_boveda import validate

PACKAGE = Path(crear_instancia.__file__).resolve().parent.parent

# Vendored byte-verbatim copy of the upstream synthetic handoff package.
MANIFEST = Path(__file__).resolve().parent / "fixtures" / "traspaso_sintetico" / "manifest.json"


class OperacionTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.vault = self.root / 'boveda'
        create('EMPRESA-PRUEBA', 'Fictitious test business', self.vault)

    def source(self, id='F-TEST-01'):
        return create_source(self.vault, id, 'Source created for test',
                             'urn:synthetic:source', 'nota', read_status='no_verificada')

    def test_registry_has_clear_distinctions_and_valid_relations(self):
        reg = load_registry()
        self.assertEqual(len(reg), 27)
        self.assertIn('producto', reg); self.assertIn('oferta', reg)
        self.assertIn('consultoria', reg); self.assertIn('herramienta', reg)
        self.assertIn('persona', reg); self.assertIn('cliente_cuenta', reg)
        self.assertIn('propuesta_comercial', reg); self.assertIn('acuerdo', reg)
        for item in reg.values():
            self.assertGreater(len(item['no_confundir']), 10)
            self.assertGreater(len(item['pregunta_de_prueba']), 15)
            self.assertTrue(set(item['relaciones_candidatas']).issubset(reg))
            self.assertTrue((PACKAGE / 'plantilla_boveda' / '90_Sistema' / 'Plantillas'
                             / ('Ficha_' + item['tipo'] + '.md')).is_file())

    def test_first_installed_vault_has_no_fake_business_data(self):
        self.assertEqual(validate(self.vault)['errores'], [])
        self.assertEqual(list((self.vault / '20_Entidades').glob('*.md')), [])
        self.assertFalse((self.vault / '30_Registros').exists())
        self.assertIn('not a form', (self.vault / 'Inicio.md').read_text(encoding='utf-8'))

    def test_create_ficha_draft_with_source(self):
        self.source()
        result = create_ficha(self.vault, 'consultoria',
                              'Technical diagnostics of projects', sources=['F-TEST-01'])
        p = Path(result['ruta']); self.assertTrue(p.exists())
        props, body = split_frontmatter(p.read_text(encoding='utf-8'))
        self.assertEqual(props['estado_conocimiento'], 'pendiente')
        self.assertEqual(props['estado_editorial'], 'borrador')
        self.assertEqual(props['vigencia'], 'sin_verificar')
        self.assertIn('[[50_Fuentes/Source created for test]]', props['fuentes'])
        self.assertIn('is not approval', body.lower())
        self.assertEqual(validate(self.vault)['errores'], [])

    def test_new_ficha_without_source_never_approved(self):
        result = create_ficha(self.vault, 'oferta', 'Offer not yet approved')
        text = Path(result['ruta']).read_text(encoding='utf-8')
        self.assertIn('sin_verificar', text)
        self.assertIn('fuentes: []', text)
        self.assertIn('pendiente', text)
        self.assertEqual(validate(self.vault)['errores'], [])

    def test_ficha_rejects_unregistered_source(self):
        with self.assertRaises(ValueError):
            create_ficha(self.vault, 'oferta', 'Offer', sources=['F-AUSENTE'])
        self.assertEqual(list((self.vault / '20_Entidades').glob('*.md')), [])

    def test_ficha_rejects_unsupported_type(self):
        with self.assertRaises(ValueError):
            create_ficha(self.vault, 'sistema_de_contabilidad_magico', 'invention')
        with self.assertRaises(ValueError):
            create_ficha(self.vault, 'fuente', 'use source function')

    def test_injection_title_rejected(self):
        with self.assertRaises(ValueError):
            create_ficha(self.vault, 'proyecto', 'Title\nanother field')

    def test_same_visible_name_blocks_collision_without_losing_first_note(self):
        x = create_ficha(self.vault, 'proyecto', 'Same title')
        before = Path(x['ruta']).read_bytes()
        with self.assertRaises(FileExistsError):
            create_ficha(self.vault, 'proyecto', 'Same title')
        self.assertEqual(Path(x['ruta']).read_bytes(), before)
        self.assertEqual(validate(self.vault)['errores'], [])

    def test_sources_are_references_not_originals_and_no_overwrite(self):
        src = self.source(); self.assertTrue(Path(src['ruta']).exists())
        self.assertFalse(src['copia_original'])
        self.assertNotIn('intact original document',
                         Path(src['ruta']).read_text(encoding='utf-8'))
        with self.assertRaises(FileExistsError):
            self.source()

    def test_protected_source_rejected(self):
        with self.assertRaises(ValueError):
            create_source(self.vault, 'F-TEST-01', 'material', 'url', 'contrato',
                          permission='restringido')

    def test_status_summary_tracks_only_actual_notes(self):
        before = summary(self.vault)
        self.assertEqual(before['por_tipo'].get('oferta'), None)
        create_ficha(self.vault, 'oferta', 'Demo')
        after = summary(self.vault)
        self.assertEqual(after['por_tipo']['oferta'], 1)
        self.assertEqual(after['conocimiento']['pendiente'], 1)
        self.assertIn('NOT coverage sufficiency', after['advertencia'])

    def test_proposal_is_separate_and_hash_provenance(self):
        o = create_ficha(self.vault, 'oferta', 'Offer under study')
        target = Path(o['ruta']); original = target.read_bytes()
        change = propose_change(self.vault, o['id'],
                                'The scope must be updated', 'Add conditions under review')
        self.assertTrue(Path(change['archivo']).is_file())
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(change['objetivo_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(validate(self.vault)['errores'], [])

    def test_proposal_does_not_write_nonexistent_target(self):
        with self.assertRaises(ValueError):
            propose_change(self.vault, 'NO-EXISTE', 'reason', 'content')

    def test_continuity_records_not_as_authority(self):
        r = save_continuity(self.vault,
                            summary='A synthetic offer was evaluated.',
                            next_step='Recover the real source before approving',
                            reviewer='por_validar')
        self.assertEqual(summary(self.vault)['ultima_continuidad'],
                         Path(r['ruta']).resolve().relative_to(self.vault.resolve()).as_posix())
        self.assertIn('is not authority', Path(r['ruta']).read_text(encoding='utf-8'))
        self.assertEqual(validate(self.vault)['errores'], [])

    def test_continuity_requires_next_step(self):
        with self.assertRaises(ValueError):
            save_continuity(self.vault, summary='done', next_step='')

    def test_literal_search_is_not_semantic(self):
        create_ficha(self.vault, 'proyecto', 'Launch campaign', resumen='We will research inventories')
        res = exact_search(self.vault, 'inventories')
        self.assertEqual(res['total'], 1)
        self.assertIn('NOT semantic retrieval', res['alcance'])
        self.assertEqual(exact_search(self.vault, 'no_existe_algo')['total'], 0)

    def test_authority_query_no_import_returns_unknown(self):
        res = authority_lookup(self.vault, 'precio', 'oferta:xxx')
        self.assertEqual(res['estado'], 'sin_autoridad_explicita')

    def test_authority_query_imported_synthetic_price(self):
        from hermes_business_brain.engine.importar_traspaso import import_package
        other = self.root / 'brisa'
        create('BRISA-SINTETICA', 'Brisa Ficticia', other)
        import_package(MANIFEST, other)
        before = authority_lookup(other, 'precio_modulo_estandar', 'oferta:OFR-BRISA-001', as_of='2026-09-30')
        active = authority_lookup(other, 'precio_modulo_estandar', 'oferta:OFR-BRISA-001', as_of='2026-10-15')
        self.assertEqual(before['estado'], 'sin_autoridad_explicita')
        self.assertEqual(active['estado'], 'candidato_para_verificar')
        self.assertEqual(len(active['coincidencias']), 1)
        self.assertTrue(active['coincidencias'][0]['fuentes'])

    def test_authority_rejects_bad_date(self):
        with self.assertRaises(ValueError):
            authority_lookup(self.vault, 'precio', 'scope', as_of='2026-13-80')

    def test_bases_templates_and_schemas_present(self):
        files = list((PACKAGE / 'plantilla_boveda' / '90_Sistema' / 'Vistas').glob('*.base'))
        self.assertGreaterEqual(len(files), 12)
        for p in files:
            obj = yaml.safe_load(p.read_text(encoding='utf-8'))
            self.assertIn('filters', obj); self.assertIn('views', obj)
            self.assertTrue(all('type' in v and 'name' in v for v in obj['views']))
        docs = json.loads((PACKAGE / 'data' / 'modelo' / 'clases_documentales.json')
                          .read_text(encoding='utf-8'))['clases']
        self.assertEqual({d['id'] for d in docs},
                         {f'{p}{i:02}' for p in ('D', 'X') for i in range(1, 8)})
        for doc in docs:
            self.assertTrue(any((PACKAGE / 'plantilla_boveda/90_Sistema/Plantillas')
                                .glob(doc['id'] + '_*')))
            self.assertGreaterEqual(len(doc['encabezados']), 7)

    def test_doctor_with_no_dependencies(self):
        # In-process adaptation of the upstream `cerebro.py doctor` subprocess:
        # the zero-dependency diagnostic must not claim environment guesses.
        from hermes_business_brain.engine.doctor_preflight import diagnose
        data = diagnose()
        self.assertEqual(data['producto'], 'Business Brain 0.2.0')
        self.assertEqual(data['obsidian_gui'], 'NOT VERIFIED')
        self.assertIn('yaml', data['dependencias_python'])

    def test_cerebro_consulta_contextual_runs_in_process(self):
        # Upstream ran `python -S scripts/cerebro.py consulta-contextual ...` as
        # a subprocess and asserted the literal-search result. v2 runs the same
        # op in-process through cerebro.run() now that the engine modules
        # (including exportar_grafo) are shipped; there is no subprocess and no
        # missing-module guard to trip: the source lookup happens inside the
        # engine and the result is the upstream dict.
        old_argv = sys.argv
        sys.argv = ['cerebro.py', 'consulta-contextual',
                    '--vault', str(self.vault), '--texto', 'compras']
        try:
            _, args = cerebro.parse_args()
            result = cerebro.run(args)
            self.assertEqual(result['modo'], 'busqueda_literal_de_bloques_con_contexto')
            self.assertEqual(result['total_coincidencias'], 0)
            self.assertFalse(result['respuesta_semantica_generada'])
        finally:
            sys.argv = old_argv

    def test_oferta_never_assumes_country_or_currency(self):
        x = create_ficha(self.vault, 'oferta', 'International fictitious offer')
        fm, _ = split_frontmatter(Path(x['ruta']).read_text(encoding='utf-8'))
        self.assertEqual(fm['moneda'], 'por_definir')
        self.assertEqual(fm['precio_sistema_fuente'], '')
        self.assertEqual(fm['estado_editorial'], 'borrador')

    def test_approval_not_inferred_from_text(self):
        x = create_ficha(self.vault, 'decision',
                         'We approve the sale per someone said', resumen='approved approved approved')
        fm, _ = split_frontmatter(Path(x['ruta']).read_text(encoding='utf-8'))
        self.assertEqual(fm['estado_editorial'], 'borrador')
        self.assertEqual(fm['estado_conocimiento'], 'pendiente')


if __name__ == '__main__':
    unittest.main()
