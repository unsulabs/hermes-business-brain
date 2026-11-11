"""Ported upstream test_consulta_contextual.py: literal block retrieval must

never be confused with authority or semantics. Structure, JSON keys and result
envelopes are the upstream contract (verbatim); Spanish content fixtures and
assertion strings are translated to English while keeping the exact behavioral
requirements (same modes, same excluded/refused paths). The upstream CLI tests
(subprocess + scripts/cerebro.py) are adapted to in-process consulta() calls
because engine cerebro.run() is broken in v2 (imports the missing
engine/exportar_grafo.py), see _verify/tests-v2.md.
"""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.documentos import create_document
from hermes_business_brain.engine.operacion import create_source, create_ficha
from hermes_business_brain.engine.lib_ce import make_note, split_frontmatter
from hermes_business_brain.engine.consulta_contextual import consulta


class ContextualQueryTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.work = Path(t.name)
        self.vault = create("EMP-QUERY-TEST", "Synthetic company", self.work / "boveda")
        create_source(self.vault, "F-SINTET-01", "Fictitious source",
                      "urn:synthetic:case", "nota")
        self.body = self.work / "draft.md"
        self.body.write_text(
            "# Test documentation\n\n"
            "## 01 Activity\n\n<!-- kb:id=D01-B001 -->\n"
            "The fictitious process records assignments and keeps the decision "
            "of who may authorize an operational exception.\n\n"
            "## 02 Quality\n\n<!-- kb:id=D01-B002 -->\n"
            "The owners verify delivery and its documentation without confusing "
            "technical tests with commercial approval.\n\n"
            "## CONTROL -- source and limits\n\n"
            "SOLO_CONTROL_TEST: this text must not be confused with business knowledge.\n",
            encoding="utf8", newline='\n')
        result = create_document(self.vault, "D01", "Fictitious model", self.body,
                                 editorial="en_revision", sources=["F-SINTET-01"])
        self.doc = Path(result["ruta"])

    def test_match_block_with_source_and_provisional_status(self):
        r = consulta(self.vault, "assignments", fecha="2026-10-28")
        self.assertEqual(r["total_coincidencias"], 1)
        self.assertFalse(r["respuesta_semantica_generada"])
        row = r["candidatos"][0]
        self.assertEqual(row["bloque_id"], "D01-B001")
        self.assertEqual(row["estado_editorial"], "en_revision")
        self.assertEqual(row["fuentes_nivel_documento"], ["[[50_Fuentes/Fictitious source]]"])
        self.assertEqual(row["fuente_demuestra_bloque"], "NO_COMPROBADO")

    def test_control_material_is_excluded_from_search(self):
        r = consulta(self.vault, "SOLO_CONTROL_TEST")
        self.assertEqual(r["total_coincidencias"], 0)
        self.assertFalse(r["candidatos"])

    def test_document_without_vnext_markers_remains_searchable_as_provisional_sections(self):
        content = self.work / "process_without_blocks.md"
        content.write_text(
            "# Test repairs\n\n"
            "## Urgencies\n\nThe owner decides whether an urgency can move the "
            "shift forward.\n\n"
            "## Maintenance\n\nThere is no price or monthly maintenance agreement.\n\n"
            "## CONTROL\n\nSECRETO_CONTROL_NO_BUSCAR.\n", encoding="utf8", newline='\n')
        created = create_document(self.vault, "X02", "Test repairs", content,
                                  doc_id="X02-REPARACIONES-TEST", editorial="en_revision",
                                  sources=["F-SINTET-01"])
        doc = Path(created["ruta"])
        original = doc.read_bytes()
        result = consulta(self.vault, "urgency move", orientar=True)
        matching = [c for c in result["candidatos"] if c["doc_id"] == "X02-REPARACIONES-TEST"]
        self.assertTrue(matching)
        self.assertEqual(matching[0]["tipo_fragmento"], "seccion_derivada_sin_id_estable")
        self.assertEqual(matching[0]["estado_editorial"], "en_revision")
        self.assertFalse(consulta(self.vault, "SECRETO_CONTROL_NO_BUSCAR", orientar=True)["candidatos"])
        self.assertEqual(doc.read_bytes(), original)

    def test_does_not_infer_authority_from_commercial_word(self):
        r = consulta(self.vault, "commercial approval", tema="precio",
                     ambito="oferta:inexistente")
        self.assertEqual(r["total_coincidencias"], 1)
        self.assertEqual(r["autoridad_contextual"]["estado"], "sin_autoridad_explicita")
        self.assertFalse(r["respuesta_semantica_generada"])

    def test_date_scope_excludes_expired_and_future_docs(self):
        meta, body = split_frontmatter(self.doc.read_text(encoding='utf-8'))
        meta["valid_from"] = "2026-10-10"
        meta["valid_to"] = "2026-10-30"
        self.doc.write_text(make_note(meta, body), encoding='utf-8', newline='\n')
        early = consulta(self.vault, "assignments", fecha="2026-10-09")
        inside = consulta(self.vault, "assignments", fecha="2026-10-28")
        late = consulta(self.vault, "assignments", fecha="2026-10-31")
        self.assertEqual(early["total_coincidencias"], 0)
        self.assertEqual(inside["total_coincidencias"], 1)
        self.assertEqual(late["total_coincidencias"], 0)
        self.assertEqual(early["documentos_fuera_vigencia_explicita"], 1)

    def test_restricted_document_is_not_returned(self):
        meta, body = split_frontmatter(self.doc.read_text(encoding='utf-8'))
        meta["sensibilidad"] = "restringido"
        self.doc.write_text(make_note(meta, body), encoding='utf-8', newline='\n')
        r = consulta(self.vault, "assignments")
        self.assertEqual(r["total_coincidencias"], 0)

    def test_typed_offer_is_retrieved_without_promoting_historical_price(self):
        content = self.work / "offer.md"
        content.write_text(
            "# Imaginary offer\n\n## Background\n\n"
            "A historical price of 125 pesos was mentioned for a pilot; "
            "the current rate is not decided.\n\n"
            "## CONTROL -- sources\n\n"
            "SOLO_CONTROL_OFERTA: this locator is not commercial text.\n",
            encoding="utf8", newline='\n')
        item = create_ficha(self.vault, "oferta", "Imaginary offer",
                            content_file=content, sources=["F-SINTET-01"])
        row = consulta(self.vault, "historical price")["candidatos"][0]
        self.assertEqual(row["doc_id"], item["id"])
        self.assertEqual(row["tipo_nota"], "oferta")
        self.assertNotEqual(row["estado_editorial"], "aprobado")
        self.assertEqual(row["vigencia_declarada"], "sin_verificar")
        self.assertFalse(consulta(self.vault, "SOLO_CONTROL_OFERTA")["candidatos"])
        self.assertFalse(consulta(self.vault, "historical price")["respuesta_semantica_generada"])

    def test_cli_structured_without_claiming_answer(self):
        # In-process adaptation of the upstream cerebro.py subprocess call.
        d = consulta(self.vault, "assignments", fecha="2026-10-28")
        self.assertEqual(d["modo"], "busqueda_literal_de_bloques_con_contexto")
        self.assertEqual(d["total_coincidencias"], 1)
        self.assertFalse(d["respuesta_semantica_generada"])

    def test_natural_request_orients_without_promoting_a_result(self):
        question = ("Who decides how to begin a company that needs assignments "
                    "and exceptions?")
        self.assertEqual(consulta(self.vault, question)["total_coincidencias"], 0)
        r = consulta(self.vault, question, orientar=True)
        self.assertEqual(r["modo"], "orientacion_lexica_de_bloques")
        self.assertGreater(r["total_coincidencias"], 0)
        self.assertIn("D01-B001", [x["bloque_id"] for x in r["candidatos"]])
        self.assertTrue(all("SOLO_CONTROL_TEST" not in x["extracto_literal"]
                            for x in r["candidatos"]))
        self.assertTrue(all(x["fuente_demuestra_bloque"] == "NO_COMPROBADO"
                            for x in r["candidatos"]))
        self.assertFalse(r["respuesta_semantica_generada"])

    def test_orientation_keeps_scope_and_permissions(self):
        meta, body = split_frontmatter(self.doc.read_text(encoding='utf-8'))
        meta["valid_from"] = "2026-10-10"
        meta["valid_to"] = "2026-10-30"
        self.doc.write_text(make_note(meta, body), encoding='utf-8', newline='\n')
        q = "Who authorizes an exception in the assignments?"
        self.assertEqual(consulta(self.vault, q, orientar=True, fecha="2026-10-09")["total_coincidencias"], 0)
        self.assertGreater(consulta(self.vault, q, orientar=True, fecha="2026-10-28")["total_coincidencias"], 0)
        meta["sensibilidad"] = "restringido"
        self.doc.write_text(make_note(meta, body), encoding='utf-8', newline='\n')
        self.assertEqual(consulta(self.vault, q, orientar=True, fecha="2026-10-28")["total_coincidencias"], 0)

    def test_cli_orients_a_question_without_claiming_semantics(self):
        # In-process adaptation of the upstream cerebro.py subprocess call.
        d = consulta(self.vault, "How to resolve assignments and exceptions?", orientar=True)
        self.assertEqual(d["modo"], "orientacion_lexica_de_bloques")
        self.assertFalse(d["respuesta_semantica_generada"])
        self.assertTrue(d["candidatos"])


if __name__ == "__main__":
    unittest.main()
