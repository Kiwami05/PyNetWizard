from .operation_type import OperationType


class Operation:
    def __init__(self, operation: OperationType, **kwargs):
        self.operation = operation
        self.args = kwargs
