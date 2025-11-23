from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPlainTextEdit,
    QHBoxLayout,
    QCheckBox,
    QMessageBox,
)
import ipaddress

from services.parsed_config import ParsedConfig


# ================================================================
#                 WALIDACJA IP / MASK / WILDCARD
# ================================================================


def is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except Exception:
        return False


def is_valid_netmask(mask: str) -> bool:
    try:
        parts = [int(p) for p in mask.split(".")]
        if len(parts) != 4:
            return False
        bits = "".join(f"{p:08b}" for p in parts)
        return "01" not in bits  # maska ciągła np. 11111000....
    except Exception:
        return False


def is_valid_wildcard(w: str) -> bool:
    try:
        parts = [int(p) for p in w.split(".")]
        if len(parts) != 4:
            return False
        for p in parts:
            if p < 0 or p > 255:
                return False
        return True
    except Exception:
        return False


def wildcard_to_mask(w: str) -> str:
    parts = [255 - int(p) for p in w.split(".")]
    return ".".join(str(p) for p in parts)


class RoutingTab(QWidget):
    """
    Pełna, działająca implementacja RoutingTab:
    - Static routing
    - RIP v2 (checkbox enable)
    - OSPF process 1
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.pending_cmds: list[str] = []
        self._loading: bool = False  # blokuje eventy podczas sync/import

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        # === Tytuł ===
        main_layout.addWidget(QLabel("<h2>Routing Configuration</h2>"))

        # === Subtaba ===
        self.subtabs = QTabWidget()
        self.subtabs.addTab(self._make_static_tab(), "Static")
        self.subtabs.addTab(self._make_rip_tab(), "RIP")
        self.subtabs.addTab(self._make_ospf_tab(), "OSPF")
        main_layout.addWidget(self.subtabs, 4)

        # === Konsola lokalna (routing only) ===
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Routing commands preview...")
        self.console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #111;
                color: #0f0;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.console, 2)

    # ============================================================
    #                         STATIC
    # ============================================================

    def _make_static_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- Form ---
        form_box = QGroupBox("Add / Edit Static Route")
        form_layout = QFormLayout(form_box)

        self.static_dest = QLineEdit()
        self.static_mask = QLineEdit()
        self.static_next_hop = QLineEdit()
        self.static_dest.setPlaceholderText("192.168.10.0")
        self.static_mask.setPlaceholderText("255.255.255.0")
        self.static_next_hop.setPlaceholderText("10.0.0.2")

        form_layout.addRow("Destination:", self.static_dest)
        form_layout.addRow("Mask:", self.static_mask)
        form_layout.addRow("Next Hop:", self.static_next_hop)

        row = QHBoxLayout()
        btn_add = QPushButton("Add")
        btn_update = QPushButton("Update")

        btn_add.clicked.connect(self._on_static_add)
        btn_update.clicked.connect(self._on_static_update)

        row.addWidget(btn_add)
        row.addWidget(btn_update)
        form_layout.addRow(row)

        layout.addWidget(form_box)

        # --- Table ---
        self.static_table = QTableWidget(0, 3)
        self.static_table.setHorizontalHeaderLabels(["Destination", "Mask", "Next Hop"])
        self.static_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.static_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.static_table.setSelectionMode(QTableWidget.SingleSelection)
        self.static_table.itemSelectionChanged.connect(
            self._on_static_selection_changed
        )
        layout.addWidget(self.static_table, 1)

        # --- Delete ---
        btn_delete = QPushButton("Delete Route")
        btn_delete.clicked.connect(self._on_static_delete)
        row = QHBoxLayout()
        row.addWidget(btn_delete)
        row.addStretch()
        layout.addLayout(row)

        return tab

    def _get_static_selected_row(self):
        rows = self.static_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _on_static_selection_changed(self):
        if self._loading:
            return
        row = self._get_static_selected_row()
        if row is None:
            return
        self.static_dest.setText(self.static_table.item(row, 0).text())
        self.static_mask.setText(self.static_table.item(row, 1).text())
        self.static_next_hop.setText(self.static_table.item(row, 2).text())

    def _on_static_add(self):
        dest = self.static_dest.text().strip()
        mask = self.static_mask.text().strip()
        nh = self.static_next_hop.text().strip()

        # walidacja
        if not (is_valid_ip(dest) and is_valid_netmask(mask) and is_valid_ip(nh)):
            QMessageBox.warning(
                self, "Błąd", "Wprowadź poprawne Destination / Mask / Next Hop."
            )
            return

        # sprawdź duplikat
        for r in range(self.static_table.rowCount()):
            d = self.static_table.item(r, 0).text()
            m = self.static_table.item(r, 1).text()
            n = self.static_table.item(r, 2).text()
            if d == dest and m == mask and n == nh:
                QMessageBox.information(self, "Info", "Taka trasa już istnieje.")
                return

        r = self.static_table.rowCount()
        self.static_table.insertRow(r)
        self.static_table.setItem(r, 0, QTableWidgetItem(dest))
        self.static_table.setItem(r, 1, QTableWidgetItem(mask))
        self.static_table.setItem(r, 2, QTableWidgetItem(nh))

        self._enqueue([f"ip route {dest} {mask} {nh}"])
        self.static_table.selectRow(r)

    def _on_static_update(self):
        row = self._get_static_selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Najpierw wybierz istniejącą trasę.")
            return

        dest = self.static_dest.text().strip()
        mask = self.static_mask.text().strip()
        nh = self.static_next_hop.text().strip()

        if not (is_valid_ip(dest) and is_valid_netmask(mask) and is_valid_ip(nh)):
            QMessageBox.warning(
                self, "Błąd", "Wprowadź poprawne Destination / Mask / Next Hop."
            )
            return

        old_dest = self.static_table.item(row, 0).text()
        old_mask = self.static_table.item(row, 1).text()
        old_nh = self.static_table.item(row, 2).text()

        if dest == old_dest and mask == old_mask and nh == old_nh:
            return

        cmds = [
            f"no ip route {old_dest} {old_mask} {old_nh}",
            f"ip route {dest} {mask} {nh}",
        ]
        self._enqueue(cmds)

        self.static_table.setItem(row, 0, QTableWidgetItem(dest))
        self.static_table.setItem(row, 1, QTableWidgetItem(mask))
        self.static_table.setItem(row, 2, QTableWidgetItem(nh))

    def _on_static_delete(self):
        row = self._get_static_selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Wybierz trasę do usunięcia.")
            return

        dest = self.static_table.item(row, 0).text()
        mask = self.static_table.item(row, 1).text()
        nh = self.static_table.item(row, 2).text()

        self._enqueue([f"no ip route {dest} {mask} {nh}"])
        self.static_table.removeRow(row)

    # ============================================================
    #                           RIP
    # ============================================================

    def _make_rip_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.rip_enabled = QCheckBox("Enable RIP v2")
        self.rip_enabled.toggled.connect(self._rip_toggle)
        layout.addWidget(self.rip_enabled)

        self.rip_table = QTableWidget(0, 1)
        self.rip_table.setHorizontalHeaderLabels(["Network"])
        self.rip_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rip_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rip_table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.rip_table, 1)

        # Form add
        form = QGroupBox("Add RIP Network")
        f = QFormLayout(form)
        self.rip_net = QLineEdit()
        self.rip_net.setPlaceholderText("10.0.0.0")
        f.addRow("Network:", self.rip_net)

        btn_add = QPushButton("Add")
        btn_add.clicked.connect(self._rip_add)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._rip_delete)
        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_del)
        f.addRow(row)

        layout.addWidget(form)
        return tab

    def _rip_selected_row(self):
        rows = self.rip_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _rip_toggle(self, enabled: bool):
        if self._loading:
            return
        if enabled:
            self._enqueue(["router rip", " version 2", " exit"])
        else:
            self._enqueue(["no router rip"])

    def _rip_add(self):
        net = self.rip_net.text().strip()

        if not is_valid_ip(net):
            QMessageBox.warning(self, "Błąd", "Niepoprawna sieć RIP.")
            return

        if not self.rip_enabled.isChecked():
            QMessageBox.warning(self, "Info", "Najpierw włącz RIP.")
            return

        # duplikaty
        for r in range(self.rip_table.rowCount()):
            if self.rip_table.item(r, 0).text() == net:
                QMessageBox.information(self, "Info", "Ta sieć już istnieje.")
                return

        r = self.rip_table.rowCount()
        self.rip_table.insertRow(r)
        self.rip_table.setItem(r, 0, QTableWidgetItem(net))
        self._enqueue(["router rip", f" network {net}", " exit"])
        self.rip_table.selectRow(r)
        self.rip_net.clear()

    def _rip_delete(self):
        row = self._rip_selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Wybierz sieć do usunięcia.")
            return
        net = self.rip_table.item(row, 0).text()
        self._enqueue(["router rip", f" no network {net}", " exit"])
        self.rip_table.removeRow(row)

    # ============================================================
    #                           OSPF
    # ============================================================

    def _make_ospf_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("<b>OSPF (process 1)</b>"))

        # Table
        self.ospf_table = QTableWidget(0, 3)
        self.ospf_table.setHorizontalHeaderLabels(["Network", "Wildcard", "Area"])

        self.ospf_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ospf_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ospf_table.setSelectionMode(QTableWidget.SingleSelection)
        self.ospf_table.itemSelectionChanged.connect(self._ospf_selection)
        layout.addWidget(self.ospf_table, 1)

        # Form
        form = QGroupBox("Add / Edit OSPF Network")
        f = QFormLayout(form)

        self.ospf_network = QLineEdit()
        self.ospf_wild = QLineEdit()
        self.ospf_area = QLineEdit()

        self.ospf_network.setPlaceholderText("192.168.0.0")
        self.ospf_wild.setPlaceholderText("0.0.0.255")
        self.ospf_area.setPlaceholderText("0")

        f.addRow("Network:", self.ospf_network)
        f.addRow("Wildcard:", self.ospf_wild)
        f.addRow("Area:", self.ospf_area)

        row = QHBoxLayout()
        btn_add = QPushButton("Add")
        btn_update = QPushButton("Update")

        btn_add.clicked.connect(self._on_ospf_add)
        btn_update.clicked.connect(self._on_ospf_update)

        row.addWidget(btn_add)
        row.addWidget(btn_update)
        f.addRow(row)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._ospf_delete)

        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_del)
        f.addRow(row)

        layout.addWidget(form)
        return tab

    def _ospf_selected_row(self):
        rows = self.ospf_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _ospf_selection(self):
        if self._loading:
            return
        row = self._ospf_selected_row()
        if row is None:
            return
        self.ospf_pid.setText(self.ospf_table.item(row, 0).text())
        self.ospf_network.setText(self.ospf_table.item(row, 1).text())
        self.ospf_wild.setText(self.ospf_table.item(row, 2).text())
        self.ospf_area.setText(self.ospf_table.item(row, 3).text())

    def _on_ospf_add(self):
        net = self.ospf_network.text().strip()
        wc = self.ospf_wild.text().strip()
        area = self.ospf_area.text().strip()

        if not (is_valid_ip(net) and is_valid_wildcard(wc)):
            QMessageBox.warning(self, "Błąd", "Niepoprawne Network / Wildcard.")
            return

        if not area.isdigit():
            QMessageBox.warning(self, "Błąd", "Area musi być liczbą.")
            return

        # duplikaty
        for r in range(self.ospf_table.rowCount()):
            if (
                self.ospf_table.item(r, 0).text() == net
                and self.ospf_table.item(r, 1).text() == wc
                and self.ospf_table.item(r, 2).text() == area
            ):
                QMessageBox.information(self, "Info", "Taki wpis OSPF już istnieje.")
                return

        r = self.ospf_table.rowCount()
        self.ospf_table.insertRow(r)
        self.ospf_table.setItem(r, 0, QTableWidgetItem(net))
        self.ospf_table.setItem(r, 1, QTableWidgetItem(wc))
        self.ospf_table.setItem(r, 2, QTableWidgetItem(area))

        cmds = ["router ospf 1", f" network {net} {wc} area {area}", " exit"]
        self._enqueue(cmds)
        self.ospf_table.selectRow(r)

    def _on_ospf_update(self):
        row = self._ospf_selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Wybierz wpis OSPF do aktualizacji.")
            return

        net = self.ospf_network.text().strip()
        wc = self.ospf_wild.text().strip()
        area = self.ospf_area.text().strip()

        if not (is_valid_ip(net) and is_valid_wildcard(wc)):
            QMessageBox.warning(self, "Błąd", "Niepoprawne Network / Wildcard.")
            return

        if not area.isdigit():
            QMessageBox.warning(self, "Błąd", "Area musi być liczbą.")
            return

        old_net = self.ospf_table.item(row, 0).text()
        old_wc = self.ospf_table.item(row, 1).text()
        old_area = self.ospf_table.item(row, 2).text()

        if net == old_net and wc == old_wc and area == old_area:
            return

        cmds = [
            "router ospf 1",
            f" no network {old_net} {old_wc} area {old_area}",
            " exit",
            "router ospf 1",
            f" network {net} {wc} area {area}",
            " exit",
        ]
        self._enqueue(cmds)

        self.ospf_table.setItem(row, 0, QTableWidgetItem(net))
        self.ospf_table.setItem(row, 1, QTableWidgetItem(wc))
        self.ospf_table.setItem(row, 2, QTableWidgetItem(area))

    def _ospf_delete(self):
        row = self._ospf_selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Wybierz wpis OSPF do usunięcia.")
            return

        pid = self.ospf_table.item(row, 0).text()
        net = self.ospf_table.item(row, 1).text()
        w = self.ospf_table.item(row, 2).text()
        area = self.ospf_table.item(row, 3).text()

        self._enqueue(
            [
                f"router ospf {pid}",
                f" no network {net} {w} area {area}",
                " exit",
            ]
        )
        self.ospf_table.removeRow(row)

    # ============================================================
    #                     BUFORY + IMPORT / EXPORT
    # ============================================================

    def _enqueue(self, cmds: list[str]):
        """
        Wysyła komendy:
        - do lokalnego logu taba
        - do globalnej konsoli urządzenia (DeviceDetailWidget)
        - do pending_cmds
        """
        for c in cmds:
            self.console.appendPlainText(c)
            # globalna konsola
            try:
                if hasattr(self.parent(), "append_console"):
                    self.parent().append_console(c)
            except Exception:
                pass

        self.pending_cmds.extend(cmds)

    def get_pending_commands(self, clear=False):
        cmds = list(self.pending_cmds)
        if clear:
            self.pending_cmds = []
        return cmds

    def clear_pending_commands(self):
        self.pending_cmds = []

    def export_state(self):
        data = {
            "static": [],
            "rip_enabled": self.rip_enabled.isChecked(),
            "rip": [],
            "ospf": [],
            "pending_cmds": list(self.pending_cmds),
            "console": self.console.toPlainText(),
        }

        # static
        for r in range(self.static_table.rowCount()):
            row = [
                self.static_table.item(r, 0).text(),
                self.static_table.item(r, 1).text(),
                self.static_table.item(r, 2).text(),
            ]
            data["static"].append(row)

        for r in range(self.rip_table.rowCount()):
            data["rip"].append(self.rip_table.item(r, 0).text())

        for r in range(self.ospf_table.rowCount()):
            data["ospf"].append(
                [
                    self.ospf_table.item(r, 0).text(),
                    self.ospf_table.item(r, 1).text(),
                    self.ospf_table.item(r, 2).text(),
                    self.ospf_table.item(r, 3).text(),
                ]
            )

        return data

    def import_state(self, data):
        self._loading = True
        try:
            # static
            self.static_table.setRowCount(0)
            for row in data.get("static", []):
                r = self.static_table.rowCount()
                self.static_table.insertRow(r)
                self.static_table.setItem(r, 0, QTableWidgetItem(row[0]))
                self.static_table.setItem(r, 1, QTableWidgetItem(row[1]))
                self.static_table.setItem(r, 2, QTableWidgetItem(row[2]))

            # RIP
            self.rip_enabled.setChecked(data.get("rip_enabled", False))
            self.rip_table.setRowCount(0)
            for net in data.get("rip", []):
                r = self.rip_table.rowCount()
                self.rip_table.insertRow(r)
                self.rip_table.setItem(r, 0, QTableWidgetItem(net))

            # OSPF
            self.ospf_table.setRowCount(0)
            for row in data.get("ospf", []):
                r = self.ospf_table.rowCount()
                self.ospf_table.insertRow(r)
                for i in range(4):
                    self.ospf_table.setItem(r, i, QTableWidgetItem(row[i]))

            self.console.setPlainText(data.get("console", ""))
            self.pending_cmds = list(data.get("pending_cmds", []))
        finally:
            self._loading = False

    # ============================================================
    #                     SYNC Z PARSED CONFIG
    # ============================================================

    def sync_from_config(self, conf: ParsedConfig):
        self._loading = True
        try:
            # static
            self.static_table.setRowCount(0)
            for r in conf.routing.static:
                dest, mask, nh = r["dest"], r["mask"], r["nh"]
                row = self.static_table.rowCount()
                self.static_table.insertRow(row)
                self.static_table.setItem(row, 0, QTableWidgetItem(dest))
                self.static_table.setItem(row, 1, QTableWidgetItem(mask))
                self.static_table.setItem(row, 2, QTableWidgetItem(nh))

            # RIP
            self.rip_table.setRowCount(0)
            for net in conf.routing.rip_networks:
                r = self.rip_table.rowCount()
                self.rip_table.insertRow(r)
                self.rip_table.setItem(r, 0, QTableWidgetItem(net))
            self.rip_enabled.setChecked(bool(conf.routing.rip_networks))

            # OSPF
            self.ospf_table.setRowCount(0)
            for o in conf.routing.ospf:
                if o["process"] != "1":
                    continue
                row = self.ospf_table.rowCount()
                self.ospf_table.insertRow(row)
                self.ospf_table.setItem(row, 0, QTableWidgetItem(o["network"]))
                self.ospf_table.setItem(row, 1, QTableWidgetItem(o["wildcard"]))
                self.ospf_table.setItem(row, 2, QTableWidgetItem(o["area"]))

            self.pending_cmds.clear()
            self.console.appendPlainText("[SYNC] Routing updated from running-config.")
        finally:
            self._loading = False
