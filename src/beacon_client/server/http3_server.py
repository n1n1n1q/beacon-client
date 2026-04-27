from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from aioquic.asyncio import serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import DataReceived, H3Event, HeadersReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import ProtocolNegotiated, QuicEvent

from beacon_client.models.messages import ChannelName
from beacon_client.server._tls import ensure_self_signed_cert


class _Http3ServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._http: H3Connection | None = None
        self._streams: dict[int, dict] = {}

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated):
            if event.alpn_protocol in H3_ALPN:
                self._http = H3Connection(self._quic)
        if self._http is not None:
            for h3_event in self._http.handle_event(event):
                self._handle_h3_event(h3_event)

    def _handle_h3_event(self, event: H3Event) -> None:
        stream_id = getattr(event, "stream_id", None)
        if stream_id is None:
            return
        bucket = self._streams.setdefault(stream_id, {"headers": [], "body": b"", "method": b"GET", "path": b"/"})

        if isinstance(event, HeadersReceived):
            bucket["headers"] = event.headers
            for name, value in event.headers:
                if name == b":method":
                    bucket["method"] = value
                elif name == b":path":
                    bucket["path"] = value
        elif isinstance(event, DataReceived):
            bucket["body"] += event.data

        if getattr(event, "stream_ended", False):
            self._respond(stream_id, bucket)

    def _respond(self, stream_id: int, bucket: dict) -> None:
        assert self._http is not None
        path = bucket["path"].decode("utf-8", errors="replace")
        method = bucket["method"].decode("ascii", errors="replace")

        if method != "POST" or not path.startswith("/beacon"):
            self._send_json(stream_id, status=404, body={"detail": "Not found"})
            return

        try:
            payload_obj = json.loads(bucket["body"].decode("utf-8"))
        except Exception as exc:
            self._send_json(stream_id, status=400, body={"detail": f"Invalid JSON: {exc}"})
            return

        client_id = payload_obj.get("client_id", "unknown")
        response = {
            "status_code": 201,
            "detail": "Beacon accepted over HTTP/3",
            "websocket_path": f"/ws/{client_id}",
            "accepted_channel": ChannelName.HTTP3.value,
            "server_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._send_json(stream_id, status=201, body=response)
        print(f"[HTTP/3] Beacon from {client_id}")

    def _send_json(self, stream_id: int, status: int, body: dict) -> None:
        assert self._http is not None
        body_bytes = json.dumps(body).encode("utf-8")
        self._http.send_headers(
            stream_id=stream_id,
            headers=[
                (b":status", str(status).encode()),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body_bytes)).encode()),
                (b"server", b"beacon-http3/0.1 aioquic"),
            ],
        )
        self._http.send_data(stream_id=stream_id, data=body_bytes, end_stream=True)


async def run_http3_server(host: str = "0.0.0.0", port: int = 4433) -> None:
    cert_path, key_path = ensure_self_signed_cert()

    configuration = QuicConfiguration(is_client=False, alpn_protocols=H3_ALPN)
    configuration.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

    print(f"[HTTP/3] Listening on udp/{host}:{port}")

    await serve(host, port, configuration=configuration, create_protocol=_Http3ServerProtocol)

    await asyncio.Event().wait()
