"""Ported upstream test_revision_editorial.py: the G1-G7 evaluation registers a

review without inferring approval; promotion requires exact confirmation and
history. Imports point to the native English engine; Spanish strings are
translated to the engine's English equivalents; JSON keys and gate ids stay
verbatim. The CLI test is exercised in-process.
"""
from __future__ import annotations
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.documentos import create_document
from hermes_business_brain.engine.lib_ce import make_note, split_frontmatter
from hermes_business_brain.engine.operacion import create_source
from hermes_business_brain.engine.revision_editorial import registrar_evaluacion, aprobar_documento
from hermes_business_brain.engine.validar_boveda import validate


class EvaluationDxTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = create("DEMO-EDITORIAL", "Fictitious company", self.root / "boveda")
        create_source(self.vault, "F-PRUEBA-01", "Synthetic reference",
                      "urn:synthetic:test", "nota")
        self.body = self.root / "content_D01.md"
        self.body.write_text(
            "# Direction of an invented company\n\n"
            "## 01 Activity\n\n<!-- kb:id=D01-B001 -->\n"
            "The test team collects the work it performs, distinguishes decisions "
            "from records and uses those distinctions to organize itself.\n\n"
            "## 02 Decisions\n\n<!-- kb:id=D01-B002 -->\n"
            "The synthetic review demands explaining who decides and why, "
            "without simulating contracts or income.\n\n"
            "## CONTROL\n\nThis demonstration does not assert data of any real company.\n",
            encoding="utf8", newline='\n')
        result = create_document(self.vault, "D01", "Fictitious direction", self.body,
                                 sources=["F-PRUEBA-01"], editorial="en_revision")
        self.file = Path(result["ruta"])
        self.act = self.root / "evaluation.json"
        self.backup = self.root / "backups"
        self.set_coverage("suficiente_para_tarea")

    def set_coverage(self, coverage):
        fm, body = split_frontmatter(self.file.read_text(encoding="utf8"))
        fm["cobertura"] = coverage
        self.file.write_text(make_note(fm, body), encoding="utf8", newline='\n')

    def sha(self):
        return hashlib.sha256(self.file.read_bytes()).hexdigest()

    def write_act(self, decision="recomendar_integral", scope=None, gates=None):
        if scope is None:
            scope = ["D01-B001", "D01-B002"]
        if gates is None:
            gates = {f"G{i}": {"estado": "cumple",
                               "fundamento": f"Aspect G{i} verified in the fictitious evaluation."}
                     for i in range(1, 8)}
        act = {"doc_id": "D01", "sha_documento": self.sha(), "decision": decision,
               "revisor": "Fictitious owner",
               "referencia_decision": "Synthetic internal act with scope review",
               "alcance_bloques": scope, "gates": gates}
        self.act.write_text(json.dumps(act, ensure_ascii=False), encoding="utf8", newline='\n')
        return act

    def test_gates_create_audit_not_approval(self):
        self.write_act(decision="recomendar_parcial", scope=["D01-B001"])
        original = self.file.read_bytes()
        result = registrar_evaluacion(self.vault, "D01", self.act, expected_sha=self.sha())
        self.assertEqual(result["decision"], "recomendar_parcial")
        self.assertFalse(result["documento_modificado"])
        self.assertEqual(self.file.read_bytes(), original)
        self.assertEqual(validate(self.vault)["errores"], [])
        self.assertTrue(Path(result["ruta"]).is_file())

    def test_partial_coverage_blocks_full_promotion(self):
        self.set_coverage("parcial")
        self.write_act()
        with self.assertRaises(ValueError):
            registrar_evaluacion(self.vault, "D01", self.act, expected_sha=self.sha())
        self.assertFalse((self.vault / "90_Sistema" / "Evaluaciones_DX").exists())

    def test_missing_critical_gate_prevents_recommendation(self):
        g = {f"G{i}": {"estado": "cumple",
                       "fundamento": "Fictitious evaluation sufficiently argued."}
             for i in range(1, 8)}
        g["G2"] = {"estado": "no_cumple",
                   "fundamento": "Expert criteria missing in the example."}
        self.write_act(gates=g)
        with self.assertRaises(ValueError):
            registrar_evaluacion(self.vault, "D01", self.act, expected_sha=self.sha())
        self.write_act(decision="requiere_cambios", gates=g)
        self.assertEqual(registrar_evaluacion(self.vault, "D01", self.act,
                                              expected_sha=self.sha())["decision"],
                         "requiere_cambios")

    def test_wrong_scope_and_missing_gate_rejected(self):
        self.write_act(scope=["D01-B099"])
        with self.assertRaises(ValueError):
            registrar_evaluacion(self.vault, "D01", self.act, expected_sha=self.sha())
        self.write_act()
        obj = json.loads(self.act.read_text(encoding='utf-8'))
        del obj["gates"]["G7"]
        self.act.write_text(json.dumps(obj), encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            registrar_evaluacion(self.vault, "D01", self.act, expected_sha=self.sha())

    def test_promote_only_after_exact_confirmation_with_history(self):
        self.write_act()
        eid = registrar_evaluacion(self.vault, "D01", self.act,
                                   expected_sha=self.sha())["evaluacion_id"]
        before = self.file.read_bytes()
        oldsha = self.sha()
        with self.assertRaises(ValueError):
            aprobar_documento(self.vault, eid, expected_sha=oldsha,
                              responsable="synthetic operator",
                              referencia_autorizacion="fictitious literal authorization",
                              backup_dir=self.backup, confirmacion="SI")
        self.assertEqual(self.file.read_bytes(), before)
        result = aprobar_documento(self.vault, eid, expected_sha=oldsha,
                                   responsable="synthetic operator",
                                   referencia_autorizacion="fictitious literal authorization",
                                   backup_dir=self.backup,
                                   confirmacion="APPROVE D01 " + oldsha[:12])
        fm, body = split_frontmatter(self.file.read_text(encoding="utf8"))
        self.assertEqual(fm["estado_editorial"], "aprobado")
        self.assertEqual(fm["revision"], "0.2")
        self.assertEqual(fm["revisado_por"], "Fictitious owner")
        self.assertEqual(fm["vigencia"], "sin_verificar")
        self.assertTrue(result["aprobacion_editorial"])
        self.assertFalse(result["aprobacion_semantica_automatica"])
        self.assertEqual((Path(result["respaldo_externo"]) / "anterior.snapshot").read_bytes(),
                         before)
        self.assertEqual(validate(self.vault)["errores"], [])

    def test_stale_sha_blocks_promotion_without_writing(self):
        self.write_act()
        eid = registrar_evaluacion(self.vault, "D01", self.act,
                                   expected_sha=self.sha())["evaluacion_id"]
        oldsha = self.sha()
        fm, body = split_frontmatter(self.file.read_text(encoding='utf-8'))
        fm["fecha_corte"] = "2026-10-27"
        self.file.write_text(make_note(fm, body), encoding='utf-8', newline='\n')
        before = self.file.read_bytes()
        with self.assertRaises(ValueError):
            aprobar_documento(self.vault, eid, expected_sha=oldsha,
                              responsable="synthetic operator",
                              referencia_autorizacion="fictitious literal authorization",
                              backup_dir=self.backup,
                              confirmacion="APPROVE D01 " + oldsha[:12])
        self.assertEqual(self.file.read_bytes(), before)

    def test_cli_evaluate_synthetic(self):
        # In-process adaptation of the upstream cerebro.py subprocess call.
        self.write_act(decision="recomendar_parcial", scope=["D01-B001"])
        result = registrar_evaluacion(self.vault, "D01", self.act, expected_sha=self.sha())
        self.assertEqual(result["doc_id"], "D01")


if __name__ == "__main__":
    unittest.main()
