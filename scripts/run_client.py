from __future__ import annotations

import asyncio

from beacon_client.client.beacon_runner import BeaconRunner
from beacon_client.config import Settings


async def main() -> None:
    settings = Settings()
    runner = BeaconRunner(settings=settings)
    await runner.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
