"""Ported upstream test_autoempleo_internacional.py: a sole trader's explicit

context (Portugal, EUR) must not acquire regional defaults; no extraction by
guessing (moneda stays por_definir, impuestos por_verificar). Adaptation: the
upstream fixture locator pointed at upstream ejemplos/escenarios/...; the v2
plugin repo ships no ejemplos, so the scenario file is created in the temp
directory (behavior unchanged -- the source is a record card, not a parser).
"""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.operacion import create_ficha, create_source, read_note
from hermes_business_brain.engine.validar_boveda import validate


class InternationalSoleTraderTest(unittest.TestCase):
    def test_portugal_eur_source_preserves_unknown_tax_and_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            vault = work / 'audio'
            create('AUDIO-SINTETICO', 'Self-employed audio editing', vault)
            offer = create_ficha(vault, 'oferta', 'Podcast editing')
            _, props, _ = read_note(vault, offer['id'])
            self.assertEqual(props['moneda'], 'por_definir')
            self.assertEqual(props['impuestos'], 'por_verificar')
            scenario = work / '04_international_sole_trader.md'
            scenario.write_text(
                '# International sole trader scenario\n\n'
                'Portugal. Individual work. Proposal: EUR 90 per 45 minutes of audio. '
                'Unknown taxes.\n', encoding='utf8', newline='\n')
            create_source(vault, 'F-AUDIO', 'Synthetic sole-trader scenario',
                          str(scenario), 'documento', read_status='leida_completa')
            contextual = create_ficha(
                vault, 'oferta', 'Situated editing proposal',
                resumen='Portugal. Individual work. Proposal: EUR 90 per 45 minutes '
                        'of audio. Unknown taxes.',
                sources=['F-AUDIO'])
            _, props, body = read_note(vault, contextual['id'])
            self.assertIn('EUR 90', body)
            self.assertIn('Portugal', body)
            self.assertEqual(props['estado_editorial'], 'borrador')
            self.assertEqual(props['impuestos'], 'por_verificar')
            self.assertEqual(props['moneda'], 'por_definir')  # No extraction by guessing.
            self.assertTrue(props['fuentes'])
            self.assertNotIn('MXN', body)
            self.assertEqual(validate(vault)['errores'], [])


if __name__ == '__main__':
    unittest.main()
