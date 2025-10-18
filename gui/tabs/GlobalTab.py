from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QFormLayout, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt
from devices.Vendor import Vendor


class GlobalTab(QWidget):
    """
    Dummy zakładka 'GLOBAL' — styl Packet Tracera.
    Na razie czysto wizualny mock, bez funkcji Netmiko.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(15)

        # === Nagłówek ===
        title = QLabel("<h2>Global Settings</h2>")
        main_layout.addWidget(title)

        # === Hostname & Display Name ===
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft)
        self.display_name = QLineEdit()
        self.hostname = QLineEdit()
        self.display_name.setPlaceholderText("np. R1 / SW-Core / FW1")
        self.hostname.setPlaceholderText("np. Router1")

        form.addRow(QLabel("Display name:"), self.display_name)
        form.addRow(QLabel("Hostname:"), self.hostname)
        main_layout.addLayout(form)

        # === NVRAM ===
        nvram_box = self._make_box("NVRAM", [
            ("Erase", self._dummy_action),
            ("Save", self._dummy_action),
        ])
        main_layout.addWidget(nvram_box)

        # === Startup-config ===
        startup_box = self._make_box("Startup Config", [
            ("Load...", self._dummy_action),
            ("Export...", self._dummy_action),
        ])
        main_layout.addWidget(startup_box)

        # === Running-config ===
        running_box = self._make_box("Running Config", [
            ("Export...", self._dummy_action),
            ("Merge...", self._dummy_action),
        ])
        main_layout.addWidget(running_box)

        # === Sync Config ===
        self.btn_sync = QPushButton("🔄 Sync Configuration")
        self.btn_sync.setToolTip("Pobiera konfigurację z urządzenia (dummy).")
        self.btn_sync.clicked.connect(lambda: print("[GLOBAL TAB] Sync clicked"))
        main_layout.addWidget(self.btn_sync)

        # === Wypełniacz ===
        spacer = QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_layout.addItem(spacer)

    # --- Helper ---
    def _make_box(self, title: str, buttons: list[tuple[str, callable]]) -> QGroupBox:
        """Pomocniczy konstruktor sekcji (grup z przyciskami)."""
        box = QGroupBox(title)
        layout = QHBoxLayout(box)
        layout.setSpacing(8)
        for text, handler in buttons:
            btn = QPushButton(text)
            btn.setFixedWidth(100)
            btn.clicked.connect(handler)
            layout.addWidget(btn)
        layout.addStretch()
        return box

    # --- Dummy actions ---
    def _dummy_action(self):
        """Na razie tylko symulacja działania."""
        sender = self.sender()
        print(f"[GLOBAL TAB] Kliknięto: {sender.text()}")

    # --- API do aktualizacji GUI w zależności od typu urządzenia ---
    def adapt_to_vendor(self, vendor: Vendor):
        """
        W przyszłości: dostosowuje aktywne pola i przyciski do producenta (Cisco/Juniper).
        Na razie tylko placeholder.
        """
        if vendor == Vendor.JUNIPER:
            # Juniper nie ma "erase nvram" -> wyłącz przycisk
            self._set_button_enabled("Erase", False)
        else:
            self._set_button_enabled("Erase", True)

    def _set_button_enabled(self, text: str, enabled: bool):
        """Wyszukuje przycisk po etykiecie i zmienia jego stan."""
        for box in self.findChildren(QGroupBox):
            for btn in box.findChildren(QPushButton):
                if btn.text() == text:
                    btn.setEnabled(enabled)
