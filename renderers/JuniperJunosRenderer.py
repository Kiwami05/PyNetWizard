from typing import Iterable, List

from operations.Operation import Operation
from operations.OperationEnum import OperationEnum
from renderers.base import OperationRenderer


class JuniperJunosRenderer(OperationRenderer):
    """
    Renderer operacji dla Juniper Junos.
    """

    def render(self, operations: Iterable[Operation]) -> List[str]:
        cmds: List[str] = []

        ops = list(operations)
        if not ops:
            return cmds

        cmds.append("configure")

        for op in ops:
            if op.operation == OperationEnum.SET_HOSTNAME:
                cmds.append(f"set system host-name {op.args.get('hostname')}")
            else:
                raise NotImplementedError(
                    f"{self.__class__.__name__} does not this operation"
                )
            # # ================= VLAN =================
            #
            # elif isinstance(op, CreateVlan):
            #     cmds.append(f"set vlans vlan-{op.vlan_id} vlan-id {op.vlan_id}")
            #     if op.name:
            #         cmds.append(f"set vlans vlan-{op.vlan_id} description \"{op.name}\"")
            #
            # elif isinstance(op, DeleteVlan):
            #     cmds.append(f"delete vlans vlan-{op.vlan_id}")
            #
            # elif isinstance(op, RenameVlan):
            #     if op.name:
            #         cmds.append(
            #             f"set vlans vlan-{op.vlan_id} description \"{op.name}\""
            #         )
            #     else:
            #         cmds.append(
            #             f"delete vlans vlan-{op.vlan_id} description"
            #         )

        cmds.append("commit")
        cmds.append("exit")
        return cmds
