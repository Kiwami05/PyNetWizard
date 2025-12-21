from typing import Iterable, List

from operations.base import Operation
from operations.global_ops import SetHostname
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
            if isinstance(op, SetHostname):
                cmds.append(f"set system host-name {op.hostname}")
            else:
                raise NotImplementedError(
                    f"JuniperJunosRenderer does not support operation {type(op).__name__}"
                )

        cmds.append("commit")
        cmds.append("exit")
        return cmds
