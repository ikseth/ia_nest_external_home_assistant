"""Scripts de la casa declarados en la configuracion del despliegue (decision 0003).

Los scripts son de cada hogar, no de Home Assistant: no viven en el codigo. El despliegue
declara una lista cerrada en un fichero JSON; un script que no esta en la lista no se publica.
Cada entrada exige su marca (anotaciones MCP con `destructiveHint` explicito) y un esquema de
argumentos cerrado. Formato:

    {"scripts": [{"tool": "media_recommend", "script": "media_recommend",
                  "description": "...", "arguments": {"request": {"type": "string"}},
                  "annotations": {"destructiveHint": false, "openWorldHint": true}}]}
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .catalog import CATALOG_BY_NAME, CatalogTool

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_HINTS = {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}


class ScriptConfigError(ValueError):
    """El fichero de scripts declarados no es valido."""


def load_scripts(path: str | None) -> tuple[CatalogTool, ...]:
    if not path:
        return ()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ScriptConfigError(f"scripts file cannot be read: {exc.__class__.__name__}") from exc
    entries = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ScriptConfigError("scripts file must contain a 'scripts' list")
    tools: list[CatalogTool] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        where = f"scripts[{index}]"
        if not isinstance(entry, dict) or set(entry) - {"tool", "script", "description", "arguments", "annotations"}:
            raise ScriptConfigError(f"{where}: unknown or missing fields")
        tool, script = entry.get("tool"), entry.get("script")
        if not isinstance(tool, str) or not _NAME.fullmatch(tool):
            raise ScriptConfigError(f"{where}.tool must be snake_case")
        if not isinstance(script, str) or not _NAME.fullmatch(script):
            raise ScriptConfigError(f"{where}.script must be a script object id")
        if tool in CATALOG_BY_NAME or tool in seen:
            raise ScriptConfigError(f"{where}.tool '{tool}' is already used")
        seen.add(tool)
        annotations = entry.get("annotations")
        if not isinstance(annotations, dict) or set(annotations) - _HINTS or not all(
            isinstance(v, bool) for v in annotations.values()
        ):
            raise ScriptConfigError(f"{where}.annotations must be MCP boolean hints")
        if "destructiveHint" not in annotations:
            raise ScriptConfigError(f"{where}.annotations.destructiveHint must be declared")
        arguments = entry.get("arguments", {})
        if not isinstance(arguments, dict) or not all(isinstance(v, dict) for v in arguments.values()):
            raise ScriptConfigError(f"{where}.arguments must map names to JSON schemas")
        description = entry.get("description", "")
        if not isinstance(description, str):
            raise ScriptConfigError(f"{where}.description must be text")
        tools.append(
            CatalogTool(
                name=tool,
                intent=f"script__{script}",
                description=description,
                input_schema={"type": "object", "properties": arguments, "additionalProperties": False},
                fixed_arguments={},
                annotations={"readOnlyHint": False, "idempotentHint": False, "openWorldHint": False, **annotations},
            )
        )
    return tuple(tools)


def upstream_accepts_arguments(tool: CatalogTool, upstream_schema: dict[str, Any]) -> bool:
    """D2 para scripts: Home Assistant acepta cada argumento declarado."""
    properties = upstream_schema.get("properties") or {}
    return isinstance(properties, dict) and all(name in properties for name in tool.input_schema["properties"])
