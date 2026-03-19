from __future__ import annotations

import httpx

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class HttpChannel(BeaconChannel):
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> ChannelName:
        return ChannelName.HTTP

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{self._base_url}/beacon", json=payload.model_dump(mode="json"))

        body = response.json()
        return BeaconResponse(
            status_code=response.status_code,
            detail=body.get("detail", "No detail"),
            websocket_path=body.get("websocket_path"),
            accepted_channel=ChannelName(body["accepted_channel"]) if body.get("accepted_channel") else None,
        )
