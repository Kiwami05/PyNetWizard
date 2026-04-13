from PySide6.QtWidgets import (
    QWidget,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QSpinBox,
    QPushButton,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QTableWidgetItem,
)
from PySide6.QtCore import Qt

from gui.tabs.InterfacesTab import InterfacesTab, mask_to_cidr
from operations.operation import Operation
from operations.operation_type import OperationType
from services.parsed_config import ParsedConfig


class VLANSelectDialog(QDialog):
    """
    Dialog wyboru VLAN-ów dla portu:
    - mode == "access" -> pojedynczy VLAN (radio-button),
    - mode == "trunk"  -> wiele VLAN-ów (checkboxy).
    """

    def __init__(
        self,
        parent: QWidget | None,
        vlans: dict[str, dict],
        mode: str,
        current_vlans: list[str],
    ):
        super().__init__(parent)
        self.setWindowTitle("Wybór VLAN-ów")
        self.mode = mode
        self.vlans = vlans or {}
        self._selected = list(current_vlans)

        layout = QVBoxLayout(self)

        if not self.vlans:
            layout.addWidget(
                QLabel(
                    "Brak dostępnych VLAN-ów. Najpierw zdefiniuj je w zakładce VLAN."
                )
            )
        else:
            # Scrollowalna lista VLAN-ów
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            inner = QFrame()
            inner_layout = QVBoxLayout(inner)

            self._widgets = {}  # vid -> widget (QRadioButton/QCheckBox)

            # posortowane po numerze
            vids = sorted(self.vlans.keys(), key=lambda x: int(x))
            for vid in vids:
                vinfo = self.vlans.get(vid, {})
                name = vinfo.get("name", "")
                label_text = f"{vid}"
                if name:
                    label_text += f" - {name}"

                if mode == "access":
                    from PySide6.QtWidgets import QRadioButton

                    w = QRadioButton(label_text)
                    if self._selected and vid == self._selected[0]:
                        w.setChecked(True)
                else:  # trunk
                    from PySide6.QtWidgets import QCheckBox

                    w = QCheckBox(label_text)
                    if vid in self._selected:
                        w.setChecked(True)

                w.setProperty("vid", vid)
                inner_layout.addWidget(w)
                self._widgets[vid] = w

            inner_layout.addStretch()
            scroll.setWidget(inner)
            layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_vlans(self) -> list[str]:
        """
        Zwraca listę wybranych VLAN ID (stringi).
        - dla access: lista jednoelementowa,
        - dla trunk: lista VLAN-ów z zaznaczonym checkboxem.
        """
        if not getattr(self, "_widgets", None):
            return []

        if self.mode == "access":
            for vid, w in self._widgets.items():
                if w.isChecked():
                    return [vid]
            return []

        # trunk
        selected = []
        for vid, w in self._widgets.items():
            if w.isChecked():
                selected.append(vid)
        return selected


