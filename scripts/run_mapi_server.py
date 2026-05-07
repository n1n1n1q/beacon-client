from __future__ import annotations

import asyncio

from beacon_client.config import Settings
from beacon_client.server.mapi_server import run_mapi_server


async def main() -> None:
    settings = Settings()
    await run_mapi_server(
        host="0.0.0.0",
        port=settings.server_mapi_port,
        user=settings.mapi_user,
        password=settings.mapi_password,
    )


if __name__ == "__main__":
    asyncio.run(main())
