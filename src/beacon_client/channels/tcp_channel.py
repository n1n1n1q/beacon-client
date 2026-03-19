from __future__ import annotations

import asyncio
import json

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class TcpChannel(BeaconChannel):
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    @property
    def name(self) -> ChannelName:
        return ChannelName.TCP

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        reader, writer = await asyncio.open_connection(self._host, self._port)

        try:
            serialized = json.dumps(payload.model_dump(mode="json")) + "\n"
            writer.write(serialized.encode("utf-8"))
            await writer.drain()

            line = await asyncio.wait_for(reader.readline(), timeout=15.0)
            if not line:
                return BeaconResponse(status_code=500, detail="TCP server closed connection")

            response_obj = json.loads(line.decode("utf-8"))
            accepted_channel = response_obj.get("accepted_channel")

            return BeaconResponse(
                status_code=int(response_obj.get("status_code", 500)),
                detail=response_obj.get("detail", "No detail"),
                websocket_path=response_obj.get("websocket_path"),
                accepted_channel=ChannelName(accepted_channel) if accepted_channel else None,
            )
        finally:
            writer.close()
            await writer.wait_closed()
