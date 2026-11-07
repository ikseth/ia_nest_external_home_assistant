"""Aplicacion ASGI y configuracion de entorno."""

from __future__ import annotations

import contextlib
import hmac
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from .catalog import CatalogTool
from .scripts import ScriptConfigError, load_scripts
from .server import CatalogServer
from .upstream import HomeAssistantClient


class ConfigurationError(ValueError):
    """Falta una configuracion de despliegue obligatoria o no es valida."""


@dataclass(frozen=True)
class Settings:
    ha_url: str
    ha_token: str
    core_token: str
    timeout_s: float
    scripts: tuple[CatalogTool, ...] = ()

    @classmethod
    def from_environment(cls, environment: dict[str, str] | None = None) -> Settings:
        values = os.environ if environment is None else environment
        ha_url = values.get("IANEST_EXTERNAL_HA_URL", "").strip()
        if not ha_url:
            raise ConfigurationError("IANEST_EXTERNAL_HA_URL is required")
        try:
            timeout_s = float(values.get("IANEST_EXTERNAL_HA_TIMEOUT_S", "8"))
        except ValueError as exc:
            raise ConfigurationError("IANEST_EXTERNAL_HA_TIMEOUT_S must be numeric") from exc
        if not 0 < timeout_s < 10:
            raise ConfigurationError("IANEST_EXTERNAL_HA_TIMEOUT_S must be greater than 0 and below 10")
        return cls(
            ha_url=ha_url,
            ha_token=_read_token(values.get("IANEST_EXTERNAL_HA_TOKEN_FILE"), "IANEST_EXTERNAL_HA_TOKEN_FILE"),
            core_token=_read_token(
                values.get("IANEST_EXTERNAL_HA_CORE_TOKEN_FILE"),
                "IANEST_EXTERNAL_HA_CORE_TOKEN_FILE",
            ),
            timeout_s=timeout_s,
            scripts=_load_scripts(values.get("IANEST_EXTERNAL_HA_SCRIPTS_FILE")),
        )


def _load_scripts(path: str | None) -> tuple[CatalogTool, ...]:
    try:
        return load_scripts(path)
    except ScriptConfigError as exc:
        raise ConfigurationError(f"IANEST_EXTERNAL_HA_SCRIPTS_FILE: {exc}") from exc


def _read_token(path_value: str | None, setting: str) -> str:
    if not path_value:
        raise ConfigurationError(f"{setting} is required")
    try:
        token = Path(path_value).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ConfigurationError(f"{setting} cannot be read") from exc
    if not token:
        raise ConfigurationError(f"{setting} is empty")
    return token


class BearerMiddleware:
    """Exige el token Bearer del core antes de entregar la solicitud a MCP."""

    def __init__(self, app: Any, token: str) -> None:
        self.app = app
        self.expected = f"Bearer {token}".encode("utf-8")

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            headers = {name.lower(): value for name, value in scope.get("headers", [])}
            supplied = headers.get(b"authorization", b"")
            if not hmac.compare_digest(supplied, self.expected):
                response = PlainTextResponse("unauthorized", status_code=401)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_app(settings: Settings) -> Starlette:
    catalog_server = CatalogServer(
        HomeAssistantClient(settings.ha_url, settings.ha_token, settings.timeout_s),
        settings.scripts,
    )
    manager = catalog_server.create_session_manager()

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with manager.run():
            yield

    class _McpEndpoint:
        """ASGI en la ruta exacta /mcp, sin la redireccion 307 de Mount."""

        async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
            await manager.handle_request(scope, receive, send)

    app = Starlette(
        routes=[Route("/mcp", endpoint=_McpEndpoint(), methods=["GET", "POST", "DELETE"])],
        lifespan=lifespan,
    )
    return BearerMiddleware(app, settings.core_token)  # type: ignore[return-value]


def create_app_from_environment() -> Starlette:
    return create_app(Settings.from_environment())
