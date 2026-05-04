from __future__ import annotations

import asyncio

from beacon_client.config import Settings
from beacon_client.server.ldap_server import run_ldap_server


async def main() -> None:
    settings = Settings()
    await run_ldap_server(
        host="0.0.0.0",
        port=settings.server_ldap_port,
        user=settings.ldap_user,
        password=settings.ldap_password,
        base_dn=settings.ldap_base_dn,
    )


if __name__ == "__main__":
    asyncio.run(main())
