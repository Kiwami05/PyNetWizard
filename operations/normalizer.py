from collections.abc import Callable

from operations.operation import Operation
from operations.operation_type import OperationType


_LAST_WRITE_GROUPS: tuple[set[OperationType], ...] = (
    {OperationType.SET_HOSTNAME},
    {OperationType.SET_INTERFACE_DESCRIPTION},
    {OperationType.SET_INTERFACE_STATUS},
    {OperationType.SET_INTERFACE_IP, OperationType.CLEAR_INTERFACE_IP},
    {
        OperationType.SET_SWITCHPORT_MODE_ACCESS,
        OperationType.SET_SWITCHPORT_MODE_TRUNK,
        OperationType.SET_SWITCHPORT_MODE_ROUTED,
    },
    {
        OperationType.SET_ACCESS_VLAN,
        OperationType.CLEAR_ACCESS_VLAN,
        OperationType.SET_TRUNK_ALLOWED_VLANS,
        OperationType.CLEAR_TRUNK_ALLOWED_VLANS,
    },
    {OperationType.RENAME_VLAN},
    {OperationType.ENABLE_RIP, OperationType.DISABLE_RIP},
)

_TOGGLE_PAIRS: dict[OperationType, OperationType] = {
    OperationType.CREATE_VLAN: OperationType.DELETE_VLAN,
    OperationType.DELETE_VLAN: OperationType.CREATE_VLAN,
    OperationType.ADD_STATIC_ROUTE: OperationType.DEL_STATIC_ROUTE,
    OperationType.DEL_STATIC_ROUTE: OperationType.ADD_STATIC_ROUTE,
    OperationType.ADD_RIP_NETWORK: OperationType.DEL_RIP_NETWORK,
    OperationType.DEL_RIP_NETWORK: OperationType.ADD_RIP_NETWORK,
    OperationType.ADD_RIP_INTERFACE: OperationType.DEL_RIP_INTERFACE,
    OperationType.DEL_RIP_INTERFACE: OperationType.ADD_RIP_INTERFACE,
    OperationType.ADD_OSPF_NETWORK: OperationType.DEL_OSPF_NETWORK,
    OperationType.DEL_OSPF_NETWORK: OperationType.ADD_OSPF_NETWORK,
    OperationType.ADD_OSPF_INTERFACE: OperationType.DEL_OSPF_INTERFACE,
    OperationType.DEL_OSPF_INTERFACE: OperationType.ADD_OSPF_INTERFACE,
    OperationType.ADD_SRX_POLICY: OperationType.DEL_SRX_POLICY,
    OperationType.DEL_SRX_POLICY: OperationType.ADD_SRX_POLICY,
    OperationType.BIND_ACL: OperationType.UNBIND_ACL,
    OperationType.UNBIND_ACL: OperationType.BIND_ACL,
}


def normalize_operations(operations: list[Operation]) -> list[Operation]:
    normalized: list[Operation] = []

    for op in operations:
        group = _last_write_group_for(op.operation_type)
        if group is not None:
            key = _operation_key(op)
            normalized = [
                existing
                for existing in normalized
                if not (
                    existing.operation_type in group
                    and _operation_key(existing) == key
                )
            ]
            normalized.append(op)
            continue

        opposite = _TOGGLE_PAIRS.get(op.operation_type)
        if opposite is not None:
            key = _operation_key(op)
            removed_opposite = False
            kept: list[Operation] = []
            for existing in normalized:
                if existing.operation_type == opposite and _operation_key(existing) == key:
                    removed_opposite = True
                    continue
                if existing.operation_type == op.operation_type and _operation_key(existing) == key:
                    continue
                kept.append(existing)
            normalized = kept
            if not removed_opposite:
                normalized.append(op)
            continue

        normalized.append(op)

    return normalized


def _last_write_group_for(op_type: OperationType) -> set[OperationType] | None:
    for group in _LAST_WRITE_GROUPS:
        if op_type in group:
            return group
    return None


def _operation_key(op: Operation):
    key_fn = _KEY_BUILDERS.get(op.operation_type)
    if key_fn is not None:
        return key_fn(op)
    return (op.operation_type, tuple(sorted(op.args.items())))


def _key_from_fields(*fields: str) -> Callable[[Operation], tuple]:
    def build(op: Operation) -> tuple:
        return tuple(op.args.get(field) for field in fields)

    return build


_KEY_BUILDERS: dict[OperationType, Callable[[Operation], tuple]] = {
    OperationType.SET_HOSTNAME: lambda _op: ("hostname",),
    OperationType.SET_INTERFACE_DESCRIPTION: _key_from_fields("iface"),
    OperationType.SET_INTERFACE_STATUS: _key_from_fields("iface"),
    OperationType.SET_INTERFACE_IP: _key_from_fields("iface"),
    OperationType.CLEAR_INTERFACE_IP: _key_from_fields("iface"),
    OperationType.SET_SWITCHPORT_MODE_ACCESS: _key_from_fields("iface"),
    OperationType.SET_SWITCHPORT_MODE_TRUNK: _key_from_fields("iface"),
    OperationType.SET_SWITCHPORT_MODE_ROUTED: _key_from_fields("iface"),
    OperationType.SET_ACCESS_VLAN: _key_from_fields("iface"),
    OperationType.CLEAR_ACCESS_VLAN: _key_from_fields("iface"),
    OperationType.SET_TRUNK_ALLOWED_VLANS: _key_from_fields("iface"),
    OperationType.CLEAR_TRUNK_ALLOWED_VLANS: _key_from_fields("iface"),
    OperationType.CREATE_VLAN: _key_from_fields("vlan_id"),
    OperationType.DELETE_VLAN: _key_from_fields("vlan_id"),
    OperationType.RENAME_VLAN: _key_from_fields("vlan_id"),
    OperationType.ADD_STATIC_ROUTE: _key_from_fields("dest", "mask", "nh"),
    OperationType.DEL_STATIC_ROUTE: _key_from_fields("dest", "mask", "nh"),
    OperationType.ENABLE_RIP: lambda _op: ("rip",),
    OperationType.DISABLE_RIP: lambda _op: ("rip",),
    OperationType.ADD_RIP_NETWORK: _key_from_fields("network"),
    OperationType.DEL_RIP_NETWORK: _key_from_fields("network"),
    OperationType.ADD_RIP_INTERFACE: _key_from_fields("group", "interface"),
    OperationType.DEL_RIP_INTERFACE: _key_from_fields("group", "interface"),
    OperationType.ADD_OSPF_NETWORK: _key_from_fields(
        "process", "network", "wildcard", "area"
    ),
    OperationType.DEL_OSPF_NETWORK: _key_from_fields(
        "process", "network", "wildcard", "area"
    ),
    OperationType.ADD_OSPF_INTERFACE: _key_from_fields("area", "interface"),
    OperationType.DEL_OSPF_INTERFACE: _key_from_fields("area", "interface"),
    OperationType.ADD_SRX_POLICY: _key_from_fields("from_zone", "to_zone", "name"),
    OperationType.DEL_SRX_POLICY: _key_from_fields("from_zone", "to_zone", "name"),
    OperationType.BIND_ACL: _key_from_fields("iface", "direction"),
    OperationType.UNBIND_ACL: _key_from_fields("iface", "direction"),
}
