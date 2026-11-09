from __future__ import annotations

import json
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ianest_external_ha.app import ConfigurationError, Settings
from ianest_external_ha.catalog import CATALOG
from .conftest import free_port, run_gateway, wait_for_port


@asynccontextmanager
async def gateway_client(url: str, token: str):
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as http_client:
        async with streamable_http_client(f"{url}/mcp", http_client=http_client) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


def settings(ha_url: str) -> Settings:
    return Settings(ha_url=ha_url, ha_token="ha-token-not-logged", core_token="core-token-not-logged", timeout_s=1)


def calls(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]


@pytest.mark.asyncio
async def test_list_publishes_exact_catalog_and_annotations(ha_server):
    ha_url, _ = ha_server
    port = free_port()
    async with run_gateway(settings(ha_url), port):
        async with gateway_client(f"http://127.0.0.1:{port}", "core-token-not-logged") as client:
            tools = (await client.list_tools()).tools
    assert [tool.name for tool in tools] == [tool.name for tool in CATALOG]
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.openWorldHint is False
        assert tool.annotations.destructiveHint is False
        assert tool.inputSchema["additionalProperties"] is False


@pytest.mark.asyncio
async def test_light_domain_is_fixed_and_caller_domain_is_rejected(ha_server):
    ha_url, record = ha_server
    port = free_port()
    async with run_gateway(settings(ha_url), port):
        async with gateway_client(f"http://127.0.0.1:{port}", "core-token-not-logged") as client:
            result = await client.call_tool("light_turn_on", {"name": "Salon"})
            rejected = await client.call_tool("light_turn_on", {"name": "Salon", "domain": ["lock"]})
    assert result.isError is False
    assert rejected.isError is True
    assert calls(record) == [{"name": "intent__HassTurnOn", "arguments": {"name": "Salon", "domain": ["light"]}}]


@pytest.mark.asyncio
async def test_missing_fixed_domain_removes_tools_and_rejects_without_call(tmp_path: Path):
    ha_port = free_port()
    record = tmp_path / "calls.jsonl"
    process = subprocess.Popen([sys.executable, "tests/fake_ha.py", "--port", str(ha_port), "--record", str(record), "--without-turn-domain"])
    try:
        await wait_for_port(ha_port)
        port = free_port()
        async with run_gateway(settings(f"http://127.0.0.1:{ha_port}"), port):
            async with gateway_client(f"http://127.0.0.1:{port}", "core-token-not-logged") as client:
                names = [tool.name for tool in (await client.list_tools()).tools]
                result = await client.call_tool("light_turn_on", {"name": "Salon"})
        assert "light_turn_on" not in names
        assert "light_turn_off" not in names
        assert result.isError is True
        assert calls(record) == []
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.mark.asyncio
async def test_catalog_rejects_unknown_and_out_of_range_arguments(ha_server):
    ha_url, record = ha_server
    port = free_port()
    async with run_gateway(settings(ha_url), port):
        async with gateway_client(f"http://127.0.0.1:{port}", "core-token-not-logged") as client:
            generic = await client.call_tool("HassTurnOn", {"name": "lock"})
            broadcast = await client.call_tool("HassBroadcast", {"message": "no"})
            script = await client.call_tool("script__house_script", {})
            brightness = await client.call_tool("light_set", {"brightness": 150})
            extra = await client.call_tool("light_set", {"unknown": "no"})
    assert generic.isError and broadcast.isError and script.isError
    assert brightness.isError and extra.isError
    assert calls(record) == []


@pytest.mark.asyncio
async def test_upstream_error_is_preserved_and_unavailable_is_readable(ha_server):
    ha_url, _ = ha_server
    port = free_port()
    async with run_gateway(settings(ha_url), port):
        async with gateway_client(f"http://127.0.0.1:{port}", "core-token-not-logged") as client:
            result = await client.call_tool("light_turn_on", {"name": "ha_error"})
    assert result.isError is True
    assert result.content[0].text == "Home Assistant reported an error."

    offline_port = free_port()
    port = free_port()
    async with run_gateway(settings(f"http://127.0.0.1:{offline_port}"), port):
        async with gateway_client(f"http://127.0.0.1:{port}", "core-token-not-logged") as client:
            assert (await client.list_tools()).tools == []
            unavailable = await client.call_tool("light_turn_on", {"name": "Salon"})
    assert unavailable.isError is True
    assert unavailable.content[0].text == "Home Assistant is unavailable."


