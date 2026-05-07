from __future__ import annotations

import base64
import json
import uuid

import httpx

from beacon_client.channels.base import BeaconChannel
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName

_MAPI_CONTENT_TYPE = "application/mapi-http"
_CLIENT_APP = "Outlook/16.0.14931.20466"


class MapiChannel(BeaconChannel):
    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        self._base_url = f"http://{host}:{port}"
        self._auth = base64.b64encode(f"{user}:{password}".encode()).decode()

    @property
    def name(self) -> ChannelName:
        return ChannelName.MAPI

    async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
        client_guid = f"{{{str(uuid.uuid4()).upper()}}}"
        request_id = f"{{{str(uuid.uuid4()).upper()}}}:1"

        headers = {
            "Content-Type": _MAPI_CONTENT_TYPE,
            "X-ClientInfo": client_guid,
            "X-ClientApplication": _CLIENT_APP,
            "X-RequestId": request_id,
            "X-RequestType": "Execute",
            "Authorization": f"Basic {self._auth}",
        }

        body_bytes = json.dumps(payload.model_dump(mode="json")).encode("utf-8")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self._base_url}/mapi/emsmdb/",
                    content=body_bytes,
                    headers=headers,
                )
        except httpx.RequestError as exc:
            return BeaconResponse(status_code=500, detail=f"MAPI connection error: {exc}")

        mapi_code = response.headers.get("X-ResponseCode", "-1")
        if mapi_code != "0":
            return BeaconResponse(
                status_code=response.status_code,
                detail=f"MAPI server error: X-ResponseCode={mapi_code}",
            )

        try:
            data = response.json()
        except ValueError as exc:
            return BeaconResponse(
                status_code=response.status_code,
                detail=f"Invalid MAPI response body: {exc}",
            )

        return BeaconResponse(
            status_code=data.get("status_code", response.status_code),
            detail=data.get("detail", "No detail"),
            websocket_path=data.get("websocket_path"),
            accepted_channel=ChannelName(data["accepted_channel"]) if data.get("accepted_channel") else None,
        )
