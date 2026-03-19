from __future__ import annotations

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class StubChannel(BeaconChannel):
    def __init__(self, channel_name: ChannelName) -> None:
        self._name = channel_name

    @property
    def name(self) -> ChannelName:
        return self._name

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        return BeaconResponse(
            status_code=501,
            detail=f"Channel {self._name.value} is not implemented yet",
            accepted_channel=self._name,
        )
