from devices.vendor import Vendor
from renderers.base import OperationRenderer
from renderers.cisco_ios_renderer import CiscoIOSRenderer
from renderers.juniper_junos_renderer import JuniperJunosRenderer


class RendererFactory:
    """
    Fabryka dobierająca renderer na podstawie vendora urządzenia.
    """

    @staticmethod
    def for_vendor(vendor: Vendor) -> OperationRenderer:
        if vendor == Vendor.CISCO:
            return CiscoIOSRenderer()
        if vendor == Vendor.JUNIPER:
            return JuniperJunosRenderer()

        raise ValueError(f"No renderer available for vendor {vendor}")
