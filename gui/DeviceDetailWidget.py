from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QStackedWidget,
    QPlainTextEdit,
    QFrame,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Qt

from devices.DeviceBuffer import DeviceBuffer
from devices.DeviceType import DeviceType
from gui.tabs.GlobalTab import GlobalTab
from gui.tabs.RoutingTab import RoutingTab
from gui.tabs.InterfacesTab import InterfacesTab
from gui.tabs.VLANsTab import VLANsTab
from gui.tabs.ACLTab import ACLTab
from services.parsed_config import ParsedConfig


class DeviceDetailWidget(QWidget):
    """
    Główny panel szczegółów urządzenia.
    Zawiera dynamicznie zmieniane zakładki (GLOBAL / ROUTING / INTERFACES / VLANs / ACL)
    oraz dolną konsolę logów.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_device = None
        self.buffers: dict[str, DeviceBuffer] = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # === GÓRNY PANEL (zakładki + widok treści) ===
        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        main_layout.addWidget(content_frame, 4)

        # === LEWY PANEL: lista kategorii ===
        self.category_list = QListWidget()
        # self.category_list.setStyleSheet("""
        #     QListWidget {
        #         background-color: #f5f5f5;
        #         font-weight: bold;
        #         border: 1px solid #aaa;
        #     }
        #     QListWidget::item:selected {
        #         background-color: #0078d7;
        #         color: white;
        #     }
        # """)
        content_layout.addWidget(self.category_list, 1)

        # === PRAWY PANEL: zawartość zakładek ===
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 3)

        # --- Strony (tworzone raz, ale dodawane dynamicznie) ---
        self.pages = {
            "GLOBAL": GlobalTab(),
            "ROUTING": RoutingTab(),
            "INTERFACES": InterfacesTab(),
            "VLANs": VLANsTab(),
            "ACL": ACLTab(),
        }

        # Po kliknięciu w liście zmieniamy stronę
        self.category_list.currentRowChanged.connect(self.stack.setCurrentIndex)

        # === DOLNA KONSOLA ===
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("System log / command preview...")
        self.console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #111;
                color: #0f0;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.console, 1)

        # === Przykładowy przycisk testowy ===
        self.btn_test = QPushButton("Symuluj wysłanie komendy")
        self.btn_test.clicked.connect(
            lambda: self.append_console("> show running-config")
        )
        main_layout.addWidget(self.btn_test)

    # === Pomocnicze metody ===

    def clear_stack(self):
        """Usuwa wszystkie widgety ze stacka."""
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)

    def show_for_device(self, device):
        """Aktualizuje zakładki w zależności od typu urządzenia i przywraca stan z bufora."""
        # 🆕 zapisz stan poprzedniego urządzenia
        if self.current_device:
            self.save_tab_state(self.current_device)

        self.current_device = device
        self.category_list.clear()
        self.clear_stack()

        if not device:
            self.category_list.addItem("No device selected")
            placeholder = QLabel("<i>No device selected</i>")
            placeholder.setAlignment(Qt.AlignCenter)
            self.stack.addWidget(placeholder)
            return

        # Ustal, które zakładki mają się pojawić
        if device.device_type == DeviceType.ROUTER:
            tabs = ["GLOBAL", "ROUTING", "INTERFACES"]
        elif device.device_type == DeviceType.SWITCH:
            tabs = ["GLOBAL", "VLANs", "INTERFACES"]
        elif device.device_type == DeviceType.FIREWALL:
            tabs = ["GLOBAL", "INTERFACES", "ACL"]
        else:
            tabs = ["GLOBAL"]

        for name in tabs:
            self.category_list.addItem(name)
            self.stack.addWidget(self.pages[name])

        self.category_list.setCurrentRow(0)

        # 🆕 wczytaj stan z bufora
        self.load_tab_state(device)

    def append_console(self, text: str):
        """Dodaje linię do globalnej konsoli."""
        self.console.appendPlainText(text.strip())

    # =====================================================
    #        OBSŁUGA BUFORA (export/import zakładek)
    # =====================================================

    def save_tab_state(self, device):
        """Zapisuje stan aktualnych zakładek do bufora."""
        if not device:
            return
        buf = self.buffers.setdefault(device.host, DeviceBuffer())
        for name, tab in self.pages.items():
            if hasattr(tab, "export_state"):
                try:
                    buf.tabs[name] = tab.export_state()
                except Exception as e:
                    print(f"[WARN] Nie zapisano stanu {name}: {e}")

    def load_tab_state(self, device):
        """Wczytuje stan zakładek z bufora lub resetuje zakładki, jeśli bufora brak."""
        if not device:
            return

        buf = self.buffers.get(device.host)
        if not buf:
            # 🆕 brak bufora — wyczyść wszystkie taby
            for name, tab in self.pages.items():
                if hasattr(tab, "import_state"):
                    try:
                        tab.import_state({})  # pusta struktura
                    except Exception:
                        pass
            return

        # 🧠 bufor istnieje — przywróć stan
        for name, tab in self.pages.items():
            if name in buf.tabs and hasattr(tab, "import_state"):
                try:
                    tab.import_state(buf.tabs[name])
                except Exception as e:
                    print(f"[WARN] Nie wczytano stanu {name}: {e}")

    def sync_tabs_from_config(self, conf: ParsedConfig):
        # Zapisz w buforze urządzenia
        buf = self.buffers.setdefault(self.current_device.host, DeviceBuffer())
        buf.hostname = conf.hostname or buf.hostname
        buf.logs = (buf.logs or "") + "\n[SYNC] Config applied to tabs."
        buf.tabs.setdefault("GLOBAL", {})
        buf.config = conf  # zawsze aktualny snapshot

        # Rozsyłanie do aktywnych tabów, tylko tych które istnieją teraz w stacku
        for idx in range(self.stack.count()):
            widget = self.stack.widget(idx)
            if hasattr(widget, "sync_from_config"):
                try:
                    widget.sync_from_config(conf)
                except Exception as e:
                    self.append_console(f"[WARN] Tab sync failed: {e}")

    def restore_from_snapshot(self):
        """Przywraca stan tabów z ostatniego pobranego configu (buf.config)."""
        if not self.current_device:
            return
        buf = self.buffers.get(self.current_device.host)
        if not buf or not buf.config:
            self.append_console("[INFO] Brak zapisanego snapshotu dla tego urządzenia.")
            return
        self.append_console("[RESET] Przywracanie konfiguracji z ostatniego synca...")
        self.sync_tabs_from_config(buf.config)
