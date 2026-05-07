from __future__ import annotations

import struct

ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0

_ICMP_HEADER_LEN = 8
_MIN_IPV4_HEADER_LEN = 20


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"

    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) + data[i + 1]
        total = (total & 0xFFFF) + (total >> 16)

    return ~total & 0xFFFF


def _build_echo_packet(icmp_type: int, identifier: int, sequence: int, payload: bytes) -> bytes:
    header = struct.pack("!BBHHH", icmp_type, 0, 0, identifier, sequence)
    check = checksum(header + payload)
    return struct.pack("!BBHHH", icmp_type, 0, check, identifier, sequence) + payload


def build_echo_request(identifier: int, sequence: int, payload: bytes) -> bytes:
    return _build_echo_packet(ICMP_ECHO_REQUEST, identifier, sequence, payload)


def build_echo_reply(identifier: int, sequence: int, payload: bytes) -> bytes:
    return _build_echo_packet(ICMP_ECHO_REPLY, identifier, sequence, payload)


def parse_icmp_packet(raw: bytes) -> tuple[int, int, int, int, bytes] | None:
    if len(raw) < _ICMP_HEADER_LEN:
        return None

    offset = 0
    if len(raw) >= _MIN_IPV4_HEADER_LEN and (raw[0] >> 4) == 4:
        header_len = (raw[0] & 0x0F) * 4
        if len(raw) < header_len + _ICMP_HEADER_LEN:
            return None
        offset = header_len

    if len(raw) < offset + _ICMP_HEADER_LEN:
        return None

    icmp_type, icmp_code, _checksum, identifier, sequence = struct.unpack(
        "!BBHHH", raw[offset : offset + _ICMP_HEADER_LEN]
    )
    payload = raw[offset + _ICMP_HEADER_LEN :]
    return icmp_type, icmp_code, identifier, sequence, payload
