"""D2 contra los esquemas reales de Home Assistant 2026.10.4 (sin red)."""

from __future__ import annotations

import json
from pathlib import Path

from ianest_external_ha.catalog import CATALOG
from ianest_external_ha.server import _validated_catalog_tool
from ianest_external_ha.upstream import UpstreamTool

DATA = json.loads((Path(__file__).parent / "data" / "ha_assist_tools_2026_10.json").read_text())
REAL = [UpstreamTool(name=t["name"], input_schema=t["inputSchema"]) for t in DATA["tools"]]


def test_every_catalog_tool_resolves_and_accepts_fixed_arguments():
    for tool in CATALOG:
        upstream = _validated_catalog_tool(tool, REAL)
        assert upstream is not None, tool.name
        assert upstream.name.rsplit("__", 1)[-1] == tool.intent


def test_catalog_never_maps_to_generic_or_house_tools():
    intents = {tool.intent for tool in CATALOG}
    assert "HassBroadcast" not in intents
    assert "HassCancelAllTimers" not in intents
    generic = [tool for tool in CATALOG if tool.intent in {"HassTurnOn", "HassTurnOff"}]
    assert generic and all(tool.fixed_arguments == {"domain": ["light"]} for tool in generic)


def test_a_wrong_fixed_domain_fails_against_real_enum():
    light_set = next(tool for tool in CATALOG if tool.name == "light_set")
    bad = type(light_set)(**{**light_set.__dict__, "fixed_arguments": {"domain": ["lock"]}})
    assert _validated_catalog_tool(bad, REAL) is None
