"""Ported upstream test_entrega.py (all methods skipped with reason).

Upstream validates the DELIVERABLE of the monorepo distribution: the demo
vault (ejemplos/boveda_demo), skills inventory (.agents/skills), methodology
and research assets (metodologia/, investigacion/), and auditar_paquete.audit
(scripts/auditar_paquete.py). None of those upstream repository artifacts or
scripts exist in the v2 plugin repo layout (hermes_business_brain/), so the
whole behavior set is recorded here as skipped-with-reason; the venv-ignored
audit rule is effectively covered by tests/upstream_port/test_exportar_producto.py
(private components of the distributable product). See _verify/tests-v2.md.
"""
from __future__ import annotations
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REASON = ('requires upstream monorepo artifacts missing from the v2 plugin repo: '
          'ejemplos/boveda_demo, .agents/skills, metodologia/, investigacion/ and '
          'the auditar_paquete audit script')


class DeliveryTest(unittest.TestCase):
    def test_example_vault_is_synthetic_and_valid(self):
        raise unittest.SkipTest(REASON)

    def test_skills_triggers_and_content(self):
        raise unittest.SkipTest(REASON)

    def test_assets_are_not_disconnected_references(self):
        raise unittest.SkipTest(REASON)

    def test_product_audit_excludes_authorized_private_material(self):
        raise unittest.SkipTest(REASON)

    def test_venv_is_only_exempt_when_ignored_untracked_checkout_tooling(self):
        # The .venv/private-component rule itself is ported and proven in
        # test_exportar_producto.py (_synthetic_repo includes scripts/.venv).
        raise unittest.SkipTest(REASON)


if __name__ == "__main__":
    unittest.main()
