from __future__ import annotations

from typing import Protocol

from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class BeaconChannel(Protocol):
    @property
    def name(self) -> ChannelName:
        ...

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        ...
