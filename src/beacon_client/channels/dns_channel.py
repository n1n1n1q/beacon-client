from __future__ import annotations

import json

import dns.asyncresolver
import dns.exception
import dns.rdatatype

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class DnsChannel(BeaconChannel):
    def __init__(self, host: str, port: int, zone: str) -> None:
        self._host = host
        self._port = port
        self._zone = zone.strip(".")

    @property
    def name(self) -> ChannelName:
        return ChannelName.DNS

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        resolver = dns.asyncresolver.Resolver(configure=False)
        resolver.nameservers = [self._host]
        resolver.port = self._port
        resolver.lifetime = 15.0
        resolver.timeout = 15.0

        # (letters, digits, hyphen).
        sanitized = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in payload.client_id)
        qname = f"{sanitized}.{self._zone}."

        try:
            answer = await resolver.resolve(qname, dns.rdatatype.TXT)
        except dns.exception.DNSException as exc:
            return BeaconResponse(status_code=500, detail=f"DNS error: {exc}")

        for rrset in answer:
            joined = b"".join(rrset.strings).decode("utf-8", errors="replace")
            try:
                response_obj = json.loads(joined)
            except json.JSONDecodeError:
                continue

            return BeaconResponse(
                status_code=int(response_obj.get("status_code", 500)),
                detail=response_obj.get("detail", "No detail"),
                websocket_path=response_obj.get("websocket_path"),
                accepted_channel=ChannelName(response_obj["accepted_channel"]) if response_obj.get("accepted_channel") else None,
            )

        return BeaconResponse(status_code=500, detail="DNS response missing TXT payload")
