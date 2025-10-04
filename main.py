import sys

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QTextEdit,
    QFormLayout,
    QCheckBox,
    QComboBox,
    QMessageBox,
)
from netmiko import ConnectHandler


class CiscoManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyNetWizard")
        self.device_connection = None
        self.interfaces = []

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Device login form
        form_layout = QFormLayout()
        self.ip_input = QLineEdit()
        self.user_input = QLineEdit()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Device IP:", self.ip_input)
        form_layout.addRow("Username:", self.user_input)
        form_layout.addRow("Password:", self.pass_input)
        self.layout.addLayout(form_layout)

        # Connect button
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_device)
        self.layout.addWidget(self.connect_btn)

        # Interface selection
        self.interface_combo = QComboBox()
        self.layout.addWidget(QLabel("Select Interface:"))
        self.layout.addWidget(self.interface_combo)

        # IP address input
        self.ip_edit = QLineEdit()
        self.layout.addWidget(QLabel("New IP Address:"))
        self.layout.addWidget(self.ip_edit)

        # No shutdown checkbox
        self.no_shutdown_check = QCheckBox("Enable Interface (no shutdown)")
        self.layout.addWidget(self.no_shutdown_check)

        # Apply button
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self.apply_changes)
        self.layout.addWidget(self.apply_btn)

        # Output console
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.layout.addWidget(QLabel("Command Output:"))
        self.layout.addWidget(self.output)

    def connect_device(self):
        device = {
            "device_type": "cisco_ios",
            "host": self.ip_input.text(),
            "username": self.user_input.text(),
            "password": self.pass_input.text(),
        }
        try:
            self.device_connection = ConnectHandler(**device)
            self.output.append("Connected successfully!")

            # Get interfaces
            interfaces_raw = self.device_connection.send_command(
                "show ip interface brief"
            )
            self.interfaces = []
            self.interface_combo.clear()
            for line in interfaces_raw.splitlines()[1:]:  # skip header
                if line.strip():
                    iface = line.split()[0]
                    self.interfaces.append(iface)
                    self.interface_combo.addItem(iface)
            self.output.append("Fetched interfaces successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))

    def apply_changes(self):
        if not self.device_connection:
            QMessageBox.warning(self, "Error", "Not connected to a device")
            return

        iface = self.interface_combo.currentText()
        ip = self.ip_edit.text()
        no_shutdown = self.no_shutdown_check.isChecked()

        commands = [f"interface {iface}"]
        if ip:
            commands.append(f"ip address {ip} 255.255.255.0")  # assuming /24
        if no_shutdown:
            commands.append("no shutdown")

        try:
            output = self.device_connection.send_config_set(commands)
            self.output.append(output)
            QMessageBox.information(self, "Success", "Changes applied successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


if __name__ == "__main__":
    # print(PySide6.__path__)
    app = QApplication(sys.argv)
    window = CiscoManager()
    window.resize(500, 600)
    window.show()
    sys.exit(app.exec())
