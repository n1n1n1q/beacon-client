from __future__ import annotations

from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from beacon_client.models.messages import ChannelName


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    client_id: str = Field(default="beacon-client-01")
    beacon_interval_hours: float = Field(default=1.0, gt=0)

    server_http_base: str = Field(default="http://localhost:8000")
    server_ws_base: str = Field(default="ws://localhost:8000")

    server_tcp_host: str = Field(default="localhost")
    server_tcp_port: int = Field(default=9000)

    enabled_channels: str = Field(default="HTTP,TCP")

    @cached_property
    def enabled_channel_names(self) -> list[ChannelName]:
        raw_values = [item.strip() for item in self.enabled_channels.split(",") if item.strip()]
        resolved: list[ChannelName] = []

        for value in raw_values:
            normalized = value.upper()
            if normalized == "HTTP2":
                value = "HTTP/2"
            elif normalized == "HTTP3":
                value = "HTTP/3"
            elif normalized == "DOH":
                value = "DoH"

            try:
                resolved.append(ChannelName(value))
            except ValueError:
                continue

        if not resolved:
            resolved = [ChannelName.HTTP]

        return resolved
