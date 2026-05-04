from __future__ import annotations

import asyncio

from beacon_client.config import Settings
from beacon_client.server.doh_server import run_doh_server


async def main() -> None:
    settings = Settings()
    await run_doh_server(
        host="0.0.0.0",
        port=settings.server_doh_port,
        zone=settings.dns_zone,
    )


if __name__ == "__main__":
    asyncio.run(main())
