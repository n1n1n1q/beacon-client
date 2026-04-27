from __future__ import annotations

import asyncio
from pathlib import Path

import aioftp


async def run_ftp_server(
    host: str = "0.0.0.0",
    port: int = 2121,
    user: str = "beacon",
    password: str = "beacon",
    home_dir: str = "/tmp/beacon_ftp",
) -> None:
    home_path = Path(home_dir)
    upload_dir = home_path / "upload"
    upload_dir.mkdir(parents=True, exist_ok=True)

    server = aioftp.Server(
        users=[
            aioftp.User(
                login=user,
                password=password,
                home_path=str(home_path),
                permissions=[
                    aioftp.Permission(str(home_path), readable=True, writable=True),
                ],
            ),
        ],
    )

    await server.start(host=host, port=port)
    print(f"[FTP] Listening on {host}:{port} (user={user}, home={home_path})")

    try:
        await asyncio.Event().wait()
    finally:
        try:
            await server.close()
        except AttributeError:
            pass
