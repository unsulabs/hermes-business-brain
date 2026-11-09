"""Ported upstream test_aceptacion_integracion_local.py (all methods skipped).

Upstream produces the Codex report for a REAL local-instance acceptance flow
(scripts/aceptacion_integracion_local.py: zip report over a real Obsidian
instance without publishing notes). The v2 plugin repo ships no
aceptacion_integracion_local module and the flow requires a real user vault /
Obsidian GUI, so the whole behavior set is recorded here as skipped-with-reason
(see _verify/tests-v2.md).
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REASON = ('requires a real Obsidian local instance, a real user vault and the '
          'upstream scripts/aceptacion_integracion_local.py report flow, none '
          'of which exist in the v2 plugin repo')


class LocalAcceptanceTest(unittest.TestCase):
    def test_report_does_not_publish_notes_or_change_user_vault(self):
        raise unittest.SkipTest(REASON)


if __name__ == "__main__":
    unittest.main()
