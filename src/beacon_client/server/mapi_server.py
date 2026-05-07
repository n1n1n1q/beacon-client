from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone

from aiohttp import web

from beacon_client.models.messages import ChannelName

_SERVER_APP = "Exchange/15.02.1118.007"

# X-ResponseCode values follow the MAPI error namespace.
# 0 = success, 8 = ecAccessDenied.
_RC_OK = "0"
_RC_DENIED = "8"
_RC_ERROR = "1"


def _mapi_response(
    body: dict,
    *,
    response_code: str = _RC_OK,
    request_id: str = "",
    status: int = 200,
) -> web.Response:
    headers: dict[str, str] = {
        "Content-Type": _MAPI_CONTENT_TYPE,
        "X-ResponseCode": response_code,
        "X-ServerApplication": _SERVER_APP,
    }
    if request_id:
        headers["X-RequestId"] = request_id
    return web.Response(status=status, headers=headers, text=json.dumps(body))


_MAPI_CONTENT_TYPE = "application/mapi-http"
_VALID_REQUEST_TYPES = {"Connect", "Execute", "Disconnect", "NotificationWait"}


def _authenticate(request: web.Request, user: str, password: str) -> bool:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8")
        u, p = decoded.split(":", 1)
        return u == user and p == password
    except Exception:
        return False


async def _handle_emsmdb(request: web.Request) -> web.Response:
    user: str = request.app["mapi_user"]
    password: str = request.app["mapi_password"]

    if not _authenticate(request, user, password):
        return web.Response(
            status=401,
            headers={
                "WWW-Authenticate": 'Basic realm="MAPI"',
                "X-ResponseCode": _RC_DENIED,
                "X-ServerApplication": _SERVER_APP,
            },
        )

    request_type = request.headers.get("X-RequestType", "")
    request_id = request.headers.get("X-RequestId", "")
    client_info = request.headers.get("X-ClientInfo", "unknown")

    if request_type not in _VALID_REQUEST_TYPES:
        return _mapi_response(
            {"error": f"Unknown X-RequestType: {request_type!r}"},
            response_code=_RC_ERROR,
            request_id=request_id,
        )

    if request_type == "Disconnect":
        return _mapi_response(
            {"status_code": 200, "detail": "Session disconnected"},
            request_id=request_id,
        )

    if request_type == "NotificationWait":
        # Long-poll placeholder: immediately return with no pending notifications.
        return _mapi_response(
            {"status_code": 200, "detail": "No pending notifications"},
            request_id=request_id,
        )

    # Connect or Execute: read and parse the beacon payload.
    client_id = "unknown"
    try:
        raw = await request.read()
        if raw:
            data = json.loads(raw.decode("utf-8"))
            client_id = data.get("client_id", "unknown")
    except Exception:
        pass

    print(f"[MAPI] {request_type} from client_id={client_id!r} client_info={client_info!r}")

    return _mapi_response(
        {
            "status_code": 201,
            "detail": f"Beacon accepted over MAPI ({request_type})",
            "websocket_path": f"/ws/{client_id}",
            "accepted_channel": ChannelName.MAPI.value,
            "server_timestamp": datetime.now(timezone.utc).isoformat(),
        },
        request_id=request_id,
    )


async def _handle_nspi(request: web.Request) -> web.Response:
    """Address-book endpoint — returns a minimal OK response."""
    return _mapi_response(
        {"status_code": 200, "detail": "NSPI endpoint ready"},
        request_id=request.headers.get("X-RequestId", ""),
    )


async def run_mapi_server(
    host: str = "0.0.0.0",
    port: int = 8007,
    user: str = "beacon",
    password: str = "beacon",
) -> None:
    app = web.Application()
    app["mapi_user"] = user
    app["mapi_password"] = password

    app.router.add_post("/mapi/emsmdb/", _handle_emsmdb)
    app.router.add_post("/mapi/nspi/", _handle_nspi)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    print(f"[MAPI] Listening on {host}:{port} (user={user})")

    while True:
        await asyncio.sleep(3600)
