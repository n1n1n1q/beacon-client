from __future__ import annotations

import asyncio
import json
import ssl
from datetime import datetime, timezone

from aiohttp import web
from dnslib import QTYPE, RR, TXT, DNSRecord

from beacon_client.models.messages import ChannelName
from beacon_client.server._tls import ensure_self_signed_cert

_TXT_CHUNK_SIZE = 200

def _chunk_text(text: str) -> list[bytes]:
    raw = text.encode("utf-8")
    return [raw[i : i + _TXT_CHUNK_SIZE] for i in range(0, len(raw), _TXT_CHUNK_SIZE)] or [b""]

class _DoHBeaconHandler:
    def __init__(self, zone: str) -> None:
        self._zone = zone.strip(".").lower()

    def _matches_zone(self, qname: str) -> bool:
        return qname == self._zone or qname.endswith("." + self._zone)

    def _extract_client_id(self, qname: str) -> str:
        if not self._matches_zone(qname) or qname == self._zone:
            return "unknown"
        prefix = qname[: -(len(self._zone) + 1)]
        labels = prefix.split(".")
        return labels[0] if labels else "unknown"

    def _process_dns_query(self, data: bytes, client_addr: str) -> bytes | None:
        try:
            request = DNSRecord.parse(data)
        except Exception as exc:
            print(f"[DoH] Failed to parse query from {client_addr}: {exc}")
            return None

        qname_text = str(request.q.qname).rstrip(".").lower()
        qtype = QTYPE[request.q.qtype]
        client_id = self._extract_client_id(qname_text)

        print(f"[DoH] Query {qtype} {qname_text} from {client_addr} -> client_id={client_id}")

        reply = request.reply()
        if qtype == "TXT" and self._matches_zone(qname_text):
            response_obj = {
                "status_code": 201,
                "detail": "Beacon accepted over DoH",
                "websocket_path": f"/ws/{client_id}",
                "accepted_channel": ChannelName.DOH.value, 
                "server_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            chunks = _chunk_text(json.dumps(response_obj))
            reply.add_answer(RR(request.q.qname, QTYPE.TXT, ttl=30, rdata=TXT(chunks)))
        else:
            reply.header.rcode = 3 

        return reply.pack()

    async def handle_post(self, request: web.Request) -> web.Response:
        if request.content_type != "application/dns-message":
            return web.Response(status=415, text="Unsupported Media Type")
        
        body = await request.read()
        client_addr = request.remote or "unknown"
        
        response_bytes = self._process_dns_query(body, client_addr)
        if response_bytes is None:
            return web.Response(status=400, text="Bad Request")
            
        return web.Response(body=response_bytes, content_type="application/dns-message")


async def run_doh_server(host: str = "0.0.0.0", port: int = 8043, zone: str = "alive.beacon.local") -> None:
    handler = _DoHBeaconHandler(zone=zone)

    cert_path, key_path = ensure_self_signed_cert()
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

    app = web.Application()
    app.router.add_post("/dns-query", handler.handle_post)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port, ssl_context=ssl_context)
    await site.start()

    print(f"[DoH] Listening on https://{host}:{port}/dns-query authoritative for *.{zone}")

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()