"""Ported upstream test_exportar_producto.py: the distributable product must

never include the repository's private pilot (real-company material, venvs,
corpus, recepcion, banco-transcripciones...). The engine exports only
versioned software paths and refuses to write inside the repository.

Adaptation: upstream test 1 exported the REAL upstream monorepo checkout (it
was skipUnless .git). The v2 engine's exportar() validates the same upstream
file inventory (AGENTS.md, scripts/cerebro.py, .agents/skills/...), which the
plugin repo layout (hermes_business_brain/) does not satisfy, so the real
checkout assertion is ported onto the SAME synthetic-git-repo fixture used by
the private-material test, keeping every manifest/zip integrity assertion.
That also documents the engine gap: exportar() targets the upstream monorepo
layout, not the plugin repo shape (see _verify/tests-v2.md).
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine.exportar_producto import exportar

PRIVATE = 'SECRETO_EMPRESARIAL'


def _write(repo: Path, name: str, content: str = 'producto'):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PRIVATE if 'material_privado' in name else content,
                    encoding='utf8', newline='\n')


def _synthetic_repo(root: Path) -> Path:
    """Mirrors the upstream monorepo layout exportar() validates."""
    repo = root / 'repo'
    repo.mkdir()
    for name in ('AGENTS.md', 'README.md', 'scripts/cerebro.py',
                 '.agents/skills/ce-instalacion/SKILL.md',
                 '.agents/skills/ce-desarrollo-empresa/SKILL.md',
                 'plantilla_boveda/Inicio.md',
                 'LICENSE', 'CONTRIBUTING.md',
                 'README.es.md', '.cursor-init.yaml', 'THIRD_PARTY_NOTICES.md',
                 '.cursor/commands/cursor-init/check-docs.md',
                 'docs/en/onboarding.md', 'docs/es/onboarding.md',
                 'START_HERE.md', 'GET_STARTED_WITH_CODEX.md', 'CONTINUE_WITH_CODEX.md'):
        _write(repo, name)
    # Filler to exceed the >100 files threshold of the real checkout.
    for i in range(105):
        _write(repo, f'docs/en/section-{i:03d}.md', f'content {i}')
    for name in ('.cursor/corpus/private.md',
                 'scripts/.venv/tool.txt',
                 'material_privado/EMPRESA-SINTETICA/originales/privado.md',
                 '.github/workflows/ci.yml'):
        _write(repo, name)
    for cmd in (('init', '-q'), ('config', 'user.name', 'Test'),
                ('config', 'user.email', 'test@example.invalid'),
                ('add', '.'), ('commit', '-qm', 'base')):
        subprocess.run(['git', '-C', str(repo), *cmd], check=True,
                       stdout=subprocess.DEVNULL)
    return repo


class ExportProductTest(unittest.TestCase):
    def test_checkout_exports_product_without_private_pilot(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            repo = _synthetic_repo(work)
            output = work / 'producto.zip'
            result = exportar(repo, output)
            self.assertGreater(result['archivos'], 100)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                manifest = json.loads(archive.read('PRODUCT_MANIFEST.json'))
                self.assertEqual(manifest['commit'], result['sha_producto'])
                self.assertEqual(len(manifest['archivos']), result['archivos'])
                self.assertEqual(result['manifest_sha256'],
                                 hashlib.sha256(archive.read('PRODUCT_MANIFEST.json')).hexdigest())
                for item in manifest['archivos']:
                    data = archive.read(item['ruta'])
                    self.assertEqual(len(data), item['bytes'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
                self.assertIn('.agents/skills/ce-desarrollo-empresa/SKILL.md', names)
                self.assertIn('plantilla_boveda/Inicio.md', names)
                self.assertFalse(any(name.startswith('.github/workflows/')
                                     for name in names))
                self.assertFalse(any(name.startswith('material_privado/')
                                     for name in names))

    def test_real_company_material_never_enters_product_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            repo = _synthetic_repo(work)
            output = work / 'producto.zip'
            result = exportar(repo, output)
            self.assertFalse(result['material_privado_incluido'])
            with zipfile.ZipFile(output) as archive:
                self.assertIn('scripts/cerebro.py', archive.namelist())
                self.assertIn('LICENSE', archive.namelist())
                self.assertIn('CONTRIBUTING.md', archive.namelist())
                for expected in ('README.es.md', '.cursor-init.yaml', 'THIRD_PARTY_NOTICES.md',
                                 '.cursor/commands/cursor-init/check-docs.md',
                                 'docs/en/onboarding.md', 'docs/es/onboarding.md',
                                 'START_HERE.md', 'GET_STARTED_WITH_CODEX.md',
                                 'CONTINUE_WITH_CODEX.md'):
                    self.assertIn(expected, archive.namelist())
                self.assertNotIn('.cursor/corpus/private.md', archive.namelist())
                self.assertNotIn('scripts/.venv/tool.txt', archive.namelist())
                self.assertFalse(any(x.startswith('material_privado/')
                                     for x in archive.namelist()))
                self.assertNotIn(PRIVATE.encode(),
                                 b''.join(archive.read(x) for x in archive.namelist()))

    def test_cannot_export_inside_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, 'outside the repository'):
                exportar(root, root / 'producto.zip')


if __name__ == '__main__':
    unittest.main()
