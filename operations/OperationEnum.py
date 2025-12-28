from enum import Enum, auto


class OperationEnum(Enum):
    # Global
    SET_HOSTNAME = auto()
    # VLANs
    CREATE_VLAN = auto()
    DELETE_VLAN = auto()
    RENAME_VLAN = auto()
    # Interfaces
    SET_INTERFACE_IP = auto()
    SET_INTERFACE_STATUS = auto()
    SET_INTERFACE_DESCRIPTION = auto()
    CLEAR_INTERFACE_IP = auto()
    # Switch Interfaces
    SET_SWITCHPORT_MODE_ACCESS = auto()
    SET_SWITCHPORT_MODE_TRUNK = auto()
    SET_SWITCHPORT_MODE_ROUTED = auto()
    SET_ACCESS_VLAN = auto()
    CLEAR_ACCESS_VLAN = auto()
    SET_TRUNK_ALLOWED_VLANS = auto()
    CLEAR_TRUNK_ALLOWED_VLANS = auto()
