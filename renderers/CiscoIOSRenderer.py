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
                cmds.append(f"hostname {op.args.get('hostname')}")
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
