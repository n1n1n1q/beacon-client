from __future__ import annotations

import asyncio
import json
import socket
import struct
from datetime import datetime, timezone

from beacon_client.channels.icmp_channel import (
    ICMP_ECHO_REPLY,
    ICMP_ECHO_REQUEST,
    MAGIC_HEADER,
    build_icmp_packet,
)
from beacon_client.models.messages import ChannelName


def _handle_packet(sock: socket.socket, raw: bytes, source: tuple) -> None:
    if len(raw) < 28:
        return
    ip_header_len = (raw[0] & 0x0F) * 4
    icmp_packet = raw[ip_header_len:]
    if len(icmp_packet) < 8:
        return

    icmp_type, _code, _chk, identifier, sequence = struct.unpack("!BBHHH", icmp_packet[:8])
    if icmp_type != ICMP_ECHO_REQUEST:
        return

    data = icmp_packet[8:]
    if not data.startswith(MAGIC_HEADER):
        return

    try:
        request_obj = json.loads(data[len(MAGIC_HEADER):].decode("utf-8"))
    except Exception as exc:
        print(f"[ICMP] Malformed payload from {source}: {exc}")
        return

    client_id = request_obj.get("client_id", "unknown")
    print(f"[ICMP] Beacon from {source[0]} client_id={client_id}")

    response = {
        "status_code": 201,
        "detail": "Beacon accepted over ICMP",
        "websocket_path": f"/ws/{client_id}",
        "accepted_channel": ChannelName.ICMP.value,
        "server_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    response_payload = MAGIC_HEADER + json.dumps(response).encode("utf-8")
    reply = build_icmp_packet(ICMP_ECHO_REPLY, identifier, sequence, response_payload)

    try:
        sock.sendto(reply, source)
    except OSError as exc:
        print(f"[ICMP] Failed to send reply to {source}: {exc}")


async def run_icmp_server(host: str = "0.0.0.0") -> None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError as exc:
        raise RuntimeError(
            "ICMP server requires raw socket privileges. Run with CAP_NET_RAW.",
        ) from exc

    sock.setblocking(False)
    sock.bind((host, 0))

    loop = asyncio.get_running_loop()

    def _on_readable() -> None:
        try:
            raw, source = sock.recvfrom(65535)
        except BlockingIOError:
            return
        except OSError as exc:
            print(f"[ICMP] recv error: {exc}")
            return
        _handle_packet(sock, raw, source)

    loop.add_reader(sock.fileno(), _on_readable)
    print(f"[ICMP] Raw socket listening on {host} (Echo Request -> Echo Reply)")

    try:
        await asyncio.Event().wait()
    finally:
        loop.remove_reader(sock.fileno())
        sock.close()
