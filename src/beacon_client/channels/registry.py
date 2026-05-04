from __future__ import annotations

import random

from beacon_client.channels.base import BeaconChannel
from beacon_client.channels.dns_channel import DnsChannel
from beacon_client.channels.ftp_channel import FtpChannel
from beacon_client.channels.http2_channel import Http2Channel
from beacon_client.channels.http3_channel import Http3Channel
from beacon_client.channels.http_channel import HttpChannel
from beacon_client.channels.icmp_channel import IcmpChannel
from beacon_client.channels.imap_channel import ImapChannel
from beacon_client.channels.ldap_channel import LdapChannel
from beacon_client.channels.smb_channel import SmbChannel
from beacon_client.channels.stub_channel import StubChannel
from beacon_client.channels.tcp_channel import TcpChannel
from beacon_client.channels.doh_channel import DoHChannel
from beacon_client.config import Settings
from beacon_client.models.messages import ChannelName


class ChannelRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._channels: dict[ChannelName, BeaconChannel] = {
            ChannelName.HTTP: HttpChannel(base_url=settings.server_http_base),
            ChannelName.TCP: TcpChannel(host=settings.server_tcp_host, port=settings.server_tcp_port),
            ChannelName.HTTP2: Http2Channel(host=settings.server_http2_host, port=settings.server_http2_port),
            ChannelName.HTTP3: Http3Channel(host=settings.server_http3_host, port=settings.server_http3_port),
            ChannelName.DNS: DnsChannel(
                host=settings.server_dns_host,
                port=settings.server_dns_port,
                zone=settings.dns_zone,
            ),
            ChannelName.ICMP: IcmpChannel(host=settings.server_icmp_host),
            ChannelName.FTP: FtpChannel(
                host=settings.server_ftp_host,
                port=settings.server_ftp_port,
                user=settings.ftp_user,
                password=settings.ftp_password,
            ),
            ChannelName.IMAP: ImapChannel(
                host=settings.server_imap_host,
                port=settings.server_imap_port,
                user=settings.imap_user,
                password=settings.imap_password,
            ),
            ChannelName.SMB: SmbChannel(
                host=settings.server_smb_host,
                port=settings.server_smb_port,
                user=settings.smb_user,
                password=settings.smb_password,
                share=settings.smb_share,
            ),
            ChannelName.LDAP: LdapChannel(
                host=settings.server_ldap_host,
                port=settings.server_ldap_port,
                user=settings.ldap_user,
                password=settings.ldap_password,
                base_dn=settings.ldap_base_dn,
            ),
            ChannelName.DOH: DoHChannel(
                host=settings.server_doh_host,
                port=settings.server_doh_port,
                zone=settings.dns_zone
            )
        }

        for channel_name in ChannelName:
            self._channels.setdefault(channel_name, StubChannel(channel_name=channel_name))

    def choose_random(self) -> BeaconChannel:
        enabled = [self._channels[name] for name in self._settings.enabled_channel_names]
        return random.choice(enabled)
