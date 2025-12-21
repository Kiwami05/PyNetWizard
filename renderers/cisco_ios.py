from typing import Iterable, List

from operations.base import Operation
from operations.global_ops import SetHostname
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

        cmds.append("conf t")

        for op in ops:
            if isinstance(op, SetHostname):
                cmds.append(f"hostname {op.hostname}")
            else:
                raise NotImplementedError(
                    f"CiscoIOSRenderer does not support operation {type(op).__name__}"
                )

        cmds.append("end")
        return cmds
