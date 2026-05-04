from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from beacon_client.models.messages import ChannelName

_LITERAL_RE = re.compile(r"\{(\d+)(\+)?\}$")


class _ImapSession:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        user: str,
        password: str,
        mailbox_dir: Path,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._user = user
        self._password = password
        self._mailbox_dir = mailbox_dir
        self._authed = False
        self._peer = writer.get_extra_info("peername")

    async def run(self) -> None:
        await self._send_line("* OK IMAP4rev1 Beacon IMAP Server Ready")

        while True:
            line = await self._read_line()
            if line is None:
                break
            if not line:
                continue

            tag, command, args = self._parse_command(line)
            if tag is None or command is None:
                await self._send_line("* BAD Invalid command")
                continue

            if command == "CAPABILITY":
                await self._send_line("* CAPABILITY IMAP4rev1")
                await self._send_line(f"{tag} OK CAPABILITY completed")
            elif command == "NOOP":
                await self._send_line(f"{tag} OK NOOP completed")
            elif command == "ID":
                await self._send_line("* ID NIL")
                await self._send_line(f"{tag} OK ID completed")
            elif command == "LOGOUT":
                await self._send_line("* BYE Logging out")
                await self._send_line(f"{tag} OK LOGOUT completed")
                break
            elif command == "LOGIN":
                await self._handle_login(tag, args)
            elif command == "APPEND":
                await self._handle_append(tag, line)
            else:
                await self._send_line(f"{tag} BAD Unknown command")

        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:
            pass

    async def _handle_login(self, tag: str, args: str) -> None:
        parts = [item.strip('"') for item in args.split()]
        user = parts[0] if parts else ""
        password = parts[1] if len(parts) > 1 else ""

        if user == self._user and password == self._password:
            self._authed = True
            await self._send_line(f"{tag} OK LOGIN completed")
        else:
            await self._send_line(f"{tag} NO Invalid credentials")

    async def _handle_append(self, tag: str, line: str) -> None:
        if not self._authed:
            await self._send_line(f"{tag} NO Authentication required")
            return

        match = _LITERAL_RE.search(line)
        if not match:
            await self._send_line(f"{tag} BAD APPEND missing literal size")
            return

        size = int(match.group(1))
        non_sync = bool(match.group(2))

        if not non_sync:
            await self._send_line("+ Ready for literal data")

        try:
            data = await self._reader.readexactly(size)
        except asyncio.IncompleteReadError:
            await self._send_line(f"{tag} NO APPEND incomplete")
            return

        await self._reader.readline()

        client_id = self._store_message(data)
        await self._send_line("* OK Beacon accepted over IMAP")
        await self._send_line(f"{tag} OK APPEND completed")
        print(f"[IMAP] Beacon from {client_id} via {self._peer}")

    def _store_message(self, data: bytes) -> str:
        payload = self._extract_payload(data)
        client_id = payload.get("client_id", "unknown") if payload else "unknown"
        filename = f"{client_id}-{int(time.time() * 1000)}.eml"
        path = self._mailbox_dir / filename
        path.write_bytes(data)
        return client_id

    def _extract_payload(self, data: bytes) -> dict | None:
        text = data.decode("utf-8", errors="replace")
        if "\r\n\r\n" in text:
            body = text.split("\r\n\r\n", 1)[1]
        elif "\n\n" in text:
            body = text.split("\n\n", 1)[1]
        else:
            body = text

        try:
            return json.loads(body.strip())
        except json.JSONDecodeError:
            return None

    async def _read_line(self) -> str | None:
        raw = await self._reader.readline()
        if not raw:
            return None
        return raw.decode("utf-8", errors="replace").rstrip("\r\n")

    async def _send_line(self, line: str) -> None:
        self._writer.write((line + "\r\n").encode("utf-8"))
        await self._writer.drain()

    def _parse_command(self, line: str) -> tuple[str | None, str | None, str]:
        parts = line.split(" ", 2)
        if len(parts) < 2:
            return None, None, ""
        tag = parts[0]
        command = parts[1].upper()
        args = parts[2] if len(parts) > 2 else ""
        return tag, command, args


async def run_imap_server(
    host: str = "0.0.0.0",
    port: int = 1143,
    user: str = "beacon",
    password: str = "beacon",
    mailbox_dir: str = "/tmp/beacon_imap",
) -> None:
    mailbox_path = Path(mailbox_dir)
    mailbox_path.mkdir(parents=True, exist_ok=True)

    async def _handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        session = _ImapSession(reader, writer, user=user, password=password, mailbox_dir=mailbox_path)
        await session.run()

    server = await asyncio.start_server(_handler, host=host, port=port)
    address = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"[IMAP] Listening on {address} (user={user})")

    async with server:
        await server.serve_forever()
