"""Cliente MCP efimero para el endpoint Assist de Home Assistant."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class UpstreamError(Exception):
    """Error base para un endpoint MCP de Home Assistant no disponible o invalido."""


class UpstreamConnectionError(UpstreamError):
    """No se pudo alcanzar Home Assistant."""


class UpstreamAuthenticationError(UpstreamError):
    """Home Assistant no acepto el token Bearer configurado."""


class UpstreamTimeoutError(UpstreamError):
    """Home Assistant no respondio dentro del tiempo configurado."""


class UpstreamProtocolError(UpstreamError):
    """Home Assistant devolvio una respuesta MCP invalida."""


@dataclass(frozen=True)
class UpstreamTool:
    name: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class UpstreamResult:
    content: list[Any]
    is_error: bool
    structured_content: dict[str, Any] | None


class HomeAssistantClient:
    """Crea una sesion MCP autenticada para cada operacion entrante."""

    def __init__(self, url: str, token: str, timeout_s: float) -> None:
        self.url = f"{url.rstrip('/')}/api/mcp/assist"
        self.token = token
        self.timeout_s = timeout_s

    @asynccontextmanager
    async def session(self) -> AsyncIterator[HomeAssistantSession]:
        try:
            timeout = httpx.Timeout(self.timeout_s)
            async with httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.token}"}, timeout=timeout
            ) as http_client:
                async with streamable_http_client(
                    self.url, http_client=http_client, terminate_on_close=True
                ) as streams:
                    read_stream, write_stream, _ = streams
                    async with ClientSession(
                        read_stream,
                        write_stream,
                        read_timeout_seconds=timedelta(seconds=self.timeout_s),
                    ) as client_session:
                        await client_session.initialize()
                        yield HomeAssistantSession(client_session, self.timeout_s)
        except UpstreamError:
            raise
        except Exception as exc:
            raise _typed_error(exc) from exc


class HomeAssistantSession:
    def __init__(self, session: ClientSession, timeout_s: float) -> None:
        self._session = session
        self._timeout_s = timeout_s

    async def list_tools(self) -> list[UpstreamTool]:
        try:
            tools: list[UpstreamTool] = []
            cursor: str | None = None
            while True:
                result = await self._session.list_tools(cursor=cursor)
                tools.extend(
                    UpstreamTool(name=str(tool.name), input_schema=dict(tool.inputSchema))
                    for tool in result.tools
                )
                cursor = result.nextCursor
                if not cursor:
                    return tools
        except Exception as exc:
            raise _typed_error(exc) from exc

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> UpstreamResult:
        try:
            result = await self._session.call_tool(
                name, arguments, read_timeout_seconds=timedelta(seconds=self._timeout_s)
            )
            return UpstreamResult(
                content=list(result.content),
                is_error=bool(result.isError),
                structured_content=result.structuredContent,
            )
        except Exception as exc:
            raise _typed_error(exc) from exc


def _typed_error(error: Exception) -> UpstreamError:
    """Conserva la clase de fallo aunque la libreria la agrupe en tareas."""
    errors = list(_leaf_errors(error))
    if any(isinstance(item, (httpx.TimeoutException, TimeoutError)) for item in errors):
        return UpstreamTimeoutError()
    for item in errors:
        if isinstance(item, httpx.HTTPStatusError):
            if item.response.status_code in {401, 403}:
                return UpstreamAuthenticationError()
            return UpstreamConnectionError()
    if any(isinstance(item, (httpx.ConnectError, httpx.NetworkError)) for item in errors):
        return UpstreamConnectionError()
    return UpstreamProtocolError()


def _leaf_errors(error: BaseException):
    if isinstance(error, BaseExceptionGroup):
        for nested in error.exceptions:
            yield from _leaf_errors(nested)
    else:
        yield error


def resolve_intent(tools: list[UpstreamTool], intent: str) -> UpstreamTool | None:
    """Resuelve una intencion por su nombre exacto o por ``prefijo__nombre``."""
    for tool in tools:
        if tool.name == intent or tool.name.rsplit("__", 1)[-1] == intent:
            return tool
    return None
