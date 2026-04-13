from dataclasses import dataclass, field
from typing import Any

from .operation_type import OperationType


@dataclass
class Operation:
    operation_type: OperationType
    args: dict[str, Any] = field(default_factory=dict)

    def __init__(self, operation_type: OperationType, **kwargs):
        self.operation_type = operation_type
        self.args = kwargs
