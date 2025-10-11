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
    QHBoxLayout,
    QRadioButton,
    QGroupBox,  # <-- added
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

        # ---- Device type selection inside its own groupbox ----
        device_groupbox = QGroupBox("Device Type")
        device_type_layout = QHBoxLayout()
        self.cisco_radio = QRadioButton("Cisco IOS")
        self.junos_radio = QRadioButton("Juniper JunOS")
        self.cisco_radio.setChecked(True)  # default
        device_type_layout.addWidget(self.cisco_radio)
        device_type_layout.addWidget(self.junos_radio)
        device_groupbox.setLayout(device_type_layout)
        self.layout.addWidget(device_groupbox)

        # ---- Protocol selection inside its own groupbox ----
        proto_groupbox = QGroupBox("Protocol")
        proto_layout = QHBoxLayout()
        self.ssh_radio = QRadioButton("SSH")
        self.telnet_radio = QRadioButton("Telnet")
        self.ssh_radio.setChecked(True)  # default
        proto_layout.addWidget(self.ssh_radio)
        proto_layout.addWidget(self.telnet_radio)
        proto_groupbox.setLayout(proto_layout)
        self.layout.addWidget(proto_groupbox)

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

    def get_device_type(self):
        """Return the selected Netmiko device type string."""
        if self.cisco_radio.isChecked():
            return "cisco_ios"
        elif self.junos_radio.isChecked():
            return "juniper"
        return None

    def get_protocol(self):
        base_type = self.get_device_type()
        if not base_type:
            return None
        if self.ssh_radio.isChecked():
            return base_type
        elif self.telnet_radio.isChecked():
            return base_type + "_telnet"
        return None

    def connect_device(self):
        device_type = self.get_protocol()
        if not device_type:
            QMessageBox.warning(self, "Error", "Please select device type and protocol")
            return

        device = {
            "device_type": device_type,
            "host": self.ip_input.text(),
            "username": self.user_input.text(),
            "password": self.pass_input.text(),
        }

        try:
            self.device_connection = ConnectHandler(**device)
            self.output.append(f"Connected successfully to {device_type}!")

            # Fetch interfaces
            self.interfaces = []
            self.interface_combo.clear()

            if "cisco_ios" in device_type:
                interfaces_raw = self.device_connection.send_command(
                    "show ip interface brief"
                )
                for line in interfaces_raw.splitlines()[1:]:
                    if line.strip():
                        iface = line.split()[0]
                        self.interfaces.append(iface)
                        self.interface_combo.addItem(iface)
            elif "juniper" in device_type:
                interfaces_raw = self.device_connection.send_command(
                    "show interfaces terse"
                )
                for line in interfaces_raw.splitlines():
                    if "Interface" in line or not line.strip():
                        continue
                    iface = line.split()[0]
                    if "mt-" not in iface and "." not in iface:  # skip logicals
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
        device_type = self.get_protocol()

        try:
            if "cisco_ios" in device_type:
                commands = [f"interface {iface}"]
                if ip:
                    commands.append(f"ip address {ip} 255.255.255.0")
                if no_shutdown:
                    commands.append("no shutdown")

            elif "juniper" in device_type:
                commands = [
                    f"set interfaces {iface} unit 0 family inet address {ip}/24"
                ]
                if no_shutdown:
                    commands.append(f"delete interfaces {iface} disable")

            output = self.device_connection.send_config_set(commands)
            self.output.append(output)
            QMessageBox.information(self, "Success", "Changes applied successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CiscoManager()
    window.resize(500, 600)
    window.show()
    sys.exit(app.exec())
