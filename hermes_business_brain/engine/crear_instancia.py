#!/usr/bin/env python3
"""Creates a new company vault from an empty template. Never overwrites."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / 'plantilla_boveda'


def create(company_id: str, name: str, dest: Path) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{1,63}', company_id):
        raise ValueError('The ID must have 2-64 characters: letters, digits, hyphen or underscore')
    if not name.strip() or '\n' in name or '\r' in name:
        raise ValueError('Empty company name or contains line breaks')
    dest = dest.expanduser().resolve()
    if dest.exists():
        raise FileExistsError(f'Safe failure: destination already exists: {dest}')
    try:
        shutil.copytree(TEMPLATE, dest)
        for p in dest.rglob('*'):
            if p.is_file() and p.suffix in {'.md', '.yaml', '.json'}:
                if p.name == 'config_empresa.yaml':
                    config = yaml.safe_load(p.read_text(encoding='utf-8'))
                    config.update({'company_id': company_id, 'company_name': name})
                    p.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8', newline='\n')
                else:
                    txt = p.read_text(encoding='utf-8')
                    txt = txt.replace('{{EMPRESA_ID}}', company_id).replace('{{EMPRESA_NOMBRE}}', name)
                    p.write_text(txt, encoding='utf-8', newline='\n')
    except Exception:
        if dest.exists(): shutil.rmtree(dest)
        raise
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--id', required=True)
    ap.add_argument('--nombre', required=True)
    ap.add_argument('--dest', type=Path, required=True)
    a = ap.parse_args()
    try:
        print('VAULT CREATED:', create(a.id, a.nombre, a.dest))
    except (ValueError, FileExistsError) as e:
        ap.error(str(e))

if __name__ == '__main__': main()
