from __future__ import annotations

import asyncio

from beacon_client.channels.registry import ChannelRegistry
from beacon_client.client.websocket_client import BeaconWebSocketClient
from beacon_client.config import Settings
from beacon_client.models.messages import BeaconMessage


class BeaconRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._registry = ChannelRegistry(settings=settings)
        self._ws_client = BeaconWebSocketClient(ws_base_url=settings.server_ws_base)

    async def run_forever(self) -> None:
        interval_seconds = self._settings.beacon_interval_hours * 3600

        while True:
            await self.run_once()
            await asyncio.sleep(interval_seconds)

    async def run_once(self) -> None:
        channel = self._registry.choose_random()
        payload = BeaconMessage(client_id=self._settings.client_id, channel=channel.name)

        print(f"[BEACON] Sending via {channel.name.value}")

        response = await channel.send_alive(payload)
        print(f"[BEACON] Response {response.status_code}: {response.detail}")

        if response.status_code == 201 and response.websocket_path:
            await self._ws_client.run_session(
                websocket_path=response.websocket_path,
                client_id=self._settings.client_id,
            )
