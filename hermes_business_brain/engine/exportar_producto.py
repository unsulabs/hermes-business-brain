#!/usr/bin/env python3
"""Export only versioned software; excludes pilots and private sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DIRECTORIES = {
    '.agents', '.cursor', 'contratos', 'docs', 'ejemplos', 'guia',
    'investigacion', 'metodologia', 'modelo', 'plantilla_boveda',
    'recursos', 'scripts', 'tests',
}
FILES = {
    '.gitignore', '.gitattributes', 'AGENTS.md', 'README.md', 'EMPIEZA_AQUI.md',
    'CHANGELOG.md', 'PROMPT_INICIO_CODEX.md',
    'PROMPT_RECUPERAR_EMPRESA_EXISTENTE_CODEX.md',
    'PROMPT_SUBIR_A_GITHUB.md', 'LICENSE', 'CONTRIBUTING.md',
    'requirements.txt', 'README.es.md', '.cursor-init.yaml', 'THIRD_PARTY_NOTICES.md',
    'START_HERE.md', 'GET_STARTED_WITH_CODEX.md', 'CONTINUE_WITH_CODEX.md',
}
MANIFEST = 'PRODUCT_MANIFEST.json'
# Also excluded below allowed folders and even where Git accepted them with
# --force. The names reserve private containers, not code files.
PRIVATE_COMPONENTS = frozenset({
    '.venv',
    'material_privado', 'instancias', 'legado_rechazado',
    'banco-transcripciones', 'recepcion', 'corpus', 'transcripciones_completas',
})


def es_ruta_privada(path: str) -> bool:
    return any(part.casefold() in PRIVATE_COMPONENTS for part in path.split('/'))


is_private_path = es_ruta_privada


def _git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(root), *args])


def exportar(root: Path, destino: Path) -> dict:
    root, destino = root.resolve(), destino.expanduser().resolve()
    if root == destino or root in destino.parents:
        raise ValueError('The package must be saved outside the repository')
    sha = _git(root, 'rev-parse', 'HEAD').decode().strip()
    tracked = [x.decode('utf8') for x in _git(root, 'ls-tree', '-r', '--name-only', '-z', 'HEAD').split(b'\0') if x]
    selected = [p for p in tracked
                if (p in FILES or p.split('/')[0] in DIRECTORIES)
                and not es_ruta_privada(p)]
    if not {'AGENTS.md', 'README.md', 'scripts/cerebro.py',
            '.agents/skills/ce-instalacion/SKILL.md'} <= set(selected):
        raise ValueError('Essential product files are missing')
    if not selected:
        raise ValueError('No product files found')
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + '.incompleto')
    try:
        with tmp.open('wb') as output:
            subprocess.run(['git', '-C', str(root), 'archive', '--format=zip', 'HEAD',
                            '--', *selected], stdout=output, check=True)
        with zipfile.ZipFile(tmp) as archive:
            entries = {name for name in archive.namelist() if not name.endswith('/')}
            if entries != set(selected) or any(es_ruta_privada(p) for p in entries):
                raise ValueError('Incomplete package or contains private files')
            bad = archive.testzip()
            if bad:
                raise ValueError('Invalid ZIP: ' + bad)
            manifest = {
                'formato': 'ce-producto-distribuible-1.0',
                'commit': sha,
                'archivos': [
                    {'ruta': name, 'bytes': len(data),
                     'sha256': hashlib.sha256(data).hexdigest()}
                    for name in sorted(entries)
                    for data in [archive.read(name)]
                ],
                'exclusiones': [name + '/' for name in sorted(PRIVATE_COMPONENTS)],
                'alcance_exclusiones': 'Any path component, case-insensitive',
            }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                     indent=2) + '\n').encode('utf8')
        with zipfile.ZipFile(tmp, 'a') as archive:
            item = zipfile.ZipInfo(MANIFEST, (1980, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, manifest_bytes)
        with zipfile.ZipFile(tmp) as archive:
            final_files = {name for name in archive.namelist() if not name.endswith('/')}
            if archive.testzip() or final_files != entries | {MANIFEST}:
                raise ValueError('Final ZIP invalid or incomplete')
        tmp.replace(destino)
    finally:
        tmp.unlink(missing_ok=True)
    return {'sha_producto': sha, 'archivos': len(selected), 'salida': str(destino),
            'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'material_privado_incluido': False}
