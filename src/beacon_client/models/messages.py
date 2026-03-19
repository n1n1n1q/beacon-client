from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ChannelName(str, Enum):
    TCP = "TCP"
    HTTP = "HTTP"
    HTTP2 = "HTTP/2"
    HTTP3 = "HTTP/3"
    DNS = "DNS"
    DOH = "DoH"
    ICMP = "ICMP"
    FTP = "FTP"
    IMAP = "IMAP"
    MAPI = "MAPI"
    SMB = "SMB"
    LDAP = "LDAP"


class BeaconMessage(BaseModel):
    client_id: str = Field(..., description="Unique client identifier")
    channel: ChannelName
    message: str = Field(default="I am alive")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BeaconResponse(BaseModel):
    status_code: int
    detail: str
    websocket_path: str | None = None
    accepted_channel: ChannelName | None = None
