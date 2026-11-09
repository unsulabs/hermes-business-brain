"""Bounded plan and migration of visible names, without changing editorial identity.

The private input contains {"notas": [{"id": "...", "nombre": "Readable subject"}]}.
Only rewrites wiki-link destinations and Canvas paths; backs up the original
bytes outside Git/vault. Does not create knowledge or touch Bases.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from .lib_ce import (
    WIKI_RE,
    notes_in_vault,
    resolve_link,
    target_index,
    visible_filename,
)
from .operacion import index_ids, safe_vault
from .validar_boveda import validate

# Repository root (upstream operacion.ROOT analog).
ROOT = Path(__file__).resolve().parent.parent.parent


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_spec(path: Path) -> list[dict]:
    obj = json.loads(path.read_text(encoding='utf8'))
    rows = obj.get('notas') if isinstance(obj, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError('A non-empty list of notes is required')
    if any(not isinstance(x, dict) or not isinstance(x.get('id'), str)
           or not isinstance(x.get('nombre'), str) for x in rows):
        raise ValueError('Each note requires an id and a readable name')
    if len({x['id'] for x in rows}) != len(rows):
        raise ValueError('Repeated ID in the plan')
    return rows


def _rewrite_wiki(text: str, vault: Path, renames: dict[Path, Path],
                  paths: dict, names: dict) -> tuple[str, int]:
    count = 0
    def replace(match: re.Match) -> str:
        nonlocal count
        inner = match.group(1)
        target = inner.split('|', 1)[0]
        base, mark, anchor = target.partition('#')
        had_ext = base.endswith('.md')
        resolved = resolve_link(base, paths, names)
        if resolved not in renames:
            return match.group(0)
        new = renames[resolved].relative_to(vault).with_suffix('').as_posix()
        remainder = inner[len(target):]
        count += 1
        prefix = '!' if match.group(0).startswith('!') else ''
        return prefix + '[[' + new + ('.md' if had_ext else '') + (mark + anchor if mark else '') + remainder + ']]'
    return WIKI_RE.sub(replace, text), count


def _build(vault_path: Path, spec_path: Path) -> tuple[dict, dict[Path, bytes], dict[Path, Path]]:
    vault, _ = safe_vault(vault_path)
    if spec_path.resolve().is_relative_to(vault) or spec_path.resolve().is_relative_to(ROOT):
        raise ValueError('The private plan must be outside Git and outside the vault')
    prior = validate(vault)
    if prior['errores']:
        raise ValueError('Vault with previous errors: ' + '; '.join(prior['errores'][:3]))
    ids = index_ids(vault)
    renames: dict[Path, Path] = {}
    rows = []
    for row in _read_spec(spec_path):
        old = ids.get(row['id'])
        if old is None or old.is_symlink():
            raise ValueError('ID missing or symbolic: ' + row['id'])
        new = old.with_name(visible_filename(row['nombre']))
        if new != old:
            renames[old] = new
        rows.append({'id': row['id'], 'anterior': old.relative_to(vault).as_posix(),
                     'propuesta': new.relative_to(vault).as_posix(),
                     'sha_anterior': _sha(old.read_bytes())})
    all_notes = notes_in_vault(vault)
    destinations = [renames.get(p, p).relative_to(vault).as_posix().casefold() for p in all_notes]
    if len(set(destinations)) != len(destinations):
        raise ValueError('Visible-name collision with another note')
    # os.replace overwrites existing destinations: also block swaps
    # A -> B and B -> A, even if the final set has no duplicates.
    occupied = set(all_notes)
    for old, new in renames.items():
        if new in occupied and new != old:
            raise ValueError('Destination occupied by another note; migrate in stages without overwriting: '
                             + str(new.relative_to(vault)))
    paths, names = target_index(vault)
    changes: dict[Path, bytes] = {}
    affected = []
    for p in all_notes:
        if p.is_symlink():
            raise ValueError('Symbolic note not migrable: ' + str(p.relative_to(vault)))
        before = p.read_bytes()
        rewritten, count = _rewrite_wiki(before.decode('utf8'), vault, renames, paths, names)
        after = rewritten.encode('utf8')
        if after != before or p in renames:
            changes[p] = after
            affected.append({'ruta': p.relative_to(vault).as_posix(),
                             'sha_anterior': _sha(before), 'sha_propuesto': _sha(after),
                             'enlaces_actualizados': count})
    # Canvas are derived views with file paths; their content is not authority.
    for p in vault.rglob('*.canvas'):
        if p.is_symlink(): raise ValueError('Symbolic Canvas: ' + str(p))
        original = p.read_bytes()
        obj = json.loads(original)
        count = 0
        def visit(value):
            nonlocal count
            if isinstance(value, dict):
                for k, v in value.items():
                    if k == 'file' and isinstance(v, str):
                        old = vault / v
                        if old in renames:
                            value[k] = renames[old].relative_to(vault).as_posix()
                            count += 1
                    else: visit(v)
            elif isinstance(value, list):
                for item in value: visit(item)
        visit(obj)
        if count:
            updated = (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode()
            changes[p] = updated
            affected.append({'ruta': p.relative_to(vault).as_posix(),
                             'sha_anterior': _sha(original), 'sha_propuesto': _sha(updated),
                             'enlaces_actualizados': count})
    # Other formats with exact paths require a specific migrator.
    old_paths = [p.relative_to(vault).as_posix() for p in renames]
    # A normal Markdown link must not be left pointing at a path that changes.
    # It is blocked so the operator handles it explicitly with URL/fragment
    # syntax, instead of leaving a silent broken reference.
    for p in all_notes:
        content = p.read_text(encoding='utf8')
        if any(re.search(r'\]\([^)]*' + re.escape(old) + r'[^)]*\)', content)
               for old in old_paths):
            raise ValueError('Markdown link to old path not migrable: ' + str(p.relative_to(vault)))
    for p in vault.rglob('*'):
        if not p.is_file() or p.suffix not in {'.base', '.json', '.yaml', '.yml'}:
            continue
        if p.name == 'workspace.json' or '.obsidian' in p.parts:
            continue
        content = p.read_text(encoding='utf8')
        if any(old in content for old in old_paths):
            raise ValueError('Reference to old path in non-migrable format: ' + str(p.relative_to(vault)))
    fingerprint = _sha(json.dumps({'notas': rows, 'afectados': affected},
                                  sort_keys=True, ensure_ascii=True).encode())
    report = {'sha_plan': fingerprint, 'notas': rows, 'afectados': affected,
              'renombradas': len(renames), 'archivos_afectados': len(changes),
              'errores_previos': len(prior['errores'])}
    return report, changes, renames


def plan(vault: Path, spec: Path) -> dict:
    return _build(vault, spec)[0]


def apply(vault_path: Path, spec: Path, backup_dir: Path, expected_sha: str) -> dict:
    report, changes, renames = _build(vault_path, spec)
    vault, _ = safe_vault(vault_path)
    backup = backup_dir.expanduser().absolute()
    if report['sha_plan'] != expected_sha:
        raise ValueError('sha_plan stale; regenerate the plan')
    if (backup.exists() or backup == ROOT or backup.is_relative_to(ROOT)
        or backup == vault or backup.is_relative_to(vault) or backup.is_symlink()):
        raise ValueError('Backup must be a new private path outside Git and the vault')
    old_bytes = {p: p.read_bytes() for p in changes}
    for item in report['afectados']:
        p = vault / item['ruta']
        if _sha(old_bytes[p]) != item['sha_anterior']:
            raise ValueError('Concurrent change: ' + item['ruta'])
    backup.mkdir(parents=True, mode=0o700)
    try:
        for p, data in old_bytes.items():
            dest = backup / p.relative_to(vault)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        (backup / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
        for p, data in old_bytes.items():
            if p.read_bytes() != data:
                raise ValueError('Concurrent change before applying: '+str(p.relative_to(vault)))
        for old, new in renames.items():
            os.replace(old, new)
        for old, data in changes.items():
            target = renames.get(old, old)
            temp = target.with_name('.'+target.name+'.tmp-'+uuid4().hex[:8])
            temp.write_bytes(data)
            os.replace(temp, target)
        result = validate(vault)
        if result['errores']:
            raise ValueError('Posterior validation: '+'; '.join(result['errores'][:3]))
    except Exception:
        for old, new in renames.items():
            if new.exists(): new.unlink()
        for p, data in old_bytes.items():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        raise
    return {**report, 'respaldo': str(backup), 'validacion': 'PASS',
            'reversion': 'Restore only the manifest files after verifying current fingerprints; do not use git reset.'}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vault', required=True, type=Path)
    ap.add_argument('--spec', required=True, type=Path)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--sha-plan')
    ap.add_argument('--backup-dir', type=Path)
    args = ap.parse_args()
    if args.apply:
        if not args.sha_plan or not args.backup_dir:
            ap.error('--apply requires --sha-plan and --backup-dir')
        report = apply(args.vault, args.spec, args.backup_dir, args.sha_plan)
    else:
        report = plan(args.vault, args.spec)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
