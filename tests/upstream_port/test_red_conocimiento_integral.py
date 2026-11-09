"""Ported upstream test_red_conocimiento_integral.py: synthetic walkthrough

INSTALL -> ARCHITECTURE -> NOTES -> LINKS -> MAP -> ANOTHER SESSION. The plan
must be audited without copying any template; the original notes and views
must stay byte-identical. Spanish free text is translated to English (the
structure and all JSON keys stay verbatim); the upstream cerebro.py subprocess
step is exercised in-process.
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
from hermes_business_brain.engine.operacion import create_source, create_ficha, summary
from hermes_business_brain.engine.plan_conocimiento import planificar
from hermes_business_brain.engine.relaciones import propose, query
from hermes_business_brain.engine.mapa_conocimiento import previsualizar, publicar, MAP_MD, MAP_CANVAS
from hermes_business_brain.engine.consulta_contextual import consulta
from hermes_business_brain.engine.validar_boveda import validate


class RedPortableIntegralTest(unittest.TestCase):
    def test_new_company_develops_connected_knowledge_without_copying_templates(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        private = Path(temp.name)
        vault = create("NEGOCIO-PORTABLE", "Hypothetical company", private / "empresa")
        self.assertEqual(validate(vault)["errores"], [])
        config = (vault / "90_Sistema" / "config_empresa.yaml").read_text(encoding='utf-8')
        self.assertIn("0.2.0", config)
        vista = (vault / "90_Sistema" / "Vistas" / "Ofertas.base")
        original_vista = vista.read_bytes()

        create_source(vault, "F-TEST-001", "Imaginary statement",
                      "urn:synthetic:conversation", "entrevista")
        direction = private / "direction.md"
        direction.write_text(
            "# Direction of a fictitious business\n\n"
            "## Model and criteria\n\n<!-- kb:id=D01-B001 -->\n"
            "The fictitious organization decides which activities to prioritize and "
            "how to transmit the decisions of the team that handles its projects.\n\n"
            "## CONTROL\n\nThere are no confirmed sales in this example.\n",
            encoding="utf8", newline='\n')
        d01 = create_document(vault, "D01", "Fictitious direction", direction,
                              tags=["direccion/modelo-valor"], sources=["F-TEST-001"],
                              editorial="en_revision")
        original_d01 = Path(d01["ruta"]).read_bytes()

        plan = {
            "pregunta": "Distribute fictitious decisions, offer and process without copying information",
            "asuntos": [
                {"clave": "principio", "criterio": "The owner defines a general orientation for the fictitious operation.",
                 "fuentes": ["F-TEST-001"], "por_que_importa": "The direction serves to compare alternatives without holding every rule."},
                {"clave": "producto", "criterio": "The team considers an offer with a specific scope and changing conditions.",
                 "fuentes": ["F-TEST-001"], "por_que_importa": "The offer needs its commercial state and independent references."},
                {"clave": "flujo", "criterio": "The business documents a recurring sequence so other people can execute it.",
                 "fuentes": ["F-TEST-001"], "por_que_importa": "The sequence is maintained without rewriting the strategic vision."}],
            "unidades": [
                {"clave": "direccion", "titulo": "Fictitious direction", "tipo": "documento",
                 "clase": "D01", "accion": "referenciar", "id_existente": "D01",
                 "razon_identidad": "D01 already exists and must be a reference of the model without duplicating commercial conditions.",
                 "asuntos": ["principio"], "etiquetas": ["direccion/modelo-valor"]},
                {"clave": "oferta", "titulo": "Imaginary service", "tipo": "oferta",
                 "accion": "crear", "razon_identidad": "The offer has a price and a scope revisable with its own history.",
                 "asuntos": ["producto"], "etiquetas": ["comercial/ofertas"]},
                {"clave": "proceso", "titulo": "Imaginary process", "tipo": "proceso",
                 "accion": "crear", "razon_identidad": "The flow has owners and versions that can evolve separately.",
                 "asuntos": ["flujo"], "etiquetas": ["operacion/procesos"]}],
            "relaciones": [
                {"origen": "direccion", "destino": "oferta", "predicado": "refiere_a",
                 "ambito": "general synthesis", "fundamento": "The direction document must link an offer without duplicating it."},
                {"origen": "direccion", "destino": "proceso", "predicado": "refiere_a",
                 "ambito": "operational work", "fundamento": "The synthesis points to the execution procedure without rewriting it."}]}
        plan_file = private / "plan.json"
        plan_file.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8', newline='\n')
        tracked = set(vault.rglob("*.md"))
        plan_result = planificar(vault, plan_file)
        self.assertTrue(plan_result["plan_consistente"])
        self.assertEqual(set(vault.rglob("*.md")), tracked)

        paths = []
        for typ, title, text, tags in [
            ("oferta", "Imaginary service",
             "# Imaginary service\n\n## Scope\n\n"
             "Offer accompaniment only if the test client accepts a scope and an "
             "independent human decision is recorded.",
             ["comercial/ofertas"]),
            ("proceso", "Imaginary process",
             "# Imaginary process\n\n## Execution\n\n"
             "The team records a request, reviews its background and proposes a "
             "solution that a person reviews before executing.",
             ["operacion/procesos"]),
        ]:
            content = private / (typ + ".md")
            content.write_text(text, encoding="utf8", newline='\n')
            item = create_ficha(vault, typ, title, content_file=content,
                                sources=["F-TEST-001"], tags=tags)
            paths.append(item)
            self.assertTrue(item["nota_desarrollada"])
        for item in paths:
            propose(vault, "D01", item["id"], "refiere_a",
                    fuentes=["F-TEST-001"], ambito="fictitious company",
                    motivo="Proposed relation from a direction note to the test entity.")
        self.assertEqual(query(vault)["total"], 2)

        # No changes to the original note, no invented invoices.
        self.assertEqual(Path(d01["ruta"]).read_bytes(), original_d01)
        self.assertEqual(vista.read_bytes(), original_vista)
        self.assertEqual(validate(vault)["errores"], [])
        state = summary(vault)
        self.assertEqual(state["documentos_dx"]["total"], 1)
        self.assertGreaterEqual(state["capas"]["entidades_operativas"], 2)

        first = previsualizar(vault)
        self.assertEqual(first["sha_actual"], "NUEVO")
        self.assertEqual(first["relaciones_tipadas"], 2)
        self.assertFalse((vault / MAP_MD).exists())
        published = publicar(vault, sha_actual=first["sha_actual"],
                             sha_propuesto=first["sha_propuesto"],
                             confirmacion=first["confirmacion_requerida"],
                             backup_dir=private / "backups")
        self.assertEqual(published["resultado"], "APLICADO")
        self.assertEqual(validate(vault)["errores"], [])
        self.assertEqual(Path(d01["ruta"]).read_bytes(), original_d01)
        self.assertEqual(vista.read_bytes(), original_vista)
        markdown = (vault / MAP_MD).read_text(encoding='utf-8')
        self.assertIn("Imaginary service", markdown)
        self.assertIn("comercial/ofertas", markdown)
        canvas = json.loads((vault / MAP_CANVAS).read_text(encoding='utf-8'))
        self.assertEqual(len(canvas["edges"]), 2)

        # Another session / another process recovering from files, not from chat:
        # in-process adaptation of the upstream cerebro.py relations subprocess.
        self.assertEqual(query(vault)["total"], 2)
        finding = consulta(vault, "fictitious organization", fecha="2026-10-29")
        self.assertEqual(finding["total_coincidencias"], 1)
        negative = consulta(vault, "confirmed sales", fecha="2026-10-29")
        self.assertEqual(negative["total_coincidencias"], 0)
        self.assertFalse(negative["respuesta_semantica_generada"])


if __name__ == "__main__":
    unittest.main()
