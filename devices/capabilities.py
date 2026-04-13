from dataclasses import dataclass

from devices.DeviceType import DeviceType
from devices.Vendor import Vendor
from operations.OperationEnum import OperationEnum


@dataclass(frozen=True)
class PlatformCapabilities:
    vendor: Vendor
    device_type: DeviceType
    tab_keys: tuple[str, ...]
    operations: frozenset[OperationEnum]
    features: frozenset[str]


GLOBAL_OPS = frozenset({OperationEnum.SET_HOSTNAME})

INTERFACE_OPS = frozenset(
    {
        OperationEnum.SET_INTERFACE_IP,
        OperationEnum.CLEAR_INTERFACE_IP,
        OperationEnum.SET_INTERFACE_STATUS,
        OperationEnum.SET_INTERFACE_DESCRIPTION,
    }
)

VLAN_OPS = frozenset(
    {
        OperationEnum.CREATE_VLAN,
        OperationEnum.DELETE_VLAN,
        OperationEnum.RENAME_VLAN,
    }
)

SWITCHPORT_OPS = frozenset(
    {
        OperationEnum.SET_SWITCHPORT_MODE_ACCESS,
        OperationEnum.SET_SWITCHPORT_MODE_TRUNK,
        OperationEnum.SET_SWITCHPORT_MODE_ROUTED,
        OperationEnum.SET_ACCESS_VLAN,
        OperationEnum.CLEAR_ACCESS_VLAN,
        OperationEnum.SET_TRUNK_ALLOWED_VLANS,
        OperationEnum.CLEAR_TRUNK_ALLOWED_VLANS,
    }
)

STATIC_ROUTING_OPS = frozenset(
    {
        OperationEnum.ADD_STATIC_ROUTE,
        OperationEnum.DEL_STATIC_ROUTE,
    }
)

CISCO_RIP_OPS = frozenset(
    {
        OperationEnum.ENABLE_RIP,
        OperationEnum.DISABLE_RIP,
        OperationEnum.ADD_RIP_NETWORK,
        OperationEnum.DEL_RIP_NETWORK,
    }
)

JUNIPER_RIP_OPS = frozenset(
    {
        OperationEnum.ADD_RIP_INTERFACE,
        OperationEnum.DEL_RIP_INTERFACE,
    }
)

CISCO_OSPF_OPS = frozenset(
    {
        OperationEnum.ADD_OSPF_NETWORK,
        OperationEnum.DEL_OSPF_NETWORK,
    }
)

JUNIPER_OSPF_OPS = frozenset(
    {
        OperationEnum.ADD_OSPF_INTERFACE,
        OperationEnum.DEL_OSPF_INTERFACE,
    }
)

ASA_ACL_OPS = frozenset(
    {
        OperationEnum.ADD_ACL_RULE,
        OperationEnum.DEL_ACL_RULE,
        OperationEnum.BIND_ACL,
        OperationEnum.UNBIND_ACL,
    }
)

SRX_POLICY_OPS = frozenset(
    {
        OperationEnum.ADD_SRX_POLICY,
        OperationEnum.DEL_SRX_POLICY,
    }
)


def _caps(
    vendor: Vendor,
    device_type: DeviceType,
    tab_keys: tuple[str, ...],
    operations: frozenset[OperationEnum],
    features: frozenset[str],
) -> PlatformCapabilities:
    return PlatformCapabilities(
        vendor=vendor,
        device_type=device_type,
        tab_keys=tab_keys,
        operations=operations,
        features=features,
    )


PLATFORM_CAPABILITIES = {
    (Vendor.CISCO, DeviceType.ROUTER): _caps(
        Vendor.CISCO,
        DeviceType.ROUTER,
        ("GLOBAL", "ROUTING", "INTERFACES"),
        GLOBAL_OPS | INTERFACE_OPS | STATIC_ROUTING_OPS | CISCO_RIP_OPS | CISCO_OSPF_OPS,
        frozenset({"global", "interfaces", "static-routing", "rip", "ospf"}),
    ),
    (Vendor.JUNIPER, DeviceType.ROUTER): _caps(
        Vendor.JUNIPER,
        DeviceType.ROUTER,
        ("GLOBAL", "ROUTING", "INTERFACES"),
        GLOBAL_OPS
        | INTERFACE_OPS
        | STATIC_ROUTING_OPS
        | JUNIPER_RIP_OPS
        | JUNIPER_OSPF_OPS,
        frozenset({"global", "interfaces", "static-routing", "rip", "ospf"}),
    ),
    (Vendor.CISCO, DeviceType.SWITCH): _caps(
        Vendor.CISCO,
        DeviceType.SWITCH,
        ("GLOBAL", "VLANs", "SWITCH_INTERFACES"),
        GLOBAL_OPS | INTERFACE_OPS | VLAN_OPS | SWITCHPORT_OPS,
        frozenset({"global", "interfaces", "vlan", "switchport"}),
    ),
    (Vendor.JUNIPER, DeviceType.SWITCH): _caps(
        Vendor.JUNIPER,
        DeviceType.SWITCH,
        ("GLOBAL", "VLANs", "SWITCH_INTERFACES"),
        GLOBAL_OPS | INTERFACE_OPS | VLAN_OPS | SWITCHPORT_OPS,
        frozenset({"global", "interfaces", "vlan", "switchport"}),
    ),
    (Vendor.CISCO, DeviceType.FIREWALL): _caps(
        Vendor.CISCO,
        DeviceType.FIREWALL,
        ("GLOBAL", "INTERFACES", "ACL"),
        GLOBAL_OPS | INTERFACE_OPS | ASA_ACL_OPS,
        frozenset({"global", "interfaces", "asa-acl"}),
    ),
    (Vendor.JUNIPER, DeviceType.FIREWALL): _caps(
        Vendor.JUNIPER,
        DeviceType.FIREWALL,
        ("GLOBAL", "INTERFACES", "SRX_POLICIES"),
        GLOBAL_OPS | INTERFACE_OPS | SRX_POLICY_OPS,
        frozenset({"global", "interfaces", "srx-policies"}),
    ),
}


FALLBACK_CAPABILITIES = _caps(
    Vendor.CISCO,
    DeviceType.ROUTER,
    ("GLOBAL",),
    GLOBAL_OPS,
    frozenset({"global"}),
)


def capabilities_for_device(device) -> PlatformCapabilities:
    return capabilities_for_platform(device.vendor, device.device_type)


def capabilities_for_platform(
    vendor: Vendor, device_type: DeviceType
) -> PlatformCapabilities:
    return PLATFORM_CAPABILITIES.get((vendor, device_type), FALLBACK_CAPABILITIES)
