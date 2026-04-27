from __future__ import annotations

import asyncio

from beacon_client.config import Settings
from beacon_client.server.http2_server import run_http2_server


async def main() -> None:
    settings = Settings()
    await run_http2_server(host="0.0.0.0", port=settings.server_http2_port)


if __name__ == "__main__":
    asyncio.run(main())
