from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from beacon_client.models.messages import ChannelName


async def handle_tcp_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=30.0)
        if not raw:
            return

        payload = json.loads(raw.decode("utf-8"))
        client_id = payload.get("client_id", "unknown")

        response = {
            "status_code": 201,
            "detail": "Beacon accepted over TCP",
            "websocket_path": f"/ws/{client_id}",
            "accepted_channel": ChannelName.TCP.value,
            "server_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        writer.write((json.dumps(response) + "\n").encode("utf-8"))
        await writer.drain()
    except Exception as exc:
        error_payload = {"status_code": 500, "detail": f"TCP server error: {exc}"}
        writer.write((json.dumps(error_payload) + "\n").encode("utf-8"))
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def run_tcp_server(host: str = "0.0.0.0", port: int = 9000) -> None:
    server = await asyncio.start_server(handle_tcp_client, host=host, port=port)
    address = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"[TCP] Listening on {address}")

    async with server:
        await server.serve_forever()
