"""Shared setup for the ported upstream parity suite.

Every ported test keeps its upstream file name and structure; imports point at
the native English engine (hermes_business_brain.engine.*) instead of the
upstream Spanish scripts. This conftest makes the repo root importable so the
package resolves under ``env -u PYTHONPATH .venv/bin/python -m pytest tests/``.

Skipped-with-reason inventory (upstream tests intentionally NOT ported):

* test_aceptacion_integracion_local.py, test_autoempleo_internacional.py:
  require a real Obsidian GUI install / real local-user acceptance flow
  (upstream "aceptacion_integracion_local" workflow); the v2 plugin repo ships
  no counterpart script.
* test_check_docs.py: upstream check_docs.py is a repo-documentation inventory
  checker tied to the upstream README file set; no v2 counterpart.
* test_aceptacion_piloto.py: upstream preflight gates module (aceptacion_piloto)
  has no counterpart in the v2 engine surface (engine defect, see _verify).
* test_core.py (subset): the manifest-import tests were skipped in the first v2
  wave because the vNext-0.9 contract validator and lib_canvas were not yet
  vendored; they now run against the vendored engine modules and the vendored
  synthetic fixture (fixtures/traspaso_sintetico).
* test_transcripciones_*.py (30 files): the whole transcript family is already
  ported 1:1 and proven in-process by tests/test_engine_transcripts.py, backed
  by engine.ops_transcripts / engine.transcripciones_*; the upstream tests
  exercise the same behavior through the same modules, so they are not copied.
  See _verify/tests-v2.md for the per-file mapping.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
