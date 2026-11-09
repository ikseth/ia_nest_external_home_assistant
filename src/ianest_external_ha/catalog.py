"""El catalogo cerrado D1 de Home Assistant.

Este modulo es la unica fuente de las herramientas MCP publicas y sus
esquemas de entrada. No se expone una herramienta de Home Assistant fuera de
esta tabla.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CatalogTool:
    """Una herramienta publica y su intencion fija de Home Assistant."""

    name: str
    intent: str
    description: str
    input_schema: dict[str, Any]
    fixed_arguments: dict[str, Any]
    annotations: dict[str, bool]


_NAME = "Device name or alias exactly as the person says it, for example 'luz de prueba'. Prefer it when the person names a device."
_AREA = "Room or area name, for example 'Salon'. Use it only when the person names a room."
_FLOOR = "Floor name. Use it only when the person names a floor."

# Lectura del estado: Home Assistant filtra por nombre, area o dominio. Una respuesta mayor que
# este limite no se entrega truncada (el modelo supondria estados): se pide repetir con filtro.
LIVE_CONTEXT_MAX_CHARS = 4000
LIVE_CONTEXT_TOO_LARGE = (
    "Too much data for one answer. Call get_live_context again with a filter: "
    "name (a device), area (a room) or domain (for example 'light')."
)

_LIVE_CONTEXT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Only devices with this name or alias, for example 'luz de prueba'."},
        "area": {"type": "string", "description": "Only devices in this room or area, for example 'Salon'."},
        "domain": {
            "type": "string",
            "description": "Only devices of this type: light, fan, climate, media_player, sensor, binary_sensor, switch or weather.",
        },
    },
    "additionalProperties": False,
}


def _selector_schema(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "name": {"type": "string", "description": _NAME},
        "area": {"type": "string", "description": _AREA},
        "floor": {"type": "string", "description": _FLOOR},
    }
    if extra:
        properties.update(extra)
    return {"type": "object", "properties": properties, "additionalProperties": False}


_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
_SAFE_ACTION = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


CATALOG: tuple[CatalogTool, ...] = (
    CatalogTool(
        "get_live_context",
        "GetLiveContext",
        "Read the CURRENT state of devices and sensors of the home (lights on or off, temperatures, media players, fans). Always filter by name, area or domain. Use it before answering any question about the state of the house; never guess a state.",
        _LIVE_CONTEXT_SCHEMA,
        {},
        _READ_ONLY,
    ),
    CatalogTool(
        "get_date_time",
        "GetDateTime",
        "Get the current date and time of the home.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        {},
        _READ_ONLY,
    ),
    CatalogTool("light_turn_on", "HassTurnOn", "Turn on lights only. Target them by name, area or floor (for example area 'Salon').", _selector_schema(), {"domain": ["light"]}, _SAFE_ACTION),
    CatalogTool("light_turn_off", "HassTurnOff", "Turn off lights only. Target them by name, area or floor.", _selector_schema(), {"domain": ["light"]}, _SAFE_ACTION),
    CatalogTool(
        "light_set",
        "HassLightSet",
        "Set the brightness (percent 0-100), color name or color temperature of lights, by name, area or floor.",
        _selector_schema(
            {
                "brightness": {"type": "integer", "minimum": 0, "maximum": 100},
                "color": {"type": "string"},
                "temperature": {"type": "integer", "minimum": 0},
            }
        ),
        {"domain": ["light"]},
        _SAFE_ACTION,
    ),
    CatalogTool("media_pause", "HassMediaPause", "Pause a media player (TV, Kodi, speaker) by name, area or floor.", _selector_schema(), {"domain": ["media_player"]}, _SAFE_ACTION),
    CatalogTool("media_unpause", "HassMediaUnpause", "Resume a paused media player by name, area or floor.", _selector_schema(), {"domain": ["media_player"]}, _SAFE_ACTION),
    CatalogTool(
        "media_set_volume",
        "HassSetVolume",
        "Set the volume (percent 0-100) of a media player by name, area or floor.",
        _selector_schema({"volume_level": {"type": "integer", "minimum": 0, "maximum": 100}}),
        {"domain": ["media_player"]},
        _SAFE_ACTION,
    ),
    CatalogTool(
        "climate_set_temperature",
        "HassClimateSetTemperature",
        "Set the target temperature of the heating or air conditioning by name, area or floor.",
        _selector_schema({"temperature": {"type": "number"}}),
        {},
        _SAFE_ACTION,
    ),
    CatalogTool(
        "fan_set_speed",
        "HassFanSetSpeed",
        "Set the speed (percent 0-100, 0 stops it) of a fan by name, area or floor.",
        _selector_schema({"percentage": {"type": "integer", "minimum": 0, "maximum": 100}}),
        {"domain": ["fan"]},
        _SAFE_ACTION,
    ),
)

CATALOG_BY_NAME = {tool.name: tool for tool in CATALOG}
