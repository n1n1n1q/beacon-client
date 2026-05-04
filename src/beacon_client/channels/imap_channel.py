from __future__ import annotations

import asyncio
import imaplib
import json
from email.message import EmailMessage
from email.utils import formatdate

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class ImapChannel(BeaconChannel):
    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password

    @property
    def name(self) -> ChannelName:
        return ChannelName.IMAP

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._send_blocking, payload)

    def _send_blocking(self, payload: BeaconMessage) -> BeaconResponse:
        message = self._build_message(payload)

        try:
            client = imaplib.IMAP4(self._host, self._port)
            try:
                client.login(self._user, self._password)
                status, _data = client.append("INBOX", None, None, message)
            finally:
                try:
                    client.logout()
                except Exception:
                    pass
        except Exception as exc:
            return BeaconResponse(status_code=500, detail=f"IMAP error: {exc}")

        if status != "OK":
            return BeaconResponse(status_code=500, detail=f"IMAP APPEND failed: {status}")

        return BeaconResponse(
            status_code=201,
            detail="Beacon accepted over IMAP",
            websocket_path=f"/ws/{payload.client_id}",
            accepted_channel=ChannelName.IMAP,
        )

    def _build_message(self, payload: BeaconMessage) -> bytes:
        msg = EmailMessage()
        msg["From"] = self._user
        msg["To"] = "beacon-imap"
        msg["Subject"] = f"Beacon {payload.client_id}"
        msg["Date"] = formatdate(localtime=True)
        msg["X-Beacon-Channel"] = ChannelName.IMAP.value
        msg.set_content(json.dumps(payload.model_dump(mode="json")), subtype="json", charset="utf-8")
        return msg.as_bytes()
