from __future__ import annotations

import asyncio
from pathlib import Path

from impacket import ntlm
from impacket.smbserver import SimpleSMBServer


def _add_smb_credential(server: SimpleSMBServer, user: str, password: str) -> None:
    try:
        server.addCredential(user, 0, password)
    except TypeError:
        lmhash = ntlm.compute_lmhash(password)
        nthash = ntlm.compute_nthash(password)
        server.addCredential(user, 0, lmhash, nthash)


async def run_smb_server(
    host: str = "0.0.0.0",
    port: int = 1445,
    user: str = "beacon",
    password: str = "beacon",
    share: str = "BEACON",
    share_dir: str = "/tmp/beacon_smb",
) -> None:
    share_path = Path(share_dir)
    upload_path = share_path / "upload"
    upload_path.mkdir(parents=True, exist_ok=True)

    server = SimpleSMBServer(listenAddress=host, listenPort=port)
    server.addShare(share, str(share_path), "Beacon SMB share")
    server.setSMB2Support(True)
    if user:
        _add_smb_credential(server, user, password)

    print(f"[SMB] Listening on {host}:{port} share={share} path={share_path}")

    loop = asyncio.get_running_loop()
    server_task = loop.run_in_executor(None, server.start)

    try:
        await asyncio.Event().wait()
    finally:
        try:
            server.stop()
        except Exception:
            pass
        try:
            await asyncio.wait_for(server_task, timeout=5.0)
        except Exception:
            pass
