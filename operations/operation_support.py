from devices.Vendor import Vendor
from devices.DeviceType import DeviceType
from devices.platform_capabilities import (
    capabilities_for_device,
    capabilities_for_platform,
)
from operations.Operation import Operation
from operations.OperationEnum import OperationEnum


_ALL_OPERATIONS = set(OperationEnum)

_OPERATION_LABELS = {
    OperationEnum.SET_HOSTNAME: "zmiana nazwy hosta",
    OperationEnum.CREATE_VLAN: "utworzenie VLAN",
    OperationEnum.DELETE_VLAN: "usunięcie VLAN",
    OperationEnum.RENAME_VLAN: "zmiana opisu VLAN",
    OperationEnum.SET_INTERFACE_IP: "ustawienie IP interfejsu",
    OperationEnum.CLEAR_INTERFACE_IP: "usunięcie IP interfejsu",
    OperationEnum.SET_INTERFACE_STATUS: "zmiana statusu interfejsu",
    OperationEnum.SET_INTERFACE_DESCRIPTION: "zmiana opisu interfejsu",
    OperationEnum.SET_SWITCHPORT_MODE_ACCESS: "tryb access portu switcha",
    OperationEnum.SET_SWITCHPORT_MODE_TRUNK: "tryb trunk portu switcha",
    OperationEnum.SET_SWITCHPORT_MODE_ROUTED: "tryb routed portu switcha",
    OperationEnum.SET_ACCESS_VLAN: "przypisanie access VLAN",
    OperationEnum.CLEAR_ACCESS_VLAN: "usunięcie access VLAN",
    OperationEnum.SET_TRUNK_ALLOWED_VLANS: "lista VLAN trunk",
    OperationEnum.CLEAR_TRUNK_ALLOWED_VLANS: "usunięcie listy VLAN trunk",
    OperationEnum.ADD_STATIC_ROUTE: "dodanie trasy statycznej",
    OperationEnum.DEL_STATIC_ROUTE: "usunięcie trasy statycznej",
    OperationEnum.ENABLE_RIP: "włączenie RIP",
    OperationEnum.DISABLE_RIP: "wyłączenie RIP",
    OperationEnum.ADD_RIP_NETWORK: "dodanie sieci RIP",
    OperationEnum.DEL_RIP_NETWORK: "usunięcie sieci RIP",
    OperationEnum.ADD_RIP_INTERFACE: "dodanie interfejsu RIP",
    OperationEnum.DEL_RIP_INTERFACE: "usunięcie interfejsu RIP",
    OperationEnum.ADD_OSPF_NETWORK: "dodanie sieci OSPF",
    OperationEnum.DEL_OSPF_NETWORK: "usunięcie sieci OSPF",
    OperationEnum.ADD_OSPF_INTERFACE: "dodanie interfejsu OSPF",
    OperationEnum.DEL_OSPF_INTERFACE: "usunięcie interfejsu OSPF",
    OperationEnum.ADD_ACL_RULE: "dodanie reguły ACL",
    OperationEnum.DEL_ACL_RULE: "usunięcie reguły ACL",
    OperationEnum.BIND_ACL: "podpięcie ACL do interfejsu",
    OperationEnum.UNBIND_ACL: "odpięcie ACL od interfejsu",
    OperationEnum.ADD_SRX_POLICY: "dodanie polityki SRX",
    OperationEnum.DEL_SRX_POLICY: "usunięcie polityki SRX",
}


class UnsupportedOperationsError(ValueError):
    def __init__(self, vendor: Vendor, operations: list[OperationEnum]):
        labels = [operation_label(op) for op in operations]
        message = (
            f"Te operacje nie są jeszcze obsługiwane dla {vendor.name.title()}: "
            + ", ".join(labels)
            + "."
        )
        super().__init__(message)
        self.vendor = vendor
        self.operations = operations


def supported_operations(vendor: Vendor) -> set[OperationEnum]:
    """Compatibility fallback for older call sites that only know vendor."""
    if vendor == Vendor.CISCO:
        return set(_ALL_OPERATIONS)
    supported: set[OperationEnum] = set()
    for device_type in DeviceType:
        supported.update(capabilities_for_platform(vendor, device_type).operations)
    return supported


def supported_operations_for_device(device) -> set[OperationEnum]:
    return set(capabilities_for_device(device).operations)


def unsupported_operations(
    vendor: Vendor, operations: list[Operation]
) -> list[OperationEnum]:
    supported = supported_operations(vendor)
    unsupported: list[OperationEnum] = []
    for op in operations:
        if op.operation not in supported and op.operation not in unsupported:
            unsupported.append(op.operation)
    return unsupported


def validate_operations_supported(vendor: Vendor, operations: list[Operation]) -> None:
    unsupported = unsupported_operations(vendor, operations)
    if unsupported:
        raise UnsupportedOperationsError(vendor, unsupported)


def validate_operations_supported_for_device(
    device, operations: list[Operation]
) -> None:
    supported = supported_operations_for_device(device)
    unsupported: list[OperationEnum] = []
    for op in operations:
        if op.operation not in supported and op.operation not in unsupported:
            unsupported.append(op.operation)
    if unsupported:
        raise UnsupportedOperationsError(device.vendor, unsupported)


def operation_label(operation: OperationEnum) -> str:
    return _OPERATION_LABELS.get(operation, operation.name)
