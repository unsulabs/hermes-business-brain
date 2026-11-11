"""Ported upstream test_exportar_producto.py: the distributable product must

never include the repository's private pilot (real-company material, venvs,
corpus, recepcion, banco-transcripciones...). The engine exports only
versioned software paths and refuses to write inside the repository.

Adaptation: upstream test 1 exported the REAL upstream monorepo checkout (it
was skipUnless .git). The v2 engine's exportar() validates the plugin repo
file inventory (README.md, plugin.yaml, hermes_business_brain/engine/cerebro.py,
hermes_business_brain/skills/ce-instalacion/SKILL.md), so the real checkout
assertion is ported onto the SAME synthetic-git-repo fixture used by the
private-material test, keeping every manifest/zip integrity assertion.
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
    """Mirrors the plugin repo layout exportar() validates."""
    repo = root / 'repo'
    repo.mkdir()
    for name in ('README.md', 'LICENSE', 'plugin.yaml', '__init__.py',
                 'schemas.py', 'tools.py', '.gitignore', '.gitattributes',
                 'hermes_business_brain/engine/cerebro.py',
                 'hermes_business_brain/skills/ce-instalacion/SKILL.md',
                 'hermes_business_brain/skills/ce-desarrollo-empresa/SKILL.md',
                 'hermes_business_brain/data/modelo/clases_documentales.json',
                 'docs/en/onboarding.md',
                 'tests/test_sample.py'):
        _write(repo, name)
    # Filler to exceed the >100 files threshold of the real checkout.
    for i in range(105):
        _write(repo, f'docs/en/section-{i:03d}.md', f'content {i}')
    for name in ('material_privado/EMPRESA-SINTETICA/originales/privado.md',
                 'hermes_business_brain/.venv/tool.txt',
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
                self.assertIn('hermes_business_brain/skills/ce-desarrollo-empresa/SKILL.md', names)
                self.assertIn('hermes_business_brain/data/modelo/clases_documentales.json', names)
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
                self.assertIn('hermes_business_brain/engine/cerebro.py', archive.namelist())
                self.assertIn('LICENSE', archive.namelist())
                self.assertIn('plugin.yaml', archive.namelist())
                for expected in ('README.md', 'schemas.py', 'tools.py', '__init__.py',
                                 'hermes_business_brain/skills/ce-instalacion/SKILL.md',
                                 'docs/en/onboarding.md'):
                    self.assertIn(expected, archive.namelist())
                self.assertNotIn('material_privado/EMPRESA-SINTETICA/originales/privado.md',
                                 archive.namelist())
                self.assertNotIn('hermes_business_brain/.venv/tool.txt', archive.namelist())
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
