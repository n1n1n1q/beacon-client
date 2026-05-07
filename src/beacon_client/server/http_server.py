from __future__ import annotations

import asyncio

import uvicorn

from beacon_client.server.app import app


async def run_http_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    print(f"[HTTP/1.1] Listening on http://{host}:{port}")

    await server.serve()
