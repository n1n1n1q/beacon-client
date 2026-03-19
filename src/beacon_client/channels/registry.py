from __future__ import annotations

import random

from beacon_client.channels.base import BeaconChannel
from beacon_client.channels.http_channel import HttpChannel
from beacon_client.channels.stub_channel import StubChannel
from beacon_client.channels.tcp_channel import TcpChannel
from beacon_client.config import Settings
from beacon_client.models.messages import ChannelName


class ChannelRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._channels: dict[ChannelName, BeaconChannel] = {
            ChannelName.HTTP: HttpChannel(base_url=settings.server_http_base),
            ChannelName.TCP: TcpChannel(host=settings.server_tcp_host, port=settings.server_tcp_port),
        }

        for channel_name in ChannelName:
            self._channels.setdefault(channel_name, StubChannel(channel_name=channel_name))

    def choose_random(self) -> BeaconChannel:
        enabled = [self._channels[name] for name in self._settings.enabled_channel_names]
        return random.choice(enabled)
