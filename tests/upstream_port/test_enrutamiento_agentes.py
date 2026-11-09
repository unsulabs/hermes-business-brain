"""Ported upstream test_enrutamiento_agentes.py (all methods skipped).

Upstream checks the DOCUMENTAL integrity of the agent-routing contract in the
upstream monorepo layout: .agents/skills inventory, AGENTS.md reachability,
docs/es/agent-contract.md obligations and the ce-extraer-meetgeek reception
template. The v2 plugin repo ships that material under
hermes_business_brain/skills/ (and has no AGENTS.md / docs/es agent contract),
so the entire behavior set is recorded here as skipped-with-reason; the local
link integrity helper it uses is exercised per-skill in the plugin's own
tooling. See _verify/tests-v2.md.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REASON = ('requires the upstream monorepo distribution layout (.agents/skills, '
          'AGENTS.md, docs/es/agent-contract.md, ce-extraer-meetgeek reception '
          'template); the v2 plugin repo ships skills under hermes_business_brain/skills/ '
          'with no AGENTS.md contract')


class AgentRoutingTests(unittest.TestCase):
    def test_skill_names_are_unique_and_discoverable(self):
        raise unittest.SkipTest(REASON)

    def test_new_routes_reachable_from_product_contract(self):
        raise unittest.SkipTest(REASON)

    def test_skill_references_survive_distribution_without_workspace(self):
        raise unittest.SkipTest(REASON)

    def test_reference_checker_rejects_missing_dependency(self):
        # The local-link checker itself is trivially portable; it is kept
        # exercised in test_plan_conocimiento/test_estado via file fixtures.
        raise unittest.SkipTest(REASON)

    def test_new_skills_have_contract_and_shared_boundary(self):
        raise unittest.SkipTest(REASON)

    def test_acceptance_obligations_are_scoped_away_from_daily_continuity(self):
        raise unittest.SkipTest(REASON)

    def test_reception_template_resolves_from_external_bank_in_both_layouts(self):
        raise unittest.SkipTest(REASON)


if __name__ == '__main__':
    unittest.main()
