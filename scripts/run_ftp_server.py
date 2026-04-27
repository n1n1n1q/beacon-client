from __future__ import annotations

import asyncio

from beacon_client.config import Settings
from beacon_client.server.ftp_server import run_ftp_server


async def main() -> None:
    settings = Settings()
    await run_ftp_server(
        host="0.0.0.0",
        port=settings.server_ftp_port,
        user=settings.ftp_user,
        password=settings.ftp_password,
    )


if __name__ == "__main__":
    asyncio.run(main())
