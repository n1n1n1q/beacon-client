from __future__ import annotations

import httpx

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class Http2Channel(BeaconChannel):
    def __init__(self, host: str, port: int, verify: bool = False) -> None:
        self._host = host
        self._port = port
        self._verify = verify

    @property
    def name(self) -> ChannelName:
        return ChannelName.HTTP2

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        url = f"https://{self._host}:{self._port}/beacon"

        async with httpx.AsyncClient(http1=False, http2=True, verify=self._verify, timeout=15.0) as client:
            response = await client.post(url, json=payload.model_dump(mode="json"))

        if response.http_version != "HTTP/2":
            return BeaconResponse(
                status_code=500,
                detail=f"Server negotiated {response.http_version} instead of HTTP/2",
            )

        body = response.json()
        return BeaconResponse(
            status_code=response.status_code,
            detail=body.get("detail", "No detail"),
            websocket_path=body.get("websocket_path"),
            accepted_channel=ChannelName(body["accepted_channel"]) if body.get("accepted_channel") else None,
        )
