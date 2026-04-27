from __future__ import annotations

import asyncio

from beacon_client.config import Settings
from beacon_client.server.http3_server import run_http3_server


async def main() -> None:
    settings = Settings()
    await run_http3_server(host="0.0.0.0", port=settings.server_http3_port)


if __name__ == "__main__":
    asyncio.run(main())
