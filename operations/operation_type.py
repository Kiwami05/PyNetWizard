from enum import Enum, auto


class OperationType(Enum):
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

    # Routing
    ADD_STATIC_ROUTE = auto()
    DEL_STATIC_ROUTE = auto()
    ENABLE_RIP = auto()
    DISABLE_RIP = auto()
    ADD_RIP_NETWORK = auto()
    DEL_RIP_NETWORK = auto()
    ADD_RIP_INTERFACE = auto()
    DEL_RIP_INTERFACE = auto()
    ADD_OSPF_NETWORK = auto()
    DEL_OSPF_NETWORK = auto()
    ADD_OSPF_INTERFACE = auto()
    DEL_OSPF_INTERFACE = auto()

    # ACL
    ADD_ACL_RULE = auto()
    DEL_ACL_RULE = auto()
    BIND_ACL = auto()
    UNBIND_ACL = auto()

    # Juniper SRX
    ADD_SRX_POLICY = auto()
    DEL_SRX_POLICY = auto()
