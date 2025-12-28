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
            else:
                raise NotImplementedError(
                    f"{self.__class__.__name__} does not this operation"
                )

        cmds.append("end")
        return cmds
