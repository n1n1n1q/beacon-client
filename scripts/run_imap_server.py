from __future__ import annotations

import asyncio

from beacon_client.config import Settings
from beacon_client.server.imap_server import run_imap_server


async def main() -> None:
    settings = Settings()
    await run_imap_server(
        host="0.0.0.0",
        port=settings.server_imap_port,
        user=settings.imap_user,
        password=settings.imap_password,
    )


if __name__ == "__main__":
    asyncio.run(main())
