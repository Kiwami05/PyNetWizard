from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QLineEdit,
    QSpinBox,
)
from PySide6.QtCore import Qt


from gui.tabs.InterfacesTab import InterfacesTab
from services.parsed_config import ParsedConfig
from gui.tabs.InterfacesTab import cidr_to_mask, mask_to_cidr  # wykorzystujemy helpery


class SwitchInterfacesTab(InterfacesTab):
    """
    Wersja InterfacesTab dla switchy:
    - dziedziczy z bazowego InterfacesTab,
    - dodaje kolumnę Mode (access/trunk/routed),
    - obsługuje komendy switchport/no switchport.
    """

    COL_NAME = 0
    COL_DESC = 1
    COL_IP = 2
    COL_MASK = 3
    COL_MODE = 4
    COL_STATUS = 5

    def __init__(self, parent=None):
        super().__init__(parent)

        # Przebuduj tabelę: teraz ma 6 kolumn
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Description", "IP Address", "Mask (/CIDR)", "Mode", "Status"]
        )

    # ================================================================
    #                 NADPISANE TWORZENIE WIERSZA
    # ================================================================

    def _create_interface_row(self, name, desc, ip, cidr_str, mode, status):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # NAME
        item_name = self.table.item(row, self.COL_NAME)
        if not item_name:
            from PySide6.QtWidgets import QTableWidgetItem
            item_name = QTableWidgetItem(name)
            item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, self.COL_NAME, item_name)

        # DESC
        edit_desc = QLineEdit(desc)
        edit_desc.setToolTip("Opis interfejsu (opcjonalny).")
        edit_desc.setProperty("iface", name)
        edit_desc.editingFinished.connect(self._on_desc_changed)
        self.table.setCellWidget(row, self.COL_DESC, edit_desc)

        # IP
        edit_ip = QLineEdit(ip)
        edit_ip.setToolTip("Adres IPv4 (np. 192.168.1.1).")
        edit_ip.setProperty("iface", name)
        edit_ip.editingFinished.connect(self._on_ip_changed)
        self.table.setCellWidget(row, self.COL_IP, edit_ip)

        # MASK
        spin_mask = QSpinBox()
        spin_mask.setRange(0, 32)
        spin_mask.setValue(int(cidr_str))
        spin_mask.setToolTip("Maska w formacie CIDR (0–32). Do IOS trafia maska kropkowa.")
        spin_mask.setProperty("iface", name)
        spin_mask.valueChanged.connect(self._on_mask_changed)
        self.table.setCellWidget(row, self.COL_MASK, spin_mask)

        # MODE
        combo_mode = QComboBox()
        combo_mode.addItems(["access", "trunk", "routed"])
        combo_mode.setToolTip("Tryb portu: access / trunk / routed.")
        mode = (mode or "").lower()
        if mode in ("access", "trunk", "routed"):
            combo_mode.setCurrentText(mode)
        combo_mode.setProperty("iface", name)
        combo_mode.currentTextChanged.connect(self._on_mode_changed)
        self.table.setCellWidget(row, self.COL_MODE, combo_mode)

        # STATUS
        chk_status = QCheckBox("up")
        chk_status.setToolTip("Stan interfejsu: zaznaczone = up (no shutdown), odznaczone = down (shutdown).")
        chk_status.setChecked(status.lower() != "down")
        chk_status.setProperty("iface", name)
        chk_status.toggled.connect(self._on_status_changed)
        self.table.setCellWidget(row, self.COL_STATUS, chk_status)

    # ================================================================
    #             HANDLER MODE (tylko w switchowym tabie)
    # ================================================================

    def _on_mode_changed(self, mode: str):
        if self._loading:
            return

        w = self.sender()
        iface = w.property("iface")
        mode = (mode or "").lower()

        cmds = [f"interface {iface}"]

        if mode == "access":
            cmds.append(" switchport mode access")
        elif mode == "trunk":
            cmds.append(" switchport mode trunk")
        elif mode == "routed":
            cmds.append(" no switchport")
        else:
            return

        cmds.append(" exit")
        self._enqueue(cmds)

    # ================================================================
    #                 NADPISANY EXPORT / IMPORT / SYNC
    # ================================================================

    def export_state(self):
        rows = []
        for r in range(self.table.rowCount()):
            name_item = self.table.item(r, self.COL_NAME)
            name = name_item.text() if name_item else ""

            desc_w = self.table.cellWidget(r, self.COL_DESC)
            ip_w = self.table.cellWidget(r, self.COL_IP)
            mask_w = self.table.cellWidget(r, self.COL_MASK)
            mode_w = self.table.cellWidget(r, self.COL_MODE)
            status_w = self.table.cellWidget(r, self.COL_STATUS)

            desc = desc_w.text() if isinstance(desc_w, QLineEdit) else ""
            ip = ip_w.text() if isinstance(ip_w, QLineEdit) else ""
            cidr = mask_w.value() if isinstance(mask_w, QSpinBox) else 0
            mode = mode_w.currentText() if isinstance(mode_w, QComboBox) else ""
            status = (
                "up" if isinstance(status_w, QCheckBox) and status_w.isChecked() else "down"
            )

            rows.append([name, desc, ip, str(cidr), mode, status])

        return {
            "rows": rows,
            "console": self.console.toPlainText(),
            "pending_cmds": list(self.pending_cmds),
        }

    def import_state(self, data: dict):
        self._loading = True
        try:
            self.table.setRowCount(0)
            for row in data.get("rows", []):
                name, desc, ip, cidr, mode, status = row
                self._create_interface_row(name, desc, ip, cidr, mode, status)

            self.console.setPlainText(data.get("console", ""))
            self.pending_cmds = list(data.get("pending_cmds", []))
        finally:
            self._loading = False

    def sync_from_config(self, conf: ParsedConfig):
        self._loading = True
        try:
            self.table.setRowCount(0)

            for name, data in conf.interfaces.items.items():
                desc = data.get("description", "")
                ip = data.get("ip", "")
                mask = data.get("mask", "")
                cidr = mask_to_cidr(mask) if mask else 0
                mode = (data.get("mode", "") or "").lower()
                status = data.get("status", "")

                self._create_interface_row(
                    name=name,
                    desc=desc,
                    ip=ip,
                    cidr_str=str(cidr),
                    mode=mode,
                    status=status,
                )

            self.pending_cmds.clear()
            self.console.appendPlainText("[SYNC] Switch interfaces updated from running-config.")
        finally:
            self._loading = False

    # ================================================================
    #           KOMPATYBILNOŚĆ: add_interface_to_table dla switchy
    # ================================================================

    def add_interface_to_table(self, name, desc, ip, mask, mode):
        try:
            if mask and "." in str(mask):
                cidr = mask_to_cidr(mask)
            else:
                cidr = int(mask) if mask not in (None, "") else 0
        except Exception:
            cidr = 0

        row = self._find_row(name)
        if row == -1:
            self._create_interface_row(name, desc, ip, str(cidr), mode or "", "up")
            return

        self._loading = True
        try:
            desc_w = self.table.cellWidget(row, self.COL_DESC)
            ip_w = self.table.cellWidget(row, self.COL_IP)
            mask_w = self.table.cellWidget(row, self.COL_MASK)
            mode_w = self.table.cellWidget(row, self.COL_MODE)

            if isinstance(desc_w, QLineEdit):
                desc_w.setText(desc)
            if isinstance(ip_w, QLineEdit):
                ip_w.setText(ip)
            if isinstance(mask_w, QSpinBox):
                mask_w.setValue(cidr)
            if isinstance(mode_w, QComboBox) and mode:
                mode_w.setCurrentText(mode)
        finally:
            self._loading = False
