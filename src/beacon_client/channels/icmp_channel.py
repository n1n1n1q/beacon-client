from __future__ import annotations

import asyncio
import json
import random
import socket
import time

from beacon_client.channels.base import BeaconChannel
from beacon_client.icmp_utils import ICMP_ECHO_REPLY, build_echo_request, parse_icmp_packet
from beacon_client.models.messages import BeaconMessage, BeaconResponse, ChannelName

_MAX_PAYLOAD_SIZE = 1400


class IcmpChannel(BeaconChannel):
	def __init__(self, host: str, timeout: float = 5.0) -> None:
		self._host = host
		self._timeout = timeout

	@property
	def name(self) -> ChannelName:
		return ChannelName.ICMP

	async def send_alive(self, payload: BeaconMessage) -> BeaconResponse:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor(None, self._send_blocking, payload)

	def _send_blocking(self, payload: BeaconMessage) -> BeaconResponse:
		body = json.dumps(payload.model_dump(mode="json")).encode("utf-8")
		if len(body) > _MAX_PAYLOAD_SIZE:
			return BeaconResponse(status_code=413, detail="ICMP payload too large")

		try:
			dest_ip = socket.gethostbyname(self._host)
		except OSError as exc:
			return BeaconResponse(status_code=500, detail=f"Failed to resolve {self._host}: {exc}")

		try:
			sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
		except PermissionError as exc:
			return BeaconResponse(
				status_code=500,
				detail=f"ICMP raw socket requires elevated privileges: {exc}",
			)
		except OSError as exc:
			return BeaconResponse(status_code=500, detail=f"Failed to open ICMP socket: {exc}")

		identifier = random.randint(0, 0xFFFF)
		sequence = int(time.time() * 1000) & 0xFFFF
		packet = build_echo_request(identifier, sequence, body)

		try:
			sock.settimeout(self._timeout)
			sock.sendto(packet, (dest_ip, 0))

			deadline = time.time() + self._timeout
			while True:
				remaining = deadline - time.time()
				if remaining <= 0:
					return BeaconResponse(status_code=504, detail="ICMP reply timed out")
				sock.settimeout(remaining)

				try:
					data, _addr = sock.recvfrom(65535)
				except socket.timeout:
					return BeaconResponse(status_code=504, detail="ICMP reply timed out")

				parsed = parse_icmp_packet(data)
				if not parsed:
					continue

				icmp_type, _icmp_code, resp_id, resp_seq, resp_payload = parsed
				if icmp_type != ICMP_ECHO_REPLY:
					continue
				if resp_id != identifier or resp_seq != sequence:
					continue

				return _parse_response_payload(resp_payload)
		finally:
			sock.close()


class Icmpv6Channel(IcmpChannel):
	"""
	Backward compatible name for the ICMP channel.
	"""


def _parse_response_payload(payload: bytes) -> BeaconResponse:
	try:
		obj = json.loads(payload.decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError):
		return BeaconResponse(status_code=500, detail="ICMP reply did not include JSON payload")

	if not isinstance(obj, dict):
		return BeaconResponse(status_code=500, detail="ICMP reply payload was not a JSON object")

	status = obj.get("status_code")
	if status is None:
		return BeaconResponse(
			status_code=201,
			detail="ICMP echo reply received",
			accepted_channel=ChannelName.ICMP,
		)

	try:
		status_code = int(status)
	except (TypeError, ValueError):
		status_code = 500

	accepted_channel = obj.get("accepted_channel")
	try:
		accepted_enum = ChannelName(accepted_channel) if accepted_channel else None
	except ValueError:
		accepted_enum = None

	return BeaconResponse(
		status_code=status_code,
		detail=obj.get("detail", "No detail"),
		websocket_path=obj.get("websocket_path"),
		accepted_channel=accepted_enum,
	)
