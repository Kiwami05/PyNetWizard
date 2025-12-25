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
        if device.vendor == Vendor.JUNIPER:
            raw = self.cm.send_command(device, "show configuration | display set")
            conf = parse_config(device, raw)

        else:
            # === CISCO ===
            raw_running = self.cm.send_command(device, "show running-config")
            raw_vlan = self.cm.send_command(device, "show vlan")

            conf = parse_config(
                device,
                raw_running=raw_running,
                raw_vlan=raw_vlan,
            )

        return conf

