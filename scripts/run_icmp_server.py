from __future__ import annotations

import asyncio

from beacon_client.server.icmp_server import run_icmp_server


async def main() -> None:
    await run_icmp_server(host="0.0.0.0")


if __name__ == "__main__":
    asyncio.run(main())
