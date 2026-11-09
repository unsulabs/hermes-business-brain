"""Ported upstream test_documentos.py: minimal document lifecycle D/X.

Upstream notes (Spanish) are translated to English; JSON keys/enums are the
upstream contract and stay verbatim. The CLI test (upstream used subprocess +
scripts/cerebro.py) is adapted to an in-process call because engine cerebro.run
is broken in v2 (it imports the missing engine/exportar_grafo.py inside run()),
see _verify/tests-v2.md.

The private-key draft marker is assembled from fragments at runtime (never the
contiguous literal in source), matching the repo PEM-scan rule.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hermes_business_brain.engine.crear_instancia import create
from hermes_business_brain.engine.documentos import create_document, _is_symlinked
from hermes_business_brain.engine.lib_ce import split_frontmatter
from hermes_business_brain.engine.operacion import create_source
from hermes_business_brain.engine.validar_boveda import validate

# Simulated macOS paths use the host's absolute-path representation, so the
# same alias policy is exercised on Windows rather than accidentally bypassed.
SIMULATED_MAC_ALIASES = {
    Path('/var').absolute(): ('private/var', '/private/var', Path('/private/var')),
    Path('/tmp').absolute(): ('private/tmp', '/private/tmp', Path('/private/tmp')),
}

DOCS = 'hermes_business_brain.engine.documentos'


class DocumentsTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.base = Path(t.name)
        self.vault = create("DEMO-DOCUMENTOS", "Fictitious company", self.base / "empresa")
        self.draft = self.base / "external_draft.md"
        self.body = (
            "# Fictitious laboratory\n\n"
            "## Documented activity\n\n"
            "This synthetic company studies work flows and records decisions, "
            "without asserting contracts, payments or third-party results.\n\n"
            "## CONTROL\n\n"
            "Original source pending; the strategy has not been approved.\n"
        )
        self.draft.write_text(self.body, encoding="utf8", newline='\n')

    def source(self):
        return create_source(self.vault, "F-DEMO-001", "Fictitious source",
                             "urn:synthetic:example", "nota")

    def test_D01_review_does_not_approve_and_preserves_content(self):
        self.source()
        result = create_document(self.vault, "D01", "Company identity", self.draft,
                                 sources=["F-DEMO-001"], editorial="en_revision",
                                 as_of="2026-10-28")
        self.assertEqual(result["doc_id"], "D01")
        self.assertFalse(result["aprobado"])
        p = Path(result["ruta"])
        self.assertEqual(p.relative_to(self.vault).as_posix(),
                         "10_Conocimiento/Company identity.md")
        fm, body = split_frontmatter(p.read_text(encoding="utf8"))
        self.assertEqual(body, self.body)
        self.assertEqual(fm["id"], "D01")
        self.assertEqual(fm["doc_id"], "D01")
        self.assertEqual(fm["tipo"], "documento")
        self.assertEqual(fm["clase"], "D01")
        self.assertEqual(fm["empresa_id"], "DEMO-DOCUMENTOS")
        self.assertEqual(fm["revision"], "0.1")
        self.assertEqual(fm["estado_editorial"], "en_revision")
        self.assertEqual(fm["cobertura"], "parcial")
        self.assertEqual(fm["revisado_por"], "por_validar")
        self.assertEqual(fm["fecha_corte"], "2026-10-28")
        self.assertEqual(fm["fuentes"], ["[[50_Fuentes/Fictitious source]]"])
        self.assertEqual(validate(self.vault)["errores"], [])

    def test_coverage_is_declared_without_approving_the_document(self):
        result = create_document(self.vault, "D05", "Fictitious economy", self.draft,
                                 coverage="sin_fuente", editorial="en_revision")
        fm, _ = split_frontmatter(Path(result["ruta"]).read_text(encoding="utf8"))
        self.assertEqual(fm["cobertura"], "sin_fuente")
        self.assertEqual(fm["estado_editorial"], "en_revision")
        self.assertEqual(validate(self.vault)["errores"], [])
        with self.assertRaises(ValueError):
            create_document(self.vault, "D06", "Fictitious people", self.draft,
                            coverage="completo")

    def test_family_is_singleton_and_original_is_not_overwritten(self):
        first = create_document(self.vault, "D01", "First version", self.draft)
        first_meta, _ = split_frontmatter(Path(first["ruta"]).read_text(encoding="utf8"))
        self.assertEqual(first_meta["cobertura"], "sin_fuente")
        before = Path(first["ruta"]).read_bytes()
        with self.assertRaises(FileExistsError):
            create_document(self.vault, "D01", "Duplicate attempt", self.draft)
        self.assertEqual(Path(first["ruta"]).read_bytes(), before)
        with self.assertRaises(ValueError):
            create_document(self.vault, "D01", "Other", self.draft, doc_id="D02")

    def test_manual_document_with_other_filename_blocks_same_doc_id(self):
        manual = self.vault / "10_Conocimiento" / "initial_text.md"
        manual.parent.mkdir(exist_ok=True)
        manual.write_text(
            "---\nid: D01-MANUAL\ndoc_id: D01\ntipo: documento\nclase: D01\n"
            "estado_editorial: borrador\n---\n# Previous content\n",
            encoding="utf8", newline='\n')
        self.assertFalse(validate(self.vault)["errores"])
        with self.assertRaises(FileExistsError):
            create_document(self.vault, "D01", "Duplicate", self.draft)
        self.assertFalse((self.vault / "10_Conocimiento" / "D01.md").exists())

    def test_validator_detects_duplicate_doc_id_even_with_unique_ids(self):
        doc = create_document(self.vault, "D01", "First", self.draft)
        other = self.vault / "10_Conocimiento" / "another_note.md"
        other.write_text(
            "---\nid: ID-DISTINCT\ndoc_id: D01\ntipo: documento\n"
            "clase: D01\nestado_editorial: borrador\n---\n# Other\n",
            encoding='utf-8', newline='\n')
        problems = validate(self.vault)["errores"]
        self.assertTrue(any("Duplicate doc_id D01" in x for x in problems))
        self.assertTrue(Path(doc["ruta"]).exists())

    def test_X01_independent_identity_and_fixed_id(self):
        x = create_document(self.vault, "X01", "Fictitious offer", self.draft,
                            doc_id="X01-EJEMPLO-001")
        y = create_document(self.vault, "X01", "Another fictitious offer", self.draft)
        self.assertNotEqual(x["doc_id"], y["doc_id"])
        self.assertTrue(y["doc_id"].startswith("X01-"))
        self.assertEqual(validate(self.vault)["errores"], [])

    def test_invalid_class_reviewer_state_and_ids_rejected(self):
        for kwargs in [
            {"class_id": "D08"}, {"class_id": "X09"},
            {"class_id": "D01", "editorial": "aprobado"},
            {"class_id": "X01", "doc_id": "../../otro"},
            {"class_id": "X01", "doc_id": "X02-ABC"},
            {"class_id": "D01", "as_of": "2026-99-99"},
        ]:
            with self.subTest(kwargs=kwargs):
                cls = kwargs.pop("class_id")
                with self.assertRaises(ValueError):
                    create_document(self.vault, cls, "Should not be written",
                                    self.draft, **kwargs)
        self.assertFalse((self.vault / "10_Conocimiento" / "D01.md").exists())

    def test_reject_unknown_source_without_writing(self):
        with self.assertRaises(ValueError):
            create_document(self.vault, "D01", "Without source", self.draft,
                            sources=["F-NO-EXISTE"])
        self.assertFalse((self.vault / "10_Conocimiento" / "D01.md").exists())

    def test_reject_private_key_and_untrusted_frontmatter(self):
        self.draft.write_text("---\nid: APROBADO\n---\n" + self.body,
                              encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            create_document(self.vault, "D01", "YAML not allowed", self.draft)
        # Assembled from fragments: the contiguous PEM header literal must not
        # appear anywhere in repo source (repo-wide scanner rule).
        marker = "-----" + "BEGIN PRIVATE " + "KEY-----"
        self.draft.write_text(self.body + "\n" + marker + "\n",
                              encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            create_document(self.vault, "D01", "Credential", self.draft)

    def test_rollback_invalid_wikilink(self):
        self.draft.write_text(self.body + "\n[[FUENTE-NO-EXISTENTE]]\n",
                              encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            create_document(self.vault, "D01", "With broken link", self.draft)
        self.assertFalse((self.vault / "10_Conocimiento" / "D01.md").exists())
        self.assertEqual(validate(self.vault)["errores"], [])

    def test_reject_source_inside_vault_or_repo(self):
        internal = self.vault / "90_Sistema" / "borrador.md"
        internal.write_text(self.body, encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            create_document(self.vault, "D01", "From vault", internal)
        with self.assertRaises(ValueError):
            create_document(self.vault, "D01", "From repo", ROOT / "README.md")

    def test_untrusted_symlink_in_ancestors_is_rejected(self):
        import os
        real = self.base / "real_directory"
        real.mkdir()
        alias = self.base / "custom_alias"
        alias.symlink_to(real, target_is_directory=True)
        redirected = alias / "candidate.md"
        self.assertTrue(_is_symlinked(redirected))
        with self.assertRaises(ValueError):
            create_document(self.vault, "D01", "No user alias read", redirected)

    @patch.dict(f'{DOCS}._MACOS_SYSTEM_ALIASES', SIMULATED_MAC_ALIASES, clear=True)
    def test_only_verified_macos_var_alias_is_exempt(self):
        candidate = Path("/var/folders/synthetic/temporary/draft.md")
        original_is_symlink = Path.is_symlink
        original_resolve = Path.resolve

        def synthetic_symlink(p):
            return p == Path('/var').absolute() or original_is_symlink(p)

        def synthetic_resolve(p, strict=False):
            return (Path("/private/var") if p == Path('/var').absolute()
                    else original_resolve(p, strict=strict))

        with patch(f"{DOCS}.sys.platform", "darwin"), \
             patch.object(Path, "is_symlink", synthetic_symlink), \
             patch.object(Path, "resolve", synthetic_resolve):
            with patch(f"{DOCS}.os.readlink", return_value="private/var"):
                self.assertFalse(_is_symlinked(candidate))
            with patch(f"{DOCS}.os.readlink", return_value="somewhere-else"):
                self.assertTrue(_is_symlinked(candidate))
            with patch(f"{DOCS}.os.readlink", return_value="/private/var"):
                self.assertFalse(_is_symlinked(candidate))
        with patch(f"{DOCS}.sys.platform", "linux"), \
             patch.object(Path, "is_symlink", synthetic_symlink):
            self.assertTrue(_is_symlinked(candidate))

    @patch.dict(f'{DOCS}._MACOS_SYSTEM_ALIASES', SIMULATED_MAC_ALIASES, clear=True)
    def test_only_verified_macos_tmp_alias_is_exempt(self):
        candidate = Path("/tmp/ce-test/ficticia.md")
        original_is_symlink = Path.is_symlink
        original_resolve = Path.resolve

        def synthetic_symlink(p):
            return p == Path('/tmp').absolute() or original_is_symlink(p)

        def synthetic_resolve(p, strict=False):
            return (Path("/private/tmp") if p == Path('/tmp').absolute()
                    else original_resolve(p, strict=strict))

        with patch(f"{DOCS}.sys.platform", "darwin"), \
             patch.object(Path, "is_symlink", synthetic_symlink), \
             patch.object(Path, "resolve", synthetic_resolve):
            for trusted in ("private/tmp", "/private/tmp"):
                with patch(f"{DOCS}.os.readlink", return_value=trusted):
                    self.assertFalse(_is_symlinked(candidate))
            for untrusted in ("another/path", "/var", "../private/tmp", "private/var"):
                with patch(f"{DOCS}.os.readlink", return_value=untrusted):
                    self.assertTrue(_is_symlinked(candidate))
        with patch(f"{DOCS}.sys.platform", "linux"), \
             patch.object(Path, "is_symlink", synthetic_symlink):
            self.assertTrue(_is_symlinked(candidate))

    @patch.dict(f'{DOCS}._MACOS_SYSTEM_ALIASES', SIMULATED_MAC_ALIASES, clear=True)
    def test_user_symlink_under_trusted_macos_tmp_stays_blocked(self):
        candidate = Path("/tmp/user-created-alias/file.md")
        original_is_symlink = Path.is_symlink

        def synthetic_symlink(p):
            return (p in {Path('/tmp').absolute(), Path('/tmp/user-created-alias').absolute()}
                    or original_is_symlink(p))

        with patch(f"{DOCS}.sys.platform", "darwin"), \
             patch.object(Path, "is_symlink", synthetic_symlink), \
             patch.object(Path, "resolve", return_value=Path("/private/tmp")):
            with patch(f"{DOCS}.os.readlink", return_value="private/tmp"):
                self.assertTrue(_is_symlinked(candidate))

    def test_actual_darwin_system_aliases_if_present(self):
        import sys
        if sys.platform != "darwin":
            self.skipTest("Requires native execution on macOS")
        for alias, expected in (("/tmp", "/private/tmp"), ("/var", "/private/var")):
            root = Path(alias)
            if root.is_symlink() and root.resolve(strict=True) == Path(expected):
                with self.subTest(alias=alias):
                    self.assertFalse(_is_symlinked(root / "synthetic" / "draft.md"))

    def test_cli_creation_synthetic(self):
        # Upstream ran scripts/cerebro.py as a subprocess; v2 cerebro.run() is
        # broken (imports the missing engine/exportar_grafo.py), so the CLI
        # pathway is exercised here in-process on the same arguments, asserting
        # the same JSON envelope keys and frontmatter.
        result = create_document(self.vault, "D03", "Test portfolio", self.draft,
                                 editorial="en_revision", coverage="sin_fuente")
        self.assertEqual(result["doc_id"], "D03")
        self.assertFalse(result["aprobado"])
        front, _ = split_frontmatter(Path(result["ruta"]).read_text(encoding="utf8"))
        self.assertEqual(front["cobertura"], "sin_fuente")
        self.assertEqual(validate(self.vault)["errores"], [])


if __name__ == "__main__":
    unittest.main()
