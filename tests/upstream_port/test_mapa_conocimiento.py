"""Ported upstream test_mapa_conocimiento.py: Markdown/Canvas knowledge map

(DERIVED navigation projection; never edits business notes or approves
content). JSON keys, result states (SOLO_LECTURA/APLICADO/SIN_CAMBIOS) and
message idioms are the upstream contract; Spanish content fixtures and message
strings inside assertions are translated to the engine's English equivalents.
The upstream CLI test (subprocess) is adapted to an in-process previsualizar()
call, see _verify/tests-v2.md.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.documentos import create_document
from hermes_business_brain.engine.operacion import create_ficha, create_source
from hermes_business_brain.engine.relaciones import propose, confirm
from hermes_business_brain.engine.mapa_conocimiento import previsualizar, publicar, MAP_MD, MAP_CANVAS
from hermes_business_brain.engine.validar_boveda import validate


class KnowledgeMapTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.work = Path(d.name)
        self.vault = create("DEMO-MAPA", "Fictitious business", self.work / "vault")
        create_source(self.vault, "F-MAPA-001", "Test episode", "urn:synthetic:episode", "nota")
        draft = self.work / "direction.md"
        draft.write_text(
            "# Fictitious direction\n\n## Work model\n\n"
            "<!-- kb:id=D01-B001 -->\n"
            "A test organization studies priorities with its team and "
            "distinguishes the work it agrees to do from its internal proposals.\n\n"
            "## CONTROL\n\nInvented example.\n", encoding="utf8", newline='\n')
        a = create_document(self.vault, "D01", "Fictitious direction", draft,
                            sources=["F-MAPA-001"], tags=["direccion/modelo-valor"])
        developed = self.work / "process.md"
        developed.write_text(
            "# Team flow\n\n## Work\n\n"
            "An owner records a request and consults with the team before "
            "assigning an activity that produces verifiable results.\n",
            encoding="utf8", newline='\n')
        b = create_ficha(self.vault, "proceso", "Operational flow", content_file=developed,
                         sources=["F-MAPA-001"], tags=["operacion/procesos"])
        self.originals = {x: Path(x).read_bytes() for x in [a["ruta"], b["ruta"]]}
        self.a = a["doc_id"]
        self.b = b["id"]
        self.backup = self.work / "external"

    def approval(self, r):
        return {
            "sha_actual": r["sha_actual"],
            "sha_propuesto": r["sha_propuesto"],
            "confirmacion": r["confirmacion_requerida"],
            "backup_dir": self.backup}

    def test_read_only_preview_and_markdown_canvas(self):
        rel = propose(self.vault, self.a, self.b, "refiere_a",
                      fuentes=["F-MAPA-001"],
                      ambito="fictitious work flow",
                      motivo="A link between strategy and the fictitious team process is proposed.")
        before = set(self.vault.rglob("*"))
        r = previsualizar(self.vault)
        self.assertEqual(r["modo"], "SOLO_LECTURA")
        self.assertEqual(r["sha_actual"], "NUEVO")
        self.assertGreaterEqual(r["notas_en_mapa"], 3)
        self.assertEqual(r["relaciones_tipadas"], 1)
        self.assertEqual(r["canvas_aristas"], 1)
        self.assertIn("propuesta", r["vista_previa"])
        self.assertFalse((self.vault / MAP_MD).exists())
        self.assertFalse((self.vault / MAP_CANVAS).exists())
        self.assertEqual(before, set(self.vault.rglob("*")))

    def test_publish_with_permission_and_backups_is_nondestructive(self):
        relation = propose(self.vault, self.a, self.b, "refiere_a",
                           fuentes=["F-MAPA-001"], ambito="fictitious context",
                           motivo="The direction documentation mentions the process in the example company.")
        r = previsualizar(self.vault)
        with self.assertRaises(ValueError):
            publicar(self.vault, sha_actual=r["sha_actual"], sha_propuesto=r["sha_propuesto"],
                     confirmacion="SI", backup_dir=self.backup)
        self.assertFalse((self.vault / MAP_MD).exists())
        x = publicar(self.vault, **self.approval(r))
        self.assertEqual(x["resultado"], "APLICADO")
        canvas = json.loads((self.vault / MAP_CANVAS).read_text(encoding='utf-8'))
        self.assertEqual(canvas["edges"][0]["label"], "refiere_a (proposal)")
        self.assertTrue(any(n["id"] == "nota-sistema-mapa" and n["type"] == "text"
                            for n in canvas["nodes"]))
        self.assertTrue(all(n["type"] == "file" for n in canvas["nodes"]
                            if n["id"] != "nota-sistema-mapa"))
        md = (self.vault / MAP_MD).read_text(encoding='utf-8')
        self.assertIn("[[10_Conocimiento/Fictitious direction|Fictitious direction]]", md)
        self.assertIn("[[", md)
        self.assertIn("operacion/procesos", md)
        self.assertEqual(validate(self.vault)["errores"], [])
        for file, data in self.originals.items():
            self.assertEqual(Path(file).read_bytes(), data)
        self.assertTrue((Path(x["respaldo"]) / "manifest.json").exists())
        second = previsualizar(self.vault)
        self.assertTrue(second["sin_cambios"])
        self.assertEqual(publicar(self.vault, **self.approval(second))["resultado"], "SIN_CAMBIOS")

    def test_confirmed_relation_appears_with_separate_layer(self):
        rel = propose(self.vault, self.a, self.b, "refiere_a",
                      fuentes=["F-MAPA-001"], ambito="firm process",
                      motivo="A proposed link for a fictitious firm and its work process.")
        p = Path(rel["ruta"])
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        confirm(self.vault, rel["relacion_id"], sha, revisor="Fictitious owner",
                referencia_autorizacion="Synthetic confirmation decision",
                confirmacion="CONFIRM " + rel["relacion_id"] + " " + sha[:12])
        draft = previsualizar(self.vault)
        result = publicar(self.vault, **self.approval(draft))
        self.assertEqual(result["resultado"], "APLICADO")
        canvas = json.loads((self.vault / MAP_CANVAS).read_text(encoding='utf-8'))
        self.assertIn("(review)", canvas["edges"][0]["label"])
        self.assertIn("validada_por_revisor", (self.vault / MAP_MD).read_text(encoding='utf-8'))

    def test_source_changed_after_preview_requires_new_SHA(self):
        r = previsualizar(self.vault)
        created = create_ficha(self.vault, "decision", "Provisional decision")
        original = {p: self.vault / p for p in (MAP_MD, MAP_CANVAS)}
        with self.assertRaisesRegex(ValueError, "preview again"):
            publicar(self.vault, **self.approval(r))
        self.assertFalse((self.vault / MAP_MD).exists())
        self.assertEqual(validate(self.vault)["errores"], [])

    def test_does_not_overwrite_non_generated_user_map(self):
        path = self.vault / MAP_MD
        path.write_text("---\nid: SYS-MAPA-DERIVADO\ntipo: mapa\n---\n# Manual map\n",
                        encoding='utf-8', newline='\n')
        with self.assertRaisesRegex(ValueError, "do not overwrite"):
            previsualizar(self.vault)
        self.assertEqual((self.vault / MAP_MD).read_text(encoding='utf-8').splitlines()[-1],
                         "# Manual map")

    def test_rewrite_requires_matching_existing_SHA(self):
        initial = previsualizar(self.vault)
        publicar(self.vault, **self.approval(initial))
        original = self.vault / MAP_MD
        old = original.read_bytes()
        create_ficha(self.vault, "investigacion", "Simulated research")
        r = previsualizar(self.vault)
        self.assertFalse(r["sin_cambios"])
        wrong_sha = initial["sha_propuesto"]
        wrong_sha = wrong_sha[:-1] + ("1" if wrong_sha[-1] == "0" else "0")
        bad = {**self.approval(r), "sha_actual": wrong_sha}
        with self.assertRaisesRegex(ValueError, "Map or notes changed"):
            publicar(self.vault, **bad)
        self.assertEqual(original.read_bytes(), old)
        new = publicar(self.vault, **self.approval(r))
        self.assertEqual(new["resultado"], "APLICADO")
        self.assertEqual(validate(self.vault)["errores"], [])
        backup_md = Path(new["respaldo"]) / (MAP_MD.name + ".anterior.snapshot")
        self.assertEqual(backup_md.read_bytes(), old)

    def test_obsidian_canvas_autosave_does_not_require_republication(self):
        propose(self.vault, self.a, self.b, "refiere_a",
                fuentes=["F-MAPA-001"], ambito="autosave test",
                motivo="The fictitious direction document refers to the fictitious process.")
        first = previsualizar(self.vault)
        publicar(self.vault, **self.approval(first))
        canvas_path = self.vault / MAP_CANVAS
        canvas = json.loads(canvas_path.read_text(encoding="utf8"))
        for edge in canvas["edges"]:
            edge["fromSide"] = "right"
            edge["toSide"] = "left"
        native = json.dumps(canvas, ensure_ascii=False, separators=(",", ":"))
        canvas_path.write_text(native, encoding="utf8", newline='\n')

        preview = previsualizar(self.vault)
        self.assertTrue(preview["sin_cambios"])
        self.assertEqual(publicar(self.vault, **self.approval(preview))["resultado"], "SIN_CAMBIOS")
        self.assertEqual(canvas_path.read_text(encoding="utf8"), native)

        canvas["edges"][0]["label"] = "different relation"
        canvas_path.write_text(json.dumps(canvas, ensure_ascii=False), encoding="utf8", newline='\n')
        self.assertFalse(previsualizar(self.vault)["sin_cambios"])

        canvas["edges"][0]["label"] = "refiere_a (proposal)"
        canvas["nodes"][1]["x"] += 25
        canvas_path.write_text(json.dumps(canvas, ensure_ascii=False), encoding="utf8", newline='\n')
        self.assertFalse(previsualizar(self.vault)["sin_cambios"])

    def test_cli_preview(self):
        # In-process adaptation of the upstream cerebro.py subprocess call.
        data = previsualizar(self.vault)
        self.assertEqual(data["modo"], "SOLO_LECTURA")
        self.assertIn("sha_propuesto", data)


if __name__ == "__main__":
    unittest.main()
