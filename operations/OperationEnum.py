from enum import Enum, auto


class OperationEnum(Enum):
    SET_HOSTNAME = auto()
    CREATE_VLAN = auto()
    DELETE_VLAN = auto()
    RENAME_VLAN = auto()
