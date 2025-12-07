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
from devices.DeviceType import DeviceType
from services.parsed_config import ParsedConfig
import re


class ACLTab(QWidget):
    """
    ASA-only ACL configuration tab.
    Supports named ACLs in ASA format:
        access-list <NAME> extended permit/deny ...
        access-group <NAME> in interface <iface>
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_acl_name = None
        self.pending_cmds = []
        self._loading = False
        self.current_device_type = None  # set by main window

        main = QVBoxLayout(self)
        main.setContentsMargins(20, 15, 20, 15)
        main.setSpacing(10)

        # ----------------------------------------------------------
        # HEADER
        # ----------------------------------------------------------
        main.addWidget(QLabel("<h2>ASA Access Control Lists (ACL)</h2>"))

        # ----------------------------------------------------------
        # ASA ONLY WARNING (hidden until device type known)
        # ----------------------------------------------------------
        self.lbl_warning = QLabel(
            "<b>This feature is only available for Cisco ASA firewalls.</b>"
        )
        self.lbl_warning.setStyleSheet("color: red; font-size: 14px;")
        self.lbl_warning.hide()
        main.addWidget(self.lbl_warning)

        # ----------------------------------------------------------
        # ACL NAME SELECTION
        # ----------------------------------------------------------
        acl_box = QGroupBox("Select or Create ASA ACL (Named)")
        acl_form = QFormLayout(acl_box)

        self.input_acl_name = QLineEdit()
        self.input_acl_name.setPlaceholderText("OUTSIDE-IN, INSIDE-POLICY, etc.")

        btn_set_acl = QPushButton("Use ACL Name")
        btn_set_acl.clicked.connect(self._select_acl)

        acl_form.addRow("ACL Name:", self.input_acl_name)
        acl_form.addRow(btn_set_acl)

        main.addWidget(acl_box)

        # ----------------------------------------------------------
        # ADD RULE
        # ----------------------------------------------------------
        rule_box = QGroupBox("Add Rule to ACL")
        rule_form = QFormLayout(rule_box)

        self.action_combo = QComboBox()
        self.action_combo.addItems(["permit", "deny"])

        self.proto_input = QLineEdit()
        self.proto_input.setPlaceholderText("tcp, udp, icmp, ip")

        self.src_input = QLineEdit()
        self.src_input.setPlaceholderText("any, host 1.1.1.1, 10.0.0.0/24")

        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("any, host 2.2.2.2, 192.168.0.0/24")

        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("optional: eq 80, range 100 200")

        rule_form.addRow("Action:", self.action_combo)
        rule_form.addRow("Protocol:", self.proto_input)
        rule_form.addRow("Source:", self.src_input)
        rule_form.addRow("Destination:", self.dest_input)
        rule_form.addRow("Port Options:", self.port_input)

        btn_add = QPushButton("Add Rule")
        btn_add.clicked.connect(self._add_rule)

        rule_form.addRow(btn_add)
        main.addWidget(rule_box)

        # ----------------------------------------------------------
        # RULE TABLE
        # ----------------------------------------------------------
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Action", "Protocol", "Source", "Destination", "Port Opts"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main.addWidget(self.table, 4)

        # ----------------------------------------------------------
        # DELETE RULE
        # ----------------------------------------------------------
        row = QHBoxLayout()
        btn_delete = QPushButton("Delete Selected Rule")
        btn_delete.clicked.connect(self._delete_rule)
        row.addWidget(btn_delete)
        row.addStretch()
        main.addLayout(row)

        # ----------------------------------------------------------
        # INTERFACE BINDING (ASA ONLY)
        # ----------------------------------------------------------
        bind_box = QGroupBox("Bind ACL to Interface (ASA)")
        bind_form = QFormLayout(bind_box)

        self.input_iface = QLineEdit()
        self.input_iface.setPlaceholderText("outside, inside, dmz...")

        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["in", "out"])

        btn_bind = QPushButton("Bind ACL")
        btn_bind.clicked.connect(self._bind_acl)

        bind_form.addRow("Interface:", self.input_iface)
        bind_form.addRow("Direction:", self.dir_combo)
        bind_form.addRow(btn_bind)

        main.addWidget(bind_box)

        # ----------------------------------------------------------
        # CONSOLE OUTPUT
        # ----------------------------------------------------------
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("ASA ACL command preview...")
        self.console.setStyleSheet(
            "background-color:#111; color:#0f0; font-family:monospace;"
        )
        main.addWidget(self.console, 2)

    # ==============================================================
    # ASA mode enforcement
    # ==============================================================

    def set_device_type(self, dev_type: DeviceType):
        """Called by DeviceDetailTab when device is changed."""
        self.current_device_type = dev_type

        if dev_type != DeviceType.FIREWALL:
            self.lbl_warning.show()
        else:
            self.lbl_warning.hide()

    # ==============================================================
    # INTERNAL HELPERS
    # ==============================================================

    def _enqueue(self, cmds):
        if isinstance(cmds, str):
            cmds = [cmds]
        for c in cmds:
            self.pending_cmds.append(c)
            self.console.appendPlainText(c)

    # ==============================================================
    # SELECT ACL NAME
    # ==============================================================

    def _select_acl(self):
        name = self.input_acl_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Enter ACL name.")
            return

        self.current_acl_name = name
        self.console.appendPlainText(f"! Using ASA ACL: {name}")

    # ==============================================================
    # ADD RULE (ASA FORMAT)
    # ==============================================================

    def _add_rule(self):
        if not self.current_acl_name:
            QMessageBox.warning(self, "Error", "Select ACL first.")
            return

        action = self.action_combo.currentText()
        proto = self.proto_input.text().strip() or "ip"
        src = self.src_input.text().strip() or "any"
        dest = self.dest_input.text().strip() or "any"
        port = self.port_input.text().strip()

        cmd = f"access-list {self.current_acl_name} extended {action} {proto} {src} {dest}"
        if port:
            cmd += f" {port}"

        # Add to table
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(action))
        self.table.setItem(r, 1, QTableWidgetItem(proto))
        self.table.setItem(r, 2, QTableWidgetItem(src))
        self.table.setItem(r, 3, QTableWidgetItem(dest))
        self.table.setItem(r, 4, QTableWidgetItem(port))

        # Add to pending commands
        self._enqueue(cmd)

        # Clear inputs
        self.proto_input.clear()
        self.src_input.clear()
        self.dest_input.clear()
        self.port_input.clear()

    # ==============================================================
    # DELETE RULE
    # ==============================================================

    def _delete_rule(self):
        r = self.table.currentRow()
        if r == -1:
            QMessageBox.information(self, "Info", "Select rule to delete.")
            return

        if not self.current_acl_name:
            QMessageBox.warning(self, "Error", "No ACL selected.")
            return

        action = self.table.item(r, 0).text()
        proto = self.table.item(r, 1).text()
        src = self.table.item(r, 2).text()
        dest = self.table.item(r, 3).text()
        port = self.table.item(r, 4).text()

        cmd = f"no access-list {self.current_acl_name} extended {action} {proto} {src} {dest}"
        if port:
            cmd += f" {port}"

        self._enqueue(cmd)
        self.table.removeRow(r)

    # ==============================================================
    # BIND ACL TO INTERFACE
    # ==============================================================

    def _bind_acl(self):
        if not self.current_acl_name:
            QMessageBox.warning(self, "Error", "Select ACL first.")
            return

        iface = self.input_iface.text().strip()
        if not iface:
            QMessageBox.warning(self, "Error", "Enter interface name.")
            return

        direction = self.dir_combo.currentText()

        cmd = f"access-group {self.current_acl_name} {direction} interface {iface}"
        self._enqueue(cmd)

        self.console.appendPlainText(f"! ACL bound: {cmd}")

    # ==============================================================
    # PENDING COMMAND API
    # ==============================================================

    def get_pending_commands(self, clear=False):
        cmds = list(self.pending_cmds)
        if clear:
            self.pending_cmds.clear()
        return cmds

    def clear_pending_commands(self):
        self.pending_cmds.clear()

    # ==============================================================
    # SYNC FROM CONFIG (ASA FORMAT)
    # ==============================================================

    def sync_from_config(self, conf: ParsedConfig):
        """
        Loads ASA ACLs from running-config.
        Expected lines:
            access-list NAME line X extended <permit|deny> <proto> <src> <dest> [opts]
        """
        self._loading = True
        try:
            self.table.setRowCount(0)
            text = conf.raw_running

            asa_acl_re = re.compile(
                r"^access-list\s+(\S+)\s+line\s+\d+\s+extended\s+(permit|deny)\s+(\S+)\s+(\S+)\s+(\S+)(.*)$",
                re.MULTILINE,
            )

            found_acl_names = set()

            for m in asa_acl_re.finditer(text):
                name, action, proto, src, dest, tail = m.groups()
                tail = tail.strip()

                found_acl_names.add(name)

                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(action))
                self.table.setItem(r, 1, QTableWidgetItem(proto))
                self.table.setItem(r, 2, QTableWidgetItem(src))
                self.table.setItem(r, 3, QTableWidgetItem(dest))
                self.table.setItem(r, 4, QTableWidgetItem(tail))

            if found_acl_names:
                # auto-select first ACL
                self.current_acl_name = next(iter(found_acl_names))
                self.input_acl_name.setText(self.current_acl_name)

            self.console.appendPlainText("[SYNC] ASA ACLs loaded from running-config.")
            self.pending_cmds.clear()

        finally:
            self._loading = False
