"""Entrada de linea de comandos para el servidor HTTP local."""

from __future__ import annotations

import argparse
import logging
import sys

import uvicorn

from .app import ConfigurationError, Settings, create_app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="IA_NEST closed Home Assistant MCP catalog")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8770, type=int)
    arguments = parser.parse_args(argv)
    try:
        settings = Settings.from_environment()
    except ConfigurationError as exc:
        parser.error(str(exc))
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    uvicorn.run(create_app(settings), host=arguments.host, port=arguments.port, log_level="info")
