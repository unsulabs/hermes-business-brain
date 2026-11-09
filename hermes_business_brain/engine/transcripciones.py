#!/usr/bin/env python3
"""Transcript custody and agent-authored analysis. Console output omits passages."""
import json
from collections import Counter
from pathlib import Path
import sys

from .transcripciones_modelo import (ModelError, atomic_write, json_bytes, load_json,
    read_bytes, result, safe_id, safe_path, sha256_bytes, validate_bank_location)
from .transcripciones_custodia import load_catalog, register_capture, verify_bank
from .transcripciones_inventario import reconcile, validate_inventory
from .transcripciones_ingreso import ingest, read_parts_manifest
from .transcripciones_pipeline import (segment_capture, consolidate_analysis, coverage_report,
    review_snapshot, review_history, store_taxonomy)
from .transcripciones_segmentacion import SEGMENTER_VERSION
from .transcripciones_permisos import record_decision
from .transcripciones_indice import rebuild_index, watermark
from .transcripciones_contexto import build_context_request

COMMANDS = ("registrar", "ingresar", "estado", "verificar", "inventario-validar", "conciliar",
            "segmentar", "analizar", "cobertura", "indexar", "buscar", "revisar-antecedentes",
            "permiso", "taxonomia")


def _required(options, key, command):
    value = options.get(key)
    if value is None:
        raise ModelError("ARGUMENT_REQUIRED", f"Step '{command}' requires option '{key}'")
    return value


def _load_profile(profile):
    """Accept an in-memory profile dict or a path to a sealed profile JSON file."""
    if isinstance(profile, dict):
        return profile
    return load_json(profile)


def validate_context(*, bank, profile, purpose, request_id, command=None, output=None):
    safe_id(request_id)
    profile = _load_profile(profile)
    if not isinstance(profile, dict) or not isinstance(profile.get("company_id"), str) or not profile["company_id"].strip():
        raise ModelError("PROFILE_INVALID")
    purposes = profile.get("allowed_purposes")
    if not isinstance(purposes, list) or not all(isinstance(p, str) and p.strip() for p in purposes):
        raise ModelError("PROFILE_INVALID")
    if purpose not in purposes:
        raise ModelError("PURPOSE_DENIED")
    bank = validate_bank_location(bank, vault=profile.get("vault"))
    if "bank" in profile and validate_bank_location(profile["bank"], vault=profile.get("vault")) != bank:
        raise ModelError("BANK_PROFILE_MISMATCH")
    # Output is a separately requested report, never an overwrite of source data.
    output_safe = False
    if output:
        output_path = Path(output)
        if command == "buscar":
            validate_bank_location(output_path.parent, vault=profile.get("vault"))
        safe_path(output_path.parent, output_path.name)
        if output_path.exists():
            raise ModelError("OUTPUT_EXISTS")
        output_safe = True
    return profile, output_safe


