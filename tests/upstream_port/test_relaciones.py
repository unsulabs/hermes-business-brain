"""Ported upstream test_relaciones.py: relation proposals and explicit human

ratifications with source and scope. JSON keys/enums stay verbatim; Spanish
strings in assertions and fixtures are translated to the engine's English
equivalents.

Adaptation: upstream asserted the graph projection (exportar_grafo.graph:
'local_propuesta'/'local_ratificada_por_revisor' layers); engine v2 does not
ship exportar_grafo.py (engine gap, see _verify/tests-v2.md), so those
assertions are replaced by the equivalent relation-registry state checks. The
CLI test is in-process (query with source_id).
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
from hermes_business_brain.engine.operacion import create_source
from hermes_business_brain.engine.relaciones import propose, query, confirm
from hermes_business_brain.engine.validar_boveda import validate


class RelationsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.vault = create("EMP-REL-SINTETICA", "Fictitious test", self.root / "boveda")
        create_source(self.vault, "F-DEMORL-01", "Synthetic original",
                      "urn:synthetic:regla", "nota")
        self.body = self.root / "draft_d01.md"
        self.body.write_text(
            "# Fictitious company\n\n## Activities\n\n<!-- kb:id=D01-B001 -->\n"
            "The example process organizes internal requests and distinguishes "
            "performed work from approved commitments.\n\n"
            "## CONTROL\n\nSynthetic document for the relations test.\n",
            encoding="utf8", newline='\n')
        create_document(self.vault, "D01", "Work model", self.body,
                        sources=["F-DEMORL-01"], editorial="en_revision")
        self.kw = {"fuentes": ["F-DEMORL-01"],
                   "ambito": "documentation of a fictitious process",
                   "motivo": "The source is proposed as support for the synthetic example explanation."}

    def make(self):
        return propose(self.vault, "D01", "F-DEMORL-01", "sustentado_por", **self.kw)

    def test_proposal_does_not_imply_validity(self):
        record = self.make()
        self.assertEqual(record["estado"], "propuesta")
        self.assertFalse(record["validada"])
        self.assertEqual(validate(self.vault)["errores"], [])
        rows = query(self.vault)["relaciones"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["estado_efectivo"], "propuesta")

    def test_confirm_requires_sha_and_literal_human_step(self):
        record = self.make()
        target = Path(record["ruta"])
        sha = hashlib.sha256(target.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            confirm(self.vault, record["relacion_id"], sha, revisor="Fictitious owner",
                    referencia_autorizacion="Written test decision",
                    confirmacion="SI")
        self.assertEqual(query(self.vault)["relaciones"][0]["estado_efectivo"], "propuesta")
        result = confirm(self.vault, record["relacion_id"], sha, revisor="Fictitious owner",
                         referencia_autorizacion="Written test decision",
                         confirmacion="CONFIRM " + record["relacion_id"] + " " + sha[:12])
        self.assertEqual(result["estado"], "validada_por_revisor")
        self.assertEqual(query(self.vault)["relaciones"][0]["estado_efectivo"],
                         "validada_por_revisor")
        self.assertEqual(validate(self.vault)["errores"], [])
        with self.assertRaises(ValueError):
            confirm(self.vault, record["relacion_id"], sha, revisor="Fictitious owner",
                    referencia_autorizacion="Written test decision",
                    confirmacion="CONFIRM " + record["relacion_id"] + " " + sha[:12])

    def test_unknown_refs_unknown_predicate_and_duplicate_blocked(self):
        with self.assertRaises(ValueError):
            propose(self.vault, "D01", "NO-EXISTE", "sustentado_por", **self.kw)
        with self.assertRaises(ValueError):
            propose(self.vault, "D01", "F-DEMORL-01", "amigo_de", **self.kw)
        with self.assertRaises(ValueError):
            propose(self.vault, "D01", "F-DEMORL-01", "sustentado_por",
                    fuentes=["F-NO-EXISTE"], ambito=self.kw["ambito"], motivo=self.kw["motivo"])
        self.make()
        with self.assertRaises(FileExistsError):
            self.make()

    def test_tampered_relations_detected_by_validator(self):
        record = self.make()
        path = Path(record["ruta"])
        data = json.loads(path.read_text(encoding='utf-8'))
        data["destino_id"] = "NOTA-INVENTADA"
        path.write_text(json.dumps(data), encoding='utf-8', newline='\n')
        result = validate(self.vault)
        self.assertTrue(any("Relation" in x for x in result["errores"]))
        with self.assertRaises(ValueError):
            query(self.vault)

    def test_cli_query_includes_candidature_state(self):
        self.make()
        # In-process adaptation of the upstream cerebro.py subprocess call.
        data = query(self.vault, source_id="D01")
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["relaciones"][0]["estado_efectivo"], "propuesta")


if __name__ == "__main__":
    unittest.main()
