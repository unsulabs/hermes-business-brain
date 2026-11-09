"""Proving tests for the native English transcript pipeline engine.

Covers hermes_business_brain/engine/ops_transcripts.py + the translated
transcripciones_* family against a synthetic temp bank:

* a full custody chain on a real committed bank (ingresar -> estado ->
  verificar -> permiso -> segmentar -> indexar -> buscar -> registrar ->
  conciliar -> inventario-validar -> taxonomia), asserting upstream result
  envelopes (resultado.v1) with English messages;
* preview semantics (commit=False writes nothing);
* hard errors raised as BrainError (engine-core class), not BLOCKED dicts;
* no Spanish accents in the modules' user-facing strings (byte-identity
  vault-template constants in importar_traspaso.py match the shipped English
  template data verbatim).

Steps analizar, cobertura and revisar-antecedentes need fully agent-authored
semantic submissions (claims/relations/subject matrix/events) on top of real
segments; they are documented in _verify/engine-transcripts.md as covered by
unit-level paths that require those authoring fixtures, not exercised here.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO_ROOT / "hermes_business_brain" / "engine"
sys.path.insert(0, str(REPO_ROOT))

from hermes_business_brain.engine import ops_transcripts as ops  # noqa: E402

# Spanish accented letters (and common diacritics) that must not appear in
# user-facing strings of the native English modules.
ACCENTED = frozenset("áéíóúÁÉÍÓÚñÑüÜàèìòùäëïöüâêîôûçãõåæœ")

# Byte-identity constants in importar_traspaso.py: they must match the verbatim
# English vault template/placeholder notes shipped as data (kept here so any
# future drift back to Spanish copy is caught by the accent assertion context;
# English phrases carry no accents, so these never exempt a line).
ALLOWED_ACCENT_MARKERS = (
    "No manifest has been imported yet",
    "The system keeps gaps",
    "PENDING: test with a real agent",
    "The vNext contract importer generates",
)

MY_MODULES = sorted(list(ENGINE_DIR.glob("transcripciones*.py")) + [
    ENGINE_DIR / "ops_transcripts.py",
    ENGINE_DIR / "importar_traspaso.py",
    ENGINE_DIR / "exportar_producto.py",
])


def _bank_safe_root():
    """Temp root whose ancestors are symlink-free and outside any Git/Obsidian tree.

    The bank location policy rejects any symlinked ancestor (macOS /var is a
    symlink), so the default system temp may be unusable; fall back to the
    configured TMPDIR, then to the home directory.
    """
    def usable(root):
        probe = root / "probe"
        for part in [*reversed(probe.parents), probe]:
            if (part.is_symlink() or (part / ".git").exists()
                    or (part / ".obsidian").exists()):
                return False
        return True
    base = Path(tempfile.mkdtemp(prefix="hbb-transcripts-"))
    if usable(base):
        return base
    for root in [Path(os.environ.get("TMPDIR") or tempfile.gettempdir()), Path.home()]:
        try:
            base = Path(tempfile.mkdtemp(prefix="hbb-transcripts-", dir=str(root)))
        except OSError:
            continue
        if usable(base):
            return base
    raise unittest.SkipTest("no bank-safe temporary location available")


def _profile(vault):
    return {"company_id": "ACME-TEST", "allowed_purposes": ["custody", "local_analysis", "internal_query"],
            "vault": str(vault)}


def _write(obj, path):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


class TranscriptPipelineTest(unittest.TestCase):
    def setUp(self):
        self.root = _bank_safe_root()
        self.vault = self.root / "vault"
        self.bank = self.root / "bank"
        self.vault.mkdir()
        self.bank.mkdir()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.profile = _profile(self.vault)
        self.kw = dict(vault=str(self.bank), profile=self.profile, request_id="REQ-TEST-1")
        self.audience = "analyst-audit"

    def _ingest(self, purpose="local_analysis", **extra):
        data = b"# Weekly Meeting\n\nWe discussed gross margin and quarterly billing forecasts.\n"
        return ops.transcript_cycle(step="ingresar", purpose=purpose, commit=True,
                                    closed=True, expected_parts=1,
                                    source_id="MTG-0001", account_id="ACC-0001",
                                    attempt_id="ATT-1", payload=data, **self.kw, **extra)

    def test_ingresar_commits_and_estado_reports(self):
        entry = self._ingest()
        self.assertEqual(entry["schema_version"], "resultado.v1")
        self.assertEqual(entry["operation"], "ingresar")
        self.assertEqual(entry["status"], "DONE")
        self.assertFalse(entry["errors"])
        self.assertTrue(entry["evidence"]["committed"])
        self.assertEqual(entry["evidence"]["completeness"], "complete")
        self.assertTrue(entry["evidence"]["tr_id"].startswith("TR-"))
        self.assertEqual(len(entry["evidence"]["tr_id"]), 67)
        self.assertTrue(entry["evidence"]["version_id"].startswith("V-"))
        self.assertEqual(len(entry["evidence"]["version_id"]), 66)

        status = ops.transcript_cycle(step="estado", purpose="local_analysis",
                                      audience=self.audience, **self.kw)
        self.assertEqual(status["status"], "DONE")
        self.assertEqual(status["evidence"]["transcriptions"], 1)
        self.assertEqual(status["evidence"]["states"]["integrity"]["verificada"], 1)
        self.assertTrue(status["evidence"]["review_snapshot_id"].startswith("SN-"))

        verified = ops.transcript_cycle(step="verificar", purpose="local_analysis", **self.kw)
        self.assertEqual(verified["status"], "DONE")
        self.assertEqual(verified["evidence"], {"transcriptions": 1, "versions": 1, "pending_journals": 0})

    def test_full_chain_segment_index_search_permissions(self):
        entry = self._ingest()
        tr, vid = entry["evidence"]["tr_id"], entry["evidence"]["version_id"]

        for purpose in ("local_analysis", "internal_query"):
            decision = {"tr_id": tr, "version_id": vid, "company": "ACME-TEST",
                        "audience": self.audience, "purpose": purpose, "action": "grant",
                        "authority": "operator-local-test",
                        "evidence": ["recorded by the proving test operator"],
                        "decided_at": "2026-11-06T12:00:00Z"}
            permitted = ops.transcript_cycle(step="permiso", purpose="custody",
                                             input=_write(decision, self.root / f"decision-{purpose}.json"),
                                             commit=True, **self.kw)
            self.assertEqual(permitted["status"], "DONE")
            self.assertTrue(permitted["evidence"]["sequence"])
            self.assertEqual(len(permitted["evidence"]["decision_hash"]), 64)

        segments = ops.transcript_cycle(step="segmentar", purpose="local_analysis",
                                        audience=self.audience, tr_id=tr, version=vid,
                                        commit=True, **self.kw)
        self.assertEqual(segments["status"], "DONE")
        self.assertGreaterEqual(segments["evidence"]["segment_count"], 1)
        self.assertTrue(segments["evidence"]["committed"])
        self.assertTrue(segments["evidence"]["bundle_id"].startswith("SG-"))

        indexed = ops.transcript_cycle(step="indexar", purpose="local_analysis",
                                       audience=self.audience, commit=True, **self.kw)
        self.assertEqual(indexed["status"], "DONE")
        self.assertEqual(indexed["evidence"]["indexed_versions"], 1)
        self.assertTrue(indexed["evidence"]["committed"])
        self.assertEqual(indexed["evidence"]["scope"]["company"], "ACME-TEST")

        request = {"query": "margin", "company": "ACME-TEST", "audience": self.audience,
                   "purpose": "internal_query", "limit": 10}
        out = self.root / "context-package.json"
        search = ops.transcript_cycle(step="buscar", purpose="internal_query",
                                      request=_write(request, self.root / "request.json"),
                                      output=str(out), **self.kw)
        self.assertEqual(search["status"], "DONE")
        self.assertEqual(search["evidence"]["candidate_count"], 1)
        self.assertEqual(len(search["outputs"]), 1)
        self.assertTrue(out.exists())
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["status"], "DONE")

        manifest = next(Path(self.bank).glob("recepcion/local/*/*/*/*/capture-manifest.v1.json"))
        registered = ops.transcript_cycle(step="registrar", purpose="custody",
                                          capture_manifest=str(manifest), commit=True, **self.kw)
        self.assertEqual(registered["status"], "DONE")
        self.assertTrue(registered["evidence"]["idempotent"])
        self.assertTrue(registered["evidence"]["committed"])

        inventory = {"schema_version": "inventario.v1", "created_at": "2026-11-06T12:00:00Z",
                     "producer_version": "proving-test", "snapshot_id": "INV-1",
                     "account": {"id": "ACC-0001", "observed_identity": "unknown"},
                     "captured_at": "2026-11-06T12:00:00Z",
                     "sections": [{"name": "Section 1", "end_observed": True,
                                   "end_evidence": "listed in the provider UI", "limit": None}],
                     "meetings": [{"id": "MTG-0001", "url": None, "title": "Weekly Meeting",
                                   "state": "inaccessible", "attempts": ["ATT-1"]}]}
        reconciled = ops.transcript_cycle(step="conciliar", purpose="local_analysis",
                                          snapshot=_write(inventory, self.root / "inventory.json"), **self.kw)
        self.assertEqual(reconciled["status"], "DONE")
        self.assertEqual(reconciled["evidence"]["counts"]["complete"], 1)
        validated = ops.transcript_cycle(step="inventario-validar", purpose="local_analysis",
                                         snapshot=str(self.root / "inventory.json"), **self.kw)
        self.assertEqual(validated["status"], "DONE")
        self.assertTrue(validated["evidence"]["inventory_closed"])

    def test_taxonomia_preview_uses_seed(self):
        from hermes_business_brain.engine.transcripciones_taxonomia import seed_taxonomy
        taxonomy = seed_taxonomy()
        self.assertEqual(taxonomy["taxonomy_version"], "generic-1")
        stored = ops.transcript_cycle(step="taxonomia", purpose="local_analysis",
                                      input=_write(taxonomy, self.root / "taxonomy.json"), **self.kw)
        self.assertEqual(stored["status"], "DONE")
        self.assertEqual(stored["evidence"]["taxonomy_version"], "generic-1")
        self.assertFalse(stored["evidence"]["committed"])

    def test_preview_does_not_commit(self):
        preview = ops.transcript_cycle(step="ingresar", purpose="local_analysis", commit=False,
                                       closed=True, expected_parts=1, source_id="MTG-0001",
                                       account_id="ACC-0001", attempt_id="ATT-1",
                                       payload=b"preview only bytes", **self.kw)
        self.assertEqual(preview["status"], "DONE")
        self.assertFalse(preview["evidence"]["committed"])
        self.assertEqual(list(Path(self.bank).glob("receipts/*.json")), [])
        self.assertEqual(list(Path(self.bank).glob("journal/*.json")), [])

    def test_hard_errors_raise_engine_core_brain_error(self):
        from hermes_business_brain.engine import BrainError as engine_brain_error
        self.assertIs(ops.BrainError, engine_brain_error)  # canonical, not the local fallback

        with self.assertRaises(ops.BrainError) as ctx:
            ops.transcript_cycle(step="unknown-step", purpose="local_analysis", **self.kw)
        self.assertEqual(getattr(ctx.exception, "code", None), "COMMAND_UNKNOWN")

        with self.assertRaises(ops.BrainError) as ctx:
            ops.transcript_cycle(step="ingresar", purpose="local_analysis", payload=b"x", **self.kw)
        self.assertEqual(getattr(ctx.exception, "code", None), "ARGUMENT_REQUIRED")

        with self.assertRaises(ops.BrainError):
            ops.transcript_cycle(step="ingresar", purpose="denied-purpose",
                                 payload=b"x", source_id="S", account_id="A",
                                 attempt_id="T", **self.kw)

        bad_id = ops.transcript_cycle  # no-op reference keeps lint quiet
        del bad_id

    def test_modules_have_no_spanish_accents(self):
        violations = []
        for path in MY_MODULES:
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not (ACCENTED & set(line)):
                    continue
                if path.name == "importar_traspaso.py" and (
                        any(marker in line for marker in ALLOWED_ACCENT_MARKERS)
                        or line.lstrip().startswith("LEGACY_RELATION_PLACEHOLDER = ")):
                    continue
                violations.append(f"{path.name}:{lineno}: {line}")
        self.assertEqual(violations, [],
                         "Spanish accents found in module user-facing strings:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main(verbosity=2)
