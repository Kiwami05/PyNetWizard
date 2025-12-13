from typing import Protocol
from devices.Device import Device
from services.parsed_config import ParsedConfig
from services.parsers import parse_config
from devices.Vendor import Vendor


class SyncableTab(Protocol):
    def sync_from_config(self, conf: ParsedConfig) -> None: ...


class ConfigSyncService:
    def __init__(self, connection_manager):
        self.cm = connection_manager

    def fetch_and_parse(self, device: Device) -> ParsedConfig:
        # 1 wybór komendy po vendorze
        if device.vendor == Vendor.JUNIPER:
            cmd = "show configuration | display set"
        else:
            # Cisco (IOS / ASA)
            cmd = "show running-config"

        # 2 pobranie raw configu
        raw = self.cm.send_command(device, cmd)

        # 3 vendor-aware parser
        conf = parse_config(device, raw)

        # ParsedConfig ZNA vendora — nie nadpisujemy go stringiem
        return conf
