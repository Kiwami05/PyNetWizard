# services/parsers/juniper_junos.py
import re
from services.parsed_config import (
    ParsedConfig,
    ParsedInterfaces,
    ParsedVLANs,
    ParsedRouting,
    ParsedACLs,
)


# ==========================================================
#                     REGEXY
# ==========================================================

# hostname
_HOSTNAME = re.compile(r"^set system host-name (\S+)", re.M)

# interfaces L3
# set interfaces ge-0/0/0 unit 0 family inet address 10.0.0.1/24
_IFACE_INET = re.compile(
    r"^set interfaces (\S+) unit (\d+) family inet address (\S+)",
    re.M,
)

# interface disable
# set interfaces ge-0/0/0 disable
_IFACE_DISABLE = re.compile(
    r"^set interfaces (\S+) disable",
    re.M,
)

# VLAN
# set vlans VLAN10 vlan-id 10
_VLAN = re.compile(
    r"^set vlans (\S+) vlan-id (\d+)",
    re.M,
)

# static routing
# set routing-options static route 0.0.0.0/0 next-hop 10.0.0.1
_STATIC_ROUTE = re.compile(
    r"^set routing-options static route (\S+) next-hop (\S+)",
    re.M,
)


# ==========================================================
#                   HELPERY
# ==========================================================

def cidr_to_mask(cidr: int) -> str:
    cidr = int(cidr)
    bits = "1" * cidr + "0" * (32 - cidr)
    return ".".join(str(int(bits[i:i+8], 2)) for i in range(0, 32, 8))


# ==========================================================
#                   PARSER GŁÓWNY
# ==========================================================

def parse(raw_config: str) -> ParsedConfig:
    cfg = ParsedConfig(vendor="JUNIPER", raw_running=raw_config)

    # ---------------- hostname ----------------
    m = _HOSTNAME.search(raw_config)
    if m:
        cfg.hostname = m.group(1)

    # ---------------- interfaces ----------------
    ifaces = ParsedInterfaces()

    # IP addresses
    for m in _IFACE_INET.finditer(raw_config):
        iface, unit, addr = m.groups()

        # v1: obsługujemy tylko unit 0
        if unit != "0":
            continue

        ip, cidr = addr.split("/")
        mask = cidr_to_mask(int(cidr))

        if iface not in ifaces.items:
            ifaces.items[iface] = {
                "description": "",
                "ip": "",
                "mask": "",
                "mode": "routed",
                "status": "up",
            }

        ifaces.items[iface]["ip"] = ip
        ifaces.items[iface]["mask"] = mask

    # interface disable
    for m in _IFACE_DISABLE.finditer(raw_config):
        iface = m.group(1)
        if iface not in ifaces.items:
            ifaces.items[iface] = {
                "description": "",
                "ip": "",
                "mask": "",
                "mode": "routed",
                "status": "down",
            }
        else:
            ifaces.items[iface]["status"] = "down"

    cfg.interfaces = ifaces

    # ---------------- VLANs ----------------
    vlans = ParsedVLANs()

    for m in _VLAN.finditer(raw_config):
        name, vid = m.groups()
        vlans.items[vid] = {
            "name": name,
            "ports": [],  # Juniper: porty później (bridge-domains)
        }

    cfg.vlans = vlans

    # ---------------- Routing ----------------
    routing = ParsedRouting()

    for m in _STATIC_ROUTE.finditer(raw_config):
        prefix, nh = m.groups()
        net, cidr = prefix.split("/")
        mask = cidr_to_mask(int(cidr))
        routing.static.append(
            {
                "dest": net,
                "mask": mask,
                "nh": nh,
            }
        )

    cfg.routing = routing

    # ---------------- ACLs (puste) ----------------
    cfg.acls = ParsedACLs()

    return cfg
