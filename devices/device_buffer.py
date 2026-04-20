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

        # dane zakładek (każdy tab przechowuje własny podzbiór)
        self.tabs = {}  # np. {"GLOBAL": {...}, "INTERFACES": {...}}
        self.config: ParsedConfig | None = None  # ostatnio pobrany i sparsowany config
