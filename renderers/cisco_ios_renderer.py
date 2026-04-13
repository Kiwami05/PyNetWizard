from typing import Iterable, List

from operations.operation import Operation

from operations.operation_type import OperationType
from renderers.base import OperationRenderer


class CiscoIOSRenderer(OperationRenderer):
    """
    Renderer operacji dla Cisco IOS / IOS-XE.
    """

    def render(self, operations: Iterable[Operation]) -> List[str]:
        cmds: List[str] = []

        ops = list(operations)
        if not ops:
            return cmds

        # cmds.append("configure terminal")

        for op in ops:
            if op.operation_type == OperationType.SET_HOSTNAME:
                hostname = op.args["hostname"]
                cmds.append(f"hostname {hostname}")
            # === VLANS ===
            elif op.operation_type == OperationType.CREATE_VLAN:
                vid = op.args["vlan_id"]
                name = op.args.get("name")

                cmds.append(f"vlan {vid}")
                if name:
                    cmds.append(f" name {name}")
                cmds.append(" exit")
            elif op.operation_type == OperationType.DELETE_VLAN:
                cmds.append(f"no vlan {op.args['vlan_id']}")
            elif op.operation_type == OperationType.RENAME_VLAN:
                vid = op.args["vlan_id"]
                name = op.args.get("name")

                cmds.append(f"vlan {vid}")
                if name:
                    cmds.append(f" name {name}")
                else:
                    cmds.append(" no name")
                cmds.append(" exit")
            # === INTERFACES ===
            elif op.operation_type == OperationType.SET_INTERFACE_DESCRIPTION:
                iface = op.args["iface"]
                desc = op.args.get("description")

                cmds.append(f"interface {iface}")
                if desc:
                    cmds.append(f" description {desc}")
                else:
                    cmds.append(" no description")
                cmds.append(" exit")

            elif op.operation_type == OperationType.SET_INTERFACE_IP:
                iface = op.args["iface"]
                ip = op.args["ip"]
                mask = op.args["mask"]

                cmds.append(f"interface {iface}")
                cmds.append(f" ip address {ip} {mask}")
                cmds.append(" exit")

            elif op.operation_type == OperationType.CLEAR_INTERFACE_IP:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(" no ip address")
                cmds.append(" exit")

            elif op.operation_type == OperationType.SET_INTERFACE_STATUS:
                iface = op.args["iface"]
                enabled = op.args["enabled"]

                cmds.append(f"interface {iface}")
                cmds.append(" no shutdown" if enabled else " shutdown")
                cmds.append(" exit")
            # === SWITCH INTERFACES ===
            elif op.operation_type == OperationType.SET_SWITCHPORT_MODE_ACCESS:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(" switchport mode access")
                cmds.append(" exit")
            elif op.operation_type == OperationType.SET_SWITCHPORT_MODE_TRUNK:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(" switchport trunk encapsulation dot1q")
                cmds.append(" switchport mode trunk")
                cmds.append(" exit")
            elif op.operation_type == OperationType.SET_SWITCHPORT_MODE_ROUTED:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(" no switchport")
                cmds.append(" exit")
            elif op.operation_type == OperationType.SET_ACCESS_VLAN:
                iface = op.args["iface"]
                vlan = op.args["vlan_id"]

                cmds.append(f"interface {iface}")
                cmds.append(f" switchport access vlan {vlan}")
                cmds.append(" exit")
            elif op.operation_type == OperationType.CLEAR_ACCESS_VLAN:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(" no switchport access vlan")
                cmds.append(" exit")
            elif op.operation_type == OperationType.SET_TRUNK_ALLOWED_VLANS:
                iface = op.args["iface"]
                vlans = ",".join(str(v) for v in op.args["vlans"])

                cmds.append(f"interface {iface}")
                cmds.append(f" switchport trunk allowed vlan {vlans}")
                cmds.append(" exit")
            elif op.operation_type == OperationType.CLEAR_TRUNK_ALLOWED_VLANS:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(" no switchport trunk allowed vlan")
                cmds.append(" exit")
            # === ROUTING ===
            elif op.operation_type == OperationType.ADD_STATIC_ROUTE:
                cmds.append(
                    f"ip route {op.args['dest']} {op.args['mask']} {op.args['nh']}"
                )
            elif op.operation_type == OperationType.DEL_STATIC_ROUTE:
                cmds.append(
                    f"no ip route {op.args['dest']} {op.args['mask']} {op.args['nh']}"
                )
            elif op.operation_type == OperationType.ENABLE_RIP:
                cmds.extend(
                    [
                        "router rip",
                        " version 2",
                        " exit",
                    ]
                )

            elif op.operation_type == OperationType.DISABLE_RIP:
                cmds.append("no router rip")

            elif op.operation_type == OperationType.ADD_RIP_NETWORK:
                cmds.extend(
                    [
                        "router rip",
                        f" network {op.args['network']}",
                        " exit",
                    ]
                )

            elif op.operation_type == OperationType.DEL_RIP_NETWORK:
                cmds.extend(
                    [
                        "router rip",
                        f" no network {op.args['network']}",
                        " exit",
                    ]
                )
            elif op.operation_type == OperationType.ADD_OSPF_NETWORK:
                cmds.extend(
                    [
                        f"router ospf {op.args['process']}",
                        f" network {op.args['network']} {op.args['wildcard']} area {op.args['area']}",
                        " exit",
                    ]
                )

            elif op.operation_type == OperationType.DEL_OSPF_NETWORK:
                cmds.extend(
                    [
                        f"router ospf {op.args['process']}",
                        f" no network {op.args['network']} {op.args['wildcard']} area {op.args['area']}",
                        " exit",
                    ]
                )
            # === ACL ===
            elif op.operation_type == OperationType.ADD_ACL_RULE:
                cmd = (
                    f"access-list {op.args['acl_name']} extended "
                    f"{op.args['action']} "
                    f"{op.args['protocol']} "
                    f"{op.args['src']} "
                    f"{op.args['dest']}"
                )
                if op.args.get("port"):
                    cmd += f" {op.args['port']}"
                cmds.append(cmd)
            elif op.operation_type == OperationType.DEL_ACL_RULE:
                cmd = (
                    f"no access-list {op.args['acl_name']} extended "
                    f"{op.args['action']} "
                    f"{op.args['protocol']} "
                    f"{op.args['src']} "
                    f"{op.args['dest']}"
                )
                if op.args.get("port"):
                    cmd += f" {op.args['port']}"
                cmds.append(cmd)
            elif op.operation_type == OperationType.BIND_ACL:
                cmds.append(
                    f"access-group {op.args['acl_name']} "
                    f"{op.args['direction']} interface {op.args['interface']}"
                )
            elif op.operation_type == OperationType.UNBIND_ACL:
                cmds.append(
                    f"no access-group {op.args['acl_name']} "
                    f"{op.args['direction']} interface {op.args['interface']}"
                )
            else:
                raise NotImplementedError(
                    f"{self.__class__.__name__} does not this operation"
                )

        cmds.append("end")
        return cmds
