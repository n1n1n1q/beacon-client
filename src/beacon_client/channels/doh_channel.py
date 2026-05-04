from __future__ import annotations

import asyncio
import json
import socket

import dns.asyncquery
import dns.exception
import dns.message
import dns.rdatatype

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class DoHChannel(BeaconChannel):
    def __init__(self, host: str, port: int, zone: str, verify: bool = False) -> None:
        self._host = host
        self._port = port
        self._zone = zone.strip(".")
        self._verify = verify

        self._host_url = f"https://{self._host}:{self._port}/dns-query"

    @property
    def name(self) -> ChannelName:
        return ChannelName.DOH

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:

        loop = asyncio.get_running_loop()
        
        try:
            addr_info = await loop.getaddrinfo(self._host, self._port, family=socket.AF_INET)
            nameserver_ip = addr_info[0][4][0]
        except Exception as exc:
            return BeaconResponse(status_code=500, detail=f"Failed to resolve nameserver {self._host}: {exc}")

        sanitized = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in payload.client_id)
        qname = f"{sanitized}.{self._zone}."
        query = dns.message.make_query(qname, dns.rdatatype.TXT)

        try:
            answer = await dns.asyncquery.https(
                query,
                self._host_url,
                timeout=15.0,
                verify=self._verify,
                bootstrap_address=nameserver_ip,
            )
        except dns.exception.DNSException as exc:
            return BeaconResponse(status_code=500, detail=f"DNS error: {exc}")

        for rrset in answer.answer:
            if rrset.rdtype != dns.rdatatype.TXT:
                continue
            for rdata in rrset:
                joined = b"".join(rdata.strings).decode("utf-8", errors="replace")
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
