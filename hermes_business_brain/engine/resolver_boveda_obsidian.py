#!/usr/bin/env python3
"""Resolve an explicit vault or project against local and native registries, read-only."""
# ruff: noqa: TRY004  (upstream-identical: ValueError with an English message)
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .registrar_boveda_obsidian import (
    FORMAT,
    NATIVE,
    REGISTRY,
    canonical,
    read_json,
    safe_relative,
)


def resolve(registry_path: Path, native_path: Path, *, selector: str | None = None,
            project: Path | None = None) -> dict:
    if (selector is None) == (project is None):
        raise ValueError("Provide exactly one explicit selector or project")
    registry = read_json(registry_path)
    entries = registry.get("vaults")
    if registry.get("format") != FORMAT or not isinstance(entries, list):
        raise ValueError("Unknown selector registry format")
    matches = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid registry entry")
        for key in ("id", "name", "path", "instructions", "entrypoint"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                raise ValueError(f"Invalid registry field: {key}")
        for key in ("aliases", "projects"):
            if not isinstance(entry.get(key, []), list) or not all(
                    isinstance(item, str) and item.strip() for item in entry.get(key, [])):
                raise ValueError(f"Invalid registry field: {key}")
        if not Path(entry["path"]).is_absolute():
            raise ValueError("Vault registry paths must be absolute")
        if selector is not None:
            tokens = [entry["id"], entry["name"], *entry.get("aliases", [])]
            selected = any(selector.casefold() == token.casefold() for token in tokens)
            if Path(selector).expanduser().is_absolute():
                selected |= canonical(selector) == canonical(entry["path"])
        else:
            target = canonical(project)
            selected = False
            for value in entry.get("projects", []):
                if not Path(value).is_absolute():
                    raise ValueError("Project registry paths must be absolute")
                root = canonical(value)
                selected |= target == root or root in target.parents
        if selected:
            matches.append(entry)
    if len(matches) != 1:
        raise ValueError("Destination missing or ambiguous; require one registered match")
    entry = matches[0]
    vault = canonical(entry["path"])
    native = read_json(native_path).get("vaults")
    if not isinstance(native, dict):
        raise ValueError("Invalid native Obsidian registry")
    ids = [key for key, value in native.items() if isinstance(value, dict)
           and isinstance(value.get("path"), str) and Path(value["path"]).is_absolute()
           and canonical(value["path"]) == vault]
    if ids != [entry["id"]]:
        raise ValueError("Native Obsidian ID/path mismatch; open the vault in Obsidian and review registration")
    # No vault contents are opened. Check instruction destinations only after native proof.
    if not vault.is_dir():
        raise ValueError("Registered vault does not exist")
    paths = {}
    for key in ("instructions", "entrypoint"):
        path = canonical(vault / safe_relative(entry[key]))
        if not path.is_relative_to(vault) or not path.is_file():
            raise ValueError(f"Missing vault {key}")
        paths[key] = str(path)
    return {"status": "selected", "id": entry["id"], "name": entry["name"],
            "path": str(vault), "native_registry_verified": True, **paths}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selector")
    group.add_argument("--project", type=Path)
    parser.add_argument("--registro", type=Path, default=REGISTRY)
    parser.add_argument("--nativo", type=Path, default=NATIVE)
    args = parser.parse_args()
    try:
        result = resolve(args.registro, args.nativo, selector=args.selector, project=args.project)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
