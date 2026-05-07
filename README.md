# Beacon Client

Multi-channel beacon client and demo servers for controlled local environments.  

This projects supports multi-protocl beaconing with HTTP/1.1, HTTP/2, HTTP/3, TCP, DNS, DoH, ICMP, FTP, IMAP, SMB, LDAP, MAPI.

> [!IMPORTANT]
> This project is designed for local educational use only. Do not deploy on public networks.

## Installation  

You can easilly setup both server and client with docker cmpose:  

```bash
docker compose up -d
```  

Use tcpdump to capture packets and analyze traffic/behaivour:  

```bash
sudo tcpdump -i lo0 -s 0 -w beacon_new.pcap
```

### Run other scripts
Kill the client from compose:  

```bash
docker compose run --rm beacon-client
```

Then, you can execute scripts locally:

```bash
PYTHONPATH=./src python scripts/run_client.py <params>
```

Or run the client inside Docker:  

```bash
docker compose exec beacon-client python scripts/run_client.py <params>
```  

Run the capture helper inside the Docker network (recommended for FTP):  

```bash
docker compose exec beacon-client python scripts/capture_all_channels.py --delay 0.67
```


> [!TIP]
> Running the capture script inside Docker avoids host-side FTP data port issues.

## Configuration

Settings are defined in [`src/beacon_client/config.py`](src/beacon_client/config.py) and loaded from environment variables.

Common variables:

| Variable | Default | Notes |
| --- | --- | --- |
| CLIENT_ID | beacon-client-01 | Client identifier in each beacon |
| BEACON_INTERVAL_HOURS | 1.0 | Interval between beacons |
| ENABLED_CHANNELS | HTTP,TCP,HTTP2,HTTP3,DNS,ICMP,FTP | Comma-separated list |
| SERVER_HTTP_BASE | http://localhost:8000 | API server base URL |
| SERVER_WS_BASE | ws://localhost:8000 | WebSocket base URL |
| SERVER_FTP_HOST | localhost | FTP server host |
| SERVER_FTP_PORT | 2121 | FTP server port |

> [!NOTE]
> Environment variable names are uppercase versions of the fields in [`src/beacon_client/config.py`](src/beacon_client/config.py).


## Considerations

> [!IMPORTANT]
> ICMP requires raw sockets. On Linux, you need privileges or `CAP_NET_RAW` (Docker Compose already sets this).

> [!WARNING]
> If FTP fails when running the capture script on the host, it is usually because passive data ports are not exposed. Run the script inside Docker or expose a passive port range.

> [!NOTE]
> HTTP/2, HTTP/3, and DoH use self-signed certificates in the demo setup.