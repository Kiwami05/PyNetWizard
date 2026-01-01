from typing import Iterable, List

from operations.Operation import Operation

from operations.OperationEnum import OperationEnum
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

        cmds.append("configure terminal")

        for op in ops:
            if op.operation == OperationEnum.SET_HOSTNAME:
                hostname = op.args["hostname"]
                cmds.append(f"hostname {hostname}")
            # === VLANS ===
            elif op.operation == OperationEnum.CREATE_VLAN:
                vid = op.args["vlan_id"]
                name = op.args.get("name")

                cmds.append(f"vlan {vid}")
                if name:
                    cmds.append(f" name {name}")
                cmds.append(" exit")
            elif op.operation == OperationEnum.DELETE_VLAN:
                cmds.append(f"no vlan {op.args['vlan_id']}")
            elif op.operation == OperationEnum.RENAME_VLAN:
                vid = op.args["vlan_id"]
                name = op.args.get("name")

                cmds.append(f"vlan {vid}")
                if name:
                    cmds.append(f" name {name}")
                else:
                    cmds.append(" no name")
                cmds.append(" exit")
            # === INTERFACES ===
            elif op.operation == OperationEnum.SET_INTERFACE_DESCRIPTION:
                iface = op.args["iface"]
                desc = op.args.get("description")

                cmds.append(f"interface {iface}")
                if desc:
                    cmds.append(f" description {desc}")
                else:
                    cmds.append(" no description")
                cmds.append(" exit")

            elif op.operation == OperationEnum.SET_INTERFACE_IP:
                iface = op.args["iface"]
                ip = op.args["ip"]
                mask = op.args["mask"]

                cmds.append(f"interface {iface}")
                cmds.append(f" ip address {ip} {mask}")
                cmds.append(" exit")

            elif op.operation == OperationEnum.CLEAR_INTERFACE_IP:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(" no ip address")
                cmds.append(" exit")

            elif op.operation == OperationEnum.SET_INTERFACE_STATUS:
                iface = op.args["iface"]
                enabled = op.args["enabled"]

                cmds.append(f"interface {iface}")
                cmds.append(" no shutdown" if enabled else " shutdown")
                cmds.append(" exit")
            # === SWITCH INTERFACES ===
            elif op.operation == OperationEnum.SET_SWITCHPORT_MODE_ACCESS:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(" switchport mode access")
                cmds.append(" exit")
            elif op.operation == OperationEnum.SET_SWITCHPORT_MODE_TRUNK:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(" switchport trunk encapsulation dot1q")
                cmds.append(" switchport mode trunk")
                cmds.append(" exit")
            elif op.operation == OperationEnum.SET_SWITCHPORT_MODE_ROUTED:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(" no switchport")
                cmds.append(" exit")
            elif op.operation == OperationEnum.SET_ACCESS_VLAN:
                iface = op.args["iface"]
                vlan = op.args["vlan_id"]

                cmds.append(f"interface {iface}")
                cmds.append(f" switchport access vlan {vlan}")
                cmds.append(" exit")
            elif op.operation == OperationEnum.CLEAR_ACCESS_VLAN:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(f" no switchport access vlan")
                cmds.append(" exit")
            elif op.operation == OperationEnum.SET_TRUNK_ALLOWED_VLANS:
                iface = op.args["iface"]
                vlans = ",".join(str(v) for v in op.args["vlans"])

                cmds.append(f"interface {iface}")
                cmds.append(f" switchport trunk allowed vlan {vlans}")
                cmds.append(" exit")
            elif op.operation == OperationEnum.CLEAR_TRUNK_ALLOWED_VLANS:
                iface = op.args["iface"]

                cmds.append(f"interface {iface}")
                cmds.append(f" no switchport trunk allowed vlan")
                cmds.append(" exit")
            # === ROUTING ===
            elif op.operation == OperationEnum.ADD_STATIC_ROUTE:
                cmds.append(
                    f"ip route {op.args['dest']} {op.args['mask']} {op.args['nh']}"
                )
            elif op.operation == OperationEnum.DEL_STATIC_ROUTE:
                cmds.append(
                    f"no ip route {op.args['dest']} {op.args['mask']} {op.args['nh']}"
                )
            elif op.operation == OperationEnum.ENABLE_RIP:
                cmds.extend([
                    "router rip",
                    " version 2",
                    " exit",
                ])

            elif op.operation == OperationEnum.DISABLE_RIP:
                cmds.append("no router rip")

            elif op.operation == OperationEnum.ADD_RIP_NETWORK:
                cmds.extend([
                    "router rip",
                    f" network {op.args['network']}",
                    " exit",
                ])

            elif op.operation == OperationEnum.DEL_RIP_NETWORK:
                cmds.extend([
                    "router rip",
                    f" no network {op.args['network']}",
                    " exit",
                ])
            elif op.operation == OperationEnum.ADD_OSPF_NETWORK:
                cmds.extend([
                    f"router ospf {op.args['process']}",
                    f" network {op.args['network']} {op.args['wildcard']} area {op.args['area']}",
                    " exit",
                ])

            elif op.operation == OperationEnum.DEL_OSPF_NETWORK:
                cmds.extend([
                    f"router ospf {op.args['process']}",
                    f" no network {op.args['network']} {op.args['wildcard']} area {op.args['area']}",
                    " exit",
                ])

            else:
                raise NotImplementedError(
                    f"{self.__class__.__name__} does not this operation"
                )

        cmds.append("end")
        return cmds
