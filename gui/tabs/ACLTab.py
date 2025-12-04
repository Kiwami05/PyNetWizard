# gui/tabs/ACLTab.py

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

from services.parsed_config import ParsedConfig


class ACLTab(QWidget):
    """
    ACL configuration tab — now fully integrated with pending commands.
    Supports only numbered ACLs (standard + extended) — minimal version.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_acl = None
        self.pending_cmds = []
        self._loading = False

        # =====================================================
        # MAIN LAYOUT
        # =====================================================
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        # === Header ===
        main_layout.addWidget(QLabel("<h2>Access Control Lists (ACL)</h2>"))

        # =====================================================
        # ACL SELECTION BOX
        # =====================================================
        acl_box = QGroupBox("Select or Create ACL")
        acl_form = QFormLayout(acl_box)

        self.acl_number = QLineEdit()
        self.acl_number.setPlaceholderText("e.g. 10 (standard) or 100 (extended)")

        btn_new = QPushButton("Create / Select ACL")
        btn_new.clicked.connect(self._select_acl)

        acl_form.addRow("ACL Number:", self.acl_number)
        acl_form.addRow(btn_new)

        main_layout.addWidget(acl_box)

        # =====================================================
        # ADD RULE SECTION
        # =====================================================
        rule_box = QGroupBox("Add Rule to ACL")
        rule_form = QFormLayout(rule_box)

        self.action_combo = QComboBox()
        self.action_combo.addItems(["permit", "deny"])

        self.protocol = QLineEdit()
        self.protocol.setPlaceholderText("e.g. ip, tcp, udp, icmp")

        self.src = QLineEdit()
        self.src.setPlaceholderText("Source (e.g. 192.168.1.0 or any)")

        self.wildcard = QLineEdit()
        self.wildcard.setPlaceholderText("Wildcard mask (optional)")

        self.dest = QLineEdit()
        self.dest.setPlaceholderText("Destination (e.g. any)")

        rule_form.addRow("Action:", self.action_combo)
        rule_form.addRow("Protocol:", self.protocol)
        rule_form.addRow("Source:", self.src)
        rule_form.addRow("Wildcard:", self.wildcard)
        rule_form.addRow("Destination:", self.dest)

        btn_add = QPushButton("Add Rule")
        btn_add.clicked.connect(self._add_rule)

        rule_form.addRow(btn_add)
        main_layout.addWidget(rule_box)

        # =====================================================
        # RULE TABLE
        # =====================================================
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Action", "Protocol", "Source", "Wildcard", "Destination"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        main_layout.addWidget(self.table, 4)

        # =====================================================
        # DELETE BUTTON
        # =====================================================
        btn_row = QHBoxLayout()
        self.btn_delete = QPushButton("Delete Selected Rule")
        self.btn_delete.clicked.connect(self._delete_rule)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch()

        main_layout.addLayout(btn_row)

        # =====================================================
        # CONSOLE (COMMAND PREVIEW)
        # =====================================================
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

    # =====================================================================
    # COMMAND ENQUEUE SYSTEM
    # =====================================================================
    def _enqueue(self, cmds):
        """Add commands to ACLTab's pending buffer and print to console."""
        if isinstance(cmds, str):
            cmds = [cmds]

        for c in cmds:
            c = c.strip()
            if not c:
                continue
            self.pending_cmds.append(c)
            self.console.appendPlainText(c)

    # =====================================================================
    # SELECT ACL
    # =====================================================================
    def _select_acl(self):
        acl_num = self.acl_number.text().strip()
        if not acl_num.isdigit():
            QMessageBox.warning(self, "Błąd", "Podaj numerowaną ACL (np. 10, 100).")
            return

        self.current_acl = acl_num
        self.console.appendPlainText(f"! Using ACL {acl_num}")

    # =====================================================================
    # ADD RULE (REAL IMPLEMENTATION)
    # =====================================================================
    def _add_rule(self):
        if not self.current_acl:
            QMessageBox.warning(self, "Brak ACL", "Najpierw wybierz ACL.")
            return

        action = self.action_combo.currentText()
        proto = self.protocol.text().strip() or "ip"
        src = self.src.text().strip() or "any"
        wc = self.wildcard.text().strip()
        dest = self.dest.text().strip() or "any"

        # Build command
        cmd = f"access-list {self.current_acl} {action} {proto} {src}"
        if wc:
            cmd += f" {wc}"
        cmd += f" {dest}"

        # Add to table
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(action))
        self.table.setItem(row, 1, QTableWidgetItem(proto))
        self.table.setItem(row, 2, QTableWidgetItem(src))
        self.table.setItem(row, 3, QTableWidgetItem(wc))
        self.table.setItem(row, 4, QTableWidgetItem(dest))

        # Buffer command
        self._enqueue(cmd)

        # Clear UI fields
        self.protocol.clear()
        self.src.clear()
        self.wildcard.clear()
        self.dest.clear()

    # =====================================================================
    # DELETE RULE
    # =====================================================================
    def _delete_rule(self):
        row = self.table.currentRow()
        if row == -1:
            QMessageBox.information(self, "Info", "Wybierz regułę do usunięcia.")
            return

        if not self.current_acl:
            QMessageBox.warning(self, "Brak ACL", "Najpierw wybierz ACL.")
            return

        action = self.table.item(row, 0).text()
        proto = self.table.item(row, 1).text()
        src = self.table.item(row, 2).text()
        wc = self.table.item(row, 3).text()
        dest = self.table.item(row, 4).text()

        cmd = f"no access-list {self.current_acl} {action} {proto} {src}"
        if wc:
            cmd += f" {wc}"
        cmd += f" {dest}"

        # Remove from UI
        self.table.removeRow(row)

        # Add to buffer
        self._enqueue(cmd)

    # =====================================================================
    # PENDING COMMANDS API (required by detail_box)
    # =====================================================================
    def get_pending_commands(self):
        return list(self.pending_cmds)

    def clear_pending_commands(self):
        self.pending_cmds.clear()

    # =====================================================================
    # STATE EXPORT / IMPORT
    # =====================================================================
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
            "pending_cmds": list(self.pending_cmds),
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
        self.pending_cmds = list(data.get("pending_cmds", []))

    # =====================================================================
    # SYNC FROM PARSED CONFIG (RUNNING-CONFIG)
    # =====================================================================
    def sync_from_config(self, conf: ParsedConfig):
        """Loads ACLs from ParsedConfig into the UI (does not generate commands)."""

        self._loading = True
        try:
            self.table.setRowCount(0)

            # Load ACL entries parsed from running-config
            for r in conf.acls.rules:
                row = self.table.rowCount()
                self.table.insertRow(row)

                self.table.setItem(row, 0, QTableWidgetItem(r["action"]))
                self.table.setItem(row, 1, QTableWidgetItem(r["protocol"]))
                self.table.setItem(row, 2, QTableWidgetItem(r["src"]))
                self.table.setItem(row, 3, QTableWidgetItem(r.get("wildcard", "")))
                self.table.setItem(row, 4, QTableWidgetItem(r.get("dest", "any")))

            self.console.appendPlainText("[SYNC] ACLs updated from running-config.")
            self.pending_cmds.clear()

        finally:
            self._loading = False
