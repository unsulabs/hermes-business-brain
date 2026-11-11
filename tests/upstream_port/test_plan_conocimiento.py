"""Ported upstream test_plan_conocimiento.py: knowledge planning -- identity,

relations, sources and no over-creation (read-only audit). Structure and all
JSON keys stay verbatim; Spanish free text and assertion strings are
translated to the engine's English equivalents. The CLI test is in-process.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.documentos import create_document
from hermes_business_brain.engine.lib_ce import make_note, split_frontmatter
from hermes_business_brain.engine.operacion import create_ficha, create_source
from hermes_business_brain.engine.plan_conocimiento import planificar


class DistributionTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = create("FICTICIA", "Test company", self.root / "vault")
        create_source(self.vault, "F-DEMO-001", "Fictitious conversation",
                      "urn:synthetic:uno", "nota")
        body = self.root / "d01.md"
        body.write_text("# Example company direction\n\n## Business\n\n"
                        "<!-- kb:id=D01-B001 -->\nThe fictitious group identifies "
                        "work situations and analyzes the value contributed by "
                        "decisions shared in its projects.\n\n"
                        "## CONTROL\n\nSynthetic test material.\n",
                        encoding="utf8", newline='\n')
        doc = create_document(self.vault, "D01", "Direction", body,
                              editorial="en_revision", sources=["F-DEMO-001"])
        self.doc = Path(doc["ruta"])
        self.input = self.root / "plan.json"

    def sample(self):
        return {
            "pregunta": "Organize independent aspects of a fictitious business conversation",
            "asuntos": [
                {"clave": "modelo-valor", "criterio": "The direction has expressed a criterion of the general model and its scope.",
                 "por_que_importa": "Needed to compare model decisions without duplicating offers.",
                 "fuentes": ["F-DEMO-001"]},
                {"clave": "oferta-servicio", "criterio": "The team explores a service whose commercial conditions may change.",
                 "por_que_importa": "The offer has terms and periods independent of the strategy.",
                 "fuentes": ["F-DEMO-001"]},
                {"clave": "proceso-servicio", "criterio": "The work needs a process other people can execute and review.",
                 "por_que_importa": "It allows delegating tasks without re-reading the whole strategy.",
                 "fuentes": ["F-DEMO-001"]},
                {"clave": "detalle-pasajero", "criterio": "An isolated anecdote does not automatically become company policy.",
                 "por_que_importa": "It stays in its source without increasing the number of notes.",
                 "fuentes": ["F-DEMO-001"]}],
            "unidades": [
                {"clave": "direccion", "titulo": "Model synthesis", "accion": "revisar",
                 "tipo": "documento", "clase": "D01", "id_existente": "D01",
                 "razon_identidad": "The synthesis integrates strategic decisions and links autonomous offers and processes.",
                 "asuntos": ["modelo-valor"], "etiquetas": ["direccion/modelo-valor"]},
                {"clave": "oferta", "titulo": "Offer under study", "accion": "crear",
                 "tipo": "oferta",
                 "razon_identidad": "The offer has a validity and conditions that evolve independently.",
                 "asuntos": ["oferta-servicio"], "etiquetas": ["comercial/ofertas"]},
                {"clave": "proceso", "titulo": "Documented process", "accion": "crear",
                 "tipo": "proceso",
                 "razon_identidad": "The process supports use, updates and owners different from the direction document.",
                 "asuntos": ["proceso-servicio"], "etiquetas": ["operacion/procesos"]},
                {"clave": "detalle", "titulo": "Isolated comment", "accion": "no_crear",
                 "razon_identidad": "The comment does not need a new entity and can remain in the original source.",
                 "asuntos": ["detalle-pasajero"]}],
            "relaciones": [
                {"origen": "direccion", "destino": "oferta", "predicado": "refiere_a",
                 "ambito": "strategic synthesis", "fundamento": "The direction links the offer without copying all its conditions."},
                {"origen": "direccion", "destino": "proceso", "predicado": "refiere_a",
                 "ambito": "operational execution", "fundamento": "The direction cites the operable process without duplicating instructions."}]
        }

    def save(self, data):
        self.input.write_text(json.dumps(data, ensure_ascii=False), encoding="utf8", newline='\n')

    def test_plan_connected_and_read_only(self):
        self.save(self.sample())
        original = self.doc.read_bytes()
        notes = set(self.vault.rglob("*.md"))
        r = planificar(self.vault, self.input)
        self.assertEqual(r["asuntos_detectados"], 4)
        self.assertEqual(len(r["unidades_propuestas"]), 4)
        self.assertEqual(len(r["relaciones_candidatas"]), 2)
        self.assertTrue(r["plan_consistente"])
        self.assertFalse(r["documentos_modificados"])
        self.assertEqual(notes, set(self.vault.rglob("*.md")))
        self.assertEqual(original, self.doc.read_bytes())

    def test_monolith_requires_rethinking(self):
        p = self.sample()
        p["unidades"] = [{
            "clave": "direccion", "titulo": "All ideas in D01",
            "accion": "revisar", "tipo": "documento", "clase": "D01", "id_existente": "D01",
            "razon_identidad": "For convenience it was decided to place commercial and operational topics in a single section.",
            "asuntos": [a["clave"] for a in p["asuntos"]],
            "etiquetas": ["direccion/modelo-valor"]}]
        p["relaciones"] = []
        self.save(p)
        result = planificar(self.vault, self.input)
        self.assertTrue(any("POSIBLE_MONOLITO" in s for s in result["advertencias"]))
        self.assertFalse(result["plan_consistente"])

    def test_existing_units_own_other_subjects_without_false_monolith(self):
        offer = create_ficha(self.vault, "oferta", "Already documented offer",
                             sources=["F-DEMO-001"])
        process = create_ficha(self.vault, "proceso", "Already documented process",
                               sources=["F-DEMO-001"])
        p = self.sample()
        p["unidades"][0].update({
            "titulo": "Transversal economy", "accion": "crear", "clase": "D05",
            "razon_identidad": "A transversal economic decision requires a history distinct from the offer and process conditions."})
        p["unidades"][0].pop("id_existente")
        p["unidades"][1].update({
            "titulo": "Already documented offer", "accion": "referenciar",
            "id_existente": offer["id"]})
        p["unidades"][2].update({
            "titulo": "Already documented process", "accion": "referenciar",
            "id_existente": process["id"]})
        self.save(p)
        result = planificar(self.vault, self.input)
        self.assertTrue(result["plan_consistente"])
        self.assertFalse(any("POSIBLE_MONOLITO" in s for s in result["advertencias"]))
        self.assertEqual(result["asuntos_detectados"], 4)

    def test_double_owner_is_rejected(self):
        p = self.sample()
        p["unidades"][1]["asuntos"].append("modelo-valor")
        self.save(p)
        with self.assertRaisesRegex(ValueError, "two canonical owners"):
            planificar(self.vault, self.input)

    def test_do_not_create_second_existing_D01(self):
        p = self.sample()
        p["unidades"][0]["accion"] = "crear"
        del p["unidades"][0]["id_existente"]
        self.save(p)
        with self.assertRaisesRegex(ValueError, "already exists"):
            planificar(self.vault, self.input)

    def test_missing_sources_warn_and_bad_tags_block(self):
        p = self.sample()
        p["asuntos"][0]["fuentes"] = ["F-NO-EXISTE"]
        self.save(p)
        result = planificar(self.vault, self.input)
        self.assertEqual(result["fuentes_pendientes"], ["F-NO-EXISTE"])
        self.assertFalse(result["plan_consistente"])
        p = self.sample()
        p["unidades"][1]["etiquetas"] = ["identifiable person"]
        self.save(p)
        with self.assertRaisesRegex(ValueError, "tags"):
            planificar(self.vault, self.input)

    def test_cli_plan(self):
        self.save(self.sample())
        # In-process adaptation of the upstream cerebro.py subprocess call.
        data = planificar(self.vault, self.input)
        self.assertEqual(data["modo"], "SOLO_LECTURA")

    def test_tag_properties_on_new_notes(self):
        fiche = create_ficha(self.vault, "proceso", "Synthetic process",
                             sources=["F-DEMO-001"], tags=["operacion/procesos"])
        fm, _ = split_frontmatter(Path(fiche["ruta"]).read_text(encoding='utf-8'))
        self.assertEqual(fm["tags"], ["operacion/procesos"])
        text = self.root / "d02.md"
        text.write_text("# Fictitious market\n\n## Situation\n\n"
                        "The synthetic organization explores a need with different buyers "
                        "and records research hypotheses.",
                        encoding="utf8", newline='\n')
        d = create_document(self.vault, "D02", "Fictitious market", text,
                            tags=["mercado/investigacion"])
        fm, _ = split_frontmatter(Path(d["ruta"]).read_text(encoding='utf-8'))
        self.assertEqual(fm["tags"], ["mercado/investigacion"])
        with self.assertRaisesRegex(ValueError, "tags"):
            create_ficha(self.vault, "oferta", "Do not use", tags=["Full name"])

    def test_developed_ficha_has_content_without_placeholders(self):
        file = self.root / "operation.md"
        content = ("# Test process\n\n## Start\n\n"
                   "When a fictitious request occurs, the team records the owners and "
                   "confirms the work objective before adjusting the tools and starting "
                   "the reviews.\n")
        file.write_text(content, encoding="utf8", newline='\n')
        out = create_ficha(self.vault, "proceso", "Synthetic operation",
                           content_file=file, sources=["F-DEMO-001"],
                           tags=["operacion/procesos"])
        meta, body = split_frontmatter(Path(out["ruta"]).read_text(encoding='utf-8'))
        self.assertEqual(body, content)
        self.assertTrue(out["nota_desarrollada"])
        self.assertEqual(meta["tags"], ["operacion/procesos"])
        self.assertNotIn("Por desarrollar", body)

    def test_single_topic_does_not_require_artificial_no_crear(self):
        p = self.sample()
        p["asuntos"] = [p["asuntos"][0]]
        p["unidades"] = [p["unidades"][0]]
        p["relaciones"] = []
        self.save(p)
        result = planificar(self.vault, self.input)
        self.assertTrue(result["plan_consistente"])
        self.assertEqual(result["advertencias"], [])
        self.assertTrue(result["recomendaciones"])

    def test_explicitly_independent_notes_need_no_fake_relation(self):
        p = self.sample()
        p["relaciones"] = []
        p["justificacion_sin_relaciones"] = (
            "The offer and the process are completely independent objects in this "
            "synthetic project, without a confirmed dependency link.")
        self.save(p)
        result = planificar(self.vault, self.input)
        self.assertTrue(result["plan_consistente"])
        self.assertFalse(result["relaciones_candidatas"])

    def test_x_id_is_not_document_class(self):
        p = self.sample()
        p["unidades"][1].update({"tipo": "documento", "clase": "X01-IDENTIDAD-TEST"})
        self.save(p)
        with self.assertRaisesRegex(ValueError, "document class must be"):
            planificar(self.vault, self.input)

    def test_detect_existing_D_family_even_if_yaml_id_is_different(self):
        fm, body = split_frontmatter(self.doc.read_text(encoding="utf8"))
        fm["id"] = "ID-DIRECCION-CANONICA"
        self.doc.write_text(make_note(fm, body), encoding="utf8", newline='\n')
        p = self.sample()
        p["unidades"][0].update({"accion": "crear", "id_existente": None})
        self.save(p)
        with self.assertRaisesRegex(ValueError, "already exists"):
            planificar(self.vault, self.input)

    def test_duplicate_entity_title_warns_without_creating_another(self):
        note = create_ficha(self.vault, "oferta", "Offer under study",
                            sources=["F-DEMO-001"])
        p = self.sample()
        self.save(p)
        before = Path(note["ruta"]).read_bytes()
        result = planificar(self.vault, self.input)
        self.assertFalse(result["plan_consistente"])
        self.assertEqual(result["posibles_duplicados"][0]["unidad"], "oferta")
        self.assertEqual(result["posibles_duplicados"][0]["ids_existentes"], [note["id"]])
        self.assertEqual(Path(note["ruta"]).read_bytes(), before)

    def test_no_crear_cannot_be_relation_endpoint(self):
        p = self.sample()
        p["relaciones"].append({
            "origen": "direccion", "destino": "detalle", "predicado": "refiere_a",
            "ambito": "fictitious anecdote",
            "fundamento": "An incorrect synthetic relation to something that will have no note."})
        self.save(p)
        with self.assertRaisesRegex(ValueError, "Cannot link"):
            planificar(self.vault, self.input)

    def test_plan_inside_vault_is_rejected(self):
        self.save(self.sample())
        inside = self.vault / "90_Sistema" / "plan.json"
        inside.write_bytes(self.input.read_bytes())
        with self.assertRaisesRegex(ValueError, "outside the private vault"):
            planificar(self.vault, inside)


if __name__ == "__main__":
    unittest.main()
