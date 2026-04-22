from PySide6.QtWidgets import QWidget

from operations.operation import Operation
from services.parsed_config import ParsedConfig


class BaseConfigTab(QWidget):
    """Wspólny interfejs dla zakładek konfiguracyjnych. Zakładki nadpisują tylko te metody, które potrzebują."""

    def set_logger(self, log_message):
        pass

    def set_device_context(self, device):
        pass

    def export_state(self) -> dict:
        return {}

    def import_state(self, data: dict):
        pass

    def sync_from_config(self, conf: ParsedConfig):
        pass

    def get_pending_operations(self, clear=False) -> list[Operation]:
        return []

    def clear_pending_operations(self):
        pass
