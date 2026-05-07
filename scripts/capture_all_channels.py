#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
import textwrap
import time
from dataclasses import dataclass

from beacon_client.channels.registry import ChannelRegistry
from beacon_client.config import Settings
from beacon_client.models.messages import BeaconMessage, ChannelName


RESET = "\033[0m"
BOLD  = "\033[1m"
GREEN = "\033[32m"
RED   = "\033[31m"
CYAN  = "\033[36m"
YELLOW = "\033[33m"
DIM   = "\033[2m"

_use_color = True


def _c(code: str, text: str) -> str:
    return f"{code}{text}{RESET}" if _use_color else text

@dataclass
class ChannelMeta:
    name: str # match ChannelName enum
    display_filter: str
    capture_filter: str
    notes: str = ""

CHANNEL_ORDER: list[ChannelMeta] = [
    ChannelMeta(
        name="HTTP",
        display_filter="http && tcp.port == 8000",
        capture_filter="tcp port 8000",
        notes="Plaintext HTTP/1.1 — readable directly in the Packet Details pane.",
    ),
    ChannelMeta(
        name="HTTP/2",
        display_filter="http2 && tcp.port == 8443",
        capture_filter="tcp port 8443",
        notes="TLS-wrapped. Decrypt with the server key log or a known cert in Wireshark prefs.",
    ),
    ChannelMeta(
        name="HTTP/3",
        display_filter="quic && udp.port == 4433",
        capture_filter="udp port 4433",
        notes="Runs over QUIC/UDP. Use 'quic' dissector; decryption needs the SSLKEYLOGFILE.",
    ),
    ChannelMeta(
        name="TCP",
        display_filter="tcp.port == 9000",
        capture_filter="tcp port 9000",
        notes="Raw TCP framing — follow the TCP stream to see the JSON payload.",
    ),
    ChannelMeta(
        name="DNS",
        display_filter="dns && udp.port == 5354",
        capture_filter="udp port 5354",
        notes="TXT query carries the client_id label; TXT answer carries JSON response.",
    ),
    ChannelMeta(
        name="DoH",
        display_filter="http && tcp.port == 8043",
        capture_filter="tcp port 8043",
        notes="DNS-over-HTTPS — filter on Content-Type: application/dns-message.",
    ),
    ChannelMeta(
        name="ICMP",
        display_filter="icmp",
        capture_filter="icmp",
        notes="Payload hidden in ICMP Echo data field after the 8-byte 'BEACON01' magic.",
    ),
    ChannelMeta(
        name="FTP",
        display_filter="ftp || ftp-data",
        capture_filter="tcp port 2121",
        notes="STOR command uploads a .json file; follow the FTP-DATA stream for the body.",
    ),
    ChannelMeta(
        name="IMAP",
        display_filter="imap && tcp.port == 1143",
        capture_filter="tcp port 1143",
        notes="APPEND command stores beacon as an email message in INBOX.",
    ),
    ChannelMeta(
        name="SMB",
        display_filter="smb2 && tcp.port == 1445",
        capture_filter="tcp port 1445",
        notes="SMB2 Write/Create to the BEACON share. Use 'smb2' dissector.",
    ),
    ChannelMeta(
        name="LDAP",
        display_filter="ldap && tcp.port == 1389",
        capture_filter="tcp port 1389",
        notes="AddRequest stores beacon JSON in the 'description' attribute of a new entry.",
    ),
    ChannelMeta(
        name="MAPI",
        display_filter="http && tcp.port == 8007",
        capture_filter="tcp port 8007",
        notes=(
            "MAPI-over-HTTP POST to /mapi/emsmdb/. "
            "Look for X-RequestType and X-ResponseCode headers."
        ),
    ),
]

_META_BY_NAME: dict[str, ChannelMeta] = {m.name: m for m in CHANNEL_ORDER}

_COMBINED_CAPTURE_FILTER = (
    "tcp port 8000 or tcp port 8443 or udp port 4433 or tcp port 9000 "
    "or udp port 5354 or tcp port 8043 or icmp "
    "or tcp port 2121 or tcp port 1143 or tcp port 1445 "
    "or tcp port 1389 or tcp port 8007"
)

_COMBINED_DISPLAY_FILTER = (
    "tcp.port in {8000,8443,9000,8043,2121,1143,1445,1389,8007} "
    "|| udp.port in {4433,5354} || icmp || quic"
)


def _banner() -> None:
    width = 62
    line = "─" * width
    print()
    print(_c(BOLD + CYAN, f"┌{line}┐"))
    print(_c(BOLD + CYAN, "│") + _c(BOLD, f"  Beacon Wireshark Capture Script".center(width)) + _c(BOLD + CYAN, "│"))
    print(_c(BOLD + CYAN, f"├{line}┤"))

    filters = [
        ("Capture filter", _COMBINED_CAPTURE_FILTER),
        ("Display filter", _COMBINED_DISPLAY_FILTER),
    ]
    for label, filt in filters:
        wrapped = textwrap.wrap(filt, width - 4)
        first = True
        for part in wrapped:
            prefix = f"  {label}: " if first else "    "
            first = False
            print(_c(BOLD + CYAN, "│") + f"{prefix}{_c(YELLOW, part)}".ljust(width + len(_c(YELLOW, ''))) + _c(BOLD + CYAN, "│"))

    print(_c(BOLD + CYAN, f"└{line}┘"))
    print()


