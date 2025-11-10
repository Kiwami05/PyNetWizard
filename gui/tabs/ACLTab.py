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
    QComboBox,
    QMessageBox,
)


class ACLTab(QWidget):
    """
    Dummy zakładka ACL — styl Packet Tracera.
    Pozwala tworzyć i przeglądać reguły ACL (permit/deny), w trybie symulacji.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        # === Nagłówek ===
        main_layout.addWidget(QLabel("<h2>Access Control Lists (ACL)</h2>"))

        # === Sekcja wyboru listy ACL ===
        acl_box = QGroupBox("Select or Create ACL")
        acl_form = QFormLayout(acl_box)
        self.acl_number = QLineEdit()
        self.acl_number.setPlaceholderText("e.g. 10 (standard) or 100 (extended)")
        btn_new = QPushButton("Create / Select ACL")
        btn_new.clicked.connect(self._dummy_select_acl)
        acl_form.addRow("ACL Number:", self.acl_number)
        acl_form.addRow(btn_new)
        main_layout.addWidget(acl_box)

        # === Sekcja dodawania reguł ===
        rule_box = QGroupBox("Add Rule to ACL")
        rule_form = QFormLayout(rule_box)

        self.action_combo = QComboBox()
        self.action_combo.addItems(["permit", "deny"])
        self.protocol = QLineEdit()
        self.protocol.setPlaceholderText("e.g. ip, tcp, udp, icmp")
        self.src = QLineEdit()
        self.src.setPlaceholderText("Source (e.g. 192.168.1.0)")
        self.wildcard = QLineEdit()
        self.wildcard.setPlaceholderText("Wildcard mask (e.g. 0.0.0.255)")
        self.dest = QLineEdit()
        self.dest.setPlaceholderText("Destination (optional)")

        rule_form.addRow("Action:", self.action_combo)
        rule_form.addRow("Protocol:", self.protocol)
        rule_form.addRow("Source:", self.src)
        rule_form.addRow("Wildcard:", self.wildcard)
        rule_form.addRow("Destination:", self.dest)

        btn_add = QPushButton("Add Rule")
        btn_add.clicked.connect(self._dummy_add_rule)
        rule_form.addRow(btn_add)
        main_layout.addWidget(rule_box)

        # === Tabela reguł ===
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Action", "Protocol", "Source", "Wildcard", "Destination"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.table, 4)

        # === Przyciski operacyjne ===
        btn_row = QHBoxLayout()
        self.btn_delete = QPushButton("Delete Selected Rule")
        self.btn_delete.clicked.connect(self._dummy_delete_rule)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch()
        main_layout.addLayout(btn_row)

        # === Dolna konsola (log komend) ===
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("ACL configuration commands preview...")
        self.console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #111;
                color: #0f0;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.console, 2)

        # === Dane wewnętrzne ===
        self.current_acl = None

    # === Dummy Actions ===
    def _dummy_select_acl(self):
        acl_num = self.acl_number.text().strip()
        if not acl_num:
            QMessageBox.warning(self, "Błąd", "Wprowadź numer ACL.")
            return

        self.current_acl = acl_num
        self._append_console(f"access-list {acl_num} selected.")
        QMessageBox.information(
            self, "ACL selected", f"Using ACL {acl_num} for new rules."
        )

    def _dummy_add_rule(self):
        if not self.current_acl:
            QMessageBox.warning(self, "Brak ACL", "Najpierw utwórz lub wybierz ACL.")
            return

        action = self.action_combo.currentText()
        proto = self.protocol.text().strip() or "ip"
        src = self.src.text().strip() or "any"
        wc = self.wildcard.text().strip() or ""
        dest = self.dest.text().strip() or "any"

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(action))
        self.table.setItem(row, 1, QTableWidgetItem(proto))
        self.table.setItem(row, 2, QTableWidgetItem(src))
        self.table.setItem(row, 3, QTableWidgetItem(wc))
        self.table.setItem(row, 4, QTableWidgetItem(dest))

        cmd = (
            f"access-list {self.current_acl} {action} {proto} {src} {wc} {dest}".strip()
        )
        self._append_console(cmd)

        self.protocol.clear()
        self.src.clear()
        self.wildcard.clear()
        self.dest.clear()

    def _dummy_delete_rule(self):
        row = self.table.currentRow()
        if row == -1:
            QMessageBox.information(self, "Info", "Wybierz regułę do usunięcia.")
            return

        rule_items = [self.table.item(row, i).text() for i in range(5)]
        cmd = f"no access-list {self.current_acl} {' '.join(rule_items)}"
        self.table.removeRow(row)
        self._append_console(cmd)

    def _append_console(self, text: str):
        self.console.appendPlainText(text.strip())

    def export_state(self):
        rules = []
        for r in range(self.table.rowCount()):
            rules.append(
                [self.table.item(r, c).text() for c in range(self.table.columnCount())]
            )
        return {
            "acl": self.current_acl,
            "rules": rules,
            "console": self.console.toPlainText(),
        }

    def import_state(self, data):
        self.current_acl = data.get("acl", None)
        self.table.setRowCount(0)
        for row in data.get("rules", []):
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, val in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(val))
        self.console.setPlainText(data.get("console", ""))
