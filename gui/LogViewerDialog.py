from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QTextEdit,
    QFileDialog,
)


class LogViewerDialog(QDialog):
    """
    Zaawansowany viewer logów:
    - kolorowanie (ERROR/WARNING/INFO/DEBUG),
    - filtracja,
    - wyszukiwanie,
    - auto-refresh,
    - tryb 'show only matches'
    """

    LOG_DIR = Path("./logs")

    LEVEL_COLORS = {
        "ERROR": "#ffcccc",
        "WARNING": "#fff5cc",
        "INFO": "#f0f0f0",
        "DEBUG": "#e5e5e5",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Przeglądarka logów")
        self.resize(1000, 700)

        main = QVBoxLayout(self)

        # ---------------------------------------
        #  Górny pasek: wybór pliku logu + kontrola
        # ---------------------------------------
        top_bar = QHBoxLayout()
        main.addLayout(top_bar)

        top_bar.addWidget(QLabel("Plik:"))
        self.combo_files = QComboBox()
        top_bar.addWidget(self.combo_files, 1)

        self.btn_refresh_files = QPushButton("Odśwież listę")
        self.btn_refresh_files.clicked.connect(self._reload_file_list)
        top_bar.addWidget(self.btn_refresh_files)

        self.btn_open_folder = QPushButton("Otwórz folder")
        self.btn_open_folder.clicked.connect(self._open_log_folder)
        top_bar.addWidget(self.btn_open_folder)

        # ---------------------------------------
        #  Pasek filtrów
        # ---------------------------------------
        filter_bar = QHBoxLayout()
        main.addLayout(filter_bar)

        self.chk_error = QCheckBox("ERROR")
        self.chk_warning = QCheckBox("WARNING")
        self.chk_info = QCheckBox("INFO")
        self.chk_debug = QCheckBox("DEBUG")

        # domyślnie wszystko włączone
        for chk in (self.chk_error, self.chk_warning, self.chk_info, self.chk_debug):
            chk.setChecked(True)
            chk.stateChanged.connect(self._apply_filters)

        filter_bar.addWidget(self.chk_error)
        filter_bar.addWidget(self.chk_warning)
        filter_bar.addWidget(self.chk_info)
        filter_bar.addWidget(self.chk_debug)

        filter_bar.addSpacing(20)

        self.chk_show_only_matches = QCheckBox("Pokaż tylko dopasowane")
        self.chk_show_only_matches.stateChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.chk_show_only_matches)

        # ---------------------------------------
        #  Pasek wyszukiwania
        # ---------------------------------------
        search_bar = QHBoxLayout()
        main.addLayout(search_bar)

        search_bar.addWidget(QLabel("Szukaj:"))
        self.input_search = QLineEdit()
        self.input_search.textChanged.connect(self._apply_filters)
        search_bar.addWidget(self.input_search, 1)

        self.btn_reload = QPushButton("Odśwież")
        self.btn_reload.clicked.connect(self._load_current_file)
        search_bar.addWidget(self.btn_reload)

        # ---------------------------------------
        #  Pole logu
        # ---------------------------------------
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QTextEdit.NoWrap)
        self.text.setStyleSheet("font-family: monospace; font-size: 11px;")
        main.addWidget(self.text, 10)

        # timer do auto-refresh
        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self._auto_refresh)

        # inicjalizacja listy plików
        self._reload_file_list()
        self.combo_files.currentIndexChanged.connect(self._load_current_file)

    # ===============================================================
    #   FILE LIST
    # ===============================================================

    def _reload_file_list(self):
        self.combo_files.blockSignals(True)
        self.combo_files.clear()

        if self.LOG_DIR.exists():
            for f in sorted(self.LOG_DIR.glob("*.log")):
                self.combo_files.addItem(f.name, f)
        self.combo_files.blockSignals(False)

        if self.combo_files.count() > 0:
            self.combo_files.setCurrentIndex(0)
            self._load_current_file()

    def _open_log_folder(self):
        QFileDialog.getOpenFileName(
            self,
            "Folder logów",
            str(self.LOG_DIR),
        )

    # ===============================================================
    #   FILE LOADING
    # ===============================================================

    def _load_current_file(self):
        file_path: Path = self.combo_files.currentData()
        if not file_path or not file_path.exists():
            self.text.setHtml("<b>Brak danych</b>")
            return

        try:
            raw = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            self.text.setHtml(f"<b>Błąd odczytu pliku:</b><br>{e}")
            return

        self._raw_lines = raw.splitlines()
        self._apply_filters()

    # ===============================================================
    #   FILTERING + SEARCH + COLORING
    # ===============================================================

    def _apply_filters(self):
        if not hasattr(self, "_raw_lines"):
            return

        search_term = self.input_search.text().strip().lower()
        only_matches = self.chk_show_only_matches.isChecked()

        allowed_levels = []
        if self.chk_error.isChecked():
            allowed_levels.append("ERROR")
        if self.chk_warning.isChecked():
            allowed_levels.append("WARNING")
        if self.chk_info.isChecked():
            allowed_levels.append("INFO")
        if self.chk_debug.isChecked():
            allowed_levels.append("DEBUG")

        html = ["<html><body style='font-family: monospace; white-space: pre;'>"]

        for line in self._raw_lines:
            lvl = self._extract_level(line)
            if lvl and lvl not in allowed_levels:
                continue

            if search_term and search_term not in line.lower():
                if only_matches:
                    continue

            color = self.LEVEL_COLORS.get(lvl, None)
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            if search_term and search_term in safe.lower():
                safe = self._highlight_search(safe, search_term)

            if color:
                html.append(f"<div style='background:{color}'>{safe}</div>")
            else:
                html.append(f"<div>{safe}</div>")

        html.append("</body></html>")
        self.text.setHtml("\n".join(html))
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())

    def _extract_level(self, line: str):
        """
        Przykładowe linie Netmiko:
        2025-02-11 20:33:22 [INFO] Connecting...
        2025-02-11 20:33:22 [ERROR] Timeout
        """
        m = re.search(r"\[(ERROR|WARNING|INFO|DEBUG)\]", line)
        return m.group(1) if m else None

    def _highlight_search(self, text: str, term: str) -> str:
        pattern = re.escape(term)
        return re.sub(
            pattern,
            lambda m: f"<span style='background:yellow'>{m.group(0)}</span>",
            text,
            flags=re.IGNORECASE,
        )

    # ===============================================================
    #   AUTO REFRESH (tail -f)
    # ===============================================================

    def _auto_refresh(self):
        idx = self.combo_files.currentIndex()
        if idx >= 0:
            self._load_current_file()

    def showEvent(self, event):
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)
