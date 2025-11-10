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
    QComboBox,
)


class VLANsTab(QWidget):
    """
    Dummy zakładka VLANs — styl Packet Tracera.
    Zawiera listę VLAN-ów, możliwość dodawania/usuwania oraz przypisywania portów.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        # === Nagłówek ===
        main_layout.addWidget(QLabel("<h2>VLAN Configuration</h2>"))

        # === Sekcja dodawania VLAN-u ===
        add_box = QGroupBox("Add VLAN")
        form = QFormLayout(add_box)
        self.vlan_id = QLineEdit()
        self.vlan_name = QLineEdit()
        self.vlan_id.setPlaceholderText("np. 10")
        self.vlan_name.setPlaceholderText("np. Management")

        btn_add = QPushButton("Add / Update VLAN")
        btn_add.clicked.connect(self._dummy_add_vlan)

        form.addRow("VLAN ID:", self.vlan_id)
        form.addRow("Name:", self.vlan_name)
        form.addRow(btn_add)
        main_layout.addWidget(add_box)

        # === Tabela VLAN-ów ===
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["VLAN ID", "Name", "Ports"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.table, 4)

        # === Sekcja przypisywania portów ===
        assign_box = QGroupBox("Assign Port to VLAN")
        form2 = QFormLayout(assign_box)
        self.combo_vlan = QComboBox()
        self.port_name = QLineEdit()
        self.port_name.setPlaceholderText("np. GigabitEthernet0/2")
        btn_assign = QPushButton("Assign Port")
        btn_assign.clicked.connect(self._dummy_assign_port)
        form2.addRow("Select VLAN:", self.combo_vlan)
        form2.addRow("Port:", self.port_name)
        form2.addRow(btn_assign)
        main_layout.addWidget(assign_box)

        # === Przyciski operacyjne ===
        btn_row = QHBoxLayout()
        self.btn_delete = QPushButton("Delete VLAN")
        self.btn_delete.clicked.connect(self._dummy_delete_vlan)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch()
        main_layout.addLayout(btn_row)

        # === Dolny log (dummy CLI output) ===
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("VLAN configuration commands preview...")
        self.console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #111;
                color: #0f0;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.console, 2)

    # === Dummy Actions ===
    def _dummy_add_vlan(self):
        vlan_id = self.vlan_id.text().strip()
        name = self.vlan_name.text().strip()
        if not vlan_id:
            QMessageBox.warning(self, "Błąd", "Pole VLAN ID jest wymagane.")
            return

        # aktualizuj lub dodaj VLAN
        row = self._find_vlan_row(vlan_id)
        if row is None:
            row = self.table.rowCount()
            self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(vlan_id))
        self.table.setItem(row, 1, QTableWidgetItem(name))
        self.table.setItem(row, 2, QTableWidgetItem(""))

        # aktualizuj listę VLAN-ów w comboboxie
        if vlan_id not in [
            self.combo_vlan.itemText(i) for i in range(self.combo_vlan.count())
        ]:
            self.combo_vlan.addItem(vlan_id)

        self._append_console(f"vlan {vlan_id}")
        if name:
            self._append_console(f" name {name}")
        self._append_console(" exit\n")

        self.vlan_id.clear()
        self.vlan_name.clear()

    def _dummy_delete_vlan(self):
        row = self.table.currentRow()
        if row == -1:
            QMessageBox.information(self, "Info", "Wybierz VLAN do usunięcia.")
            return

        vlan_id = self.table.item(row, 0).text()
        self.table.removeRow(row)
        self._append_console(f"no vlan {vlan_id}")

        # usuń z comboboxa
        index = self.combo_vlan.findText(vlan_id)
        if index >= 0:
            self.combo_vlan.removeItem(index)

    def _dummy_assign_port(self):
        vlan_id = self.combo_vlan.currentText()
        port = self.port_name.text().strip()
        if not (vlan_id and port):
            return

        # dopisz port do odpowiedniego VLAN-u w tabeli
        row = self._find_vlan_row(vlan_id)
        if row is not None:
            current_ports = self.table.item(row, 2).text() or ""
            ports_list = [p.strip() for p in current_ports.split(",") if p.strip()]
            if port not in ports_list:
                ports_list.append(port)
                self.table.setItem(row, 2, QTableWidgetItem(", ".join(ports_list)))
                self._append_console(
                    f"interface {port}\n switchport access vlan {vlan_id}\n exit"
                )
        self.port_name.clear()

    # === Helpers ===
    def _find_vlan_row(self, vlan_id: str):
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0) and self.table.item(row, 0).text() == vlan_id:
                return row
        return None

    def _append_console(self, text: str):
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
        combo = [self.combo_vlan.itemText(i) for i in range(self.combo_vlan.count())]
        return {"rows": rows, "combo": combo, "console": self.console.toPlainText()}

    def import_state(self, data):
        self.table.setRowCount(0)
        for row in data.get("rows", []):
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, val in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(val))
        self.combo_vlan.clear()
        self.combo_vlan.addItems(data.get("combo", []))
        self.console.setPlainText(data.get("console", ""))
