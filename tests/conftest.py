from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import uvicorn

from ianest_external_ha.app import Settings, create_app


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def wait_for_port(port: int) -> None:
    for _ in range(100):
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.03)
        else:
            writer.close()
            await writer.wait_closed()
            return
    raise AssertionError(f"port {port} did not open")


@asynccontextmanager
async def run_gateway(settings: Settings, port: int) -> AsyncIterator[None]:
    server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    await wait_for_port(port)
    try:
        yield
    finally:
        server.should_exit = True
        await task


@pytest.fixture
def ha_server(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    port = free_port()
    record = tmp_path / "ha_calls.jsonl"
    process = subprocess.Popen(
        [sys.executable, "tests/fake_ha.py", "--port", str(port), "--record", str(record)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.03):
                break
        except OSError:
            time.sleep(0.03)
    else:
        process.terminate()
        raise AssertionError("fake Home Assistant did not start")
    try:
        yield f"http://127.0.0.1:{port}", record
    finally:
        process.terminate()
        process.wait(timeout=5)