@pytest.mark.asyncio
async def test_bearer_is_required_and_tokens_do_not_reach_logs(ha_server, caplog):
    caplog.set_level("INFO", logger="ianest_external_ha")
    ha_url, _ = ha_server
    port = free_port()
    async with run_gateway(settings(ha_url), port):
        async with httpx.AsyncClient() as client:
            assert (await client.post(f"http://127.0.0.1:{port}/mcp", json={})).status_code == 401
            assert (await client.post(f"http://127.0.0.1:{port}/mcp", headers={"Authorization": "Bearer wrong"}, json={})).status_code == 401
        async with gateway_client(f"http://127.0.0.1:{port}", "core-token-not-logged") as client:
            await client.call_tool("light_turn_on", {"name": "Salon"})
    text = "\n".join(record.message for record in caplog.records)
    lines = [json.loads(r.message) for r in caplog.records if r.name == "ianest_external_ha" and r.message.startswith("{")]
    assert lines and lines[-1]["tool"] == "light_turn_on" and lines[-1]["status"] == "ok"
    assert "core-token-not-logged" not in text
    assert "ha-token-not-logged" not in text


def test_missing_core_token_configuration_prevents_start(tmp_path: Path):
    ha_token = tmp_path / "ha.token"
    ha_token.write_text("ha", encoding="ascii")
    with pytest.raises(ConfigurationError, match="CORE_TOKEN"):
        Settings.from_environment({"IANEST_EXTERNAL_HA_URL": "http://ha.example", "IANEST_EXTERNAL_HA_TOKEN_FILE": str(ha_token)})


@pytest.mark.asyncio
async def test_live_context_passes_filters_and_refuses_oversized_unfiltered(ha_server):
    ha_url, record = ha_server
    port = free_port()
    async with run_gateway(settings(ha_url), port):
        async with gateway_client(f"http://127.0.0.1:{port}", "core-token-not-logged") as client:
            filtered = await client.call_tool("get_live_context", {"name": "luz de prueba"})
            unfiltered = await client.call_tool("get_live_context", {})
            bad = await client.call_tool("get_live_context", {"entity_id": "lock.door"})
    assert filtered.isError is False
    assert json.loads(filtered.content[0].text) == {"filtered": {"name": "luz de prueba"}}
    assert unfiltered.isError is True
    assert "filter" in unfiltered.content[0].text
    assert bad.isError is True
    assert [c["arguments"] for c in calls(record)] == [{"name": "luz de prueba"}, {}]


@pytest.mark.asyncio
async def test_empty_selectors_are_dropped_before_calling_home_assistant(ha_server):
    ha_url, record = ha_server
    port = free_port()
    async with run_gateway(settings(ha_url), port):
        async with gateway_client(f"http://127.0.0.1:{port}", "core-token-not-logged") as client:
            result = await client.call_tool("fan_set_speed", {"name": "ventilador", "area": "", "floor": "", "percentage": 50})
    assert result.isError is False
    assert calls(record)[0]["arguments"] == {"name": "ventilador", "percentage": 50, "domain": ["fan"]}


@pytest.mark.asyncio
async def test_error_on_fixed_type_tool_explains_the_type(ha_server):
    ha_url, _ = ha_server
    port = free_port()
    async with run_gateway(settings(ha_url), port):
        async with gateway_client(f"http://127.0.0.1:{port}", "core-token-not-logged") as client:
            result = await client.call_tool("light_turn_on", {"name": "ha_error"})
            plain = await client.call_tool("climate_set_temperature", {"name": "ha_error", "temperature": 20})
    assert result.isError is True
    assert result.content[0].text == "Home Assistant reported an error."
    assert "only acts on devices of type light" in result.content[1].text
    assert "does not exist" in result.content[1].text
    assert len(plain.content) == 1
