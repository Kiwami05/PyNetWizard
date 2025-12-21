from devices.Vendor import Vendor
from renderers.base import OperationRenderer
from renderers.CiscoIOSRenderer import CiscoIOSRenderer
from renderers.JuniperJunosRenderer import JuniperJunosRenderer


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
