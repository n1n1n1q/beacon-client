from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from beacon_client.models.messages import BeaconMessage, ChannelName

app = FastAPI(title="Beacon Demo Server", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/beacon")
async def receive_http_beacon(payload: BeaconMessage) -> dict[str, str | int | None]:
    return {
        "status_code": 201,
        "detail": f"Beacon accepted over {payload.channel.value}",
        "websocket_path": f"/ws/{payload.client_id}",
        "accepted_channel": payload.channel.value,
        "server_timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/beacon/{channel_name}")
async def receive_named_beacon(channel_name: str, payload: BeaconMessage) -> dict[str, str | int | None]:
    accepted_channel = channel_name.upper()

    return {
        "status_code": 201,
        "detail": f"Beacon accepted via route channel {accepted_channel}",
        "websocket_path": f"/ws/{payload.client_id}",
        "accepted_channel": payload.channel.value,
        "server_timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.websocket("/ws/{client_id}")
async def websocket_channel(websocket: WebSocket, client_id: str) -> None:
    await websocket.accept()
    print(f"[WS] Client connected: {client_id}")

    try:
        initial = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
        await websocket.send_text(
            f"WS session established for {client_id}; received initial payload: {initial}"
        )

        # Keep the session alive briefly to demonstrate two-way communication.
        for tick in range(3):
            await asyncio.sleep(1)
            await websocket.send_text(f"tick {tick + 1}/3 from server to {client_id}")
    except asyncio.TimeoutError:
        await websocket.send_text("Server timed out waiting for hello payload")
    except WebSocketDisconnect:
        print(f"[WS] Client disconnected: {client_id}")
        return
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
