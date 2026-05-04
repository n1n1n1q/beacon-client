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

    server_http2_host: str = Field(default="localhost")
    server_http2_port: int = Field(default=8443)

    server_http3_host: str = Field(default="localhost")
    server_http3_port: int = Field(default=4433)

    server_dns_host: str = Field(default="127.0.0.1")
    server_dns_port: int = Field(default=5354)
    dns_zone: str = Field(default="alive.beacon.local")

    server_doh_host: str = Field(default="127.0.0.1")
    server_doh_port: int = Field(default=8043)

    server_icmp_host: str = Field(default="127.0.0.1")

    server_ftp_host: str = Field(default="localhost")
    server_ftp_port: int = Field(default=2121)
    ftp_user: str = Field(default="beacon")
    ftp_password: str = Field(default="beacon")

    server_imap_host: str = Field(default="localhost")
    server_imap_port: int = Field(default=1143)
    imap_user: str = Field(default="beacon")
    imap_password: str = Field(default="beacon")

    server_smb_host: str = Field(default="localhost")
    server_smb_port: int = Field(default=1445)
    smb_user: str = Field(default="beacon")
    smb_password: str = Field(default="beacon")
    smb_share: str = Field(default="BEACON")

    server_ldap_host: str = Field(default="localhost")
    server_ldap_port: int = Field(default=1389)
    ldap_user: str = Field(default="beacon")
    ldap_password: str = Field(default="beacon")
    ldap_base_dn: str = Field(default="dc=beacon,dc=local")

    enabled_channels: str = Field(default="HTTP,TCP,HTTP2,HTTP3,DNS,ICMP,FTP")

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
