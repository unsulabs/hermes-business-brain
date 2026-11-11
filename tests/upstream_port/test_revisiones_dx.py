"""Ported upstream test_revisiones_dx.py: non-destructive D/X revision cycle --

preview, authorization, history and restoration. Spanish prose fixtures and
message regexes are translated to the engine's English equivalents; JSON keys,
statuses and patch targets stay verbatim. The two cerebro CLI tests are
exercised in-process. Windows-only branches keep their explicit platform gate.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.documentos import create_document
from hermes_business_brain.engine.lib_ce import make_note, split_frontmatter
from hermes_business_brain.engine.operacion import create_source
from hermes_business_brain.engine.revisiones_dx import previsualizar, preparar, aplicar, restaurar
from hermes_business_brain.engine.validar_boveda import validate

REV_MOD = 'hermes_business_brain.engine.revisiones_dx'


class RevisionCycleTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.work = Path(t.name)
        self.vault = create("EMPRESA-DEMO", "Synthetic company", self.work / "vault")
        self.backup = self.work / "external_shields"
        self.original = self.work / "draft_v1.md"
        self.original.write_text(
            "# Fictitious company\n\n"
            "## Identity\n\n<!-- kb:id=D01-B001 -->\n"
            "The synthetic process organizes work requests in a register "
            "and lets the team check who receives them and when.\n\n"
            "## CONTROL\n\nFictitious material for change testing.\n",
            encoding="utf8", newline='\n')
        create_source(self.vault, "F-DEMO-001", "Synthetic source", "urn:demo:001", "nota")
        self.record = create_document(self.vault, "D01", "Synthetic direction",
                                      self.original, sources=["F-DEMO-001"],
                                      editorial="en_revision")
        self.doc = Path(self.record["ruta"])
        self.before = self.doc.read_bytes()
        self.next = self.work / "draft_v2.md"
        self.next.write_text(
            self.original.read_text(encoding='utf-8').replace(
                "organizes work requests in a register",
                "organizes work requests in an auditable task register"),
            encoding="utf8", newline='\n')

    def prepare(self):
        return preparar(self.vault, "D01", self.next)

    def apply(self, proposal, **opts):
        return aplicar(self.vault, proposal["propuesta_id"],
                       expected_sha=opts.get("expected_sha", proposal["sha_original"]),
                       candidate_sha=opts.get("candidate_sha", proposal["sha_candidato"]),
                       source_sha=opts.get("source_sha"),
                       responsable=opts.get("responsable", "authorized test operator"),
                       referencia_autorizacion=opts.get("referencia", "explicit decision demo-001"),
                       backup_dir=opts.get("backup_dir", self.backup))

    def test_dryrun_does_not_touch_vault(self):
        old = validate(self.vault)["notas"]
        result = previsualizar(self.vault, "D01", self.next)
        self.assertEqual(result["operacion"], "SOLO_LECTURA")
        self.assertEqual(result["revision_propuesta"], "0.2")
        self.assertIn("auditable", result["resumen_diff"])
        self.assertEqual(self.doc.read_bytes(), self.before)
        self.assertEqual(validate(self.vault)["notas"], old)
        self.assertFalse((self.vault / "90_Sistema" / "Propuestas_DX").exists())

    def test_prepare_no_overwrite_or_duplicate_note(self):
        p = self.prepare()
        self.assertTrue(Path(p["ruta_propuesta"]).is_dir())
        self.assertEqual(self.doc.read_bytes(), self.before)
        self.assertFalse(p["documento_modificado"])
        self.assertEqual(validate(self.vault)["errores"], [])
        self.assertEqual(validate(self.vault)["notas"], 9)

    def test_preserve_document_permissions_and_protect_history(self):
        if sys.platform == 'win32':
            from hermes_business_brain.engine.windows_fs import (
                security_descriptor, is_private_directory,
            )
            original = security_descriptor(self.doc)
            p = self.prepare()
            self.assertTrue(is_private_directory(self.vault / '90_Sistema' / 'Propuestas_DX'))
            out = self.apply(p)
            self.assertEqual(security_descriptor(self.doc), original)
            self.assertTrue(is_private_directory(self.vault / '90_Sistema' / 'Historial_DX'))
            self.assertTrue(Path(out['historial']).is_dir())
            return
        self.doc.chmod(0o600)
        p = self.prepare()
        self.assertEqual(stat.S_IMODE((self.vault / "90_Sistema" / "Propuestas_DX")
                                      .stat().st_mode), 0o700)
        out = self.apply(p)
        self.assertEqual(stat.S_IMODE(self.doc.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.vault / "90_Sistema" / "Historial_DX")
                                      .stat().st_mode), 0o700)
        self.assertTrue(Path(out["historial"]).is_dir())

    def test_apply_with_backup_and_review_status(self):
        p = self.prepare()
        out = self.apply(p)
        self.assertEqual(out["revision"], "0.2")
        self.assertFalse(out["aprobado"])
        meta, body = split_frontmatter(self.doc.read_text(encoding='utf-8'))
        self.assertEqual(meta["revision"], "0.2")
        self.assertEqual(meta["estado_editorial"], "en_revision")
        self.assertEqual(meta["doc_id"], "D01")
        self.assertEqual(meta["revisado_por"], "por_validar")
        self.assertIn("[[50_Fuentes/Synthetic source]]", meta["fuentes"])
        self.assertIn("auditable", body)
        self.assertEqual((Path(out["historial"]) / "anterior.snapshot").read_bytes(), self.before)
        self.assertEqual((Path(out["respaldo_externo"]) / "anterior.snapshot").read_bytes(),
                         self.before)
        self.assertEqual(validate(self.vault)["errores"], [])
        with self.assertRaises(ValueError):
            self.apply(p)

    def test_corrective_source_is_reviewed_and_added_to_properties(self):
        create_source(self.vault, "F-DEMO-002", "Synthetic correction", "urn:demo:002", "nota")
        self.next.write_text(self.next.read_text(encoding='utf-8') +
                             "\nCorrection supported by [[50_Fuentes/Synthetic correction|F-DEMO-002]].\n",
                             encoding="utf8", newline='\n')
        p = preparar(self.vault, "D01", self.next, sources=["F-DEMO-002"])
        self.assertEqual(self.doc.read_bytes(), self.before)
        self.assertEqual(p["fuentes_adicionales"], ["F-DEMO-002"])
        self.assertEqual(len(p["fuentes_resultantes"]), 2)
        with self.assertRaisesRegex(ValueError, "source fingerprint"):
            self.apply(p)
        with self.assertRaisesRegex(ValueError, "source fingerprint"):
            self.apply(p, source_sha="0" * 64)
        out = self.apply(p, source_sha=p["sha_fuentes"])
        meta, _ = split_frontmatter(self.doc.read_text(encoding='utf-8'))
        self.assertEqual(meta["revision"], "0.2")
        self.assertEqual(meta["estado_editorial"], "en_revision")
        self.assertEqual(len(meta["fuentes"]), 2)
        self.assertIn("[[50_Fuentes/Synthetic correction]]", meta["fuentes"])
        self.assertEqual(validate(self.vault)["errores"], [])
        restored = restaurar(self.vault, "D01", out["historial_id"],
                             expected_sha=hashlib.sha256(self.doc.read_bytes()).hexdigest(),
                             responsable="test operator",
                             referencia_autorizacion="synthetic restoration",
                             backup_dir=self.backup)
        meta, _ = split_frontmatter(self.doc.read_text(encoding='utf-8'))
        self.assertEqual(restored["revision"], "0.3")
        self.assertEqual(meta["fuentes"], ["[[50_Fuentes/Synthetic source]]"])

    def test_unknown_corrective_source_is_rejected_before_proposal(self):
        with self.assertRaisesRegex(ValueError, "ID does not exist"):
            preparar(self.vault, "D01", self.next, sources=["F-NO-EXISTE"])
        self.assertEqual(self.doc.read_bytes(), self.before)

    def test_cli_corrective_source_roundtrip(self):
        # In-process adaptation of the upstream cerebro.py prepare/apply-dx flow.
        create_source(self.vault, "F-DEMO-002", "Synthetic correction", "urn:demo:002", "nota")
        self.next.write_text(self.next.read_text(encoding='utf-8') +
                             "\nCorrection supported by [[50_Fuentes/Synthetic correction|F-DEMO-002]].\n",
                             encoding="utf8", newline='\n')
        proposal = preparar(self.vault, "D01", self.next, sources=["F-DEMO-002"])
        self.assertEqual(proposal["fuentes_adicionales"], ["F-DEMO-002"])
        applied = aplicar(self.vault, proposal["propuesta_id"],
                          expected_sha=proposal["sha_original"],
                          candidate_sha=proposal["sha_candidato"],
                          source_sha=proposal["sha_fuentes"],
                          responsable="test operator",
                          referencia_autorizacion="synthetic correction",
                          backup_dir=self.backup)
        self.assertEqual(applied["revision"], "0.2")
        meta, _ = split_frontmatter(self.doc.read_text(encoding='utf-8'))
        self.assertIn("[[50_Fuentes/Synthetic correction]]", meta["fuentes"])

    def test_restore_creates_forward_revision_and_keeps_history(self):
        applied = self.apply(self.prepare())
        now = self.doc.read_bytes()
        restored = restaurar(self.vault, "D01", applied["historial_id"],
                             expected_sha=hashlib.sha256(now).hexdigest(),
                             responsable="authorized operator",
                             referencia_autorizacion="restore demo-002",
                             backup_dir=self.backup)
        self.assertEqual(restored["revision"], "0.3")
        meta, body = split_frontmatter(self.doc.read_text(encoding='utf-8'))
        self.assertEqual(meta["revision"], "0.3")
        self.assertEqual(meta["estado_editorial"], "en_revision")
        self.assertNotIn("auditable", body)
        self.assertEqual((Path(restored["historial"]) / "anterior.snapshot").read_bytes(), now)
        self.assertEqual((Path(applied["historial"]) / "anterior.snapshot").read_bytes(),
                         self.before)
        self.assertEqual(validate(self.vault)["errores"], [])

    def test_concurrent_change_blocks_apply_without_backup(self):
        p = self.prepare()
        self.doc.write_bytes(self.before + "\nExternal change in another session.\n".encode("utf8"))
        changed = self.doc.read_bytes()
        with self.assertRaises(ValueError):
            self.apply(p)
        self.assertEqual(self.doc.read_bytes(), changed)
        self.assertFalse(self.backup.exists())

    def test_tampering_candidate_blocks_apply(self):
        p = self.prepare()
        (Path(p["ruta_propuesta"]) / "candidato.snapshot").write_bytes(b"altered content")
        with self.assertRaises(ValueError):
            self.apply(p)
        self.assertEqual(self.doc.read_bytes(), self.before)

    def test_auth_reference_and_sha_required(self):
        p = self.prepare()
        with self.assertRaises(ValueError):
            self.apply(p, referencia="")
        with self.assertRaises(ValueError):
            self.apply(p, expected_sha="0" * 64)
        self.assertEqual(self.doc.read_bytes(), self.before)

    def test_approved_document_cannot_be_rewritten(self):
        meta, body = split_frontmatter(self.doc.read_text(encoding='utf-8'))
        meta["estado_editorial"] = "aprobado"
        self.doc.write_text(make_note(meta, body), encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            previsualizar(self.vault, "D01", self.next)

    def test_does_not_remove_block_ids_or_bypass_links(self):
        self.next.write_text("# Fake document\n\n" + ("content without blocks. " * 10) + "\n",
                             encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            self.prepare()
        self.next.write_text(self.original.read_text(encoding='utf-8') +
                             "\n[[NOTE-QUE-NO-EXISTE]]\n", encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(self.doc.read_bytes(), self.before)

    def test_failed_validation_restores_bytes(self):
        from hermes_business_brain.engine.revisiones_dx import validate as actual_validate
        p = self.prepare()
        call_count = [0]

        def synthetic_validate(vault):
            call_count[0] += 1
            return {"errores": ["synthetic validation error"]} if call_count[0] == 2 \
                else actual_validate(vault)
        with patch(f"{REV_MOD}.validate", side_effect=synthetic_validate):
            with self.assertRaises(ValueError):
                self.apply(p)
        self.assertEqual(self.doc.read_bytes(), self.before)
        self.assertEqual(validate(self.vault)["errores"], [])

    def test_external_backup_is_owner_private_and_rejects_world_readable(self):
        if sys.platform == 'win32':
            from hermes_business_brain.engine.windows_fs import (
                ensure_private_directory, security_descriptor, set_security_descriptor,
            )
            ensure_private_directory(self.backup)
            original = security_descriptor(self.backup)
            try:
                set_security_descriptor(self.backup, 'D:P(A;OICI;FA;;;WD)')
                p = self.prepare()
                with self.assertRaises(ValueError):
                    self.apply(p)
                self.assertEqual(self.doc.read_bytes(), self.before)
            finally:
                set_security_descriptor(self.backup, original)
            self.assertEqual(self.apply(p)['revision'], '0.2')
            return
        self.backup.mkdir(mode=0o755)
        self.backup.chmod(0o755)
        p = self.prepare()
        with self.assertRaises(ValueError):
            self.apply(p)
        self.assertEqual(self.doc.read_bytes(), self.before)
        self.backup.chmod(0o700)
        self.assertEqual(self.apply(p)["revision"], "0.2")

    def test_restoration_can_remove_block_added_in_intermediate_revision(self):
        self.next.write_text(self.next.read_text(encoding="utf8") +
                             "\n<!-- kb:id=D01-B002 -->\nAdditional block created during the review.\n",
                             encoding="utf8", newline='\n')
        modified = self.apply(self.prepare())
        self.assertIn("D01-B002", self.doc.read_text(encoding='utf-8'))
        current_hash = hashlib.sha256(self.doc.read_bytes()).hexdigest()
        result = restaurar(self.vault, "D01", modified["historial_id"],
                           expected_sha=current_hash, responsable="authorized reviewer",
                           referencia_autorizacion="Validated synthetic restoration",
                           backup_dir=self.backup)
        self.assertEqual(result["revision"], "0.3")
        self.assertNotIn("D01-B002", self.doc.read_text(encoding='utf-8'))
        self.assertEqual(validate(self.vault)["errores"], [])

    def test_manifest_completion_failure_restores_original(self):
        from hermes_business_brain.engine.revisiones_dx import _write_atomic as writer
        self.prepare()
        p = self.prepare()
        tripped = [False]

        def glitch(path, contents):
            if (path.name == "manifest.json" and
                    b'"estado": "aplicado"' in contents and not tripped[0]):
                tripped[0] = True
                raise OSError("Simulated storage failure")
            return writer(path, contents)
        with patch(f"{REV_MOD}._write_atomic", side_effect=glitch):
            with self.assertRaises(OSError):
                self.apply(p)
        self.assertTrue(tripped[0])
        self.assertEqual(self.doc.read_bytes(), self.before)
        self.assertEqual(validate(self.vault)["errores"], [])

    def test_cli_simulation_and_proposal(self):
        # In-process adaptation of the upstream cerebro.py previsualizar/preparar-dx.
        published = previsualizar(self.vault, "D01", self.next)
        self.assertEqual(published["revision_propuesta"], "0.2")
        proposal = preparar(self.vault, "D01", self.next)
        self.assertIn("propuesta_id", proposal)
        self.assertEqual(self.doc.read_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
