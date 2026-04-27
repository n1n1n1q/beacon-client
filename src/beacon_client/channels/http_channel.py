from __future__ import annotations

import httpx

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class HttpChannel(BeaconChannel):
    """
    HTTP/1.1 beacon channel.
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> ChannelName:
        return ChannelName.HTTP

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        async with httpx.AsyncClient(http1=True, http2=False, timeout=15.0) as client:
            response = await client.post(
                f"{self._base_url}/beacon",
                json=payload.model_dump(mode="json"),
                headers={"User-Agent": "beacon-client/0.1 http1"},
            )

        if response.http_version != "HTTP/1.1":
            return BeaconResponse(
                status_code=500,
                detail=f"Server negotiated {response.http_version} instead of HTTP/1.1",
            )

        try:
            body = response.json()
        except ValueError as exc:
            return BeaconResponse(
                status_code=response.status_code,
                detail=f"Invalid HTTP/1.1 JSON body: {exc}",
            )

        return BeaconResponse(
            status_code=response.status_code,
            detail=body.get("detail", "No detail"),
            websocket_path=body.get("websocket_path"),
            accepted_channel=ChannelName(body["accepted_channel"]) if body.get("accepted_channel") else None,
        )
