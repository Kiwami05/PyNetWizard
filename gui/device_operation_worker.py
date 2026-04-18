from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot


class DeviceOperationWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, work: Callable[[], object]):
        super().__init__()
        self._work = work

    @Slot()
    def run(self):
        try:
            self.finished.emit(self._work())
        except Exception as exc:
            message = str(exc).strip() or type(exc).__name__
            self.error.emit(message)
