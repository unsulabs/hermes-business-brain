"""Upstream result-key parity for the native English engine (structure parity).

For each key operation the engine's result dict must expose EXACTLY the same
JSON keys as the upstream Spanish implementation. The key sets are hardcoded
here from the upstream sources (obsidian-business-brain/scripts): crear_instancia
(create + vault envelope), validar_boveda.validate, operacion.summary (top level
+ nested layers), documentos.create_document, registro_descubrimiento
.capture_discovery (CAP- output), consulta_contextual.consulta (result AND
candidate row), mapa_conocimiento.previsualizar, relaciones.propose.

Values inside those keys (Spanish enum tokens, display names) are the upstream
contract and are preserved verbatim by design; this file asserts the keys, not
the strings.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hermes_business_brain.engine import api
from hermes_business_brain.engine.validar_boveda import validate
from hermes_business_brain.engine.operacion import summary, create_source
from hermes_business_brain.engine.documentos import create_document
from hermes_business_brain.engine.registro_descubrimiento import capture_discovery
from hermes_business_brain.engine.consulta_contextual import consulta
from hermes_business_brain.engine.mapa_conocimiento import previsualizar
from hermes_business_brain.engine.relaciones import propose

# --- Key sets hardcoded from the upstream implementation ---
VALIDATE_KEYS = {"notas", "ids", "bloques", "traspasos", "errores", "advertencias", "tipos"}

STATUS_KEYS = {
    "empresa", "id_empresa", "version_instancia", "total_notas", "por_tipo",
    "editorial", "conocimiento", "capas", "plantillas_instaladas",
    "vistas_bases_instaladas", "fuentes_resumen", "documentos_dx",
    "ultima_continuidad", "continuidades_fecha_invalida", "advertencia",
}
STATUS_CAPAS_KEYS = {
    "infraestructura", "fuentes", "trabajo_provisional",
    "documentos_dx", "entidades_operativas", "otras_notas",
}
STATUS_DOCS_DX_KEYS = {"total", "por_clase", "por_estado_editorial", "registros"}
STATUS_DOC_RECORD_KEYS = {"doc_id", "clase", "estado_editorial", "ruta", "fuentes_referenciadas"}
STATUS_FUENTES_RESUMEN_KEYS = {"total", "por_lectura"}

DOCUMENT_KEYS = {
    "doc_id", "ruta", "clase", "revision", "estado_editorial", "aprobado",
    "fuentes", "insumo_sha256", "bloques_vnext_con_contrato", "limite",
}

CAPTURE_KEYS = {"id", "ruta", "estado", "fuentes", "aprobado", "importado_como_conocimiento"}

CONSULTA_KEYS = {
    "empresa_id", "consulta_literal", "fecha_consultada", "modo",
    "total_coincidencias", "candidatos", "documentos_fuera_vigencia_explicita",
    "autoridad_contextual", "respuesta_semantica_generada", "limite",
}
CANDIDATE_KEYS = {
    "doc_id", "bloque_id", "tipo_fragmento", "tipo_nota", "ruta",
    "sha256_nota", "span_bytes_nota", "extracto_literal", "estado_editorial",
    "cobertura", "vigencia_declarada", "fuentes_nivel_documento",
    "fuente_demuestra_bloque", "as_of_consultado", "fecha_corte_documento",
    "advertencia",
}

MAP_PREVIEW_KEYS = {
    "empresa_id", "modo", "rutas_generadas", "sha_actual", "sha_propuesto",
    "confirmacion_requerida", "sin_cambios", "notas_en_mapa",
    "relaciones_tipadas", "canvas_nodos", "canvas_aristas", "canvas_parcial",
    "notas_restringidas_omitidas", "vista_previa", "limite",
}

RELATION_KEYS = {"ruta", "relacion_id", "estado", "validada"}

CREATE_VIA_API_KEYS = {"creada", "estado", "nota"}


class UpstreamKeyParityTest(unittest.TestCase):
    """One synthetic vault exercises every key operation against the upstream sets."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="parity_")
        cls.root = Path(cls.tmp.name)
        cls.vault = cls.root / "vault"
        cls.api_result = api.create_vault(id="PARITY-TEST", name="Parity Company",
                                          dest=cls.vault)
        cls.draft_source = cls.root / "capture.md"
        cls.draft_source.write_text(
            "Parity observation: the synthetic company records decisions and "
            "registers the source as reference card only.\n", encoding="utf8")
        cls.input_doc = cls.root / "draft_d01.md"
        cls.input_doc.write_text(
            "# Parity document\n\n## Activity\n\n<!-- kb:id=D01-B001 -->\n"
            "The parity test registers work requests and decisions without "
            "asserting undocumented results.\n\n"
            "## CONTROL\n\nSynthetic parity fixture.\n", encoding="utf8",
            newline="\n")
        cls.source = create_source(cls.vault, "F-PARITY-01", "Parity source",
                                   "urn:synthetic:parity", "nota")
        cls.document = create_document(cls.vault, "D01", "Parity document",
                                       cls.input_doc, editorial="en_revision",
                                       sources=["F-PARITY-01"])
        cls.capture = capture_discovery(cls.vault, "Parity observation",
                                        cls.draft_source)
        cls.relation = propose(cls.vault, cls.document["doc_id"], cls.source["id"],
                               "sustentado_por", fuentes=["F-PARITY-01"],
                               ambito="parity fixture",
                               motivo="Parity key coverage only.")
        cls.preview = previsualizar(cls.vault)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_01_create_envelope_and_validate_keys(self):
        self.assertEqual(set(self.api_result), CREATE_VIA_API_KEYS)
        self.assertEqual(set(validate(self.vault)), VALIDATE_KEYS)
        self.assertEqual(validate(self.vault)["errores"], [])

    def test_02_status_nested_keys(self):
        report = summary(self.vault)
        self.assertEqual(set(report), STATUS_KEYS)
        self.assertEqual(set(report["capas"]), STATUS_CAPAS_KEYS)
        self.assertEqual(set(report["documentos_dx"]), STATUS_DOCS_DX_KEYS)
        self.assertEqual(set(report["fuentes_resumen"]), STATUS_FUENTES_RESUMEN_KEYS)
        self.assertGreater(report["capas"]["infraestructura"], 0)
        self.assertEqual(set(report["documentos_dx"]["registros"][0]),
                         STATUS_DOC_RECORD_KEYS)

    def test_03_document_and_capture_keys(self):
        self.assertEqual(set(self.document), DOCUMENT_KEYS)
        self.assertEqual(set(self.capture), CAPTURE_KEYS)
        self.assertTrue(str(self.capture["id"]).startswith("CAP-"))
        self.assertFalse(self.capture["aprobado"])

    def test_04_consulta_result_and_candidate_keys(self):
        result = consulta(self.vault, "work requests", fecha="2026-10-28")
        self.assertEqual(set(result), CONSULTA_KEYS)
        self.assertGreaterEqual(result["total_coincidencias"], 1)
        row = next(c for c in result["candidatos"] if c["doc_id"] == "D01")
        self.assertEqual(set(row), CANDIDATE_KEYS)

    def test_05_map_preview_and_relation_keys(self):
        self.assertEqual(set(self.relation), RELATION_KEYS)
        self.assertEqual(self.relation["estado"], "propuesta")
        self.assertFalse(self.relation["validada"])
        self.assertEqual(set(self.preview), MAP_PREVIEW_KEYS)
        self.assertEqual(self.preview["modo"], "SOLO_LECTURA")


if __name__ == "__main__":
    unittest.main()
