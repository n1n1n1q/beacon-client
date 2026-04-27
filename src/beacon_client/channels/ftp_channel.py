from __future__ import annotations

import json
import time

import aioftp

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName


class FtpChannel(BeaconChannel):
    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password

    @property
    def name(self) -> ChannelName:
        return ChannelName.FTP

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        serialized = json.dumps(payload.model_dump(mode="json")).encode("utf-8")
        remote_name = f"{payload.client_id}-{int(time.time() * 1000)}.json"

        try:
            async with aioftp.Client.context(
                self._host,
                self._port,
                user=self._user,
                password=self._password,
            ) as client:
                try:
                    await client.make_directory("upload", parents=True)
                except aioftp.StatusCodeError:
                    # Already exists — that's fine.
                    pass
                await client.change_directory("upload")

                async with client.upload_stream(remote_name) as stream:
                    await stream.write(serialized)
        except (aioftp.StatusCodeError, OSError, ConnectionError) as exc:
            return BeaconResponse(status_code=500, detail=f"FTP error: {exc}")

        return BeaconResponse(
            status_code=201,
            detail=f"Beacon accepted over FTP (stored as {remote_name})",
            websocket_path=f"/ws/{payload.client_id}",
            accepted_channel=ChannelName.FTP,
        )
