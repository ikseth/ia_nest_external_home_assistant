"""Servidor MCP que expone solo el catalogo cerrado D1."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator, ValidationError
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .catalog import CATALOG, CATALOG_BY_NAME, LIVE_CONTEXT_MAX_CHARS, LIVE_CONTEXT_TOO_LARGE, CatalogTool
from .upstream import HomeAssistantClient, UpstreamError, UpstreamTool, resolve_intent


LOG = logging.getLogger("ianest_external_ha")


def _upstream_accepts_fixed_arguments(tool: CatalogTool, upstream_tool: UpstreamTool) -> bool:
    """Comprueba D2 sin exigir por error argumentos normales del llamador."""
    properties = upstream_tool.input_schema.get("properties")
    if not isinstance(properties, dict):
        return not tool.fixed_arguments
    for name, value in tool.fixed_arguments.items():
        schema = properties.get(name)
        if not isinstance(schema, dict):
            return False
        try:
            Draft202012Validator(schema).validate(value)
        except ValidationError:
            return False
    return True


def _validated_catalog_tool(tool: CatalogTool, upstream_tools: list[UpstreamTool]) -> UpstreamTool | None:
    upstream_tool = resolve_intent(upstream_tools, tool.intent)
    if upstream_tool is None or not _upstream_accepts_fixed_arguments(tool, upstream_tool):
        return None
    return upstream_tool


def _mcp_tool(tool: CatalogTool) -> Tool:
    return Tool(
        name=tool.name,
        description=tool.description,
        inputSchema=tool.input_schema,
        annotations=ToolAnnotations(**tool.annotations),
    )


def _error(message: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=message)], isError=True)


def _log_call(
    tool: str,
    arguments: dict[str, Any],
    intent: str | None,
    status: str,
    started: float,
) -> None:
    LOG.info(
        json.dumps(
            {
                "tool": tool,
                "arguments": arguments,
                "intent": intent,
                "status": status,
                "latency_ms": round((time.monotonic() - started) * 1000),
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )


@dataclass(frozen=True)
class CatalogServer:
    upstream: HomeAssistantClient

    def create_mcp_server(self) -> Server:
        server = Server("ianest-external-ha", version="0.1.0")

        @server.list_tools()
        async def list_tools() -> list[Tool]:
            try:
                async with self.upstream.session() as session:
                    upstream_tools = await session.list_tools()
            except UpstreamError:
                LOG.warning("home_assistant_tools_unavailable")
                return []
            return [
                _mcp_tool(tool)
                for tool in CATALOG
                if _validated_catalog_tool(tool, upstream_tools) is not None
            ]

        @server.call_tool(validate_input=False)
        async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
            started = time.monotonic()
            catalog_tool = CATALOG_BY_NAME.get(name)
            if catalog_tool is None:
                _log_call(name, arguments, None, "rejected", started)
                return _error("Tool is not available.")

            try:
                Draft202012Validator(catalog_tool.input_schema).validate(arguments)
            except ValidationError:
                _log_call(name, arguments, catalog_tool.intent, "rejected", started)
                return _error("Arguments are not valid for this tool.")

            try:
                async with self.upstream.session() as session:
                    upstream_tools = await session.list_tools()
                    upstream_tool = _validated_catalog_tool(catalog_tool, upstream_tools)
                    if upstream_tool is None:
                        _log_call(name, arguments, catalog_tool.intent, "rejected", started)
                        return _error("Tool is not currently available.")
                    result = await session.call_tool(
                        upstream_tool.name, {**arguments, **catalog_tool.fixed_arguments}
                    )
            except UpstreamError:
                _log_call(name, arguments, catalog_tool.intent, "upstream_error", started)
                return _error("Home Assistant is unavailable.")

            if name == "get_live_context" and not result.is_error:
                size = sum(len(getattr(item, "text", "") or "") for item in result.content)
                if size > LIVE_CONTEXT_MAX_CHARS:
                    _log_call(name, arguments, catalog_tool.intent, "too_large", started)
                    return _error(LIVE_CONTEXT_TOO_LARGE)

            status = "ha_error" if result.is_error else "ok"
            _log_call(name, arguments, catalog_tool.intent, status, started)
            return CallToolResult(
                content=result.content,
                structuredContent=result.structured_content,
                isError=result.is_error,
            )

        return server

    def create_session_manager(self) -> StreamableHTTPSessionManager:
        return StreamableHTTPSessionManager(self.create_mcp_server(), stateless=True)
