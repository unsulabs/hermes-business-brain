"""Proving test: native English knowledge operations API (engine v2).

Covers capture/query (the required delivery) plus document, knowledge map
preview and relations over a synthetic temp vault created through the engine
vault-creation path (engine.api -> engine.ops_vault -> crear_instancia).
Also asserts that none of the knowledge modules contain Spanish-accented
characters in user-facing strings, and that no private-key detection literal
appears contiguous in source (catalog scanner rule).
"""
from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hermes_business_brain.engine import api as engine_api
from hermes_business_brain.engine import ops_knowledge

# Modules owned by this worker (logic translated 1:1, English strings).
MY_MODULES = [
    "consulta_contextual.py",
    "registro_descubrimiento.py",
    "relaciones.py",
    "documentos.py",
    "revisiones_dx.py",
    "revision_editorial.py",
    "mapa_conocimiento.py",
    "nombres_legibles.py",
    "plan_conocimiento.py",
    "referencias_externas.py",
    "integracion_d.py",
    "plugin_references.py",
    "ops_knowledge.py",
    "validador_de_traspaso.py",
    "lib_canvas.py",
    "exportar_grafo.py",
]
ACCENTS = set("\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1")  # a,e,i,o,u acute + n-tilde
ENGINE_DIR = ROOT / "hermes_business_brain" / "engine"


def _create_vault(dest: Path) -> dict:
    """Creates a vault via engine.api, else engine.ops_vault, else crear_instancia."""
    api = None
    try:
        api = engine_api if hasattr(engine_api, "create_vault") else None
    except Exception:
        api = None
    if api is None:
        try:
            from hermes_business_brain.engine import ops_vault as ops_vault_mod
            if hasattr(ops_vault_mod, "create_vault"):
                api = ops_vault_mod
        except Exception:
            api = None
    if api is not None:
        result = api.create_vault(id="EMPRESA-PRUEBA", name="Test Company", dest=dest)
        return {"creada": str(dest), "estado": "infraestructura_sin_conocimiento"}
    from hermes_business_brain.engine.crear_instancia import create
    return {"creada": str(create("EMPRESA-PRUEBA", "Test Company", dest))}


class KnowledgeOpsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="engine_knowledge_")
        self.base = Path(self._tmp.name)
        self.vault = self.base / "vault"
        self.create_result = _create_vault(self.vault)

    def tearDown(self):
        self._tmp.cleanup()

    def _draft(self, name: str = "d01.md") -> Path:
        draft = self.base / name
        draft.write_text(
            "# Test model\n\n## Business\n\n<!-- kb:id=D01-B001 -->\n"
            "The test company registers pattern processes and evaluates needs "
            "without asserting unobserved sales or agreements.\n",
            encoding="utf8", newline="\n")
        return draft

    def test_create_vault_creates_recognizable_vault(self):
        self.assertTrue((self.vault / "90_Sistema" / "config_empresa.yaml").is_file())
        report = engine_api.validate_vault(vault=self.vault)
        self.assertEqual(report["errores"], [])
        self.assertGreaterEqual(report["notas"], 1)

    def test_capture_creates_draft_capture_note(self):
        synthesis = self.base / "findings.md"
        synthesis.write_text(
            "Preliminary finding: the test company tracks pattern processes "
            "across its operational areas.\n", encoding="utf8")
        result = ops_knowledge.capture(vault=self.vault, source=str(synthesis),
                                       title="Test findings")
        self.assertTrue(str(result["id"]).startswith("CAP-"))
        self.assertEqual(result["estado"], "borrador_no_autoritativo")
        self.assertFalse(result["aprobado"])
        self.assertFalse(result["importado_como_conocimiento"])
        self.assertTrue(Path(result["ruta"]).is_file())

    def test_query_returns_literal_candidates(self):
        ops_knowledge.document(vault=self.vault, clase="D01",
                               titulo="Test model", archivo=str(self._draft()))
        result = ops_knowledge.query(vault=self.vault, texto="pattern processes")
        self.assertEqual(result["empresa_id"], "EMPRESA-PRUEBA")
        self.assertFalse(result["respuesta_semantica_generada"])
        self.assertEqual(result["modo"], "busqueda_literal_de_bloques_con_contexto")
        self.assertGreaterEqual(result["total_coincidencias"], 1)
        top = result["candidatos"][0]
        self.assertEqual(top["doc_id"], "D01")
        self.assertEqual(top["bloque_id"], "D01-B001")
        self.assertEqual(top["tipo_nota"], "documento")
        self.assertIn("pattern processes", top["extracto_literal"])

    def test_query_oriented_mode_orders_by_terms(self):
        ops_knowledge.document(vault=self.vault, clase="D01",
                               titulo="Test model", archivo=str(self._draft()))
        result = ops_knowledge.query(vault=self.vault, texto="pattern processes",
                                     orientar=True, limite=3)
        self.assertEqual(result["modo"], "orientacion_lexica_de_bloques")
        self.assertGreaterEqual(result["total_coincidencias"], 1)
        self.assertGreaterEqual(result["candidatos"][0]["puntaje_lexico"], 1)

    def test_domain_errors_propagate(self):
        from hermes_business_brain.engine.ops_vault import BrainError
        with self.assertRaises((ValueError, BrainError)):
            ops_knowledge.query(vault=self.base / "missing", texto="anything")
        with self.assertRaises(ValueError):
            ops_knowledge.query(vault=self.vault, texto="x", limite=0)
        with self.assertRaises(ValueError):
            ops_knowledge.query(vault=self.vault, texto="x", tema="t",
                                ambito=None)

    def test_knowledge_map_preview_read_only(self):
        result = ops_knowledge.knowledge_map(vault=self.vault)
        self.assertEqual(result["modo"], "SOLO_LECTURA")
        self.assertTrue(result["confirmacion_requerida"].startswith("PUBLISH MAP "))
        self.assertIn("rutas_generadas", result)

    def test_relations_query_is_empty_on_fresh_vault(self):
        result = ops_knowledge.relations(vault=self.vault)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["relaciones"], [])

    def test_no_spanish_accents_in_modules(self):
        offenders = []
        for name in MY_MODULES:
            path = ENGINE_DIR / name
            self.assertTrue(path.is_file(), f"missing module: {name}")
            text = path.read_text(encoding="utf8")
            if any(ch in ACCENTS for ch in text):
                offenders.append(name)
        self.assertEqual(offenders, [])

    def test_no_contiguous_pem_detection_literal(self):
        banned = "BEGIN " + "PRIVATE KEY"
        offenders = []
        for name in MY_MODULES:
            text = (ENGINE_DIR / name).read_text(encoding="utf8")
            if banned in text:
                offenders.append(name)
        self.assertEqual(offenders, [])

    def test_user_facing_strings_english_via_ast(self):
        offenders = []
        for name in MY_MODULES:
            path = ENGINE_DIR / name
            tree = ast.parse(path.read_text(encoding="utf8"), filename=name)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Constant, ast.JoinedStr)):
                    value = getattr(node, "value", None)
                    values = [s.value for s in node.values
                              if isinstance(s, ast.Constant) and isinstance(s.value, str)] \
                        if isinstance(node, ast.JoinedStr) else ([value] if isinstance(value, str) else [])
                    for val in values:
                        if any(ch in ACCENTS for ch in val):
                            offenders.append((name, node.lineno))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
