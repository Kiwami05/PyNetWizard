from dataclasses import dataclass

from devices.DeviceType import DeviceType
from devices.Vendor import Vendor


@dataclass(frozen=True)
class TabSpec:
    key: str
    label: str


TAB_LABELS = {
    "GLOBAL": "OGÓLNE",
    "ROUTING": "ROUTING",
    "INTERFACES": "INTERFEJSY",
    "SWITCH_INTERFACES": "INTERFEJSY",
    "VLANs": "VLAN-y",
    "ACL": "ACL",
    "SRX_POLICIES": "POLITYKI SRX",
}


TAB_PROFILES = {
    (Vendor.CISCO, DeviceType.ROUTER): ["GLOBAL", "ROUTING", "INTERFACES"],
    (Vendor.JUNIPER, DeviceType.ROUTER): ["GLOBAL", "ROUTING", "INTERFACES"],
    (Vendor.CISCO, DeviceType.SWITCH): ["GLOBAL", "VLANs", "SWITCH_INTERFACES"],
    (Vendor.JUNIPER, DeviceType.SWITCH): ["GLOBAL", "VLANs", "SWITCH_INTERFACES"],
    (Vendor.CISCO, DeviceType.FIREWALL): ["GLOBAL", "INTERFACES", "ACL"],
    (Vendor.JUNIPER, DeviceType.FIREWALL): [
        "GLOBAL",
        "INTERFACES",
        "SRX_POLICIES",
    ],
}


def tab_specs_for_device(device) -> list[TabSpec]:
    keys = TAB_PROFILES.get((device.vendor, device.device_type), ["GLOBAL"])
    return [TabSpec(key=key, label=TAB_LABELS.get(key, key)) for key in keys]
