from platforms.vendor import Vendor
from platforms.device_type import DeviceType
from platforms.capabilities import (
    capabilities_for_device,
    capabilities_for_platform,
)
from operations.operation import Operation
from operations.operation_type import OperationType


_ALL_OPERATIONS = set(OperationType)

_OPERATION_LABELS = {
    OperationType.SET_HOSTNAME: "zmiana nazwy hosta",
    OperationType.CREATE_VLAN: "utworzenie VLAN",
    OperationType.DELETE_VLAN: "usunięcie VLAN",
    OperationType.RENAME_VLAN: "zmiana opisu VLAN",
    OperationType.SET_INTERFACE_IP: "ustawienie IP interfejsu",
    OperationType.CLEAR_INTERFACE_IP: "usunięcie IP interfejsu",
    OperationType.SET_INTERFACE_STATUS: "zmiana statusu interfejsu",
    OperationType.SET_INTERFACE_DESCRIPTION: "zmiana opisu interfejsu",
    OperationType.SET_SWITCHPORT_MODE_ACCESS: "tryb access portu switcha",
    OperationType.SET_SWITCHPORT_MODE_TRUNK: "tryb trunk portu switcha",
    OperationType.SET_SWITCHPORT_MODE_ROUTED: "tryb routed portu switcha",
    OperationType.SET_ACCESS_VLAN: "przypisanie access VLAN",
    OperationType.CLEAR_ACCESS_VLAN: "usunięcie access VLAN",
    OperationType.SET_TRUNK_ALLOWED_VLANS: "lista VLAN trunk",
    OperationType.CLEAR_TRUNK_ALLOWED_VLANS: "usunięcie listy VLAN trunk",
    OperationType.ADD_STATIC_ROUTE: "dodanie trasy statycznej",
    OperationType.DEL_STATIC_ROUTE: "usunięcie trasy statycznej",
    OperationType.ENABLE_RIP: "włączenie RIP",
    OperationType.DISABLE_RIP: "wyłączenie RIP",
    OperationType.ADD_RIP_NETWORK: "dodanie sieci RIP",
    OperationType.DEL_RIP_NETWORK: "usunięcie sieci RIP",
    OperationType.ADD_RIP_INTERFACE: "dodanie interfejsu RIP",
    OperationType.DEL_RIP_INTERFACE: "usunięcie interfejsu RIP",
    OperationType.ADD_OSPF_NETWORK: "dodanie sieci OSPF",
    OperationType.DEL_OSPF_NETWORK: "usunięcie sieci OSPF",
    OperationType.ADD_OSPF_INTERFACE: "dodanie interfejsu OSPF",
    OperationType.DEL_OSPF_INTERFACE: "usunięcie interfejsu OSPF",
    OperationType.ADD_ACL_RULE: "dodanie reguły ACL",
    OperationType.DEL_ACL_RULE: "usunięcie reguły ACL",
    OperationType.BIND_ACL: "podpięcie ACL do interfejsu",
    OperationType.UNBIND_ACL: "odpięcie ACL od interfejsu",
    OperationType.ADD_SRX_POLICY: "dodanie polityki SRX",
    OperationType.DEL_SRX_POLICY: "usunięcie polityki SRX",
}


class UnsupportedOperationsError(ValueError):
    def __init__(self, vendor: Vendor, operations: list[OperationType]):
        labels = [operation_label(op) for op in operations]
        message = (
            f"Te operacje nie są jeszcze obsługiwane dla {vendor.name.title()}: "
            + ", ".join(labels)
            + "."
        )
        super().__init__(message)
        self.vendor = vendor
        self.operations = operations


def supported_operations(vendor: Vendor) -> set[OperationType]:
    """Rozwiązanie awaryjne zapewniające zgodność dla starszych wywołań, które znają wyłącznie dostawcę"""
    if vendor == Vendor.CISCO:
        return set(_ALL_OPERATIONS)
    supported: set[OperationType] = set()
    for device_type in DeviceType:
        supported.update(capabilities_for_platform(vendor, device_type).operations)
    return supported


def supported_operations_for_device(device) -> set[OperationType]:
    return set(capabilities_for_device(device).operations)


def unsupported_operations(
    vendor: Vendor, operations: list[Operation]
) -> list[OperationType]:
    supported = supported_operations(vendor)
    unsupported: list[OperationType] = []
    for op in operations:
        if op.operation_type not in supported and op.operation_type not in unsupported:
            unsupported.append(op.operation_type)
    return unsupported


def validate_operations_supported(vendor: Vendor, operations: list[Operation]) -> None:
    unsupported = unsupported_operations(vendor, operations)
    if unsupported:
        raise UnsupportedOperationsError(vendor, unsupported)


def validate_operations_supported_for_device(
    device, operations: list[Operation]
) -> None:
    supported = supported_operations_for_device(device)
    unsupported: list[OperationType] = []
    for op in operations:
        if op.operation_type not in supported and op.operation_type not in unsupported:
            unsupported.append(op.operation_type)
    if unsupported:
        raise UnsupportedOperationsError(device.vendor, unsupported)


def operation_label(operation: OperationType) -> str:
    return _OPERATION_LABELS.get(operation, operation.name)
