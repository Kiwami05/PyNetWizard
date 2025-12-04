from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QAbstractItemView,
)

from services.security_audit import run_security_audit, SecurityFinding


class SecurityAuditDialog(QDialog):
    """
    Dialog audytu bezpieczeństwa:
    - Źródło konfiguracji: bieżące urządzenie lub plik.
    - Uruchamia run_security_audit(config_text).
    - Wyświetla listę znalezionych problemów.
    - Pokazuje szczegóły i sugerowane komendy dla wybranego wpisu.
    """

    def __init__(
        self,
        parent=None,
        current_device_name: Optional[str] = None,
        current_config_text: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Audyt bezpieczeństwa")
        self.resize(900, 650)

        self.current_device_name = current_device_name or ""
        self.device_config_text = current_config_text or ""
        self.current_source_label = "Brak (wybierz źródło konfiguracji)"
        self.current_config_text: str = ""
        self.findings: List[SecurityFinding] = []

        main = QVBoxLayout(self)

        # -------------------------------------------------
        #  Górny pasek: źródło konfiguracji + przyciski
        # -------------------------------------------------
        header_row = QVBoxLayout()
        main.addLayout(header_row)

        self.lbl_source = QLabel()
        self._update_source_label()
        self.lbl_source.setTextFormat(Qt.RichText)
        header_row.addWidget(self.lbl_source)

        btn_row = QHBoxLayout()
        header_row.addLayout(btn_row)

        self.btn_use_device = QPushButton("Użyj konfiguracji bieżącego urządzenia")
        self.btn_use_device.clicked.connect(self._load_from_device)
        btn_row.addWidget(self.btn_use_device)

        self.btn_load_file = QPushButton("Wczytaj konfigurację z pliku…")
        self.btn_load_file.clicked.connect(self._load_from_file)
        btn_row.addWidget(self.btn_load_file)

        btn_row.addStretch()

        self.btn_run_audit = QPushButton("Uruchom audyt")
        self.btn_run_audit.clicked.connect(self._run_audit)
        btn_row.addWidget(self.btn_run_audit)

        # -------------------------------------------------
        #  Tabela wyników
        # -------------------------------------------------
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Poziom", "Kategoria", "Opis problemu"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)

        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        main.addWidget(self.table, 3)

        # -------------------------------------------------
        #  Dolny panel: szczegóły + sugerowane komendy
        # -------------------------------------------------
        bottom = QHBoxLayout()
        main.addLayout(bottom, 2)

        # Szczegóły
        left_panel = QVBoxLayout()
        bottom.addLayout(left_panel, 3)

        lbl_details = QLabel("Szczegóły:")
        left_panel.addWidget(lbl_details)

        self.txt_details = QTextEdit()
        self.txt_details.setReadOnly(True)
        self.txt_details.setLineWrapMode(QTextEdit.NoWrap)
        self.txt_details.setStyleSheet("font-family: monospace; font-size: 11px;")
        left_panel.addWidget(self.txt_details, 1)

        # Sugerowane komendy
        right_panel = QVBoxLayout()
        bottom.addLayout(right_panel, 2)

        lbl_cmds_row = QHBoxLayout()
        lbl_cmds = QLabel("Sugerowane komendy:")
        lbl_cmds_row.addWidget(lbl_cmds)
        lbl_cmds_row.addStretch()

        self.btn_copy_cmds = QPushButton("Kopiuj do schowka")
        self.btn_copy_cmds.clicked.connect(self._copy_commands_to_clipboard)
        lbl_cmds_row.addWidget(self.btn_copy_cmds)

        right_panel.addLayout(lbl_cmds_row)

        self.txt_commands = QTextEdit()
        self.txt_commands.setReadOnly(True)
        self.txt_commands.setLineWrapMode(QTextEdit.NoWrap)
        self.txt_commands.setStyleSheet("font-family: monospace; font-size: 11px;")
        right_panel.addWidget(self.txt_commands, 1)

        # Jeżeli nie mamy konfiguracji z urządzenia – wyłącz przycisk
        if not self.device_config_text:
            self.btn_use_device.setEnabled(False)

    # ======================================================
    #          Obsługa źródła konfiguracji
    # ======================================================

    def _update_source_label(self):
        text = (
            f"<b>Źródło konfiguracji:</b> {self.current_source_label}"
        )
        self.lbl_source.setText(text)

    def _load_from_device(self):
        if not self.device_config_text:
            QMessageBox.information(
                self,
                "Brak konfiguracji",
                "Brak aktualnego snapshotu konfiguracji z bieżącego urządzenia.\n"
                "Najpierw wykonaj Sync, aby pobrać running-config.",
            )
            return
        self.current_config_text = self.device_config_text
        dev_name = self.current_device_name or "(bieżące urządzenie)"
        self.current_source_label = f"Urządzenie: {dev_name}"
        self._update_source_label()
        self._run_audit()

    def _load_from_file(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz plik z konfiguracją",
            "",
            "Pliki tekstowe (*.txt *.cfg *.conf);;Wszystkie pliki (*.*)",
        )
        if not path_str:
            return

        path = Path(path_str)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Błąd odczytu pliku",
                f"Nie udało się wczytać pliku:\n{path_str}\n\n{type(e).__name__}: {e}",
            )
            return

        self.current_config_text = text
        self.current_source_label = f"Plik: {path.name}"
        self._update_source_label()
        self._run_audit()

    # ======================================================
    #                Uruchomienie audytu
    # ======================================================

    def _run_audit(self):
        if not self.current_config_text.strip():
            QMessageBox.information(
                self,
                "Brak konfiguracji",
                "Nie wybrano żadnego źródła konfiguracji.\n"
                "Użyj konfiguracji bieżącego urządzenia lub wczytaj plik.",
            )
            return

        try:
            self.findings = run_security_audit(self.current_config_text)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Błąd audytu",
                f"Wystąpił błąd podczas analizy konfiguracji:\n\n"
                f"{type(e).__name__}: {e}",
            )
            return

        self._populate_table()

    # ======================================================
    #                Tabela wyników
    # ======================================================

    def _populate_table(self):
        self.table.setRowCount(0)
        for finding in self.findings:
            row = self.table.rowCount()
            self.table.insertRow(row)

            item_sev = QTableWidgetItem(finding.severity)
            item_cat = QTableWidgetItem(finding.category)
            item_msg = QTableWidgetItem(finding.message)

            # Kolorowanie severity
            bg = None
            if finding.severity == "CRITICAL":
                bg = QColor("#ffcccc")
            elif finding.severity == "WARNING":
                bg = QColor("#fff5cc")
            elif finding.severity == "INFO":
                bg = QColor("#f0f0f0")

            if bg:
                for it in (item_sev, item_cat, item_msg):
                    it.setBackground(QBrush(bg))

            # Zapisz indeks findingu w UserRole
            item_sev.setData(Qt.UserRole, row)

            self.table.setItem(row, 0, item_sev)
            self.table.setItem(row, 1, item_cat)
            self.table.setItem(row, 2, item_msg)

        self.txt_details.clear()
        self.txt_commands.clear()

        if self.findings:
            self.table.selectRow(0)
            self._show_finding(0)

    def _get_selected_index(self) -> Optional[int]:
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return None
        return sel[0].row()

    def _on_selection_changed(self):
        idx = self._get_selected_index()
        if idx is None:
            self.txt_details.clear()
            self.txt_commands.clear()
            return
        if 0 <= idx < len(self.findings):
            self._show_finding(idx)

    def _show_finding(self, index: int):
        finding = self.findings[index]
        # Szczegóły
        details_lines = [
            f"ID: {finding.id}",
            f"Poziom: {finding.severity}",
            f"Kategoria: {finding.category}",
            "",
            finding.details or "(brak dodatkowych szczegółów)",
            "",
            "Rekomendacja:",
            finding.recommendation or "(brak rekomendacji)",
        ]
        self.txt_details.setPlainText("\n".join(details_lines))

        # Komendy
        if finding.suggested_commands:
            self.txt_commands.setPlainText("\n".join(finding.suggested_commands))
        else:
            self.txt_commands.setPlainText("Brak zasugerowanych komend dla tego wpisu.")

    # ======================================================
    #             Kopiowanie komend do schowka
    # ======================================================

    def _copy_commands_to_clipboard(self):
        text = self.txt_commands.toPlainText().strip()
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(
            self,
            "Skopiowano",
            "Sugerowane komendy zostały skopiowane do schowka.",
        )