def _channel_header(index: int, total: int, meta: ChannelMeta) -> None:
    label = f"[{index}/{total}]  {meta.name}"
    print(_c(BOLD, f"\n{'═' * 60}"))
    print(_c(BOLD + CYAN, label))
    print(f"  {_c(DIM, 'Display filter:')}  {_c(YELLOW, meta.display_filter)}")
    print(f"  {_c(DIM, 'Capture filter:')}  {_c(YELLOW, meta.capture_filter)}")
    if meta.notes:
        print(f"  {_c(DIM, 'Notes:')}          {meta.notes}")
    print()


def _result(response) -> None:  # type: ignore[no-untyped-def]
    ok = 200 <= response.status_code < 300
    status_str = _c(GREEN if ok else RED, str(response.status_code))
    symbol = _c(GREEN, "✓") if ok else _c(RED, "Not nice")
    print(f"  {symbol} {status_str}  {response.detail}")
    if response.websocket_path:
        print(f"  {_c(DIM, 'websocket_path:')} {response.websocket_path}")
    if response.accepted_channel:
        print(f"  {_c(DIM, 'accepted_channel:')} {response.accepted_channel.value}")


def _pause(seconds: float, label: str) -> None:
    if seconds <= 0:
        return
    print(f"\n  {_c(DIM, f'Pausing {seconds:.1f}s — {label}')}", end="", flush=True)
    step = 0.5
    elapsed = 0.0
    while elapsed < seconds:
        time.sleep(min(step, seconds - elapsed))
        elapsed += step
        print(_c(DIM, "."), end="", flush=True)
    print()

async def run(channels: list[ChannelMeta], delay: float, client_id: str) -> None:
    settings = Settings()
    settings.__dict__["client_id"] = client_id
    registry = ChannelRegistry(settings=settings)

    total = len(channels)
    results: list[tuple[str, bool]] = []

    _banner()
    print(f"  Probing {_c(BOLD, str(total))} channel(s) with client_id={_c(BOLD, client_id)!r}")
    print(f"  Inter-channel delay: {delay}s\n")

    _pause(3.0, "start Wireshark capture now if you haven't already")

    for idx, meta in enumerate(channels, start=1):
        _channel_header(idx, total, meta)

        try:
            channel_enum = ChannelName(meta.name)
        except ValueError:
            print(f"  {_c(RED, 'Not nice')} Unknown channel name {meta.name!r} — skipping")
            results.append((meta.name, False))
            continue

        channel = registry._channels.get(channel_enum)
        if channel is None:
            print(f"  {_c(RED, 'Not nice')} No channel registered for {meta.name} — skipping")
            results.append((meta.name, False))
            continue

        payload = BeaconMessage(client_id=client_id, channel=channel_enum)

        print(f"  → Sending beacon via {_c(BOLD, meta.name)} …", flush=True)
        t0 = time.monotonic()
        try:
            response = await channel.send_alive(payload)
        except Exception as exc:
            elapsed = time.monotonic() - t0
            print(f"  {_c(RED, 'Not nice')} Exception after {elapsed:.2f}s: {exc}")
            results.append((meta.name, False))
        else:
            elapsed = time.monotonic() - t0
            print(f"  {_c(DIM, f'({elapsed:.2f}s)')}")
            _result(response)
            results.append((meta.name, 200 <= response.status_code < 300))

        if idx < total:
            _pause(delay, f"next: {channels[idx].name}")

    passed = sum(1 for _, ok in results if ok)
    failed = total - passed
    print(_c(BOLD, "  Summary"))
    for name, ok in results:
        sym = _c(GREEN, "Nice") if ok else _c(RED, "Not nice")
        print(f"  {sym}  {name}")
    print()
    print(
        f"  {_c(GREEN, str(passed))} passed  /  "
        f"{_c(RED if failed else DIM, str(failed))} failed  /  "
        f"{total} total"
    )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--channels",
        default="",
        help="Comma-separated channel names to probe (default: all in canonical order).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Pause between channels in seconds (default: 2.0).",
    )
    parser.add_argument(
        "--client-id",
        default="wireshark-probe",
        metavar="ID",
        help="client_id embedded in every beacon message (default: wireshark-probe).",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colour output.",
    )
    args = parser.parse_args()

    global _use_color
    if args.no_color or not sys.stdout.isatty():
        _use_color = False

    if args.channels:
        requested = [n.strip().upper() for n in args.channels.split(",") if n.strip()]
        _norm = {"HTTP2": "HTTP/2", "HTTP3": "HTTP/3", "DOH": "DoH"}
        normalised = [_norm.get(r, r) for r in requested]
        selected: list[ChannelMeta] = []
        for name in normalised:
            if name in _META_BY_NAME:
                selected.append(_META_BY_NAME[name])
            else:
                print(f"Warning: unknown channel {name!r} — ignoring", file=sys.stderr)
        if not selected:
            print("No valid channels selected.", file=sys.stderr)
            sys.exit(1)
    else:
        selected = list(CHANNEL_ORDER)

    asyncio.run(run(selected, args.delay, args.client_id))


if __name__ == "__main__":
    main()
