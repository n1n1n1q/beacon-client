from __future__ import annotations

import asyncio

from hypercorn.asyncio import serve
from hypercorn.config import Config

from beacon_client.server._tls import ensure_self_signed_cert
from beacon_client.server.app import app


async def run_http2_server(host: str = "0.0.0.0", port: int = 8443) -> None:
    cert_path, key_path = ensure_self_signed_cert()

    config = Config()
    config.bind = [f"{host}:{port}"]
    config.certfile = str(cert_path)
    config.keyfile = str(key_path)
    config.alpn_protocols = ["h2", "http/1.1"]
    config.accesslog = "-"
    config.errorlog = "-"

    print(f"[HTTP/2] Listening on https://{host}:{port}")

    shutdown_event = asyncio.Event()
    await serve(app, config, shutdown_trigger=shutdown_event.wait)
