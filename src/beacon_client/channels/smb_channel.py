from __future__ import annotations

import asyncio
import json
import ntpath
import time
from io import BytesIO

from impacket.smbconnection import SessionError, SMBConnection

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class SmbChannel(BeaconChannel):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        share: str,
        timeout: float = 15.0,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._share = share
        self._timeout = timeout

    @property
    def name(self) -> ChannelName:
        return ChannelName.SMB

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._send_blocking, payload)

    def _send_blocking(self, payload: BeaconMessage) -> BeaconResponse:
        serialized = json.dumps(payload.model_dump(mode="json")).encode("utf-8")
        safe_client_id = _sanitize_client_id(payload.client_id)
        remote_name = f"{safe_client_id}-{int(time.time() * 1000)}.json"
        remote_path = ntpath.join("upload", remote_name)

        conn: SMBConnection | None = None
        try:
            conn = SMBConnection(self._host, self._host, sess_port=self._port, timeout=self._timeout)
            conn.login(self._user, self._password)

            try:
                conn.createDirectory(self._share, "upload")
            except SessionError:
                pass

            buffer = BytesIO(serialized)
            conn.putFile(self._share, remote_path, buffer.read)
        except (SessionError, OSError) as exc:
            return BeaconResponse(status_code=500, detail=f"SMB error: {exc}")
        finally:
            if conn is not None:
                try:
                    conn.logoff()
                except Exception:
                    pass

        return BeaconResponse(
            status_code=201,
            detail=f"Beacon accepted over SMB (stored as {remote_name})",
            websocket_path=f"/ws/{payload.client_id}",
            accepted_channel=ChannelName.SMB,
        )


def _sanitize_client_id(client_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in client_id)
    return cleaned or "unknown"
