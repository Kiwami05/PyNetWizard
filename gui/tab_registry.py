from dataclasses import dataclass

from devices.platform_capabilities import capabilities_for_device


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


def tab_specs_for_device(device) -> list[TabSpec]:
    capabilities = capabilities_for_device(device)
    return [
        TabSpec(key=key, label=TAB_LABELS.get(key, key))
        for key in capabilities.tab_keys
    ]
