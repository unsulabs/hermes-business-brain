"""Ported upstream test_check_docs.py (all methods skipped).

Upstream scripts/check_docs.py checks an isolated bilingual documentation tree
(inventory + local heading anchors). The v2 plugin repo does not ship a
check_docs module (the docs check belongs to the plugin's own tooling), so the
whole behavior set is recorded here as skipped-with-reason.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REASON = ('requires the upstream scripts/check_docs.py doc-inventory checker, '
          'not shipped in the v2 plugin repo')


class DocsCheckTest(unittest.TestCase):
    def test_inventory_and_links_consistent(self):
        raise unittest.SkipTest(REASON)


if __name__ == "__main__":
    unittest.main()
