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
            else:
                raise NotImplementedError(
                    f"{self.__class__.__name__} does not this operation"
                )

            # # ================= VLAN =================
            #
            # elif isinstance(op, CreateVlan):
            #     cmds.append(f"vlan {op.vlan_id}")
            #     if op.name:
            #         cmds.append(f" name {op.name}")
            #     cmds.append(" exit")
            #
            # elif isinstance(op, DeleteVlan):
            #     cmds.append(f"no vlan {op.vlan_id}")
            #
            # elif isinstance(op, RenameVlan):
            #     cmds.append(f"vlan {op.vlan_id}")
            #     if op.name:
            #         cmds.append(f" name {op.name}")
            #     else:
            #         cmds.append(" no name")
            #     cmds.append(" exit")

        cmds.append("end")
        return cmds
