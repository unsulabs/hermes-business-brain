"""Ported upstream test_bases_migration.py (all methods skipped).

Upstream migrates legacy Bases views (fixtures_bases_v0_2 -> current) through
scripts/actualizar_vistas_bases.py (plan/apply with AL_DIA/LISTO/BLOQUEADO
states and private backups). The v2 engine surface has no actualizar_vistas_bases
module (engine gap, see _verify/tests-v2.md), and the upstream zero-dot-two
fixtures are not shipped in the plugin repo, so the whole behavior set is
recorded here as skipped-with-reason.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REASON = ('requires the upstream actualizar_vistas_bases module and the '
          'tests/fixtures_bases_v0_2 fixture set, neither shipped in the v2 '
          'plugin repo (engine gap, see _verify/tests-v2.md)')


class BasesMigrationTest(unittest.TestCase):
    def test_fresh_vault_is_current(self):
        raise unittest.SkipTest(REASON)

    def test_legacy_views_are_migrated_only_with_backup(self):
        raise unittest.SkipTest(REASON)

    def test_customized_view_blocks_all_writes(self):
        raise unittest.SkipTest(REASON)


if __name__ == "__main__":
    unittest.main()
