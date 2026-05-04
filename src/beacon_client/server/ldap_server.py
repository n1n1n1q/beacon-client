from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from ldap3.protocol import rfc4511
from pyasn1.codec.ber import decoder, encoder

_SUCCESS = 0
_PROTOCOL_ERROR = 2
_INVALID_CREDENTIALS = 49
_INSUFFICIENT_ACCESS = 50


class _LdapSession:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        user: str,
        password: str,
        base_dn: str,
        storage_dir: Path | None,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._user = user
        self._password = password
        self._base_dn = base_dn.strip().lower()
        self._storage_dir = storage_dir
        self._authed = not bool(user)
        self._peer = writer.get_extra_info("peername")

    async def run(self) -> None:
        while True:
            raw = await _read_ldap_message(self._reader)
            if raw is None:
                break

            try:
                message, _ = decoder.decode(raw, asn1Spec=rfc4511.LDAPMessage())
            except Exception as exc:
                print(f"[LDAP] Failed to decode message from {self._peer}: {exc}")
                break

            message_id = int(message["messageID"])
            protocol_op = message["protocolOp"]
            op_name = _get_protocol_op_name(protocol_op)
            if not op_name:
                await self._send_result(message_id, "bindResponse", _PROTOCOL_ERROR, "Unknown protocol op")
                continue

            if op_name == "bindRequest":
                await self._handle_bind(message_id, protocol_op[op_name])
            elif op_name == "addRequest":
                await self._handle_add(message_id, protocol_op[op_name])
            elif op_name == "searchRequest":
                await self._handle_search(message_id)
            elif op_name == "unbindRequest":
                break
            else:
                await self._send_result(message_id, "bindResponse", _PROTOCOL_ERROR, f"Unsupported op {op_name}")

        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:
            pass

    async def _handle_bind(self, message_id: int, bind_request: rfc4511.BindRequest) -> None:
        bind_dn = _decode_text(bind_request["name"])
        auth = bind_request["authentication"]
        password = ""

        auth_name = _get_protocol_op_name(auth)
        if auth_name == "simple":
            password = _decode_text(auth["simple"])

        if self._validate_credentials(bind_dn, password):
            self._authed = True
            await self._send_result(message_id, "bindResponse", _SUCCESS, "Bind OK")
        else:
            await self._send_result(message_id, "bindResponse", _INVALID_CREDENTIALS, "Invalid credentials")

    async def _handle_add(self, message_id: int, add_request: rfc4511.AddRequest) -> None:
        if not self._authed:
            await self._send_result(message_id, "addResponse", _INSUFFICIENT_ACCESS, "Bind required")
            return

        entry_dn = _decode_text(add_request["entry"])
        payload = _extract_payload(add_request)
        client_id = _extract_client_id(entry_dn, payload)

        if payload and self._storage_dir is not None:
            _store_payload(self._storage_dir, client_id, payload)

        await self._send_result(message_id, "addResponse", _SUCCESS, "Beacon accepted over LDAP")
        print(f"[LDAP] Beacon from {client_id} via {self._peer}")

    async def _handle_search(self, message_id: int) -> None:
        await self._send_result(message_id, "searchResDone", _SUCCESS, "Search completed")

    async def _send_result(self, message_id: int, op_name: str, code: int, diagnostic: str) -> None:
        response = _build_result_response(op_name)
        response["resultCode"] = code
        response["matchedDN"] = ""
        response["diagnosticMessage"] = diagnostic

        message = rfc4511.LDAPMessage()
        message["messageID"] = message_id
        message["protocolOp"].setComponentByName(op_name, response)

        self._writer.write(encoder.encode(message))
        await self._writer.drain()

    def _validate_credentials(self, bind_dn: str, password: str) -> bool:
        if not self._user:
            return True
        if password != self._password:
            return False

        normalized = bind_dn.strip().lower()
        user = self._user.strip().lower()
        if normalized == user:
            return True

        if self._base_dn and normalized.endswith("," + self._base_dn):
            if normalized.startswith(f"cn={user},") or normalized.startswith(f"uid={user},"):
                return True

        return normalized in {
            f"cn={user},{self._base_dn}",
            f"uid={user},{self._base_dn}",
        }