def _execute(*, command, bank, profile, purpose, request_id, audience, commit, output, options, output_safe):
    scope = dict(company=profile["company_id"], audience=audience, purpose=purpose)
    if command == "segmentar":
        return segment_capture(bank, _required(options, "tr_id", command), _required(options, "version", command),
                               **scope, policy=options.get("policy", SEGMENTER_VERSION),
                               max_core_bytes=options.get("max_core_bytes", 4096),
                               context_bytes=options.get("context_bytes", 256), commit=commit)
    if command == "analizar":
        return consolidate_analysis(bank, load_json(_required(options, "input", command)), **scope, commit=commit)
    if command == "cobertura":
        return coverage_report(bank, _required(options, "tr_id", command), _required(options, "run", command), **scope)
    if command == "taxonomia":
        if purpose != "local_analysis":
            raise ModelError("ANALYSIS_SCOPE_REQUIRED")
        event = options.get("event")
        return store_taxonomy(bank, load_json(_required(options, "input", command)),
                              event=load_json(event) if event else None, commit=commit)
    if command == "permiso":
        decision = load_json(_required(options, "input", command))
        if decision.get("company") != profile["company_id"] or purpose != "custody":
            raise ModelError("PERMISSION_SCOPE_MISMATCH")
        row = record_decision(bank, decision, commit=commit)
        return result("permiso", evidence={"sequence": row["sequence"], "committed": commit,
                                           "decision_hash": sha256_bytes(json_bytes(row))})
    if command == "indexar":
        if purpose not in ("local_analysis", "internal_query"):
            raise ModelError("INDEX_SCOPE_REQUIRED")
        report = rebuild_index(bank, None if options.get("snapshot") == "current" else options.get("snapshot"),
                               **scope, commit=commit)
        return result("indexar", evidence=report)
    if command == "buscar":
        if not output:
            raise ModelError("PRIVATE_OUTPUT_REQUIRED")
        request = load_json(_required(options, "request", command))
        if not isinstance(request, dict) or set(request) - {"query", "company", "audience", "purpose", "references", "limit",
                                                           "task", "entities", "period", "mode"}:
            raise ModelError("QUERY_REQUEST_INVALID")
        if request.get("company") != profile["company_id"] or request.get("purpose") != purpose or purpose not in ("internal_query", "local_analysis", "evaluation"):
            raise ModelError("QUERY_SCOPE_MISMATCH")
        package = build_context_request(dict(request, bank=bank))
        return result("buscar", evidence={"context": package})
    if command == "revisar-antecedentes":
        results = options.get("results")
        return review_history(bank, load_json(_required(options, "event", command)),
                              _required(options, "snapshot", command), **scope,
                              results=load_json(results) if results else None,
                              previous_path=options.get("previous"),
                              taxonomy_version=options.get("taxonomy_version"), commit=commit)
    if command == "registrar":
        return register_capture(bank, _required(options, "capture_manifest", command), commit=commit)
    if command == "ingresar":
        expected, closed = options.get("expected_parts"), options.get("closed")
        parts_manifest = options.get("parts_manifest")
        file = options.get("file")
        payload = options.get("payload")
        if parts_manifest:
            if expected is not None or closed:
                raise ModelError("PARTS_OPTIONS_CONFLICT")
            parts, expected, closed = read_parts_manifest(parts_manifest)
        elif payload is not None:
            parts = [(1, payload)]
        elif file:
            parts = [(1, read_bytes(Path(file).parent, Path(file).name))]
        else:
            raise ModelError("SOURCE_REQUIRED", "Step 'ingresar' requires one of source file, payload, or parts manifest")
        return ingest(bank, job_id=request_id, account_id=_required(options, "account_id", command),
                      source_id=_required(options, "source_id", command),
                      attempt_id=_required(options, "attempt_id", command), parts=parts,
                      closed=closed, expected_parts=expected,
                      method="pasted-text" if payload is not None else "file-import", commit=commit)
    if command == "verificar":
        return verify_bank(bank)
    if command == "estado":
        rows = load_catalog(bank)
        dimensions = {dimension: dict(Counter(row["states"][dimension] for row in rows))
                      for dimension in ("integrity", "completeness", "analysis", "editorial", "validity")}
        evidence = {"transcriptions": len(rows), "states": dimensions,
                    "account_count": len({o["account_id"] for row in rows for o in row["occurrences"]}),
                    "index_watermark": watermark(bank)}
        if audience:
            evidence["review_snapshot_id"] = review_snapshot(bank, **scope)["snapshot_id"]
        return result("estado", evidence=evidence)
    snapshot = load_json(_required(options, "snapshot", command))
    if command == "inventario-validar":
        return result(command, input_hashes=[sha256_bytes(json_bytes(snapshot))], evidence=validate_inventory(snapshot))
    return reconcile(snapshot, load_catalog(bank))


def execute_request(*, command, bank, profile, purpose, request_id, audience=None, commit=False, output=None, options=None):
    """In-process equivalent of the upstream CLI entry point.

    Returns the same plain result dict the upstream CLI printed to stdout
    (upstream JSON keys preserved, English messages). Validation errors are
    raised as ModelError for the caller to translate into BrainError.
    """
    if command not in COMMANDS:
        raise ModelError("COMMAND_UNKNOWN", f"Unknown transcript step '{command}'")
    options = dict(options or {})
    profile, output_safe = validate_context(bank=bank, profile=profile, purpose=purpose,
                                            request_id=request_id, command=command, output=output)
    output_ = _execute(command=command, bank=bank, profile=profile, purpose=purpose,
                       request_id=request_id, audience=audience, commit=commit,
                       output=output, options=options, output_safe=output_safe)
    output_.update(operation=command, request_id=request_id)
    if output_["warnings"] and output_["status"] == "DONE":
        output_["status"] = "DONE_WITH_CONCERNS"
    if output and (command != "buscar" or output_safe):
        try:
            path = Path(output)
            safe_path(path.parent, path.name)
            if path.exists():
                raise ModelError("OUTPUT_EXISTS")
            atomic_write(path.parent, path.name, json_bytes(output_))
            if command == "buscar" and not output_["errors"]:
                package = output_["evidence"]["context"]
                replaced = result("buscar", request_id=request_id,
                                  outputs=[{"path": str(path.absolute()), "sha256": sha256_bytes(json_bytes(output_))}],
                                  evidence={"candidate_count": len(package["candidates"]), "abstention": package["abstention"],
                                            "semantic_answer_generated": False})
                output_ = replaced
        except (ModelError, OSError, ValueError, TypeError):
            raise
    return output_


