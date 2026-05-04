from __future__ import annotations

import asyncio

from beacon_client.config import Settings
from beacon_client.server.smb_server import run_smb_server


async def main() -> None:
    settings = Settings()
    await run_smb_server(
        host="0.0.0.0",
        port=settings.server_smb_port,
        user=settings.smb_user,
        password=settings.smb_password,
        share=settings.smb_share,
    )


if __name__ == "__main__":
    asyncio.run(main())
