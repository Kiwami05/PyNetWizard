from devices.Vendor import Vendor
from operations.Operation import Operation
from operations.OperationEnum import OperationEnum


_ALL_OPERATIONS = set(OperationEnum)

_JUNIPER_SUPPORTED = {
    OperationEnum.SET_HOSTNAME,
    OperationEnum.CREATE_VLAN,
    OperationEnum.DELETE_VLAN,
    OperationEnum.RENAME_VLAN,
    OperationEnum.SET_INTERFACE_IP,
    OperationEnum.CLEAR_INTERFACE_IP,
    OperationEnum.SET_INTERFACE_STATUS,
    OperationEnum.SET_INTERFACE_DESCRIPTION,
    OperationEnum.ADD_STATIC_ROUTE,
    OperationEnum.DEL_STATIC_ROUTE,
}

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
    OperationEnum.ADD_OSPF_NETWORK: "dodanie sieci OSPF",
    OperationEnum.DEL_OSPF_NETWORK: "usunięcie sieci OSPF",
    OperationEnum.ADD_ACL_RULE: "dodanie reguły ACL",
    OperationEnum.DEL_ACL_RULE: "usunięcie reguły ACL",
    OperationEnum.BIND_ACL: "podpięcie ACL do interfejsu",
    OperationEnum.UNBIND_ACL: "odpięcie ACL od interfejsu",
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
    if vendor == Vendor.CISCO:
        return set(_ALL_OPERATIONS)
    if vendor == Vendor.JUNIPER:
        return set(_JUNIPER_SUPPORTED)
    return set()


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


def operation_label(operation: OperationEnum) -> str:
    return _OPERATION_LABELS.get(operation, operation.name)
