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
                hostname = op.args["hostname"]
                cmds.append(f"set system host-name {hostname}")
            elif op.operation == OperationEnum.CREATE_VLAN:
                vid = op.args["vlan_id"]
                name = op.args.get("name")

                cmds.append(f"set vlans vlan-{vid} vlan-id {vid}")
                if name:
                    cmds.append(f'set vlans vlan-{vid} description "{name}"')

            elif op.operation == OperationEnum.DELETE_VLAN:
                cmds.append(f"delete vlans vlan-{op.args['vlan_id']}")

            elif op.operation == OperationEnum.RENAME_VLAN:
                vid = op.args["vlan_id"]
                name = op.args.get("name")

                if name:
                    cmds.append(f'set vlans vlan-{vid} description "{name}"')
                else:
                    cmds.append(f"delete vlans vlan-{vid} description")

            else:
                raise NotImplementedError(
                    f"{self.__class__.__name__} does not this operation"
                )

        cmds.append("commit")
        cmds.append("exit")
        return cmds
