# services/parsers/__init__.py
from devices.Vendor import Vendor
from services.parsers import cisco_ios, juniper_junos


def parse_config(device, raw_config: str):
    if device.vendor == Vendor.CISCO:
        return cisco_ios.parse(raw_config)

    if device.vendor == Vendor.JUNIPER:
        return juniper_junos.parse(raw_config)

    raise NotImplementedError(f"No config parser for vendor: {device.vendor}")
