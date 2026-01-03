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

from operations.Operation import Operation
from operations.OperationEnum import OperationEnum
from services.parsed_config import ParsedConfig
import re


class ACLTab(QWidget):
    """
    ASA-only ACL configuration tab.

    Obsługuje:
      - named ACL w formacie ASA:
            access-list <NAME> extended permit/deny <proto> <src> <dest> [opts]
      - wiązania:
            access-group <NAME> in/out interface <nameif>
      - automatyczne wczytywanie:
            - ACL z running-config
            - access-group powiązań
            - interfejsów + nameif (do wyboru tylko poprawnych nazw)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_acl_name: str | None = None
        self.pending_ops: list[Operation] = []
        self._loading: bool = False

        # lista dostępnych interfejsów: [(nameif, ifname), ...]
        self._iface_map: list[tuple[str, str]] = []

        main = QVBoxLayout(self)
        main.setContentsMargins(20, 15, 20, 15)
        main.setSpacing(10)

        # ----------------------------------------------------------
        # HEADER
        # ----------------------------------------------------------
        main.addWidget(QLabel("<h2>Cisco ASA Access Control Lists (ACL)</h2>"))

        # ----------------------------------------------------------
        # ACL NAME SELECTION
        # ----------------------------------------------------------
        acl_box = QGroupBox("Select or Create ASA ACL (Named)")
        acl_form = QFormLayout(acl_box)

        self.input_acl_name = QLineEdit()
        self.input_acl_name.setPlaceholderText("OUTSIDE-IN, INSIDE-POLICY, ...")

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
        self.proto_input.setPlaceholderText("tcp, udp, icmp, ip (default: ip)")

        self.src_input = QLineEdit()
        self.src_input.setPlaceholderText("any, host 1.1.1.1, 10.0.0.0/24")

        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("any, host 2.2.2.2, 192.168.0.0/24")

        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("optional: eq 80, range 100 200, ...")

        rule_form.addRow("Action:", self.action_combo)
        rule_form.addRow("Protocol:", self.proto_input)
        rule_form.addRow("Source:", self.src_input)
        rule_form.addRow("Destination:", self.dest_input)
        rule_form.addRow("Port Options:", self.port_input)

        btn_add_rule = QPushButton("Add Rule")
        btn_add_rule.clicked.connect(self._add_rule)
        rule_form.addRow(btn_add_rule)

        main.addWidget(rule_box)

        # ----------------------------------------------------------
        # RULE TABLE
        # ----------------------------------------------------------
        self.table_rules = QTableWidget(0, 5)
        self.table_rules.setHorizontalHeaderLabels(
            ["Action", "Protocol", "Source", "Destination", "Port Opts"]
        )
        self.table_rules.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_rules.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_rules.setSelectionMode(QTableWidget.SingleSelection)

        main.addWidget(self.table_rules, 4)

        # Delete rule
        row = QHBoxLayout()
        btn_del_rule = QPushButton("Delete Selected Rule")
        btn_del_rule.clicked.connect(self._delete_rule)
        row.addWidget(btn_del_rule)
        row.addStretch()
        main.addLayout(row)

        # ----------------------------------------------------------
        # BINDINGS (access-group)
        # ----------------------------------------------------------
        bind_box = QGroupBox("Bind ACL to Interface (ASA access-group)")
        bind_form = QFormLayout(bind_box)

        self.iface_combo = QComboBox()
        self.iface_combo.setPlaceholderText("No nameif interfaces found yet")

        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["in", "out"])

        btn_bind = QPushButton("Bind ACL")
        btn_bind.clicked.connect(self._bind_acl)

        bind_form.addRow("Interface (nameif):", self.iface_combo)
        bind_form.addRow("Direction:", self.dir_combo)
        bind_form.addRow(btn_bind)

        # Tabela istniejących wiązań
        self.table_bindings = QTableWidget(0, 3)
        self.table_bindings.setHorizontalHeaderLabels(
            ["ACL Name", "Direction", "Interface (nameif)"]
        )
        self.table_bindings.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_bindings.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_bindings.setSelectionMode(QTableWidget.SingleSelection)

        btn_del_bind = QPushButton("Delete Selected Binding")
        btn_del_bind.clicked.connect(self._delete_binding)

        # Layout dla części pod bind_box
        bind_bottom = QVBoxLayout()
        bind_bottom.addWidget(self.table_bindings, 1)

        row_bind = QHBoxLayout()
        row_bind.addWidget(btn_del_bind)
        row_bind.addStretch()
        bind_bottom.addLayout(row_bind)

        # Dodajemy do głównego layoutu:
        main.addWidget(bind_box)  # bind_form jest wewnątrz bind_box
        main.addLayout(bind_bottom)  # tabela + delete-button — osobny layout

        # ----------------------------------------------------------
        # CONSOLE
        # ----------------------------------------------------------
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("ASA ACL command preview...")
        self.console.setStyleSheet(
            "background-color:#111; color:#0f0; font-family:monospace; font-size:12px;"
        )
        main.addWidget(self.console, 2)

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

        # Dodaj do tabeli reguł
        r = self.table_rules.rowCount()
        self.table_rules.insertRow(r)
        self.table_rules.setItem(r, 0, QTableWidgetItem(action))
        self.table_rules.setItem(r, 1, QTableWidgetItem(proto))
        self.table_rules.setItem(r, 2, QTableWidgetItem(src))
        self.table_rules.setItem(r, 3, QTableWidgetItem(dest))
        self.table_rules.setItem(r, 4, QTableWidgetItem(port))

        # Do bufora
        self.pending_ops.append(
            Operation(
                OperationEnum.ADD_ACL_RULE,
                acl_name=self.current_acl_name,
                action=action,
                protocol=proto,
                src=src,
                dest=dest,
                port=port or None,
            )
        )
        self.console.appendPlainText(
            f"[OP] added ACL {self.current_acl_name} rule"
        )

        # Wyczyść inputy
        self.proto_input.clear()
        self.src_input.clear()
        self.dest_input.clear()
        self.port_input.clear()

    # ==============================================================
    # DELETE RULE
    # ==============================================================

    def _delete_rule(self):
        r = self.table_rules.currentRow()
        if r == -1:
            QMessageBox.information(self, "Info", "Select rule to delete.")
            return

        if not self.current_acl_name:
            QMessageBox.warning(self, "Error", "No ACL selected.")
            return

        action = self.table_rules.item(r, 0).text()
        proto = self.table_rules.item(r, 1).text()
        src = self.table_rules.item(r, 2).text()
        dest = self.table_rules.item(r, 3).text()
        port = self.table_rules.item(r, 4).text()

        self.pending_ops.append(
            Operation(
                OperationEnum.DEL_ACL_RULE,
                acl_name=self.current_acl_name,
                action=action,
                protocol=proto,
                src=src,
                dest=dest,
                port=port or None,
            )
        )
        self.console.appendPlainText(
            f"[OP] removed ACL {self.current_acl_name} rule"
        )
        self.table_rules.removeRow(r)

    # ==============================================================
    # BIND ACL TO INTERFACE (access-group)
    # ==============================================================

    def _bind_acl(self):
        if not self.current_acl_name:
            QMessageBox.warning(self, "Error", "Select ACL first.")
            return

        if self.iface_combo.count() == 0:
            QMessageBox.warning(self, "Error", "No ASA interfaces with nameif found.")
            return

        idx = self.iface_combo.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Error", "Select interface (nameif).")
            return

        nameif = self.iface_combo.currentData()  # przechowujemy tu nameif
        direction = self.dir_combo.currentText()

        # Jeśli istnieje już inne wiązanie dla tego interfejsu+direction, generujemy no access-group
        existing_row = self._find_binding_row(direction, nameif)
        if existing_row is not None:
            old_acl = self.table_bindings.item(existing_row, 0).text()
            if old_acl != self.current_acl_name:
                self.pending_ops.append(
                    Operation(
                        OperationEnum.UNBIND_ACL,
                        acl_name=old_acl,
                        direction=direction,
                        interface=nameif,
                    )
                )
                self.table_bindings.removeRow(existing_row)

        # Dodaj nowe wiązanie
        self.pending_ops.append(
            Operation(
                OperationEnum.UNBIND_ACL,
                acl_name=self.current_acl_name,
                direction=direction,
                interface=nameif,
            )
        )
        self.console.appendPlainText(
            f"[OP] bound ACL {self.current_acl_name} to {nameif} interface."
        )

        r = self.table_bindings.rowCount()
        self.table_bindings.insertRow(r)
        self.table_bindings.setItem(r, 0, QTableWidgetItem(self.current_acl_name))
        self.table_bindings.setItem(r, 1, QTableWidgetItem(direction))
        self.table_bindings.setItem(r, 2, QTableWidgetItem(nameif))

    def _find_binding_row(self, direction: str, nameif: str):
        for r in range(self.table_bindings.rowCount()):
            dir_val = self.table_bindings.item(r, 1).text()
            iface_val = self.table_bindings.item(r, 2).text()
            if dir_val == direction and iface_val == nameif:
                return r
        return None

    def _delete_binding(self):
        r = self.table_bindings.currentRow()
        if r == -1:
            QMessageBox.information(self, "Info", "Select binding to delete.")
            return

        acl = self.table_bindings.item(r, 0).text()
        direction = self.table_bindings.item(r, 1).text()
        nameif = self.table_bindings.item(r, 2).text()

        self.pending_ops.append(
            Operation(
                OperationEnum.UNBIND_ACL,
                acl_name=acl,
                direction=direction,
                interface=nameif,
            )
        )
        self.console.appendPlainText(
            f"[OP] unbound ACL {acl}"
        )
        self.table_bindings.removeRow(r)

    # ==============================================================
    # PENDING COMMAND API
    # ==============================================================

    def get_pending_operations(self, clear=False) -> list[Operation]:
        ops = list(self.pending_ops)
        if clear:
            self.pending_ops.clear()
        return ops

    def clear_pending_operations(self):
        self.pending_ops.clear()

    # ==============================================================
    # SYNC FROM CONFIG (ASA FORMAT + INTERFACES + BINDINGS)
    # ==============================================================

    def sync_from_config(self, conf: ParsedConfig):
        """
        Wczytuje z running-config ASA:
          - reguły ACL:
                access-list NAME extended ...
                access-list NAME line X extended ...
          - wiązania:
                access-group NAME in/out interface nameif
          - interfejsy z nameif:
                interface Gi0/0
                 nameif outside
        """
        self._loading = True
        try:
            self.table_rules.setRowCount(0)
            self.table_bindings.setRowCount(0)
            self.pending_ops.clear()
            self._iface_map.clear()
            self.iface_combo.clear()

            text = conf.raw_running or ""
            lines = text.splitlines()

            # 1) Interfejsy + nameif
            self._parse_interfaces_with_nameif(lines)
            self._populate_iface_combo()

            # 2) ACL-e (access-list NAME [line X] extended ...)
            self._parse_asa_acls(text)

            # 3) access-group powiązania
            self._parse_access_groups(text)

            self.console.appendPlainText(
                "[SYNC] ASA ACLs and bindings loaded from running-config."
            )

            # auto-select pierwszej ACL jeśli żadna nie ustawiona
            if self.current_acl_name is None and self.table_rules.rowCount() > 0:
                # spróbuj zebrać unikalne nazwy ACL z rules
                # (tu ich nie trzymamy per wiersz, więc jeśli chcesz multi-ACL
                #  trzeba by rozbudować model; na razie zakładamy jedną ACL na tab)
                pass

        finally:
            self._loading = False

    # --------------------------------------------------------------
    # Parsing helpers
    # --------------------------------------------------------------

    def _parse_interfaces_with_nameif(self, lines: list[str]):
        """
        Szuka bloków:
            interface Gi0/0
             nameif outside
        i buduje listę (nameif, interface_name).
        """
        iface_re = re.compile(r"^interface\s+(\S+)")
        nameif_re = re.compile(r"^\s*nameif\s+(\S+)")

        current_iface = None

        for line in lines:
            m_if = iface_re.match(line)
            if m_if:
                current_iface = m_if.group(1)
                continue

            if current_iface:
                m_nm = nameif_re.match(line)
                if m_nm:
                    nameif = m_nm.group(1)
                    self._iface_map.append((nameif, current_iface))
                    # nie resetujemy current_iface, bo inne komendy też mogą być w bloku
                    # ale nameif mamy już zapisany
                    continue

    def _populate_iface_combo(self):
        self.iface_combo.clear()
        for nameif, ifname in self._iface_map:
            label = f"{nameif} ({ifname})"
            self.iface_combo.addItem(label, userData=nameif)

    def _parse_asa_acls(self, text: str):
        """
        Szuka obu form:
          access-list NAME extended ...
          access-list NAME line X extended ...
        i wypełnia table_rules.
        """
        # Opcjonalne 'line N'
        acl_re = re.compile(
            r"^access-list\s+(\S+)\s+(?:line\s+\d+\s+)?extended\s+"
            r"(permit|deny)\s+(\S+)\s+(\S+)\s+(\S+)(.*)$",
            re.MULTILINE,
        )

        for m in acl_re.finditer(text):
            name, action, proto, src, dest, tail = m.groups()
            tail = (tail or "").strip()

            r = self.table_rules.rowCount()
            self.table_rules.insertRow(r)
            self.table_rules.setItem(r, 0, QTableWidgetItem(action))
            self.table_rules.setItem(r, 1, QTableWidgetItem(proto))
            self.table_rules.setItem(r, 2, QTableWidgetItem(src))
            self.table_rules.setItem(r, 3, QTableWidgetItem(dest))
            self.table_rules.setItem(r, 4, QTableWidgetItem(tail))

            # jeśli nie mamy jeszcze current_acl_name, ustaw z pierwszej znalezionej
            if self.current_acl_name is None:
                self.current_acl_name = name
                self.input_acl_name.setText(name)

    def _parse_access_groups(self, text: str):
        """
        Szuka access-group:
            access-group NAME in/out interface NAMEIF
        i wypełnia table_bindings.
        """
        ag_re = re.compile(
            r"^access-group\s+(\S+)\s+(in|out)\s+interface\s+(\S+)",
            re.MULTILINE,
        )

        for m in ag_re.finditer(text):
            acl, direction, nameif = m.groups()
            r = self.table_bindings.rowCount()
            self.table_bindings.insertRow(r)
            self.table_bindings.setItem(r, 0, QTableWidgetItem(acl))
            self.table_bindings.setItem(r, 1, QTableWidgetItem(direction))
            self.table_bindings.setItem(r, 2, QTableWidgetItem(nameif))

            # jeśli ACL nie ustawione, a znaleźliśmy binding, weź nazwę z bindingu
            if self.current_acl_name is None:
                self.current_acl_name = acl
                self.input_acl_name.setText(acl)