class SwitchInterfacesTab(InterfacesTab):
    """
    InterfacesTab dla switchy:
    - dziedziczy z bazowego InterfacesTab (description, IP, mask, status),
    - dodaje Mode (access/trunk/routed),
    - dodaje VLAN(s) (access -> jeden, trunk -> wiele),
    - VLAN selection przez dialog z radiobutton/checkboxami.
    """

    COL_NAME = 0
    COL_DESC = 1
    COL_IP = 2
    COL_MASK = 3
    COL_MODE = 4
    COL_VLANS = 5
    COL_STATUS = 6

    def __init__(self, parent=None):
        super().__init__(parent)

        # nadpisujemy kolumny z bazowego taba
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Name",
                "Description",
                "IP Address",
                "Mask (/CIDR)",
                "Mode",
                "VLAN(s)",
                "Status",
            ]
        )

        # VLANy dostępne do wyboru (uzupełniane w sync_from_config)
        self.available_vlans: dict[str, dict] = {}

    # ===================================================================
    #                    TWORZENIE WIERSZA (OVERRIDE)
    # ===================================================================

    def _create_interface_row(
        self,
        name: str,
        desc: str,
        ip: str,
        cidr_str: str,
        mode: str,
        status: str,
        vlans: list[str] | None = None,
    ):
        """
        Tworzy wiersz z:
        - Name (RO),
        - Description (LineEdit),
        - IP (LineEdit),
        - Mask (SpinBox CIDR),
        - Mode (ComboBox),
        - VLAN(s) (przycisk '...' + tekst),
        - Status (CheckBox).
        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        # === NAME (read-only) ===
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.COL_NAME, name_item)

        # === DESC ===
        edit_desc = QLineEdit(desc)
        edit_desc.setToolTip("Opis interfejsu (opcjonalny).")
        edit_desc.setProperty("iface", name)
        edit_desc.editingFinished.connect(self._on_desc_changed)
        self.table.setCellWidget(row, self.COL_DESC, edit_desc)

        # === IP ===
        edit_ip = QLineEdit(ip)
        edit_ip.setToolTip("Adres IPv4 (np. 192.168.1.1).")
        edit_ip.setProperty("iface", name)
        edit_ip.editingFinished.connect(self._on_ip_changed)
        self.table.setCellWidget(row, self.COL_IP, edit_ip)

        # === MASK (CIDR) ===
        spin_mask = QSpinBox()
        spin_mask.setRange(0, 32)
        try:
            spin_mask.setValue(int(cidr_str))
        except Exception:
            spin_mask.setValue(0)
        spin_mask.setToolTip(
            "Maska w formacie CIDR (0–32). Do IOS trafia maska kropkowa."
        )
        spin_mask.setProperty("iface", name)
        spin_mask.valueChanged.connect(self._on_mask_changed)
        self.table.setCellWidget(row, self.COL_MASK, spin_mask)

        # === MODE ===
        combo_mode = QComboBox()
        combo_mode.addItems(["access", "trunk", "routed"])
        combo_mode.setToolTip("Tryb portu: access / trunk / routed.")
        mode = (mode or "").lower()
        if mode in ("access", "trunk", "routed"):
            combo_mode.setCurrentText(mode)
        combo_mode.setProperty("iface", name)
        combo_mode.currentTextChanged.connect(self._on_mode_changed)
        self.table.setCellWidget(row, self.COL_MODE, combo_mode)

        # === VLAN(s) ===
        vlan_btn = QPushButton()
        vlan_btn.setToolTip("Konfiguracja VLAN-ów dla tego portu.")
        vlan_btn.setProperty("iface", name)
        vlan_btn.clicked.connect(self._on_vlans_button_clicked)
        vlan_text = ", ".join(vlans) if vlans else ""
        vlan_btn.setText(vlan_text if vlan_text else "...")
        self.table.setCellWidget(row, self.COL_VLANS, vlan_btn)

        # === STATUS ===
        chk_status = QCheckBox("up")
        chk_status.setToolTip(
            "Stan interfejsu: zaznaczone = up (no shutdown), odznaczone = down (shutdown)."
        )
        chk_status.setChecked(status.lower() != "down")
        chk_status.setProperty("iface", name)
        chk_status.toggled.connect(self._on_status_changed)
        self.table.setCellWidget(row, self.COL_STATUS, chk_status)

    # ===================================================================
    #                       HANDLER TRYBU (MODE)
    # ===================================================================

    def _on_mode_changed(self, mode: str):
        if self._loading:
            return

        w = self.sender()
        iface = w.property("iface")
        mode = (mode or "").lower()

        if mode == "access":
            self.pending_ops.append(
                Operation(
                    OperationType.SET_SWITCHPORT_MODE_ACCESS,
                    iface=iface,
                )
            )
        elif mode == "trunk":
            self.pending_ops.append(
                Operation(
                    OperationType.SET_SWITCHPORT_MODE_TRUNK,
                    iface=iface,
                )
            )
        elif mode == "routed":
            self.pending_ops.append(
                Operation(
                    OperationType.SET_SWITCHPORT_MODE_ROUTED,
                    iface=iface,
                )
            )

            self._append_log(f"[OP] set mode {mode} on {iface}")

    # ===================================================================
    #                   HANDLER PRZYCISKU VLAN(s)
    # ===================================================================

    def _on_vlans_button_clicked(self):
        if self._loading:
            return

        btn = self.sender()
        if not isinstance(btn, QPushButton):
            return

        iface = btn.property("iface")
        if not iface:
            return

        # znajdź wiersz, żeby sprawdzić mode
        row = self._find_row(iface)
        if row == -1:
            return

        mode_w = self.table.cellWidget(row, self.COL_MODE)
        if not isinstance(mode_w, QComboBox):
            return

        mode = mode_w.currentText().lower()
        if mode not in ("access", "trunk"):
            # dla routed nie ma VLANów
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "Informacja",
                "VLANs można przypisywać tylko w trybie access lub trunk.",
            )
            return

        # aktualne VLAN-y z przycisku
        current_text = btn.text().strip()
        current_vlans = (
            [v.strip() for v in current_text.split(",") if v.strip()]
            if current_text and current_text != "..."
            else []
        )

        dlg = VLANSelectDialog(self, self.available_vlans, mode, current_vlans)
        if dlg.exec() != QDialog.Accepted:
            return

        selected = dlg.selected_vlans()
        if not selected:
            # na razie wymagamy co najmniej jednego VLAN-u
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "Błąd",
                "Musisz wybrać przynajmniej jeden VLAN.",
            )
            return

        # zaktualizuj przycisk
        btn.setText(", ".join(selected))

        # wygeneruj komendy
        if mode == "access":
            # zakładamy jeden VLAN
            vid = selected[0]
            self.pending_ops.append(
                Operation(OperationType.SET_ACCESS_VLAN, iface=iface, vlan_id=vid)
            )
        else:  # trunk
            self.pending_ops.append(
                Operation(
                    OperationType.SET_TRUNK_ALLOWED_VLANS,
                    iface=iface,
                    vlans=[int(v) for v in selected],
                )
            )
        self._append_log(f"[OP] set VLAN(s) {','.join(selected)} on {iface} ({mode})")

    # ===================================================================
    #                     STATE EXPORT / IMPORT
    # ===================================================================

    def export_state(self) -> dict:
        rows = []
        for r in range(self.table.rowCount()):
            name_item = self.table.item(r, self.COL_NAME)
            name = name_item.text() if name_item else ""

            desc_w = self.table.cellWidget(r, self.COL_DESC)
            ip_w = self.table.cellWidget(r, self.COL_IP)
            mask_w = self.table.cellWidget(r, self.COL_MASK)
            mode_w = self.table.cellWidget(r, self.COL_MODE)
            vlans_w = self.table.cellWidget(r, self.COL_VLANS)
            status_w = self.table.cellWidget(r, self.COL_STATUS)

            desc = desc_w.text() if isinstance(desc_w, QLineEdit) else ""
            ip = ip_w.text() if isinstance(ip_w, QLineEdit) else ""
            cidr = mask_w.value() if isinstance(mask_w, QSpinBox) else 0
            mode = mode_w.currentText() if isinstance(mode_w, QComboBox) else ""
            vlans_text = vlans_w.text() if isinstance(vlans_w, QPushButton) else ""
            status = (
                "up"
                if isinstance(status_w, QCheckBox) and status_w.isChecked()
                else "down"
            )

            rows.append([name, desc, ip, str(cidr), mode, vlans_text, status])

        return {
            "rows": rows,
            "pending_ops": list(self.pending_ops),
        }

    def import_state(self, data: dict):
        self._loading = True
        try:
            self.table.setRowCount(0)
            for row in data.get("rows", []):
                # [name, desc, ip, cidr, mode, vlans_text, status]
                name = row[0] if len(row) > 0 else ""
                desc = row[1] if len(row) > 1 else ""
                ip = row[2] if len(row) > 2 else ""
                cidr = row[3] if len(row) > 3 else "0"
                mode = row[4] if len(row) > 4 else ""
                vlans_text = row[5] if len(row) > 5 else ""
                status = row[6] if len(row) > 6 else "up"

                vlans = (
                    [v.strip() for v in vlans_text.split(",") if v.strip()]
                    if vlans_text
                    else []
                )
                self._create_interface_row(name, desc, ip, cidr, mode, status, vlans)

            self.pending_ops = list(data.get("pending_ops", []))
        finally:
            self._loading = False

    # ===================================================================
    #                       SYNC Z PARSED CONFIG
    # ===================================================================

    def sync_from_config(self, conf: ParsedConfig):
        """
        Odczytuje interfejsy z ParsedConfig:
        - ip, mask, description, status jak w bazowym tabie,
        - mode: data.get("mode") -> access/trunk/routed,
        - VLANs:
          - access: data.get("access_vlan"),
          - trunk: data.get("trunk_vlans") (lista/string).
        """
        self._loading = True
        try:
            self.table.setRowCount(0)
            self.available_vlans = dict(conf.vlans.items)

            for name, data in conf.interfaces.items.items():
                desc = data.get("description", "")
                ip = data.get("ip", "")
                mask = data.get("mask", "")
                cidr = mask_to_cidr(mask) if mask else 0
                mode = (data.get("mode", "") or "").lower()
                status = data.get("status", "")

                vlans: list[str] = []
                if mode == "access":
                    av = data.get("access_vlan")
                    if av:
                        vlans = [str(av)]
                elif mode == "trunk":
                    tv = data.get("trunk_vlans") or data.get("trunk_allowed")
                    if isinstance(tv, str):
                        vlans = [v.strip() for v in tv.split(",") if v.strip()]
                    elif isinstance(tv, (list, tuple)):
                        vlans = [str(v) for v in tv]

                self._create_interface_row(
                    name=name,
                    desc=desc,
                    ip=ip,
                    cidr_str=str(cidr),
                    mode=mode,
                    status=status,
                    vlans=vlans,
                )

            self.pending_ops.clear()
            self._append_log("[SYNC] Switch interfaces updated from running-config.")
        finally:
            self._loading = False

    # ===================================================================
    #           KOMPATYBILNOŚĆ: add_interface_to_table dla switchy
    # ===================================================================

    def add_interface_to_table(self, name, desc, ip, mask, mode, vlans_text: str = ""):
        """
        Zostawione na wypadek, gdyby gdzieś było wołane ręcznie.
        mask może być CIDR lub kropkowa.
        vlans_text: np. '10' lub '10,20,30'.
        """
        try:
            if mask and "." in str(mask):
                cidr = mask_to_cidr(str(mask))
            else:
                cidr = int(mask) if mask not in (None, "") else 0
        except Exception:
            cidr = 0

        vlans = (
            [v.strip() for v in vlans_text.split(",") if v.strip()]
            if vlans_text
            else []
        )

        row = self._find_row(name)
        if row == -1:
            self._create_interface_row(
                name, desc, ip, str(cidr), mode or "", "up", vlans
            )
            return

        self._loading = True
        try:
            desc_w = self.table.cellWidget(row, self.COL_DESC)
            ip_w = self.table.cellWidget(row, self.COL_IP)
            mask_w = self.table.cellWidget(row, self.COL_MASK)
            mode_w = self.table.cellWidget(row, self.COL_MODE)
            vlans_w = self.table.cellWidget(row, self.COL_VLANS)

            if isinstance(desc_w, QLineEdit):
                desc_w.setText(desc)
            if isinstance(ip_w, QLineEdit):
                ip_w.setText(ip)
            if isinstance(mask_w, QSpinBox):
                mask_w.setValue(cidr)
            if isinstance(mode_w, QComboBox) and mode:
                mode_w.setCurrentText(mode)
            if isinstance(vlans_w, QPushButton):
                vlans_w.setText(", ".join(vlans) if vlans else "...")
        finally:
            self._loading = False
