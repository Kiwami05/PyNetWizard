from enum import Enum, auto


class OperationEnum(Enum):
    SET_HOSTNAME = auto()
    CREATE_VLAN = auto()
    DELETE_VLAN = auto()
    RENAME_VLAN = auto()
    SET_INTERFACE_IP = auto()
    SET_INTERFACE_STATUS = auto()
    SET_INTERFACE_DESCRIPTION = auto()
    CLEAR_INTERFACE_IP = auto()
