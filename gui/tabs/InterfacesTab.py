from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QFormLayout,
    QGroupBox,
    QPlainTextEdit,
    QMessageBox,
)

from services.parsed_config import ParsedConfig


class InterfacesTab(QWidget):
    """
    Dummy zakładka INTERFACES — styl Packet Tracera.
    Zawiera tabelę interfejsów, podstawowe pola IP i tryb portu.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        # === Nagłówek ===
        main_layout.addWidget(QLabel("<h2>Interface Configuration</h2>"))

        # === Górny formularz: dodanie interfejsu ===
        add_box = QGroupBox("Add / Edit Interface")
        form = QFormLayout(add_box)
        self.intf_name = QLineEdit()
        self.intf_desc = QLineEdit()
        self.intf_ip = QLineEdit()
        self.intf_mask = QLineEdit()
        self.intf_mode = QLineEdit()
        self.intf_name.setPlaceholderText("e.g. GigabitEthernet0/0")
        self.intf_ip.setPlaceholderText("e.g. 192.168.1.1")
        self.intf_mask.setPlaceholderText("e.g. 255.255.255.0")
        self.intf_mode.setPlaceholderText("access / trunk / routed")
        form.addRow("Name:", self.intf_name)
        form.addRow("Description:", self.intf_desc)
        form.addRow("IP Address:", self.intf_ip)
        form.addRow("Subnet Mask:", self.intf_mask)
        form.addRow("Mode:", self.intf_mode)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add / Update")
        btn_clear = QPushButton("Clear")
        btn_add.clicked.connect(self._dummy_add_intf)
        btn_clear.clicked.connect(self._clear_fields)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_clear)
        form.addRow(btn_row)
        main_layout.addWidget(add_box)

        # === Tabela interfejsów ===
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Description", "IP Address", "Mask", "Mode", "Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.cellClicked.connect(self._fill_form_from_table)
        main_layout.addWidget(self.table, 4)

        # === Przyciski operacyjne ===
        btns_box = QHBoxLayout()
        self.btn_enable = QPushButton("Enable")
        self.btn_disable = QPushButton("Disable")
        self.btn_trunk = QPushButton("Set Trunk")
        self.btn_access = QPushButton("Set Access")

        for b in (self.btn_enable, self.btn_disable, self.btn_trunk, self.btn_access):
            btns_box.addWidget(b)
        btns_box.addStretch()
        main_layout.addLayout(btns_box)

        # Dummy connections
        self.btn_enable.clicked.connect(lambda: self._dummy_cmd("no shutdown"))
        self.btn_disable.clicked.connect(lambda: self._dummy_cmd("shutdown"))
        self.btn_trunk.clicked.connect(lambda: self._dummy_cmd("switchport mode trunk"))
        self.btn_access.clicked.connect(
            lambda: self._dummy_cmd("switchport mode access")
        )

        # === Dolna konsola logów ===
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Interface commands preview...")
        self.console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #111;
                color: #0f0;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.console, 2)

    # === Dummy actions ===
    def _dummy_add_intf(self):
        name = self.intf_name.text().strip()
        desc = self.intf_desc.text().strip()
        ip = self.intf_ip.text().strip()
        mask = self.intf_mask.text().strip()
        mode = self.intf_mode.text().strip()
        if not name:
            QMessageBox.warning(self, "Błąd", "Pole 'Name' jest wymagane.")
            return

        # jeśli istnieje, aktualizuj
        row = self._find_interface_row(name)
        if row is None:
            row = self.table.rowCount()
            self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(desc))
        self.table.setItem(row, 2, QTableWidgetItem(ip))
        self.table.setItem(row, 3, QTableWidgetItem(mask))
        self.table.setItem(row, 4, QTableWidgetItem(mode))
        self.table.setItem(row, 5, QTableWidgetItem("up"))

        # symulacja komend
        self._append_console(f"interface {name}")
        if desc:
            self._append_console(f" description {desc}")
        if ip and mask:
            self._append_console(f" ip address {ip} {mask}")
        if mode:
            if mode.lower() in ["access", "trunk"]:
                self._append_console(f" switchport mode {mode.lower()}")
            elif mode.lower() == "routed":
                self._append_console(" no switchport")
        self._append_console(" no shutdown\n")

        self._clear_fields()

    def _clear_fields(self):
        for w in [
            self.intf_name,
            self.intf_desc,
            self.intf_ip,
            self.intf_mask,
            self.intf_mode,
        ]:
            w.clear()

    def _fill_form_from_table(self, row, _col):
        """Kliknięcie w tabeli – wypełnia formularz."""
        self.intf_name.setText(self.table.item(row, 0).text())
        self.intf_desc.setText(self.table.item(row, 1).text())
        self.intf_ip.setText(self.table.item(row, 2).text())
        self.intf_mask.setText(self.table.item(row, 3).text())
        self.intf_mode.setText(self.table.item(row, 4).text())

    def _find_interface_row(self, name):
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0) and self.table.item(row, 0).text() == name:
                return row
        return None

    def _dummy_cmd(self, cmd):
        """Symuluje wpisanie komendy."""
        self._append_console(cmd)

    def _append_console(self, text):
        self.console.appendPlainText(text.strip())

    def export_state(self):
        rows = []
        for r in range(self.table.rowCount()):
            rows.append(
                [
                    self.table.item(r, c).text() if self.table.item(r, c) else ""
                    for c in range(self.table.columnCount())
                ]
            )
        return {"rows": rows, "console": self.console.toPlainText()}

    def import_state(self, data):
        self.table.setRowCount(0)
        for row in data.get("rows", []):
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, val in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(val))
        self.console.setPlainText(data.get("console", ""))

    def sync_from_config(self, conf: ParsedConfig):
        self.table.setRowCount(0)
        for name, data in conf.interfaces.items.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(name))
            self.table.setItem(r, 1, QTableWidgetItem(data.get("description", "")))
            self.table.setItem(r, 2, QTableWidgetItem(data.get("ip", "")))
            self.table.setItem(r, 3, QTableWidgetItem(data.get("mask", "")))
            self.table.setItem(r, 4, QTableWidgetItem(data.get("mode", "")))
            self.table.setItem(r, 5, QTableWidgetItem(data.get("status", "up")))
        self.console.appendPlainText("[SYNC] Interfaces updated from running-config.")
