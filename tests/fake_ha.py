"""Falsificacion MCP local de Home Assistant Assist solo para pruebas."""

from __future__ import annotations

import argparse
import contextlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import CallToolResult, TextContent, Tool
from starlette.applications import Starlette
from starlette.routing import Mount


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


def _tool(name: str, schema: dict[str, Any]) -> Tool:
    return Tool(name=name, description=name, inputSchema=schema)


def create_app(record_path: Path, without_turn_domain: bool = False) -> Starlette:
    server = Server("fake-home-assistant")
    shared = {"name": {"type": "string"}, "area": {"type": "string"}, "floor": {"type": "string"}}
    domain = {"type": "array", "items": {"type": "string"}}
    turn_properties = dict(shared)
    if not without_turn_domain:
        turn_properties["domain"] = domain
    tools = [
        _tool("homeassistant__GetLiveContext", _schema({})),
        _tool("llm__GetDateTime", _schema({})),
        _tool("intent__HassTurnOn", _schema(turn_properties)),
        _tool("intent__HassTurnOff", _schema(turn_properties)),
        _tool("light__HassLightSet", _schema({**shared, "domain": domain, "brightness": {"type": "integer", "minimum": 0, "maximum": 100}, "color": {"type": "string"}, "temperature": {"type": "integer", "minimum": 0}})),
        _tool("media_player__HassMediaPause", _schema({**shared, "domain": domain})),
        _tool("media_player__HassMediaUnpause", _schema({**shared, "domain": domain})),
        _tool("media_player__HassSetVolume", _schema({**shared, "domain": domain, "volume_level": {"type": "integer", "minimum": 0, "maximum": 100}}, ["volume_level"])),
        _tool("climate__HassClimateSetTemperature", _schema({**shared, "temperature": {"type": "number"}}, ["temperature"])),
        _tool("fan__HassFanSetSpeed", _schema({**shared, "domain": domain, "percentage": {"type": "integer", "minimum": 0, "maximum": 100}}, ["percentage"])),
        _tool("assist_satellite__HassBroadcast", _schema({"message": {"type": "string"}}, ["message"])),
        _tool("script__house_script", _schema({})),
    ]

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return tools

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        with record_path.open("a", encoding="ascii") as stream:
            stream.write(json.dumps({"name": name, "arguments": arguments}, ensure_ascii=True) + "\n")
        if name == "homeassistant__GetLiveContext":
            text = "x" * 5000 if not arguments else json.dumps({"filtered": arguments}, sort_keys=True)
            return CallToolResult(content=[TextContent(type="text", text=text)], isError=False)
        if arguments.get("name") == "ha_error":
            return CallToolResult(content=[TextContent(type="text", text="Home Assistant reported an error.")], isError=True)
        if name == "intent__HassTurnOn" and arguments.get("domain") == ["lock"]:
            result = {"lock": arguments.get("name"), "state": "locked"}
        else:
            result = {"name": name, "arguments": arguments}
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, sort_keys=True))], isError=False)

    manager = StreamableHTTPSessionManager(server)

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with manager.run():
            yield

    return Starlette(routes=[Mount("/api/mcp/assist", app=manager.handle_request)], lifespan=lifespan)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--record", required=True)
    parser.add_argument("--without-turn-domain", action="store_true")
    arguments = parser.parse_args()
    import uvicorn

    uvicorn.run(create_app(Path(arguments.record), arguments.without_turn_domain), host="127.0.0.1", port=arguments.port, log_level="warning")


if __name__ == "__main__":
    main()
