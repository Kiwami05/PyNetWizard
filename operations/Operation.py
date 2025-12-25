from .OperationEnum import OperationEnum


class Operation:
    def __init__(self, operation: OperationEnum, **kwargs):
        self.operation = operation
        self.args = kwargs
