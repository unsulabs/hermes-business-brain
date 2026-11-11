"""JSON schemas for the 18 hermes-business-brain tools (v2).

Every ``TOOL_SCHEMAS`` entry is a full tool schema as ``register_tool`` expects it:
``{"name", "description", "parameters": {"type": "object", "properties", "required"}}``.

Argument names mirror the keyword arguments of the matching ``hermes_business_brain.engine.api``
operation (see the repo's engine contract); for the engine operations they follow the upstream
Engine CLI flags (``--vault`` -> ``vault``, ``--tipo`` -> ``tipo``, ...) so tool ->
engine mapping stays mechanical. The engine is a native-English, in-process reimplementation;
handlers in tools.py call it directly, never as a subprocess.

All descriptions are English. Nothing here imports the engine: the plugin registers cleanly even
before the engine package exists.
"""

TOOL_SCHEMAS: dict[str, dict] = {
    "brain_doctor": {
        "name": "brain_doctor",
        "description": (
            "Read-only environment preflight for the business-brain toolkit: reports the Python "
            "interpreter, availability of PyYAML and jsonschema, Obsidian installation candidates, "
            "and optionally whether a vault's company configuration exists. Installs nothing and "
            "writes nothing. Engine op: doctor."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to a vault to include in the preflight report.",
                },
            },
            "required": [],
        },
    },
    "brain_create_vault": {
        "name": "brain_create_vault",
        "description": (
            "Create a new empty business vault from the bundled Obsidian template. Never "
            "overwrites: fails if the destination already exists. Engine op: create_vault."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Company id, 2-64 chars: letters, digits, dash or underscore.",
                },
                "name": {
                    "type": "string",
                    "description": "Display name for the company (no newlines).",
                },
                "dest": {
                    "type": "string",
                    "description": "Absolute path where the new vault directory is created; must not exist.",
                },
            },
            "required": ["id", "name", "dest"],
        },
    },
    "brain_validate_vault": {
        "name": "brain_validate_vault",
        "description": (
            "Validate the structural integrity of a business vault: note ids, wikilinks, transfers "
            "and frontmatter. Integrity only, never business truth. Engine op: validate_vault."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory to validate.",
                },
            },
            "required": ["vault"],
        },
    },
    "brain_status": {
        "name": "brain_status",
        "description": (
            "Structural summary of a company vault: company id and name, note counts by type, "
            "editorial state, installed templates and bases, source summary. Read-only count, not "
            "validated truth. Engine op: status."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
            },
            "required": ["vault"],
        },
    },
    "brain_register_vault": {
        "name": "brain_register_vault",
        "description": (
            "Register an already-open Obsidian vault in the Codex local router so Codex can resolve "
            "it. Updates the Codex selector registry only; requires the vault to already have an id "
            "in Obsidian's native registry. May read/write the user's Codex and Obsidian registry "
            "files under the home directory - override with registro/nativo. Engine op: "
            "register_vault."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault already opened in Obsidian.",
                },
                "name": {
                    "type": "string",
                    "description": "Human-readable name for the vault entry.",
                },
                "alias": {
                    "type": "string",
                    "description": "Business id used as an alias, e.g. EMPRESA-001.",
                },
                "registry": {
                    "type": "string",
                    "description": (
                        "Absolute path to the Codex vaults registry JSON "
                        "(default ~/.codex/obsidian/vaults.json)."
                    ),
                },
                "nativo": {
                    "type": "string",
                    "description": "Absolute path to the Obsidian native registry JSON (platform default).",
                },
                "instructions": {
                    "type": "string",
                    "description": "Vault-relative instructions file (default 90_Sistema/Como_usar.md).",
                },
                "entrypoint": {
                    "type": "string",
                    "description": "Vault-relative entrypoint note (default Inicio.md).",
                },
                "proyecto": {
                    "type": "string",
                    "description": (
                        "Absolute path of the Codex project directory that should resolve this vault."
                    ),
                },
            },
            "required": ["vault", "name", "alias"],
        },
    },
    "brain_resolve_vault": {
        "name": "brain_resolve_vault",
        "description": (
            "Resolve which registered vault a Codex project (or a selector string) maps to, "
            "verifying it against Obsidian's native registry. Read-only for the registries. Use "
            "before operating on a vault to confirm identity. Engine op: resolve_vault."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": (
                        "Selector matching a registered id, name, alias or absolute vault path "
                        "(exactly one of selector/project must be given)."
                    ),
                },
                "project": {
                    "type": "string",
                    "description": (
                        "Absolute path of the Codex project whose registered vault should be "
                        "resolved (exactly one of selector/project must be given)."
                    ),
                },
                "registry": {
                    "type": "string",
                    "description": (
                        "Absolute path to the Codex vaults registry JSON "
                        "(default ~/.codex/obsidian/vaults.json)."
                    ),
                },
                "nativo": {
                    "type": "string",
                    "description": "Absolute path to the Obsidian native registry JSON (platform default).",
                },
            },
            "required": [],
            "oneOf": [{"required": ["selector"]}, {"required": ["project"]}],
        },
    },
    "brain_query": {
        "name": "brain_query",
        "description": (
            "Contextual consultation over a vault: candidate note blocks matched by literal text, "
            "with optional topic/scope/date filters and a candidate limit; set orientar to order "
            "candidates by the terms of a natural request. Returns candidates only, never a "
            "generated semantic answer. Engine op: query."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
                "texto": {
                    "type": "string",
                    "description": "Literal text to match against note blocks.",
                },
                "tema": {
                    "type": "string",
                    "description": "Optional topic filter.",
                },
                "ambito": {
                    "type": "string",
                    "description": "Optional scope filter.",
                },
                "fecha": {
                    "type": "string",
                    "description": "Optional date filter (YYYY-MM-DD).",
                },
                "limite": {
                    "type": "integer",
                    "description": "Maximum number of candidates (default 10).",
                },
                "orientar": {
                    "type": "boolean",
                    "description": (
                        "Order candidates by terms from a natural request instead of raw match "
                        "strength (default false)."
                    ),
                },
            },
            "required": ["vault", "texto"],
        },
    },
    "brain_capture": {
        "name": "brain_capture",
        "description": (
            "Save preliminary findings as a draft capture note in the vault without declaring them "
            "approved knowledge. The synthesis markdown must be prepared in a file outside the "
            "vault and Git; sources, if any, must already be registered with brain_references. "
            "Engine op: capture."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
                "title": {
                    "type": "string",
                    "description": "Title of the capture note.",
                },
                "source": {
                    "type": "string",
                    "description": (
                        "Absolute path to the authorized synthesis markdown file outside the vault "
                        "and Git."
                    ),
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Source ids (F-...) already registered with brain_references; repeatable.",
                },
            },
            "required": ["vault", "title", "source"],
        },
    },
    "brain_knowledge_map": {
        "name": "brain_knowledge_map",
        "description": (
            "Preview the knowledge map (Markdown/Canvas renderings) derived from the vault's notes "
            "and relations. Read-only by default; with publish: true, publishes only the derived "
            "map with an exact SHA confirmation and an external backup. Engine op: knowledge_map."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
                "publish": {
                    "type": "boolean",
                    "description": "Publish the derived map instead of previewing it (default false).",
                },
                "sha_actual": {
                    "type": "string",
                    "description": "For publish: SHA-256 of the currently published map.",
                },
                "sha_propuesto": {
                    "type": "string",
                    "description": "For publish: SHA-256 of the proposed map.",
                },
                "confirmacion": {
                    "type": "string",
                    "description": "For publish: explicit confirmation phrase (PUBLICAR MAPA <sha>).",
                },
                "backup_dir": {
                    "type": "string",
                    "description": "For publish: absolute path of the external backup directory.",
                },
            },
            "required": ["vault"],
        },
    },
    "brain_relations": {
        "name": "brain_relations",
        "description": (
            "Query typed relations stored in a vault and their real state (proposals, "
            "confirmations). Read-only. Engine op: relations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
                "id": {
                    "type": "string",
                    "description": "Filter: relation originates from or targets this note id.",
                },
            },
            "required": ["vault"],
        },
    },
    "brain_references": {
        "name": "brain_references",
        "description": (
            "Local versioned external-reference registry over a private bank directory (custody "
            "area outside any vault and any Git worktree). Registers metadata only - never imports "
            "content, never touches the network. Records are prepared as JSON files outside the "
            "vault, then committed here. Engine op: references."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": (
                        "Optional vault path accepted as an alias for bank (the engine's knowledge "
                        "contract keeps vault in every signature)."
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": ["register", "read", "decisions", "verify"],
                    "description": (
                        "Operation: register (add a metadata record), read (fetch one record), "
                        "decisions (list the permission chain), verify (transitive closure check)."
                    ),
                },
                "bank": {
                    "type": "string",
                    "description": (
                        "Absolute path to the private custody bank directory (must not be inside a "
                        "vault or Git worktree)."
                    ),
                },
                "commit": {
                    "type": "boolean",
                    "description": (
                        "Apply the custody mutation; default is a preview that validates without "
                        "writing (default false)."
                    ),
                },
                "metadata": {
                    "type": "string",
                    "description": (
                        "For register: absolute path to the JSON reference record prepared outside "
                        "the vault."
                    ),
                },
                "reference_id": {
                    "type": "string",
                    "description": "For read: id of the registered reference.",
                },
                "version_id": {
                    "type": "string",
                    "description": "For read: version id (EV-...) of the registered reference.",
                },
                "refs": {
                    "type": "string",
                    "description": (
                        "For verify: absolute path to a JSON array of reference descriptors to "
                        "verify transitively."
                    ),
                },
                "company": {
                    "type": "string",
                    "description": "For verify: company id scope.",
                },
                "audience": {
                    "type": "string",
                    "description": "For verify: audience scope.",
                },
                "purpose": {
                    "type": "string",
                    "description": "For verify: purpose scope (e.g. local_analysis, custody).",
                },
                "require_read": {
                    "type": "boolean",
                    "description": (
                        "For verify (default true): require reading evidence for external "
                        "references; pass false to relax the requirement."
                    ),
                },
                "require_internal": {
                    "type": "boolean",
                    "description": (
                        "For verify (default false): require 'interno' sensitivity for external "
                        "references."
                    ),
                },
                "decision": {
                    "type": "string",
                    "description": (
                        "For decisions: caller-supplied decision record (JSON path or inline "
                        "payload) when recording a permission decision."
                    ),
                },
            },
            "required": ["action", "bank"],
        },
    },
    "brain_naming": {
        "name": "brain_naming",
        "description": (
            "Plan (or apply) readable filename changes for a vault from a spec JSON prepared "
            "outside the vault and Git. Default is a read-only plan; pass apply: true to execute, "
            "which requires a backup directory. Engine op: naming."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
                "spec": {
                    "type": "string",
                    "description": "Absolute path to the naming spec JSON prepared outside the vault.",
                },
                "apply": {
                    "type": "boolean",
                    "description": "Apply the rename plan instead of only previewing it (default false).",
                },
                "sha_plan": {
                    "type": "string",
                    "description": "Expected SHA-256 of the plan file; rejects mismatches when applying.",
                },
                "backup_dir": {
                    "type": "string",
                    "description": "Absolute path of the backup directory (required when applying).",
                },
            },
            "required": ["vault", "spec"],
        },
    },
    "brain_transcript_cycle": {
        "name": "brain_transcript_cycle",
        "description": (
            "Drive one step of the transcript custody and analysis pipeline over a private "
            "transcript bank (custody area outside any Obsidian vault and Git worktree; the "
            "vault path IS the bank root). The full cycle is ingresar - registrar - segmentar - "
            "analizar - cobertura - indexar, plus read-only custody steps (estado, verificar, "
            "inventario-validar, conciliar) and buscar. Profile JSON must contain company_id and "
            "allowed_purposes and live outside the vault. Engine op: transcript_cycle."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": (
                        "Absolute path to the private transcript bank root (upstream --bank); must "
                        "not be inside an Obsidian vault or Git worktree."
                    ),
                },
                "step": {
                    "type": "string",
                    "enum": [
                        "ingresar",
                        "registrar",
                        "segmentar",
                        "analizar",
                        "cobertura",
                        "indexar",
                        "revisar-antecedentes",
                        "taxonomia",
                        "permiso",
                        "estado",
                        "verificar",
                        "inventario-validar",
                        "conciliar",
                        "buscar",
                    ],
                    "description": "Which pipeline step to run.",
                },
                "profile": {
                    "type": "string",
                    "description": (
                        "Absolute path to the profile JSON: {company_id, allowed_purposes:[...], "
                        "optional bank/vault}."
                    ),
                },
                "request_id": {
                    "type": "string",
                    "description": "Caller-supplied request id for the custody ledger (safe_id format).",
                },
                "purpose": {
                    "type": "string",
                    "description": (
                        "Purpose scope that must be allowed by the profile (e.g. custody, "
                        "local_analysis, internal_query)."
                    ),
                },
                "audience": {
                    "type": "string",
                    "description": (
                        "Audience scope; required for segmentar/analizar/cobertura/indexar/"
                        "revisar-antecedentes, optional for estado."
                    ),
                },
                "commit": {
                    "type": "boolean",
                    "description": "Apply the local custody mutation; default is a read-only preview.",
                },
                "output": {
                    "type": "string",
                    "description": (
                        "Optional absolute path for an immutable JSON report; must not already "
                        "exist (required for buscar)."
                    ),
                },
                "capture_manifest": {
                    "type": "string",
                    "description": "For registrar: absolute path to the capture receipt JSON produced by ingresar.",
                },
                "parts_manifest": {
                    "type": "string",
                    "description": "For ingresar: absolute path to a JSON parts manifest instead of a single file.",
                },
                "file": {
                    "type": "string",
                    "description": "For ingresar: absolute path to the transcript file to import.",
                },
                "payload": {
                    "type": "string",
                    "description": "For ingresar: inline raw ingest payload (alternative to file/parts_manifest).",
                },
                "source_id": {
                    "type": "string",
                    "description": "For ingresar: transcript source id.",
                },
                "account_id": {
                    "type": "string",
                    "description": "For ingresar: account id.",
                },
                "attempt_id": {
                    "type": "string",
                    "description": "For ingresar: attempt id.",
                },
                "closed": {
                    "type": "boolean",
                    "description": "For ingresar: mark the capture closed (complete).",
                },
                "expected_parts": {
                    "type": "integer",
                    "description": "For ingresar: expected part count for closed captures.",
                },
                "tr_id": {
                    "type": "string",
                    "description": "For segmentar/cobertura: transcript id.",
                },
                "version": {
                    "type": "string",
                    "description": "For segmentar: version id to segment.",
                },
                "policy": {
                    "type": "string",
                    "description": "For segmentar: segmentation policy id (default utf8-bytes-1).",
                },
                "max_core_bytes": {
                    "type": "integer",
                    "description": "For segmentar (default 4096): max bytes for a core segment.",
                },
                "context_bytes": {
                    "type": "integer",
                    "description": "For segmentar (default 256): context bytes around a segment.",
                },
                "run": {
                    "type": "string",
                    "description": "For cobertura: analysis run id.",
                },
                "input": {
                    "type": "string",
                    "description": (
                        "For analizar/permiso/taxonomia: absolute path to the JSON input payload "
                        "prepared outside the vault."
                    ),
                },
                "event": {
                    "type": "string",
                    "description": "For revisar-antecedentes/taxonomia: absolute path to the event JSON.",
                },
                "snapshot": {
                    "type": "string",
                    "description": (
                        "For revisar-antecedentes/inventario-validar/conciliar/indexar: snapshot "
                        "JSON path, or 'current' for the live watermark."
                    ),
                },
                "request": {
                    "type": "string",
                    "description": (
                        "For buscar: absolute path to the query request JSON {query, company, "
                        "audience, purpose, ...}."
                    ),
                },
                "results": {
                    "type": "string",
                    "description": "For revisar-antecedentes: optional agent-authored results JSON array path.",
                },
                "previous": {
                    "type": "string",
                    "description": "For revisar-antecedentes: prior review bundle path relative to the bank.",
                },
                "taxonomy_version": {
                    "type": "string",
                    "description": "For revisar-antecedentes: exact stored taxonomy version for claim resolution.",
                },
            },
            "required": ["vault", "step", "profile", "request_id", "purpose"],
        },
    },
    "brain_propose": {
        "name": "brain_propose",
        "description": (
            "Register a suggested change for a note in the change tray; does NOT touch the original "
            "note. The candidate text must be prepared in an authorized local file outside the "
            "vault and Git. Engine op: propose."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
                "id": {
                    "type": "string",
                    "description": "Exact id of the target note.",
                },
                "motivo": {
                    "type": "string",
                    "description": "Reason for the suggested change.",
                },
                "archivo": {
                    "type": "string",
                    "description": (
                        "Absolute path to the local authorized candidate text file outside the "
                        "vault and Git (max 120000 bytes)."
                    ),
                },
                "author": {
                    "type": "string",
                    "description": "Author recorded on the proposal (default agente).",
                },
            },
            "required": ["vault", "id", "motivo", "archivo"],
        },
    },
    "brain_card": {
        "name": "brain_card",
        "description": (
            "Create a draft record card (ficha) from a specific type in the candidate model; never "
            "invents data. Optional developed markdown must be prepared outside the vault and Git. "
            "Engine op: card."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
                "tipo": {
                    "type": "string",
                    "description": (
                        "Card type from the candidate model (e.g. empresa, persona, proyecto, "
                        "tarea); fuente requires the dedicated reference registration."
                    ),
                },
                "titulo": {
                    "type": "string",
                    "description": "Title of the record card.",
                },
                "resumen": {
                    "type": "string",
                    "description": "Optional summary (max 7000 chars).",
                },
                "archivo": {
                    "type": "string",
                    "description": (
                        "Absolute path to an optional developed note in Markdown, outside Git and "
                        "the vault, without YAML frontmatter."
                    ),
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Source ids (F-...) already registered; repeatable.",
                },
                "etiquetas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Obsidian thematic tags; repeatable.",
                },
            },
            "required": ["vault", "tipo", "titulo"],
        },
    },
    "brain_document": {
        "name": "brain_document",
        "description": (
            "Register a developed D01-D07 / X01-X07 document without approving it. The markdown "
            "must be prepared outside the vault and Git; sources, if any, must already be "
            "registered. Engine op: document."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
                "clase": {
                    "type": "string",
                    "description": "Document class, one of D01-D07 / X01-X07.",
                },
                "titulo": {
                    "type": "string",
                    "description": "Title of the document note.",
                },
                "archivo": {
                    "type": "string",
                    "description": (
                        "Absolute path to the developed Markdown prepared outside the vault and Git."
                    ),
                },
                "doc_id": {
                    "type": "string",
                    "description": "Optional identity Xnn-...; for Dnn classes it coincides with the class.",
                },
                "estado": {
                    "type": "string",
                    "enum": ["borrador", "en_revision"],
                    "description": "Editorial state (default borrador).",
                },
                "cobertura": {
                    "type": "string",
                    "enum": ["sin_fuente", "parcial", "suficiente_para_tarea", "no_aplica"],
                    "description": "Source coverage level.",
                },
                "fecha_corte": {
                    "type": "string",
                    "description": "Cut-off date YYYY-MM-DD; defaults to creation date.",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Source ids (F-...) already registered; repeatable.",
                },
                "etiquetas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Obsidian thematic tags; repeatable.",
                },
            },
            "required": ["vault", "clase", "titulo", "archivo"],
        },
    },
    "brain_knowledge_plan": {
        "name": "brain_knowledge_plan",
        "description": (
            "Audit the note map, tags and relations of a vault BEFORE drafting: read-only planning "
            "step driven by a structured JSON plan file prepared outside the vault and Git. Engine "
            "op: knowledge_plan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
                "archivo": {
                    "type": "string",
                    "description": (
                        "Absolute path to the structured JSON plan prepared outside Git and the vault."
                    ),
                },
            },
            "required": ["vault", "archivo"],
        },
    },
    "brain_dx_apply": {
        "name": "brain_dx_apply",
        "description": (
            "Apply a D/X modification proposal after specific authorization and backup. Requires "
            "exact SHA-256 fingerprints of the original and candidate documents and a backup "
            "directory; never edits without authorization evidence. Engine op: dx_apply."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the vault directory.",
                },
                "propuesta": {
                    "type": "string",
                    "description": "Absolute path to the authorized D/X proposal file.",
                },
                "sha_original": {
                    "type": "string",
                    "description": "SHA-256 of the current (original) document version.",
                },
                "sha_candidato": {
                    "type": "string",
                    "description": "SHA-256 of the candidate replacement document.",
                },
                "sha_fuentes": {
                    "type": "string",
                    "description": (
                        "SHA-256 of the resulting sources set, required when sources are added."
                    ),
                },
                "responsable": {
                    "type": "string",
                    "description": "Human responsible for the change.",
                },
                "referencia_autorizacion": {
                    "type": "string",
                    "description": "Authorization reference id (e.g. AUT-001).",
                },
                "backup_dir": {
                    "type": "string",
                    "description": "Absolute path of the backup directory.",
                },
            },
            "required": [
                "vault",
                "propuesta",
                "sha_original",
                "sha_candidato",
                "responsable",
                "referencia_autorizacion",
                "backup_dir",
            ],
        },
    },
    "brain_evolution_scan": {
        "name": "brain_evolution_scan",
        "description": (
            "Read-only evolution scan for a business vault: evaluates the promotion rules "
            "in reglas_evolucion.json against captured sources, D/X documents, entity cards "
            "and CONTROL notes, and returns evolution candidates (status ready/partial with "
            "evidence paths) plus areas whose revisit cadence is due. Writes nothing; "
            "candidates are proposals for the owner to confirm, never applied automatically. "
            "Engine op: evolution_scan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vault": {
                    "type": "string",
                    "description": "Absolute path to the business vault to scan.",
                },
            },
            "required": ["vault"],
        },
    },
}
