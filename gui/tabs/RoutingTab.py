# gui/tabs/RoutingTab.py
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

from services.parsed_config import ParsedConfig


class RoutingTab(QWidget):
    """
    Realna zakładka ROUTING z podzakładkami Static / RIP / OSPF.

    - Static:
        * tabela tras
        * Add / Update Route => ip route / no ip route
        * Delete Route => no ip route
    - RIP:
        * checkbox Enable RIP v2
        * tabela sieci
        * Add Network / Delete Network
        * komendy: router rip, version 2, network / no network, no router rip
    - OSPF:
        * wspieramy tylko process 1
        * tabela wpisów: PID, Network, Wildcard, Area
        * Add / Update / Delete wpisu
        * komendy: router ospf 1, network / no network
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.pending_cmds: list[str] = []
        self._loading: bool = False  # blokuje eventy przy sync/import

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        # === Nagłówek ===
        main_layout.addWidget(QLabel("<h2>Routing Configuration</h2>"))

        # === TabWidget z podsekcjami ===
        self.subtabs = QTabWidget()
        self.subtabs.setTabPosition(QTabWidget.North)
        self.subtabs.addTab(self._make_static_tab(), "Static")
        self.subtabs.addTab(self._make_rip_tab(), "RIP")
        self.subtabs.addTab(self._make_ospf_tab(), "OSPF")
        main_layout.addWidget(self.subtabs, 4)

        # === Dolny log (CLI preview) ===
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
    #                           STATIC
    # ============================================================

    def _make_static_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- formularz ---
        form_box = QGroupBox("Add / Edit Static Route")
        form_layout = QFormLayout(form_box)

        self.static_dest = QLineEdit()
        self.static_mask = QLineEdit()
        self.static_next_hop = QLineEdit()
        self.static_dest.setPlaceholderText("e.g. 192.168.10.0")
        self.static_mask.setPlaceholderText("e.g. 255.255.255.0")
        self.static_next_hop.setPlaceholderText("e.g. 10.0.0.2")

        form_layout.addRow("Destination:", self.static_dest)
        form_layout.addRow("Mask:", self.static_mask)
        form_layout.addRow("Next Hop:", self.static_next_hop)

        btn_add_update = QPushButton("Add / Update Route")
        btn_add_update.clicked.connect(self._on_static_add_update)
        form_layout.addRow(btn_add_update)
        layout.addWidget(form_box)

        # --- tabela tras ---
        self.static_table = QTableWidget(0, 3)
        self.static_table.setHorizontalHeaderLabels(["Destination", "Mask", "Next Hop"])
        self.static_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.static_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.static_table.setSelectionMode(QTableWidget.SingleSelection)
        self.static_table.itemSelectionChanged.connect(
            self._on_static_selection_changed
        )
        layout.addWidget(self.static_table, 1)

        # --- przyciski operacyjne ---
        btn_row = QHBoxLayout()
        btn_delete = QPushButton("Delete Route")
        btn_delete.clicked.connect(self._on_static_delete)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        return tab

    def _get_static_selected_row(self):
        rows = self.static_table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _on_static_selection_changed(self):
        if self._loading:
            return
        row = self._get_static_selected_row()
        if row is None:
            return
        d = self.static_table.item(row, 0)
        m = self.static_table.item(row, 1)
        nh = self.static_table.item(row, 2)
        self.static_dest.setText(d.text() if d else "")
        self.static_mask.setText(m.text() if m else "")
        self.static_next_hop.setText(nh.text() if nh else "")

    def _on_static_add_update(self):
        dest = self.static_dest.text().strip()
        mask = self.static_mask.text().strip()
        nh = self.static_next_hop.text().strip()

        if not dest or not mask or not nh:
            QMessageBox.warning(
                self,
                "Błąd",
                "Destination, mask i next hop są wymagane.",
            )
            return

        # Czy jest zaznaczony istniejący wpis?
        row = self._get_static_selected_row()

        if row is None:
            # Dodanie nowej trasy
            # Sprawdź, czy taka trasa już istnieje
            for r in range(self.static_table.rowCount()):
                d = self.static_table.item(r, 0).text()
                m = self.static_table.item(r, 1).text()
                n = self.static_table.item(r, 2).text()
                if d == dest and m == mask and n == nh:
                    QMessageBox.information(
                        self,
                        "Info",
                        "Taka trasa statyczna już istnieje.",
                    )
                    return

            r = self.static_table.rowCount()
            self.static_table.insertRow(r)
            self.static_table.setItem(r, 0, QTableWidgetItem(dest))
            self.static_table.setItem(r, 1, QTableWidgetItem(mask))
            self.static_table.setItem(r, 2, QTableWidgetItem(nh))

            cmds = [f"ip route {dest} {mask} {nh}"]
            self._enqueue(cmds)
        else:
            # Aktualizacja istniejącej trasy
            old_dest = self.static_table.item(row, 0).text()
            old_mask = self.static_table.item(row, 1).text()
            old_nh = self.static_table.item(row, 2).text()

            if dest == old_dest and mask == old_mask and nh == old_nh:
                # nic się nie zmieniło
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

        reply = QMessageBox.question(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz usunąć trasę:\n{dest} {mask} {nh}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        cmds = [f"no ip route {dest} {mask} {nh}"]
        self._enqueue(cmds)
        self.static_table.removeRow(row)
        self.static_dest.clear()
        self.static_mask.clear()
        self.static_next_hop.clear()

    # ============================================================
    #                             RIP
    # ============================================================

    def _make_rip_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- enable RIP ---
        self.rip_enabled = QCheckBox("Enable RIP v2")
        self.rip_enabled.setToolTip(
            "Włącza/wyłącza proces RIP na urządzeniu (router rip, version 2)."
        )
        self.rip_enabled.toggled.connect(self._on_rip_enable_toggled)
        layout.addWidget(self.rip_enabled)

        # --- tabela sieci ---
        self.rip_table = QTableWidget(0, 1)
        self.rip_table.setHorizontalHeaderLabels(["Network"])
        self.rip_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rip_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rip_table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.rip_table, 1)

        # --- formularz dodawania sieci ---
        form_box = QGroupBox("Add RIP Network")
        form_layout = QFormLayout(form_box)
        self.rip_network = QLineEdit()
        self.rip_network.setPlaceholderText("e.g. 10.0.0.0")
        form_layout.addRow("Network:", self.rip_network)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add Network")
        btn_add.clicked.connect(self._on_rip_add_network)
        btn_del = QPushButton("Delete Selected Network")
        btn_del.clicked.connect(self._on_rip_delete_network)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        form_layout.addRow(btn_row)

        layout.addWidget(form_box)
        layout.addStretch()
        return tab

    def _rip_get_selected_row(self):
        rows = self.rip_table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _on_rip_enable_toggled(self, enabled: bool):
        if self._loading:
            return

        cmds: list[str] = []
        if enabled:
            cmds += ["router rip", " version 2", " exit"]
        else:
            cmds += ["no router rip"]
        self._enqueue(cmds)

    def _on_rip_add_network(self):
        net = self.rip_network.text().strip()
        if not net:
            QMessageBox.warning(self, "Błąd", "Podaj sieć (network).")
            return

        # opcjonalnie wymagamy, aby RIP był włączony
        if not self.rip_enabled.isChecked():
            QMessageBox.information(
                self,
                "Info",
                "Najpierw włącz RIP (Enable RIP v2), aby dodawać sieci.",
            )
            return

        # duplikaty
        for r in range(self.rip_table.rowCount()):
            if self.rip_table.item(r, 0).text() == net:
                QMessageBox.information(
                    self,
                    "Info",
                    f"Sieć {net} jest już w konfiguracji RIP.",
                )
                return

        r = self.rip_table.rowCount()
        self.rip_table.insertRow(r)
        self.rip_table.setItem(r, 0, QTableWidgetItem(net))

        cmds = ["router rip", f" network {net}", " exit"]
        self._enqueue(cmds)
        self.rip_network.clear()

    def _on_rip_delete_network(self):
        row = self._rip_get_selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Wybierz sieć RIP do usunięcia.")
            return

        net = self.rip_table.item(row, 0).text()
        reply = QMessageBox.question(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz usunąć sieć RIP {net}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        cmds = ["router rip", f" no network {net}", " exit"]
        self._enqueue(cmds)
        self.rip_table.removeRow(row)

    # ============================================================
    #                             OSPF
    # ============================================================

    def _make_ospf_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("<b>OSPF Configuration (process 1)</b>"))

        # --- tabela wpisów OSPF ---
        self.ospf_table = QTableWidget(0, 4)
        self.ospf_table.setHorizontalHeaderLabels(
            ["Process ID", "Network", "Wildcard", "Area"]
        )
        self.ospf_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ospf_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ospf_table.setSelectionMode(QTableWidget.SingleSelection)
        self.ospf_table.itemSelectionChanged.connect(self._on_ospf_selection_changed)
        layout.addWidget(self.ospf_table, 1)

        # --- formularz dodawania/edycji ---
        form_box = QGroupBox("Add / Edit OSPF Network")
        form_layout = QFormLayout(form_box)

        self.ospf_process = QLineEdit("1")
        self.ospf_process.setToolTip("Process ID (obsługujemy tylko 1).")
        self.ospf_network = QLineEdit()
        self.ospf_wildcard = QLineEdit()
        self.ospf_area = QLineEdit()

        self.ospf_network.setPlaceholderText("e.g. 192.168.0.0")
        self.ospf_wildcard.setPlaceholderText("e.g. 0.0.0.255")
        self.ospf_area.setPlaceholderText("e.g. 0")

        form_layout.addRow("Process ID:", self.ospf_process)
        form_layout.addRow("Network:", self.ospf_network)
        form_layout.addRow("Wildcard:", self.ospf_wildcard)
        form_layout.addRow("Area:", self.ospf_area)

        btn_row = QHBoxLayout()
        btn_add_update = QPushButton("Add / Update")
        btn_add_update.clicked.connect(self._on_ospf_add_update)
        btn_delete = QPushButton("Delete")
        btn_delete.clicked.connect(self._on_ospf_delete)
        btn_row.addWidget(btn_add_update)
        btn_row.addWidget(btn_delete)
        form_layout.addRow(btn_row)

        layout.addWidget(form_box)
        layout.addStretch()
        return tab

    def _ospf_get_selected_row(self):
        rows = self.ospf_table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _on_ospf_selection_changed(self):
        if self._loading:
            return
        row = self._ospf_get_selected_row()
        if row is None:
            return
        pid = self.ospf_table.item(row, 0).text()
        net = self.ospf_table.item(row, 1).text()
        wc = self.ospf_table.item(row, 2).text()
        area = self.ospf_table.item(row, 3).text()
        self.ospf_process.setText(pid)
        self.ospf_network.setText(net)
        self.ospf_wildcard.setText(wc)
        self.ospf_area.setText(area)

    def _on_ospf_add_update(self):
        pid = self.ospf_process.text().strip() or "1"
        net = self.ospf_network.text().strip()
        wc = self.ospf_wildcard.text().strip()
        area = self.ospf_area.text().strip()

        if pid != "1":
            QMessageBox.warning(
                self,
                "Błąd",
                "Obsługujemy tylko OSPF process 1.",
            )
            self.ospf_process.setText("1")
            return

        if not net or not wc or not area:
            QMessageBox.warning(
                self,
                "Błąd",
                "Network, wildcard i area są wymagane.",
            )
            return

        row = self._ospf_get_selected_row()

        if row is None:
            # Dodanie nowego wpisu
            for r in range(self.ospf_table.rowCount()):
                if (
                    self.ospf_table.item(r, 0).text() == pid
                    and self.ospf_table.item(r, 1).text() == net
                    and self.ospf_table.item(r, 2).text() == wc
                    and self.ospf_table.item(r, 3).text() == area
                ):
                    QMessageBox.information(
                        self,
                        "Info",
                        "Taki wpis OSPF już istnieje.",
                    )
                    return

            r = self.ospf_table.rowCount()
            self.ospf_table.insertRow(r)
            self.ospf_table.setItem(r, 0, QTableWidgetItem(pid))
            self.ospf_table.setItem(r, 1, QTableWidgetItem(net))
            self.ospf_table.setItem(r, 2, QTableWidgetItem(wc))
            self.ospf_table.setItem(r, 3, QTableWidgetItem(area))

            cmds = [
                f"router ospf {pid}",
                f" network {net} {wc} area {area}",
                " exit",
            ]
            self._enqueue(cmds)
        else:
            # Aktualizacja istniejącego wpisu
            old_pid = self.ospf_table.item(row, 0).text()
            old_net = self.ospf_table.item(row, 1).text()
            old_wc = self.ospf_table.item(row, 2).text()
            old_area = self.ospf_table.item(row, 3).text()

            if pid == old_pid and net == old_net and wc == old_wc and area == old_area:
                return

            cmds = [
                f"router ospf {old_pid}",
                f" no network {old_net} {old_wc} area {old_area}",
                " exit",
                f"router ospf {pid}",
                f" network {net} {wc} area {area}",
                " exit",
            ]
            self._enqueue(cmds)

            self.ospf_table.setItem(row, 0, QTableWidgetItem(pid))
            self.ospf_table.setItem(row, 1, QTableWidgetItem(net))
            self.ospf_table.setItem(row, 2, QTableWidgetItem(wc))
            self.ospf_table.setItem(row, 3, QTableWidgetItem(area))

    def _on_ospf_delete(self):
        row = self._ospf_get_selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "Wybierz wpis OSPF do usunięcia.")
            return

        pid = self.ospf_table.item(row, 0).text()
        net = self.ospf_table.item(row, 1).text()
        wc = self.ospf_table.item(row, 2).text()
        area = self.ospf_table.item(row, 3).text()

        reply = QMessageBox.question(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz usunąć wpis OSPF:\n"
            f"process {pid}, network {net} {wc} area {area}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        cmds = [
            f"router ospf {pid}",
            f" no network {net} {wc} area {area}",
            " exit",
        ]
        self._enqueue(cmds)
        self.ospf_table.removeRow(row)

    # ============================================================
    #                       BUFORY / PENDING
    # ============================================================

    def _enqueue(self, cmds: list[str]):
        for c in cmds:
            self.console.appendPlainText(c.rstrip())
        self.pending_cmds.extend(cmds)

    def get_pending_commands(self, clear: bool = False) -> list[str]:
        cmds = list(self.pending_cmds)
        if clear:
            self.pending_cmds.clear()
        return cmds

    def clear_pending_commands(self):
        self.pending_cmds.clear()

    def export_state(self) -> dict:
        # Static
        static_rows = []
        for r in range(self.static_table.rowCount()):
            d = self.static_table.item(r, 0)
            m = self.static_table.item(r, 1)
            nh = self.static_table.item(r, 2)
            static_rows.append(
                [
                    d.text() if d else "",
                    m.text() if m else "",
                    nh.text() if nh else "",
                ]
            )

        # RIP
        rip_enabled = self.rip_enabled.isChecked()
        rip_networks = []
        for r in range(self.rip_table.rowCount()):
            net = self.rip_table.item(r, 0)
            rip_networks.append(net.text() if net else "")

        # OSPF
        ospf_rows = []
        for r in range(self.ospf_table.rowCount()):
            pid = self.ospf_table.item(r, 0)
            net = self.ospf_table.item(r, 1)
            wc = self.ospf_table.item(r, 2)
            area = self.ospf_table.item(r, 3)
            ospf_rows.append(
                [
                    pid.text() if pid else "",
                    net.text() if net else "",
                    wc.text() if wc else "",
                    area.text() if area else "",
                ]
            )

        return {
            "static_rows": static_rows,
            "rip_enabled": rip_enabled,
            "rip_networks": rip_networks,
            "ospf_rows": ospf_rows,
            "console": self.console.toPlainText(),
            "pending_cmds": list(self.pending_cmds),
        }

    def import_state(self, data: dict):
        self._loading = True
        try:
            # Static
            self.static_table.setRowCount(0)
            for row in data.get("static_rows", []):
                dest = row[0] if len(row) > 0 else ""
                mask = row[1] if len(row) > 1 else ""
                nh = row[2] if len(row) > 2 else ""
                r = self.static_table.rowCount()
                self.static_table.insertRow(r)
                self.static_table.setItem(r, 0, QTableWidgetItem(dest))
                self.static_table.setItem(r, 1, QTableWidgetItem(mask))
                self.static_table.setItem(r, 2, QTableWidgetItem(nh))

            # RIP
            self.rip_table.setRowCount(0)
            self.rip_enabled.setChecked(data.get("rip_enabled", False))
            for net in data.get("rip_networks", []):
                r = self.rip_table.rowCount()
                self.rip_table.insertRow(r)
                self.rip_table.setItem(r, 0, QTableWidgetItem(net))

            # OSPF
            self.ospf_table.setRowCount(0)
            for row in data.get("ospf_rows", []):
                pid = row[0] if len(row) > 0 else ""
                net = row[1] if len(row) > 1 else ""
                wc = row[2] if len(row) > 2 else ""
                area = row[3] if len(row) > 3 else ""
                r = self.ospf_table.rowCount()
                self.ospf_table.insertRow(r)
                self.ospf_table.setItem(r, 0, QTableWidgetItem(pid))
                self.ospf_table.setItem(r, 1, QTableWidgetItem(net))
                self.ospf_table.setItem(r, 2, QTableWidgetItem(wc))
                self.ospf_table.setItem(r, 3, QTableWidgetItem(area))

            self.console.setPlainText(data.get("console", ""))
            self.pending_cmds = list(data.get("pending_cmds", []))
        finally:
            self._loading = False

    # ============================================================
    #                     SYNC Z PARSED CONFIG
    # ============================================================

    def sync_from_config(self, conf: ParsedConfig):
        """
        Wypełnia zakładkę Static / RIP / OSPF na podstawie ParsedConfig.
        Czyści pending_cmds (snapshot = nowa prawda).
        """
        self._loading = True
        try:
            # --- Static ---
            self.static_table.setRowCount(0)
            for route in conf.routing.static:
                dest = route.get("dest", "")
                mask = route.get("mask", "")
                nh = route.get("nh", "")
                r = self.static_table.rowCount()
                self.static_table.insertRow(r)
                self.static_table.setItem(r, 0, QTableWidgetItem(dest))
                self.static_table.setItem(r, 1, QTableWidgetItem(mask))
                self.static_table.setItem(r, 2, QTableWidgetItem(nh))

            # --- RIP ---
            self.rip_table.setRowCount(0)
            for net in conf.routing.rip_networks:
                r = self.rip_table.rowCount()
                self.rip_table.insertRow(r)
                self.rip_table.setItem(r, 0, QTableWidgetItem(net))
            # heurystyka: jeśli są sieci RIP, uznajemy, że RIP jest włączony
            self.rip_enabled.setChecked(bool(conf.routing.rip_networks))

            # --- OSPF (tylko process 1) ---
            self.ospf_table.setRowCount(0)
            for o in conf.routing.ospf:
                if o.get("process") != "1":
                    continue
                net = o.get("network", "")
                wc = o.get("wildcard", "")
                area = o.get("area", "")
                r = self.ospf_table.rowCount()
                self.ospf_table.insertRow(r)
                self.ospf_table.setItem(r, 0, QTableWidgetItem("1"))
                self.ospf_table.setItem(r, 1, QTableWidgetItem(net))
                self.ospf_table.setItem(r, 2, QTableWidgetItem(wc))
                self.ospf_table.setItem(r, 3, QTableWidgetItem(area))

            # po syncu pendingi resetujemy
            self.pending_cmds.clear()
            self.console.appendPlainText("[SYNC] Routing updated from running-config.")
        finally:
            self._loading = False
