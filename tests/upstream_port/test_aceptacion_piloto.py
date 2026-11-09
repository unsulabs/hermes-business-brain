"""Ported upstream test_aceptacion_piloto.py (all methods skipped).

The upstream preflight gate check lives in scripts/aceptacion_piloto.py
(preflight). The v2 engine surface has NO counterpart module: cerebro.py's
'aceptacion' subcommand does a lazy ``from .aceptacion_piloto import preflight``
that fails at runtime because the module file was not shipped. Engine code is
frozen in this wave, so the whole upstream behavior set (gates, estado_tecnico,
producto_listo_para_produccion) is recorded here as skipped-with-reason and the
gap is reported in _verify/tests-v2.md.
"""
from __future__ import annotations
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REASON = ('Pilot preflight module (upstream scripts/aceptacion_piloto.py) is absent from '
          'the v2 engine surface; cerebro.py references .aceptacion_piloto which is not '
          'shipped (engine gap, see _verify/tests-v2.md)')


class PilotPreflightTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        from hermes_business_brain.engine.crear_instancia import create
        self.vault = create("TEST-PILOTO", "Totally fictitious company", self.root / "boveda")

    @unittest.skip(REASON)
    def test_empty_vault_not_claimed_ready(self):
        pass

    @unittest.skip(REASON)
    def test_first_D01_not_automatically_accepted(self):
        pass

    @unittest.skip(REASON)
    def test_vista_regresada_detected(self):
        pass


if __name__ == "__main__":
    unittest.main()
