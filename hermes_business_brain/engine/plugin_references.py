"""In-process wrapper over the local external-reference registry.

Thin English facade over referencias_externas: register (metadata only),
read, decisions (permission chain) and verify (transitive closure). Never
touches the network and never imports content. This module is importable
without running argparse; the optional CLI is guarded by __main__.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import referencias_externas


def _as_object(value, label: str):
    """Accepts a JSON file path or an already-loaded dict/list."""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (str, Path)):
        path = Path(value).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"{label} file not found: {path}")
        return json.loads(path.read_text(encoding="utf8"))
    raise TypeError(f"{label} must be a JSON file path or an object: {value!r}")


def register(bank, metadata, *, commit=False):
    """Registers a reference record (metadata only)."""
    return referencias_externas.register_reference(
        Path(bank), _as_object(metadata, "metadata"), commit=bool(commit))


def read(bank, reference_id, version_id):
    return referencias_externas.read_reference(Path(bank), reference_id, version_id)


def decisions(bank):
    return {"decisiones": referencias_externas.external_decisions(Path(bank))}


def verify(bank, refs, *, company, audience, purpose, require_read=True,
           require_internal=False, commit=False, decision=None):
    """Verifies transitive closure over the given reference descriptors."""
    if decision is not None:
        return referencias_externas.record_external_decision(
            Path(bank), _as_object(decision, "decision"), commit=bool(commit))
    scope = {"company": company, "audience": audience, "purpose": purpose}
    return referencias_externas.verify_references(
        Path(bank), _as_object(refs, "refs"), scope,
        require_read=bool(require_read), require_internal=bool(require_internal))


def run(action: str, *, bank, metadata=None, reference_id=None, version_id=None,
        refs=None, company=None, audience=None, purpose=None, commit=False,
        require_read=True, require_internal=False, decision=None) -> dict:
    """Dispatches a wrapper action; mirrors the v0.1 plugin CLI actions."""
    action = action.lower()
    if action == "register":
        result = register(bank, metadata, commit=commit)
    elif action == "read":
        result = read(bank, reference_id, version_id)
    elif action == "decisions":
        result = decisions(bank)
    elif action == "verify":
        result = verify(bank, refs, company=company, audience=audience,
                        purpose=purpose, require_read=require_read,
                        require_internal=require_internal, commit=commit,
                        decision=decision)
    else:
        raise ValueError(f"Unknown references action: {action!r}")
    return {"action": action, "result": result}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["register", "read", "decisions", "verify"])
    ap.add_argument("--bank", type=Path, required=True)
    ap.add_argument("--metadata", type=Path)
    ap.add_argument("--reference-id")
    ap.add_argument("--version-id")
    ap.add_argument("--refs", type=Path)
    ap.add_argument("--company")
    ap.add_argument("--audience")
    ap.add_argument("--purpose")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--require-read", dest="require_read", action="store_true", default=True)
    ap.add_argument("--no-require-read", dest="require_read", action="store_false")
    ap.add_argument("--require-internal", action="store_true")
    ap.add_argument("--decision", type=Path)
    args = ap.parse_args()
    print(json.dumps(run(args.action, bank=args.bank, metadata=args.metadata,
                         reference_id=args.reference_id, version_id=args.version_id,
                         refs=args.refs, company=args.company, audience=args.audience,
                         purpose=args.purpose, commit=args.commit,
                         require_read=args.require_read,
                         require_internal=args.require_internal,
                         decision=args.decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
