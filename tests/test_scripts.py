from __future__ import annotations

import json
from pathlib import Path

import pytest

from ianest_external_ha.app import ConfigurationError, Settings
from ianest_external_ha.scripts import ScriptConfigError, load_scripts
from .conftest import free_port, run_gateway
from .test_server import calls, gateway_client

ENTRY = {
    "tool": "media_recommend",
    "script": "media_recommend",
    "description": "Recommend something to watch and play it.",
    "arguments": {"request": {"type": "string"}, "room": {"type": "string", "enum": ["living", "den"]}},
    "annotations": {"destructiveHint": False, "openWorldHint": True},
}


def write(tmp_path: Path, entries: list[dict]) -> str:
    path = tmp_path / "scripts.json"
    path.write_text(json.dumps({"scripts": entries}), encoding="utf-8")
    return str(path)


def settings(ha_url: str, scripts) -> Settings:
    return Settings(ha_url=ha_url, ha_token="ha", core_token="core", timeout_s=1, scripts=scripts)


@pytest.mark.asyncio
async def test_declared_script_is_published_and_called(ha_server, tmp_path):
    ha_url, record = ha_server
    scripts = load_scripts(write(tmp_path, [ENTRY, {**ENTRY, "tool": "missing_script", "script": "not_in_ha"}]))
    port = free_port()
    async with run_gateway(settings(ha_url, scripts), port):
        async with gateway_client(f"http://127.0.0.1:{port}", "core") as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
            ok = await client.call_tool("media_recommend", {"request": "a comedy", "room": "living"})
            bad_room = await client.call_tool("media_recommend", {"room": "garage"})
            undeclared = await client.call_tool("house_script", {})
            missing = await client.call_tool("missing_script", {})
    assert "media_recommend" in tools and "missing_script" not in tools and "house_script" not in tools
    assert tools["media_recommend"].annotations.destructiveHint is False
    assert ok.isError is False and bad_room.isError and undeclared.isError and missing.isError
    assert calls(record) == [{"name": "script__media_recommend", "arguments": {"request": "a comedy", "room": "living"}}]


@pytest.mark.asyncio
async def test_script_with_argument_unknown_to_ha_is_not_published(ha_server, tmp_path):
    ha_url, _ = ha_server
    entry = {**ENTRY, "arguments": {**ENTRY["arguments"], "volume": {"type": "integer"}}}
    port = free_port()
    async with run_gateway(settings(ha_url, load_scripts(write(tmp_path, [entry]))), port):
        async with gateway_client(f"http://127.0.0.1:{port}", "core") as client:
            assert "media_recommend" not in [t.name for t in (await client.list_tools()).tools]


@pytest.mark.parametrize(
    "entry",
    [
        {k: v for k, v in ENTRY.items() if k != "annotations"},
        {**ENTRY, "annotations": {"openWorldHint": True}},
        {**ENTRY, "tool": "light_turn_on"},
        {**ENTRY, "tool": "Bad-Name"},
        {**ENTRY, "extra": 1},
    ],
)
def test_invalid_declarations_are_rejected(tmp_path, entry):
    with pytest.raises(ScriptConfigError):
        load_scripts(write(tmp_path, [entry]))


def test_invalid_scripts_file_prevents_start(tmp_path):
    token = tmp_path / "t"
    token.write_text("x", encoding="ascii")
    env = {"IANEST_EXTERNAL_HA_URL": "http://ha.example", "IANEST_EXTERNAL_HA_TOKEN_FILE": str(token),
           "IANEST_EXTERNAL_HA_CORE_TOKEN_FILE": str(token), "IANEST_EXTERNAL_HA_SCRIPTS_FILE": str(tmp_path / "none.json")}
    with pytest.raises(ConfigurationError, match="SCRIPTS_FILE"):
        Settings.from_environment(env)
