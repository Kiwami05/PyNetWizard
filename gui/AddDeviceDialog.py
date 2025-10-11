import re

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QMessageBox,
    QRadioButton,
    QLabel,
    QHBoxLayout,
)


class AddDeviceDialog(QDialog):
    """Okienko do dodawania nowego urządzenia"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dodaj urządzenie")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.input_host = QLineEdit()
        self.input_username = QLineEdit()
        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_type = QLineEdit()

        form.addRow("Host", self.input_host)
        form.addRow("Użytkownik:", self.input_username)
        form.addRow("Hasło:", self.input_password)
        # --- Radio buttony dla typu urządzenia ---
        type_layout = QHBoxLayout()
        self.radio_cisco = QRadioButton("Cisco")
        self.radio_juniper = QRadioButton("Juniper")
        self.radio_cisco.setChecked(True)  # domyślnie

        type_layout.addWidget(self.radio_cisco)
        type_layout.addWidget(self.radio_juniper)

        form.addRow(QLabel("Typ urządzenia:"))
        form.addRow(type_layout)

        layout.addLayout(form)

        # --- OK / Cancel ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate_and_accept(self):
        host = self.input_host.text().strip()
        username = self.input_username.text().strip()
        password = self.input_password.text().strip()
        device_type = "Cisco" if self.radio_cisco.isChecked() else "Juniper"

        # --- Sprawdź, czy wszystkie pola są wypełnione ---
        if not host or not username or not password or not device_type:
            QMessageBox.warning(self, "Błąd", "Wszystkie pola muszą być wypełnione.")
            return

        # --- Walidacja hosta ---
        if not validate_host(host):
            QMessageBox.warning(self, "Błąd", "Niepoprawna nazwa hosta lub adres IP.")
            return

        self.accept()

    def get_data(self):
        device_type = "cisco" if self.radio_cisco.isChecked() else "juniper"
        return {
            "host": self.input_host.text().strip(),
            "username": self.input_username.text().strip(),
            "password": self.input_password.text(),
            "device_type": device_type,
        }


def validate_host(host: str) -> bool:
    """Walidacja hosta: dozwolone domeny lub IPv4"""
    # IPv4
    ipv4_pattern = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
    if ipv4_pattern.match(host):
        return all(0 <= int(octet) <= 255 for octet in host.split("."))

    # Nazwa hosta (RFC 1035)
    hostname_pattern = re.compile(
        r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
    )
    return bool(hostname_pattern.match(host))
