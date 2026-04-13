from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QStackedWidget,
    QPlainTextEdit,
    QFrame,
    QLabel,
)
from PySide6.QtCore import Qt

from devices.DeviceBuffer import DeviceBuffer
from gui.tabs.GlobalTab import GlobalTab
from gui.tabs.RoutingTab import RoutingTab
from gui.tabs.InterfacesTab import InterfacesTab
from gui.tabs.SwitchInterfacesTab import SwitchInterfacesTab
from gui.tabs.VLANsTab import VLANsTab
from gui.tabs.ACLTab import ACLTab
from gui.tabs.SRXPoliciesTab import SRXPoliciesTab
from gui.tab_registry import tab_specs_for_device
from operations.Operation import Operation
from operations.capabilities import validate_operations_supported_for_device
from renderers.factory import RendererFactory
from services.parsed_config import ParsedConfig


class DeviceDetailWidget(QWidget):
    """
    Główny panel szczegółów urządzenia.
    Zawiera dynamicznie zmieniane zakładki (GLOBAL / ROUTING / INTERFACES / VLANs / ACL)
    oraz dolną konsolę logów.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_device = None
        self.buffers: dict[str, DeviceBuffer] = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # === GÓRNY PANEL (zakładki + widok treści) ===
        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        main_layout.addWidget(content_frame, 4)

        # === LEWY PANEL: lista kategorii ===
        self.category_list = QListWidget()
        # self.category_list.setStyleSheet("""
        #     QListWidget {
        #         background-color: #f5f5f5;
        #         font-weight: bold;
        #         border: 1px solid #aaa;
        #     }
        #     QListWidget::item:selected {
        #         background-color: #0078d7;
        #         color: white;
        #     }
        # """)
        content_layout.addWidget(self.category_list, 1)

        # === PRAWY PANEL: zawartość zakładek ===
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 3)

        # --- Strony (tworzone raz, ale dodawane dynamicznie) ---
        self.pages = {
            "GLOBAL": GlobalTab(),
            "ROUTING": RoutingTab(),
            "INTERFACES": InterfacesTab(),  # dla routerów / firewalli
            "SWITCH_INTERFACES": SwitchInterfacesTab(),  # dla switchy
            "VLANs": VLANsTab(),
            "ACL": ACLTab(),
            "SRX_POLICIES": SRXPoliciesTab(),
        }

        for page in self.pages.values():
            if hasattr(page, "set_logger"):
                page.set_logger(self.append_console)

        # Po kliknięciu w liście zmieniamy stronę
        self.category_list.currentRowChanged.connect(self.stack.setCurrentIndex)

        # === DOLNA KONSOLA ===
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Podgląd komend...")
        self.console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #111;
                color: #0f0;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.console, 1)

    # === Pomocnicze metody ===

    def clear_stack(self):
        """Usuwa wszystkie widgety ze stacka."""
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)

    def show_for_device(self, device):
        """Aktualizuje zakładki w zależności od typu urządzenia i przywraca stan z bufora."""
        # 🆕 zapisz stan poprzedniego urządzenia
        if self.current_device:
            self.save_tab_state(self.current_device)

        self.current_device = device
        for page in self.pages.values():
            if hasattr(page, "set_device_context"):
                page.set_device_context(device)

        self.category_list.clear()
        self.clear_stack()

        if not device:
            self.category_list.addItem("Brak wybranego urządzenia")
            placeholder = QLabel("<i>Brak wybranego urządzenia</i>")
            placeholder.setAlignment(Qt.AlignCenter)
            self.stack.addWidget(placeholder)
            self.load_console_state(None)
            return

        for tab in tab_specs_for_device(device):
            self.category_list.addItem(tab.label)
            self.stack.addWidget(self.pages[tab.key])

        self.category_list.setCurrentRow(0)

        # 🆕 wczytaj stan z bufora
        self.load_tab_state(device)
        self.load_console_state(device)

    def append_console(self, text: str):
        """Dodaje linię do globalnej konsoli."""
        message = text.strip()
        if not message:
            return

        self.console.appendPlainText(message)

        if not self.current_device:
            return

        buf = self.buffers.setdefault(self.current_device.host, DeviceBuffer())
        if buf.logs:
            buf.logs += "\n" + message
        else:
            buf.logs = message

    def load_console_state(self, device):
        """Ładuje globalny log dla wskazanego urządzenia."""
        self.console.clear()
        if not device:
            return

        buf = self.buffers.get(device.host)
        if buf and buf.logs:
            self.console.setPlainText(buf.logs)

    # =====================================================
    #        OBSŁUGA BUFORA (export/import zakładek)
    # =====================================================

    def save_tab_state(self, device):
        """Zapisuje stan aktualnych zakładek do bufora."""
        if not device:
            return
        buf = self.buffers.setdefault(device.host, DeviceBuffer())
        for name, tab in self.pages.items():
            if hasattr(tab, "export_state"):
                try:
                    buf.tabs[name] = tab.export_state()
                except Exception as e:
                    print(f"[WARN] Nie zapisano stanu {name}: {e}")

    def load_tab_state(self, device):
        """Wczytuje stan zakładek z bufora lub resetuje zakładki, jeśli bufora brak."""
        if not device:
            return

        buf = self.buffers.get(device.host)
        if not buf:
            # 🆕 brak bufora — wyczyść wszystkie taby
            for name, tab in self.pages.items():
                if hasattr(tab, "import_state"):
                    try:
                        tab.import_state({})  # pusta struktura
                    except Exception:
                        pass
            return

        # 🧠 bufor istnieje — przywróć stan
        for name, tab in self.pages.items():
            if name in buf.tabs and hasattr(tab, "import_state"):
                try:
                    tab.import_state(buf.tabs[name])
                except Exception as e:
                    print(f"[WARN] Nie wczytano stanu {name}: {e}")

    def sync_tabs_from_config(self, conf: ParsedConfig):
        # Zapisz w buforze urządzenia
        buf = self.buffers.setdefault(self.current_device.host, DeviceBuffer())
        buf.hostname = conf.hostname or buf.hostname
        buf.tabs.setdefault("GLOBAL", {})
        buf.config = conf  # zawsze aktualny snapshot

        # Rozsyłanie do aktywnych tabów, tylko tych które istnieją teraz w stacku
        for idx in range(self.stack.count()):
            widget = self.stack.widget(idx)
            if hasattr(widget, "sync_from_config"):
                try:
                    widget.sync_from_config(conf)
                except Exception as e:
                    self.append_console(f"[WARN] Tab sync failed: {e}")

    def restore_from_snapshot(self):
        """Przywraca stan tabów z ostatniego pobranego configu (buf.config)."""
        if not self.current_device:
            return
        buf = self.buffers.get(self.current_device.host)
        if not buf or not buf.config:
            self.append_console("[INFO] Brak zapisanego snapshotu dla tego urządzenia.")
            return
        self.append_console("[RESET] Przywracanie konfiguracji z ostatniego synca...")
        self.sync_tabs_from_config(buf.config)

    def collect_pending_commands_current(self, conf: ParsedConfig) -> list[str]:
        preview = self.preview_pending_changes_current(conf)
        return preview["commands"]

    def preview_pending_changes_current(self, conf: ParsedConfig) -> dict:
        if not self.current_device:
            return {"commands": [], "operation_count": 0, "legacy_count": 0}

        # zapisz aktualny stan tabów
        self.save_tab_state(self.current_device)

        legacy_cmds: list[str] = []
        pending_ops: list[Operation] = []

        for idx in range(self.stack.count()):
            w = self.stack.widget(idx)
            if hasattr(w, "get_pending_operations"):
                pending_ops.extend(w.get_pending_operations(clear=False))
            elif hasattr(w, "get_pending_commands"):
                legacy_cmds.extend(w.get_pending_commands(clear=False))

        # 2) GlobalTab → OPERACJE
        g = self.pages.get("GLOBAL")
        if g and hasattr(g, "build_pending_from_form"):
            pending_ops.extend(g.build_pending_from_form(conf))

        # 3) Renderowanie operacji → CLI
        rendered_cmds: list[str] = []
        if pending_ops:
            validate_operations_supported_for_device(self.current_device, pending_ops)
            renderer = RendererFactory.for_vendor(self.current_device.vendor)
            rendered_cmds = renderer.render(pending_ops)

        # 4) Finalna lista
        final_cmds = []
        final_cmds.extend(c.strip() for c in legacy_cmds if c.strip())
        final_cmds.extend(c.strip() for c in rendered_cmds if c.strip())
        return {
            "commands": final_cmds,
            "operation_count": len(pending_ops),
            "legacy_count": len([c for c in legacy_cmds if c.strip()]),
        }

    def clear_pending_commands_current(self):
        for idx in range(self.stack.count()):
            w = self.stack.widget(idx)
            if hasattr(w, "clear_pending_operations"):
                w.clear_pending_operations()
            elif hasattr(w, "clear_pending_commands"):
                w.clear_pending_commands()

    def collect_pending_commands_from_buffer(self, host: str, device=None) -> list[str]:
        buf = self.buffers.get(host)
        if not buf:
            return []

        legacy_cmds: list[str] = []
        pending_ops: list[Operation] = []

        tabs_data = buf.tabs or {}

        for name, data in tabs_data.items():
            if (
                isinstance(data, dict)
                and "pending_ops" in data
                and isinstance(data["pending_ops"], list)
            ):
                pending_ops.extend(
                    op for op in data["pending_ops"] if isinstance(op, Operation)
                )

            if (
                isinstance(data, dict)
                and "pending_cmds" in data
                and isinstance(data["pending_cmds"], list)
            ):
                legacy_cmds.extend(
                    c for c in data["pending_cmds"] if isinstance(c, str)
                )

        conf = buf.config
        global_tab = self.pages.get("GLOBAL")
        if conf and global_tab and hasattr(global_tab, "build_pending_from_form"):
            pending_ops.extend(global_tab.build_pending_from_form(conf))

        rendered_cmds: list[str] = []
        if pending_ops:
            target_device = device or self.current_device
            validate_operations_supported_for_device(target_device, pending_ops)
            renderer = RendererFactory.for_vendor(target_device.vendor)
            rendered_cmds = renderer.render(pending_ops)

        final_cmds: list[str] = []
        final_cmds.extend(c.strip() for c in legacy_cmds if c.strip())
        final_cmds.extend(c.strip() for c in rendered_cmds if c.strip())

        return final_cmds

    def clear_pending_commands_in_buffer(self, host: str):
        buf = self.buffers.get(host)
        if not buf:
            return
        for name, data in (buf.tabs or {}).items():
            if isinstance(data, dict) and "pending_ops" in data:
                data["pending_ops"] = []
            if isinstance(data, dict) and "pending_cmds" in data:
                data["pending_cmds"] = []
