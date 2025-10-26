from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QGroupBox, QFormLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QPlainTextEdit
)
from PySide6.QtCore import Qt


class RoutingTab(QWidget):
    """
    Dummy zakładka ROUTING z podzakładkami Static / RIP / OSPF
    (styl Packet Tracera, na razie czysto wizualny mock).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

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

        # === Dolny log (dummy) ===
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

    # === STATIC ROUTING ===
    def _make_static_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_box = QGroupBox("Add Static Route")
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

        btn_add = QPushButton("Add Route")
        btn_add.clicked.connect(self._dummy_add_static)
        form_layout.addRow(btn_add)
        layout.addWidget(form_box)

        # --- Tabela tras ---
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Destination", "Mask", "Next Hop"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.static_table = table
        layout.addWidget(table)

        layout.addStretch()
        return tab

    # === RIP ROUTING ===
    def _make_rip_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("<b>RIPv2 Configuration</b>"))
        self.btn_rip_enable = QPushButton("Enable RIP")
        self.btn_rip_disable = QPushButton("Disable RIP")
        self.btn_rip_enable.clicked.connect(lambda: self._append_console("> router rip\n version 2\n"))
        self.btn_rip_disable.clicked.connect(lambda: self._append_console("> no router rip\n"))
        layout.addWidget(self.btn_rip_enable)
        layout.addWidget(self.btn_rip_disable)

        net_box = QGroupBox("Networks")
        net_layout = QFormLayout(net_box)
        self.rip_network = QLineEdit()
        self.rip_network.setPlaceholderText("e.g. 10.0.0.0")
        btn_add = QPushButton("Add Network")
        btn_add.clicked.connect(self._dummy_add_rip)
        net_layout.addRow("Network:", self.rip_network)
        net_layout.addRow(btn_add)
        layout.addWidget(net_box)

        layout.addStretch()
        return tab

    # === OSPF ROUTING ===
    def _make_ospf_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("<b>OSPF Configuration</b>"))

        form = QFormLayout()
        self.ospf_process = QLineEdit()
        self.ospf_network = QLineEdit()
        self.ospf_wildcard = QLineEdit()
        self.ospf_area = QLineEdit()

        self.ospf_process.setPlaceholderText("e.g. 1")
        self.ospf_network.setPlaceholderText("e.g. 192.168.0.0")
        self.ospf_wildcard.setPlaceholderText("e.g. 0.0.0.255")
        self.ospf_area.setPlaceholderText("e.g. 0")

        form.addRow("Process ID:", self.ospf_process)
        form.addRow("Network:", self.ospf_network)
        form.addRow("Wildcard:", self.ospf_wildcard)
        form.addRow("Area:", self.ospf_area)

        btn_add = QPushButton("Add OSPF Network")
        btn_add.clicked.connect(self._dummy_add_ospf)
        form.addRow(btn_add)

        layout.addLayout(form)
        layout.addStretch()
        return tab

    # === Dummy actions ===
    def _dummy_add_static(self):
        dest = self.static_dest.text().strip()
        mask = self.static_mask.text().strip()
        nh = self.static_next_hop.text().strip()
        if not (dest and mask and nh):
            return
        row = self.static_table.rowCount()
        self.static_table.insertRow(row)
        self.static_table.setItem(row, 0, QTableWidgetItem(dest))
        self.static_table.setItem(row, 1, QTableWidgetItem(mask))
        self.static_table.setItem(row, 2, QTableWidgetItem(nh))
        self._append_console(f"ip route {dest} {mask} {nh}")
        self.static_dest.clear()
        self.static_mask.clear()
        self.static_next_hop.clear()

    def _dummy_add_rip(self):
        net = self.rip_network.text().strip()
        if not net:
            return
        self._append_console(f"router rip\n network {net}")
        self.rip_network.clear()

    def _dummy_add_ospf(self):
        p = self.ospf_process.text().strip()
        net = self.ospf_network.text().strip()
        wc = self.ospf_wildcard.text().strip()
        area = self.ospf_area.text().strip()
        if not (p and net and wc and area):
            return
        self._append_console(f"router ospf {p}\n network {net} {wc} area {area}")
        self.ospf_process.clear()
        self.ospf_network.clear()
        self.ospf_wildcard.clear()
        self.ospf_area.clear()

    def _append_console(self, text):
        """Dodaje wiersz do dolnego loga."""
        self.console.appendPlainText(text.strip())