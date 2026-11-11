---
name: obsidian-router
description: Resolve this product's private vault through explicit local registration and native Obsidian identity before access.
---

# Product vault routing

This repository-owned router needs no global skill installation. Run from the product checkout. It reads and writes the local selector registry (`hermes-obsidian-vaults/1` format); it does not copy a host's configuration or grant access.

1. Before listing, searching or reading an existing vault, obtain the explicit selector (name, ID, alias or absolute path) from the task, or an explicitly associated project. Never select by the active window or guess a destination.
2. Use the `brain_resolve_vault` tool with the explicit selector, or the project option. The resolver is read-only and must return exit 0, `status: selected` and `native_registry_verified: true`. It compares the local registry's ID and path to Obsidian's native registry; it rejects absent/ambiguous matches and symlinks. No vault content is read by the resolver.
3. Only after success, read the returned `instructions` first, then the `entrypoint`, and comply with local instructions and the authorized scope. Registration does not prove GUI/Bases function or editorial permission.
4. For an authorized new registration, first have Obsidian open the selected folder as a vault. Then use the `brain_register_vault` tool with the vault, name and alias. Optionally add the project option for durable project routing. The tool verifies the native ID and writes only the local selector registry, backing up an existing file; it never writes the vault or native registry. Existing conflicting entries need review, not forced replacement. Resolve again before access.
5. Default local registry: `~/.config/hermes-business-brain/vaults.json`. Native defaults: macOS `~/Library/Application Support/obsidian/obsidian.json`, Linux `$XDG_CONFIG_HOME/obsidian/obsidian.json` (or `~/.config/obsidian/obsidian.json`), Windows `%APPDATA%/obsidian/obsidian.json`. For a nonstandard installation, establish the actual native location and pass it via the tool's `nativo` option. Never fabricate a native file or ID to pass a check.
6. If resolution fails, preserve independently authorized work outside the vault and report the exact unresolved condition. Do not access the vault, overwrite registration or install another skill to bypass the failure.
