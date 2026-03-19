from __future__ import annotations

import asyncio

from beacon_client.config import Settings
from beacon_client.server.tcp_server import run_tcp_server


async def main() -> None:
    settings = Settings()
    await run_tcp_server(host="0.0.0.0", port=settings.server_tcp_port)


if __name__ == "__main__":
    asyncio.run(main())
