from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QStackedWidget, QLabel, QPlainTextEdit, QFrame, QPushButton
)
from devices.DeviceType import DeviceType


class DeviceDetailWidget(QWidget):
    """
    Dummy GUI sekcji konfiguracji urządzenia (styl Packet Tracera).
    Na razie tylko układ zakładek + konsola logów.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # === GŁÓWNY LAYOUT ===
        main_layout = QVBoxLayout(self)

        # --- GÓRNY PANEL ---
        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)
        main_layout.addWidget(content_frame, 4)

        # === LEWA LISTA "KATEGORII" ===
        self.category_list = QListWidget()
        self.category_list.setStyleSheet("""
            QListWidget {
                background-color: #f0f0f0;
                font-weight: bold;
                border: 1px solid #aaa;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """)
        content_layout.addWidget(self.category_list, 1)

        # === PRAWA STRONA – STOS WIDOKÓW ===
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 3)

        # --- Dummy podstrony ---
        self.pages = {
            "GLOBAL": self._make_dummy_page("Global Settings"),
            "ROUTING": self._make_dummy_page("Routing Configuration"),
            "INTERFACES": self._make_dummy_page("Interface Configuration"),
            "VLANs": self._make_dummy_page("VLAN Database"),
            "ACL": self._make_dummy_page("Access Control Lists"),
        }

        for page in self.pages.values():
            self.stack.addWidget(page)

        # Domyślnie pusty
        self.category_list.addItem("No device selected")
        self.stack.setCurrentIndex(0)

        # --- Połączenie listy z widokiem ---
        self.category_list.currentRowChanged.connect(self._switch_page)

        # === DOLNY PANEL – "Konsola" ===
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Equivalent IOS commands will appear here...")
        self.console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #111;
                color: #0f0;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.console, 1)

        # === PRZYKŁADOWY PRZYCISK TESTOWY ===
        self.test_button = QPushButton("Wyślij testowe polecenie")
        self.test_button.clicked.connect(self._append_test_command)
        main_layout.addWidget(self.test_button)

    # --- Pomocnicze metody ---
    def _make_dummy_page(self, title: str) -> QWidget:
        """Tworzy prostą stronę z nagłówkiem."""
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(f"<h3>{title}</h3><p>Tu znajdzie się konfiguracja dla sekcji {title}.</p>")
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _switch_page(self, index: int):
        """Zmienia widok w zależności od wybranej kategorii."""
        if index < 0 or index >= self.stack.count():
            return
        self.stack.setCurrentIndex(index)

    def _append_test_command(self):
        """Dodaje testowy wpis do konsoli."""
        self.console.appendPlainText("> show ip interface brief")
        self.console.appendPlainText("Interface       IP-Address      OK? Method Status Protocol")
        self.console.appendPlainText("Gig0/0          10.0.0.1        YES manual up     up\n")

    def show_for_device(self, device):
        """Aktualizuje zakładki w zależności od typu urządzenia."""
        self.category_list.clear()
        self.stack.setCurrentIndex(0)

        if not device:
            self.category_list.addItem("No device selected")
            return

        # Dobór zakładek wg typu urządzenia
        if device.device_type == DeviceType.ROUTER:
            tabs = ["GLOBAL", "ROUTING", "INTERFACES"]
        elif device.device_type == DeviceType.SWITCH:
            tabs = ["GLOBAL", "VLANs", "INTERFACES"]
        elif device.device_type == DeviceType.FIREWALL:
            tabs = ["GLOBAL", "INTERFACES", "ACL"]
        else:
            tabs = ["GLOBAL"]

        for tab in tabs:
            self.category_list.addItem(tab)

        self.category_list.setCurrentRow(0)
