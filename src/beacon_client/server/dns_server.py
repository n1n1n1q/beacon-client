from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from dnslib import QTYPE, RR, TXT, DNSRecord

from beacon_client.models.messages import ChannelName

# DNS TXT strings are limited to 255 bytes per chunk; we split if needed.
_TXT_CHUNK_SIZE = 200


def _chunk_text(text: str) -> list[bytes]:
    raw = text.encode("utf-8")
    return [raw[i : i + _TXT_CHUNK_SIZE] for i in range(0, len(raw), _TXT_CHUNK_SIZE)] or [b""]


class _DnsBeaconProtocol(asyncio.DatagramProtocol):
    def __init__(self, zone: str) -> None:
        self._zone = zone.strip(".").lower()
        self._transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            request = DNSRecord.parse(data)
        except Exception as exc:
            print(f"[DNS] Failed to parse query from {addr}: {exc}")
            return

        qname_text = str(request.q.qname).rstrip(".").lower()
        qtype = QTYPE[request.q.qtype]
        client_id = self._extract_client_id(qname_text)

        print(f"[DNS] Query {qtype} {qname_text} from {addr} -> client_id={client_id}")

        reply = request.reply()
        if qtype == "TXT" and self._matches_zone(qname_text):
            response_obj = {
                "status_code": 201,
                "detail": "Beacon accepted over DNS",
                "websocket_path": f"/ws/{client_id}",
                "accepted_channel": ChannelName.DNS.value,
                "server_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            chunks = _chunk_text(json.dumps(response_obj))
            reply.add_answer(RR(request.q.qname, QTYPE.TXT, ttl=30, rdata=TXT(chunks)))
        else:
            reply.header.rcode = 3  # NXDOMAIN

        assert self._transport is not None
        self._transport.sendto(reply.pack(), addr)

    def _matches_zone(self, qname: str) -> bool:
        return qname == self._zone or qname.endswith("." + self._zone)

    def _extract_client_id(self, qname: str) -> str:
        if not self._matches_zone(qname) or qname == self._zone:
            return "unknown"
        prefix = qname[: -(len(self._zone) + 1)]
        labels = prefix.split(".")
        return labels[0] if labels else "unknown"


async def run_dns_server(host: str = "0.0.0.0", port: int = 5353, zone: str = "alive.beacon.local") -> None:
    loop = asyncio.get_running_loop()

    transport, _protocol = await loop.create_datagram_endpoint(
        lambda: _DnsBeaconProtocol(zone=zone),
        local_addr=(host, port),
    )

    print(f"[DNS] Listening on udp/{host}:{port} authoritative for *.{zone}")

    try:
        await asyncio.Event().wait()
    finally:
        transport.close()
