# services/config_sync.py
from typing import Protocol
from devices.Device import Device
from services.parsed_config import ParsedConfig
from services.parsers import cisco_ios


class SyncableTab(Protocol):
    def sync_from_config(self, conf: ParsedConfig) -> None: ...


class ConfigSyncService:
    def __init__(self, connection_manager):
        self.cm = connection_manager

    def fetch_and_parse(self, device: Device) -> ParsedConfig:
        # Na razie: Cisco/Juniper → użyj Cisco parsera jako domyślnego
        raw = self.cm.send_command(device, "show running-config")
        # TODO: w przyszłości detekcja po vendorze/banerze i wybór parsera
        conf = cisco_ios.parse(raw)
        conf.vendor = device.vendor.name
        return conf
