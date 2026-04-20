from dataclasses import dataclass

from platforms.device_type import DeviceType
from platforms.vendor import Vendor
from operations.operation_type import OperationType


@dataclass(frozen=True)
class PlatformCapabilities:
    vendor: Vendor
    device_type: DeviceType
    tab_keys: tuple[str, ...]
    operations: frozenset[OperationType]


GLOBAL_OPS = frozenset({OperationType.SET_HOSTNAME})

INTERFACE_OPS = frozenset(
    {
        OperationType.SET_INTERFACE_IP,
        OperationType.CLEAR_INTERFACE_IP,
        OperationType.SET_INTERFACE_STATUS,
        OperationType.SET_INTERFACE_DESCRIPTION,
    }
)

VLAN_OPS = frozenset(
    {
        OperationType.CREATE_VLAN,
        OperationType.DELETE_VLAN,
        OperationType.RENAME_VLAN,
    }
)

SWITCHPORT_OPS = frozenset(
    {
        OperationType.SET_SWITCHPORT_MODE_ACCESS,
        OperationType.SET_SWITCHPORT_MODE_TRUNK,
        OperationType.SET_SWITCHPORT_MODE_ROUTED,
        OperationType.SET_ACCESS_VLAN,
        OperationType.CLEAR_ACCESS_VLAN,
        OperationType.SET_TRUNK_ALLOWED_VLANS,
        OperationType.CLEAR_TRUNK_ALLOWED_VLANS,
    }
)

STATIC_ROUTING_OPS = frozenset(
    {
        OperationType.ADD_STATIC_ROUTE,
        OperationType.DEL_STATIC_ROUTE,
    }
)

CISCO_RIP_OPS = frozenset(
    {
        OperationType.ENABLE_RIP,
        OperationType.DISABLE_RIP,
        OperationType.ADD_RIP_NETWORK,
        OperationType.DEL_RIP_NETWORK,
    }
)

JUNIPER_RIP_OPS = frozenset(
    {
        OperationType.ADD_RIP_INTERFACE,
        OperationType.DEL_RIP_INTERFACE,
    }
)

CISCO_OSPF_OPS = frozenset(
    {
        OperationType.ADD_OSPF_NETWORK,
        OperationType.DEL_OSPF_NETWORK,
    }
)

JUNIPER_OSPF_OPS = frozenset(
    {
        OperationType.ADD_OSPF_INTERFACE,
        OperationType.DEL_OSPF_INTERFACE,
    }
)

ASA_ACL_OPS = frozenset(
    {
        OperationType.ADD_ACL_RULE,
        OperationType.DEL_ACL_RULE,
        OperationType.BIND_ACL,
        OperationType.UNBIND_ACL,
    }
)

SRX_POLICY_OPS = frozenset(
    {
        OperationType.ADD_SRX_POLICY,
        OperationType.DEL_SRX_POLICY,
    }
)


PLATFORM_CAPABILITIES = {
    (Vendor.CISCO, DeviceType.ROUTER): PlatformCapabilities(
        Vendor.CISCO,
        DeviceType.ROUTER,
        ("GLOBAL", "ROUTING", "INTERFACES"),
        GLOBAL_OPS
        | INTERFACE_OPS
        | STATIC_ROUTING_OPS
        | CISCO_RIP_OPS
        | CISCO_OSPF_OPS,
    ),
    (Vendor.JUNIPER, DeviceType.ROUTER): PlatformCapabilities(
        Vendor.JUNIPER,
        DeviceType.ROUTER,
        ("GLOBAL", "ROUTING", "INTERFACES"),
        GLOBAL_OPS
        | INTERFACE_OPS
        | STATIC_ROUTING_OPS
        | JUNIPER_RIP_OPS
        | JUNIPER_OSPF_OPS,
    ),
    (Vendor.CISCO, DeviceType.SWITCH): PlatformCapabilities(
        Vendor.CISCO,
        DeviceType.SWITCH,
        ("GLOBAL", "VLANs", "SWITCH_INTERFACES"),
        GLOBAL_OPS | INTERFACE_OPS | VLAN_OPS | SWITCHPORT_OPS,
    ),
    (Vendor.JUNIPER, DeviceType.SWITCH): PlatformCapabilities(
        Vendor.JUNIPER,
        DeviceType.SWITCH,
        ("GLOBAL", "VLANs", "SWITCH_INTERFACES"),
        GLOBAL_OPS | INTERFACE_OPS | VLAN_OPS | SWITCHPORT_OPS,
    ),
    (Vendor.CISCO, DeviceType.FIREWALL): PlatformCapabilities(
        Vendor.CISCO,
        DeviceType.FIREWALL,
        ("GLOBAL", "INTERFACES", "ACL"),
        GLOBAL_OPS | INTERFACE_OPS | ASA_ACL_OPS,
    ),
    (Vendor.JUNIPER, DeviceType.FIREWALL): PlatformCapabilities(
        Vendor.JUNIPER,
        DeviceType.FIREWALL,
        ("GLOBAL", "INTERFACES", "SRX_POLICIES"),
        GLOBAL_OPS | INTERFACE_OPS | SRX_POLICY_OPS,
    ),
}


FALLBACK_CAPABILITIES = PlatformCapabilities(
    Vendor.CISCO,
    DeviceType.ROUTER,
    ("GLOBAL",),
    GLOBAL_OPS,
)


def capabilities_for_device(device) -> PlatformCapabilities:
    return capabilities_for_platform(device.vendor, device.device_type)


def capabilities_for_platform(
    vendor: Vendor, device_type: DeviceType
) -> PlatformCapabilities:
    return PLATFORM_CAPABILITIES.get((vendor, device_type), FALLBACK_CAPABILITIES)
