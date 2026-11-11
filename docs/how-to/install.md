# How to install the business-brain plugin

This guide covers the two supported ways to install the
`hermes-business-brain` plugin, how to confirm the installation, and one
common mistake to avoid. It was verified against Hermes Agent v0.23.0
(`hermes --version`); the doctor output below comes from a real run.

## What you are installing

`hermes-business-brain` adds 18 local tools (`brain_create_vault`,
`brain_validate_vault`, `brain_status`, `brain_query`, `brain_capture`,
`brain_card`, `brain_document`, `brain_propose`, `brain_knowledge_plan`,
`brain_dx_apply`, and others — see the [README](../../README.md) for the full
table) backed by a native English engine that runs **in-process**, plus a set
of 21 bundled workflow skills
([How to use the bundled skills](use-bundled-skills.md)). Everything runs
locally, with no network access. The manifest declares two Python
dependencies, `PyYAML==6.0.3` and `jsonschema>=4.23,<5`, which Hermes' plugin
manager installs when the plugin is enabled (it asks for your consent first).

## Path A — from the catalog (once published)

When the plugin is published to the Hermes catalog, install it with:

```bash
hermes plugins install unsulabs/hermes-business-brain --enable
```

- `--enable` turns the plugin on immediately (skip the confirmation prompt).
- For a non-interactive install (CI, SSH, containers), add `--yes-deps` so the
  dependency consent question is answered for you.

> **Status note (verified 2026-11-06):** the catalog entry does not exist yet.
> `hermes plugins search hermes-business-brain` returns
> "No catalog entries matched 'hermes-business-brain'". Until it is
> published, use Path B below; keep this command for later.

## Path B — local symlink (development / testing)

Clone or copy the repository (`hermes-business-brain-unsulabs` in the
development prefix), then link it into the plugin directory and enable it:

```bash
mkdir -p ~/.hermes/plugins
ln -s /path/to/hermes-business-brain-unsulabs ~/.hermes/plugins/hermes-business-brain
hermes plugins enable hermes-business-brain
```

`hermes plugins enable` may ask about dependency consent and built-in tool
overrides; answer according to your setup. The plugin manager then installs
`PyYAML` and `jsonschema` into Hermes' environment.

## Restart Hermes

After enabling the plugin (or changing its dependencies), restart Hermes so
the tools and skills load. The doctor's own output says the same for
dependency changes: *"run `hermes pm repair`, then restart Hermes."*

## Confirm the installation

Two read-only checks:

1. **List installed plugins** — you should see the plugin with status
   `enabled`:

   ```bash
   hermes plugins list
   ```

2. **Run the plugin doctor** — validates the manifest, imports and tool/skill
   registration:

   ```bash
   hermes plugins doctor hermes-business-brain --ci
   ```

   From inside the repository checkout, the same check runs without the
   plugin being enabled:

   ```bash
   hermes plugins doctor . --ci
   ```

   A passing run (real output, exit 0) looks like:

   ```
   Plugin Doctor: /Users/you/hermes-business-brain-unsulabs
     manifest: hermes-business-brain 0.2.0 (standalone)
     WARN: declared python_dependencies not installed: PyYAML==6.0.3 — install and
     enable the plugin with hermes plugins. For an enabled plugin, run hermes pm
     repair, then restart Hermes.
     OK: runtime discovery, manifest parsing, import, and registration passed
     registrations: 18 tool(s), 0 hook(s)
   ```

   The `WARN` line appears when you validate a standalone repo whose
   dependencies were never installed (the plugin is not enabled there); it is
   expected, not an error. Enable the plugin (Path A or B) and the
   dependencies get installed. Doctor exits 0 with `--ci` when registration
   passes — that is the gate.

## What is NOT supported

Installing by a **local filesystem path** with `hermes plugins install` is not
supported:

```bash
# ✗ WRONG — the CLI parses this as owner/repo, not as a path:
hermes plugins install /Users/you/hermes-business-brain
```

The CLI treats the argument as a catalog entry name, a Git URL, or an
`owner/repo` shorthand. For a local checkout, use the symlink approach in
Path B.

## Next steps

Follow the [quickstart tutorial](../tutorials/quickstart-vault.md) to create
your first business vault. The doctor run behind this guide is recorded in
[`../../_verify/tool-layer.md`](../../_verify/tool-layer.md).
