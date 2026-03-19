from __future__ import annotations

import asyncio
import json

import websockets


class BeaconWebSocketClient:
    def __init__(self, ws_base_url: str) -> None:
        self._ws_base_url = ws_base_url.rstrip("/")

    async def run_session(self, websocket_path: str, client_id: str, timeout_seconds: float = 30.0) -> None:
        ws_url = f"{self._ws_base_url}{websocket_path}"

        async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as websocket:
            await websocket.send(json.dumps({"type": "hello", "client_id": client_id}))

            try:
                reply = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
                print(f"[WS] Received: {reply}")
            except asyncio.TimeoutError:
                print("[WS] Timeout waiting for server response")