def main(argv=None):
    """CLI entry kept for parity/debugging; the native API is execute_request."""
    import argparse
    description = "Transcript custody and agent-authored analysis. Console output omits passages."
    p = argparse.ArgumentParser(description=description)
    commands = p.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        sub = commands.add_parser(name)
        for flag in ("bank", "profile", "request-id", "purpose"):
            sub.add_argument("--" + flag, required=True)
        sub.add_argument("--output", help="Optional immutable JSON report path")
        if name in ("registrar", "ingresar", "segmentar", "analizar", "indexar", "revisar-antecedentes", "permiso", "taxonomia"):
            sub.add_argument("--commit", action="store_true", help="Apply local custody mutation; default is preview")
        if name in ("segmentar", "analizar", "cobertura", "indexar", "revisar-antecedentes"):
            sub.add_argument("--audience", required=True)
        elif name == "estado":
            sub.add_argument("--audience")
        if name == "registrar":
            sub.add_argument("--capture-manifest", required=True)
        elif name in ("conciliar", "inventario-validar"):
            sub.add_argument("--snapshot", required=True)
        elif name == "ingresar":
            source = sub.add_mutually_exclusive_group(required=True)
            source.add_argument("--archivo")
            source.add_argument("--stdin", action="store_true", help="Preserve pasted UTF-8/input bytes from standard input")
            source.add_argument("--parts-manifest")
            for flag in ("source-id", "account-id", "attempt-id"):
                sub.add_argument("--" + flag, required=True)
            sub.add_argument("--closed", action="store_true")
            sub.add_argument("--expected-parts", type=int)
        elif name == "segmentar":
            sub.add_argument("--tr-id", required=True)
            sub.add_argument("--version", required=True)
            sub.add_argument("--policy", required=True)
            sub.add_argument("--max-core-bytes", type=int, default=4096)
            sub.add_argument("--context-bytes", type=int, default=256)
        elif name in ("analizar", "permiso", "taxonomia"):
            sub.add_argument("--input", required=True)
            if name == "taxonomia":
                sub.add_argument("--event")
        elif name == "cobertura":
            sub.add_argument("--tr-id", required=True)
            sub.add_argument("--run", required=True)
        elif name == "indexar":
            sub.add_argument("--snapshot", required=True, help="Expected watermark, or current for the live snapshot")
        elif name == "buscar":
            sub.add_argument("--request", required=True, help="Query/company/audience/purpose JSON; --output is required")
        elif name == "revisar-antecedentes":
            sub.add_argument("--event", required=True)
            sub.add_argument("--snapshot", required=True)
            sub.add_argument("--results", help="Optional agent-authored JSON results array")
            sub.add_argument("--previous", help="Prior immutable review bundle path relative to bank")
            sub.add_argument("--taxonomy-version", help="Exact stored taxonomy for resolved claim identities")
    args = p.parse_args(argv)
    aliases = {"archivo": "file"}
    options = {}
    for key in ("capture_manifest", "archivo", "parts_manifest", "source_id", "account_id",
                "attempt_id", "closed", "expected_parts", "tr_id", "version", "policy",
                "max_core_bytes", "context_bytes", "input", "event", "run", "snapshot",
                "request", "results", "previous", "taxonomy_version"):
        if hasattr(args, key):
            options[aliases.get(key, key)] = getattr(args, key)
    if getattr(args, "stdin", False):
        options["payload"] = sys.stdin.buffer.read()
    try:
        output = execute_request(command=args.command, bank=args.bank, profile=args.profile,
                                 request_id=args.request_id, purpose=args.purpose,
                                 audience=getattr(args, "audience", None), commit=args.commit,
                                 output=args.output, options=options)
    except (ModelError, OSError, ValueError, TypeError, KeyError) as exc:
        code = exc.code if isinstance(exc, ModelError) else "INPUT_OR_IO_INVALID"
        output = result(args.command, request_id=args.request_id, status="BLOCKED")
        output["errors"] = [{"code": code, "field": "input", "cause": "Input or local custody validation failed",
                             "recoverable": True, "next_action": "Correct the reported input condition and retry"}]
        output["next_action"] = output["errors"][0]["next_action"]
    # JSON remains lossless even when Windows redirects stdout through cp1252.
    print(json.dumps(output, ensure_ascii=True, sort_keys=True, indent=2))
    return 0 if output["status"] in ("DONE", "DONE_WITH_CONCERNS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
