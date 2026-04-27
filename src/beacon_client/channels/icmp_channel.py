from __future__ import annotations

import asyncio
import json
import os
import socket
import struct
import time

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName

ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0
MAGIC_HEADER = b"BEACON01"


def icmp_checksum(data: bytes) -> int:
    total = 0
    length = len(data)
    for i in range(0, length - length % 2, 2):
        total += (data[i + 1] << 8) | data[i]
    if length % 2:
        total += data[-1]
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return ~total & 0xFFFF


def build_icmp_packet(icmp_type: int, identifier: int, sequence: int, payload: bytes) -> bytes:
    header = struct.pack("!BBHHH", icmp_type, 0, 0, identifier, sequence)
    chk = icmp_checksum(header + payload)
    header = struct.pack("!BBHHH", icmp_type, 0, chk, identifier, sequence)
    return header + payload


class IcmpChannel(BeaconChannel):
    def __init__(self, host: str, timeout: float = 15.0) -> None:
        self._host = host
        self._timeout = timeout

    @property
    def name(self) -> ChannelName:
        return ChannelName.ICMP

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._send_blocking, payload)

    def _send_blocking(self, payload: BeaconMessage) -> BeaconResponse:
        try:
            destination = socket.gethostbyname(self._host)
        except socket.gaierror as exc:
            return BeaconResponse(status_code=500, detail=f"ICMP DNS error: {exc}")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        except PermissionError as exc:
            return BeaconResponse(
                status_code=500,
                detail=f"ICMP requires raw socket privileges (CAP_NET_RAW): {exc}",
            )

        sock.settimeout(self._timeout)

        try:
            identifier = os.getpid() & 0xFFFF
            sequence = 1

            serialized = json.dumps(payload.model_dump(mode="json")).encode("utf-8")
            data = MAGIC_HEADER + serialized
            packet = build_icmp_packet(ICMP_ECHO_REQUEST, identifier, sequence, data)

            sock.sendto(packet, (destination, 0))

            deadline = time.monotonic() + self._timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return BeaconResponse(status_code=504, detail="ICMP timeout")
                sock.settimeout(remaining)

                try:
                    raw, _src = sock.recvfrom(65535)
                except socket.timeout:
                    return BeaconResponse(status_code=504, detail="ICMP timeout")

                if len(raw) < 28:
                    continue
                ip_header_len = (raw[0] & 0x0F) * 4
                icmp_packet = raw[ip_header_len:]
                if len(icmp_packet) < 8:
                    continue

                icmp_type, _code, _chk, recv_id, recv_seq = struct.unpack("!BBHHH", icmp_packet[:8])
                response_data = icmp_packet[8:]

                if icmp_type != ICMP_ECHO_REPLY:
                    continue
                if not response_data.startswith(MAGIC_HEADER):
                    continue
                if recv_id != identifier:
                    continue

                try:
                    response_obj = json.loads(response_data[len(MAGIC_HEADER):].decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    return BeaconResponse(status_code=500, detail=f"ICMP malformed reply: {exc}")

                return BeaconResponse(
                    status_code=int(response_obj.get("status_code", 500)),
                    detail=response_obj.get("detail", "No detail"),
                    websocket_path=response_obj.get("websocket_path"),
                    accepted_channel=ChannelName(response_obj["accepted_channel"]) if response_obj.get("accepted_channel") else None,
                )
        finally:
            sock.close()
