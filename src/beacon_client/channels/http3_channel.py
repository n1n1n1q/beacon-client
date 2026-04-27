from __future__ import annotations

import asyncio
import json
import ssl
from typing import cast

from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import DataReceived, H3Event, HeadersReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import ProtocolNegotiated, QuicEvent

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class _Http3ClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._http: H3Connection | None = None
        self._streams: dict[int, dict] = {}
        self._waiters: dict[int, asyncio.Future] = {}
        self._http_ready = asyncio.Event()

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated):
            if event.alpn_protocol in H3_ALPN:
                self._http = H3Connection(self._quic)
                self._http_ready.set()

        if self._http is not None:
            for h3_event in self._http.handle_event(event):
                self._handle_h3_event(h3_event)

    def _handle_h3_event(self, event: H3Event) -> None:
        stream_id = getattr(event, "stream_id", None)
        if stream_id is None:
            return
        bucket = self._streams.setdefault(stream_id, {"headers": [], "body": b""})

        if isinstance(event, HeadersReceived):
            bucket["headers"] = event.headers
        elif isinstance(event, DataReceived):
            bucket["body"] += event.data

        if getattr(event, "stream_ended", False):
            waiter = self._waiters.pop(stream_id, None)
            if waiter is not None and not waiter.done():
                waiter.set_result(bucket)

    async def post_json(self, host: str, port: int, path: str, body: bytes) -> dict:
        await asyncio.wait_for(self._http_ready.wait(), timeout=10.0)
        assert self._http is not None

        stream_id = self._quic.get_next_available_stream_id()
        waiter: asyncio.Future = asyncio.get_running_loop().create_future()
        self._waiters[stream_id] = waiter

        authority = f"{host}:{port}".encode()
        self._http.send_headers(
            stream_id=stream_id,
            headers=[
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", authority),
                (b":path", path.encode()),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"user-agent", b"beacon-client/0.1 aioquic"),
            ],
            end_stream=False,
        )
        self._http.send_data(stream_id=stream_id, data=body, end_stream=True)
        self.transmit()

        return await asyncio.wait_for(waiter, timeout=15.0)


class Http3Channel(BeaconChannel):
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    @property
    def name(self) -> ChannelName:
        return ChannelName.HTTP3

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        configuration = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)
        configuration.verify_mode = ssl.CERT_NONE

        body = json.dumps(payload.model_dump(mode="json")).encode("utf-8")

        try:
            async with connect(
                self._host,
                self._port,
                configuration=configuration,
                create_protocol=_Http3ClientProtocol,
            ) as client:
                client = cast(_Http3ClientProtocol, client)
                await client.wait_connected()
                response = await client.post_json(self._host, self._port, "/beacon", body)
        except Exception as exc:
            return BeaconResponse(status_code=500, detail=f"HTTP/3 error: {exc}")

        headers = dict(response.get("headers", []))
        status_raw = headers.get(b":status", b"500")
        try:
            status_code = int(status_raw)
        except ValueError:
            status_code = 500

        try:
            body_obj = json.loads(response["body"].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return BeaconResponse(status_code=status_code, detail="Unparseable HTTP/3 response body")

        return BeaconResponse(
            status_code=status_code,
            detail=body_obj.get("detail", "No detail"),
            websocket_path=body_obj.get("websocket_path"),
            accepted_channel=ChannelName(body_obj["accepted_channel"]) if body_obj.get("accepted_channel") else None,
        )
