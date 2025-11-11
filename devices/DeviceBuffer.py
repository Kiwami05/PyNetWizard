from services.parsed_config import ParsedConfig


class DeviceBuffer:
    """
    Przechowuje stan GUI i konfiguracji dla jednego urządzenia.
    Buforowane dane pozwalają przy przełączaniu urządzeń
    zachować np. hostname, logi, konfiguracje tabów itp.
    """

    def __init__(self):
        # dane globalne
        self.hostname = ""
        self.logs = ""

        # dane zakładek (każda tab przechowuje własny podzbiór)
        self.tabs = {}  # np. {"GLOBAL": {...}, "INTERFACES": {...}}
        self.config: ParsedConfig | None = (
            None  # 🆕 ostatnio pobrany i sparsowany config
        )

    def export_all(self) -> dict:
        """Zwraca stan całego bufora jako dict (do ewentualnego zapisu JSON)."""
        return {
            "hostname": self.hostname,
            "logs": self.logs,
            "tabs": self.tabs,
        }

    def import_all(self, data: dict):
        """Przywraca stan bufora z dict (np. po wczytaniu sesji)."""
        self.hostname = data.get("hostname", "")
        self.logs = data.get("logs", "")
        self.tabs = data.get("tabs", {})
