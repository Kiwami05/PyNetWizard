from PySide6.QtWidgets import QVBoxLayout, QLabel, QTabWidget

from gui.tabs.base_config_tab import BaseConfigTab
from gui.tabs.routing_ospf_tab import OSPFRoutingTab
from gui.tabs.routing_rip_tab import RIPRoutingTab
from gui.tabs.routing_static_tab import StaticRoutingTab
from operations.operation import Operation
from services.parsed_config import ParsedConfig


class RoutingTab(BaseConfigTab):
    """
    Kontener routingu dla tras statycznych, RIP i OSPF.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        main_layout.addWidget(QLabel("<h2>Konfiguracja routingu</h2>"))

        self.subtabs = QTabWidget()
        self.static_tab = StaticRoutingTab()
        self.rip_tab = RIPRoutingTab()
        self.ospf_tab = OSPFRoutingTab()
        self.subtabs.addTab(self.static_tab, "Statyczny")
        self.subtabs.addTab(self.rip_tab, "RIP")
        self.subtabs.addTab(self.ospf_tab, "OSPF")
        main_layout.addWidget(self.subtabs, 4)

    def set_device_context(self, device):
        self.static_tab.set_device_context(device)
        self.rip_tab.set_device_context(device)
        self.ospf_tab.set_device_context(device)

    def set_logger(self, log_message):
        self.static_tab.set_logger(log_message)
        self.rip_tab.set_logger(log_message)
        self.ospf_tab.set_logger(log_message)

    def get_pending_operations(self, clear=False) -> list[Operation]:
        ops = self.static_tab.get_pending_operations(clear=clear)
        ops.extend(self.rip_tab.get_pending_operations(clear=clear))
        ops.extend(self.ospf_tab.get_pending_operations(clear=clear))
        return ops

    def clear_pending_operations(self):
        self.static_tab.clear_pending_operations()
        self.rip_tab.clear_pending_operations()
        self.ospf_tab.clear_pending_operations()

    def export_state(self):
        static_state = self.static_tab.export_state()
        rip_state = self.rip_tab.export_state()
        ospf_state = self.ospf_tab.export_state()

        return {
            "static": static_state.get("routes", []),
            "static_state": static_state,
            "rip_enabled": rip_state.get("rip_enabled", False),
            "rip": rip_state.get("rip", []),
            "junos_rip": rip_state.get("junos_rip", []),
            "rip_state": rip_state,
            "ospf": ospf_state.get("ospf", []),
            "junos_ospf": ospf_state.get("junos_ospf", []),
            "ospf_state": ospf_state,
            "pending_ops": ospf_state.get("pending_ops", []),
        }

    def import_state(self, data):
        static_state = data.get("static_state")
        if not isinstance(static_state, dict):
            static_state = {
                "routes": data.get("static", []),
                "pending_ops": [],
            }
        self.static_tab.import_state(static_state)

        rip_state = data.get("rip_state")
        if not isinstance(rip_state, dict):
            rip_state = {
                "rip_enabled": data.get("rip_enabled", False),
                "rip": data.get("rip", []),
                "junos_rip": data.get("junos_rip", []),
                "pending_ops": [],
            }
        self.rip_tab.import_state(rip_state)

        ospf_state = data.get("ospf_state")
        if not isinstance(ospf_state, dict):
            ospf_state = {
                "ospf": data.get("ospf", []),
                "junos_ospf": data.get("junos_ospf", []),
                "pending_ops": data.get("pending_ops", []),
            }
        self.ospf_tab.import_state(ospf_state)

    def sync_from_config(self, conf: ParsedConfig):
        self.static_tab.sync_from_config(conf)
        self.rip_tab.sync_from_config(conf)
        self.ospf_tab.sync_from_config(conf)
