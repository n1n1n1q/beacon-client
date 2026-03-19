from __future__ import annotations

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

    try:
        data = await websocket.receive_text()
        await websocket.send_text(
            f"WS session established for {client_id}; received initial payload: {data}"
        )
    except WebSocketDisconnect:
        return
    finally:
        await websocket.close()