def _build_result_response(op_name: str):
    if op_name == "bindResponse":
        return rfc4511.BindResponse()
    if op_name == "addResponse":
        return rfc4511.AddResponse()
    if op_name == "searchResDone":
        return rfc4511.SearchResultDone()
    return rfc4511.BindResponse()


def _get_protocol_op_name(protocol_op) -> str | None:
    try:
        name = protocol_op.getName()
        if name:
            return name
    except Exception:
        pass

    try:
        for named_type in protocol_op.componentType.namedTypes:
            candidate = named_type.name
            component = protocol_op.getComponentByName(candidate)
            if component is not None and component.hasValue():
                return candidate
    except Exception:
        pass

    return None


def _decode_text(value) -> str:
    try:
        return bytes(value).decode("utf-8", errors="replace")
    except Exception:
        return str(value)


def _extract_payload(add_request: rfc4511.AddRequest) -> dict | None:
    try:
        attrs = add_request["attributes"]
    except Exception:
        return None

    for attribute in attrs:
        attr_type = _decode_text(attribute["type"]).lower()
        if attr_type != "description":
            continue
        for raw in attribute["vals"]:
            text = _decode_text(raw)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    return None


def _extract_client_id(entry_dn: str, payload: dict | None) -> str:
    if payload and isinstance(payload, dict):
        client_id = payload.get("client_id")
        if client_id:
            return str(client_id)

    if "=" in entry_dn:
        rdn = entry_dn.split(",", 1)[0]
        parts = rdn.split("=", 1)
        if len(parts) == 2 and parts[1]:
            return parts[1]

    return "unknown"


def _store_payload(storage_dir: Path, client_id: str, payload: dict) -> None:
    safe_client_id = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in client_id) or "unknown"
    filename = f"{safe_client_id}-{int(time.time() * 1000)}.json"
    path = storage_dir / filename
    path.write_text(json.dumps(payload), encoding="utf-8")


async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    user: str,
    password: str,
    base_dn: str,
    storage_dir: Path | None,
) -> None:
    session = _LdapSession(reader, writer, user=user, password=password, base_dn=base_dn, storage_dir=storage_dir)
    await session.run()


async def run_ldap_server(
    host: str = "0.0.0.0",
    port: int = 1389,
    user: str = "beacon",
    password: str = "beacon",
    base_dn: str = "dc=beacon,dc=local",
    storage_dir: str = "/tmp/beacon_ldap",
) -> None:
    storage_path: Path | None = None
    if storage_dir:
        storage_path = Path(storage_dir)
        storage_path.mkdir(parents=True, exist_ok=True)

    server = await asyncio.start_server(
        lambda r, w: _handle_client(r, w, user=user, password=password, base_dn=base_dn, storage_dir=storage_path),
        host=host,
        port=port,
    )

    address = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"[LDAP] Listening on {address} base_dn={base_dn} user={user}")

    async with server:
        await server.serve_forever()


async def _read_ldap_message(reader: asyncio.StreamReader) -> bytes | None:
    try:
        tag = await reader.readexactly(1)
    except asyncio.IncompleteReadError:
        return None
    if not tag:
        return None

    try:
        length_first = await reader.readexactly(1)
    except asyncio.IncompleteReadError:
        return None

    length = length_first[0]
    length_bytes = b""
    if length & 0x80:
        num_bytes = length & 0x7F
        if num_bytes == 0:
            return None
        try:
            length_bytes = await reader.readexactly(num_bytes)
        except asyncio.IncompleteReadError:
            return None
        length = int.from_bytes(length_bytes, "big")

    try:
        body = await reader.readexactly(length)
    except asyncio.IncompleteReadError:
        return None

    return tag + length_first + length_bytes + body
