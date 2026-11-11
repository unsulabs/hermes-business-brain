"""hermes-business-brain v2 plugin: 19 in-process business-brain tools + bundled skills.

register(ctx) publishes:
  * the 19 ``brain_*`` tools declared in plugin.yaml (handlers in tools.py call the native
    English engine hermes_business_brain.engine.api IN-PROCESS; the engine is imported lazily, so
    registration never depends on it being installed yet);
  * every SKILL.md under ``hermes_business_brain/skills/<name>/`` as a plugin skill
    (``hermes-business-brain:<name>``), tolerating an empty or absent skills directory.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from . import tools

_log = logging.getLogger(__name__)

_PLUGIN_DIR = Path(__file__).resolve().parent
_BUNDLED_SKILLS_DIR = _PLUGIN_DIR / "hermes_business_brain" / "skills"

#: Frontmatter-safe key read without YAML so registration stays dependency-free.
_DESCRIPTION_KEY = "description"


def _skill_description(skill_md: Path) -> str:
    """Best-effort ``description`` from a SKILL.md frontmatter block (no YAML dependency)."""
    try:
        head = skill_md.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    except OSError:
        return ""
    if not head.startswith("---"):
        return ""
    body = head[3:]
    end = body.find("\n---")
    if end != -1:
        body = body[:end]
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith(_DESCRIPTION_KEY + ":"):
            value = line.split(":", 1)[1].strip().strip("\"'")
            return value
    return ""


def _iter_bundled_skills() -> list[tuple[str, Path, str]]:
    """(name, SKILL.md path, description) for every bundled skill; [] when absent/empty."""
    if not _BUNDLED_SKILLS_DIR.is_dir():
        return []
    found: list[tuple[str, Path, str]] = []
    for skill_md in sorted(_BUNDLED_SKILLS_DIR.glob("*/SKILL.md")):
        name = skill_md.parent.name
        if not name or name.startswith((".", "_")):
            continue
        found.append((name, skill_md, _skill_description(skill_md)))
    return found


def register(ctx: Any) -> None:
    """Register the 18 tools and every bundled skill. Never raises on engine absence."""
    # --- tools ---
    for spec in tools.TOOL_SPECS:
        try:
            ctx.register_tool(
                name=spec["name"],
                toolset=spec["toolset"],
                schema=spec["schema"],
                handler=spec["handler"],
                description=spec["description"],
                emoji=spec["emoji"],
            )
        except Exception as exc:  # noqa: BLE001 - one bad tool must not kill registration
            _log.warning("hermes-business-brain: failed to register tool %s: %s", spec["name"], exc)

    # --- bundled skills (tolerant: empty or missing skills dir is fine) ---
    for name, skill_md, description in _iter_bundled_skills():
        try:
            ctx.register_skill(name=name, path=skill_md, description=description)
        except Exception as exc:  # noqa: BLE001 - skills are best-effort
            _log.warning(
                "hermes-business-brain: failed to register skill %s from %s: %s",
                name,
                skill_md,
                exc,
            )


__all__ = ["register", "tools"]
