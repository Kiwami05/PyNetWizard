# services/parsers/__init__.py
from platforms.vendor import Vendor
from services.parsed_config import ParsedConfig
from services.parsers import cisco_ios, juniper_junos


def parse_config(
    device,
    raw_running: str,
    raw_vlan: str | None = None,
    raw_interfaces: str | None = None,
) -> ParsedConfig:
    if device.vendor == Vendor.JUNIPER:
        return juniper_junos.parse(raw_running, raw_interfaces)
    elif device.vendor == Vendor.CISCO:
        return cisco_ios.parse(raw_running, raw_vlan)

    raise NotImplementedError(f"No config parser for vendor: {device.vendor}")
