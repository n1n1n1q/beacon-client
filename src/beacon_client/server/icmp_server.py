from __future__ import annotations

import asyncio
import json
import socket
import threading
from datetime import datetime, timezone

from beacon_client.icmp_utils import ICMP_ECHO_REQUEST, build_echo_reply, parse_icmp_packet
from beacon_client.models.messages import ChannelName

_SOCKET_TIMEOUT = 1.0


def _extract_beacon_payload(payload: bytes) -> dict | None:
	try:
		obj = json.loads(payload.decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError):
		return None
	if not isinstance(obj, dict):
		return None
	return obj


def _build_beacon_response(client_id: str) -> bytes:
	response_obj = {
		"status_code": 201,
		"detail": "Beacon accepted over ICMP",
		"websocket_path": f"/ws/{client_id}",
		"accepted_channel": ChannelName.ICMP.value,
		"server_timestamp": datetime.now(timezone.utc).isoformat(),
	}
	return json.dumps(response_obj).encode("utf-8")


def _run_icmp_loop(host: str, stop_event: threading.Event) -> None:
	try:
		sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
	except PermissionError as exc:
		print(f"[ICMP] Raw socket requires elevated privileges: {exc}")
		return
	except OSError as exc:
		print(f"[ICMP] Failed to open socket: {exc}")
		return

	try:
		sock.bind((host, 0))
		sock.settimeout(_SOCKET_TIMEOUT)
		print(f"[ICMP] Listening on {host} (raw socket)")

		while not stop_event.is_set():
			try:
				data, addr = sock.recvfrom(65535)
			except socket.timeout:
				continue
			except OSError as exc:
				print(f"[ICMP] Receive error: {exc}")
				continue

			parsed = parse_icmp_packet(data)
			if not parsed:
				continue

			icmp_type, icmp_code, identifier, sequence, payload = parsed
			if icmp_type != ICMP_ECHO_REQUEST or icmp_code != 0:
				continue

			request_obj = _extract_beacon_payload(payload)
			if request_obj and request_obj.get("client_id"):
				client_id = str(request_obj.get("client_id"))
				response_payload = _build_beacon_response(client_id)
			else:
				client_id = "unknown"
				response_payload = payload

			response_packet = build_echo_reply(identifier, sequence, response_payload)

			try:
				sock.sendto(response_packet, (addr[0], 0))
			except OSError as exc:
				print(f"[ICMP] Failed to send reply to {addr[0]}: {exc}")
				continue

			print(f"[ICMP] Echo request from {addr[0]} client_id={client_id}")
	finally:
		try:
			sock.close()
		except Exception:
			pass


async def run_icmp_server(host: str = "0.0.0.0") -> None:
	loop = asyncio.get_running_loop()
	stop_event = threading.Event()
	server_future = loop.run_in_executor(None, _run_icmp_loop, host, stop_event)

	try:
		await asyncio.Event().wait()
	finally:
		stop_event.set()
		await server_future
