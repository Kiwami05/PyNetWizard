from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QStackedWidget, QPlainTextEdit, QFrame, QPushButton, QLabel
)
from PySide6.QtCore import Qt
from devices.DeviceType import DeviceType
from gui.tabs.GlobalTab import GlobalTab
from gui.tabs.RoutingTab import RoutingTab
from gui.tabs.InterfacesTab import InterfacesTab
from gui.tabs.VLANsTab import VLANsTab
from gui.tabs.ACLTab import ACLTab


class DeviceDetailWidget(QWidget):
    """
    Główny panel szczegółów urządzenia.
    Zawiera dynamicznie zmieniane zakładki (GLOBAL / ROUTING / INTERFACES / VLANs / ACL)
    oraz dolną konsolę logów.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

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
        self.category_list.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                font-weight: bold;
                border: 1px solid #aaa;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """)
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
        self.btn_test.clicked.connect(lambda: self.append_console("> show running-config"))
        main_layout.addWidget(self.btn_test)

    # === Pomocnicze metody ===

    def clear_stack(self):
        """Usuwa wszystkie widgety ze stacka."""
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)

    def show_for_device(self, device):
        """Aktualizuje zakładki w zależności od typu urządzenia."""
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

        # Utwórz dynamicznie listę + stack
        for name in tabs:
            self.category_list.addItem(name)
            self.stack.addWidget(self.pages[name])

        self.category_list.setCurrentRow(0)

    def append_console(self, text: str):
        """Dodaje linię do globalnej konsoli."""
        self.console.appendPlainText(text.strip())
