import re
from services.parsed_config import (
    ParsedConfig,
    ParsedInterfaces,
    ParsedVLANs,
    ParsedRouting,
    ParsedACLs,
)

_HOST_RE = re.compile(r"^\s*hostname\s+(\S+)", re.M)
_INT_START = re.compile(r"^\s*interface\s+(\S+)", re.M)
_DESC_RE = re.compile(r"^\s*description\s+(.+)$", re.M)
_IP_RE = re.compile(r"^\s*ip\s+address\s+(\S+)\s+(\S+)", re.M)
_NO_SWITCHPORT = re.compile(r"^\s*no\s+switchport", re.M)
_MODE_ACCESS = re.compile(r"^\s*switchport\s+mode\s+access", re.M)
_MODE_TRUNK = re.compile(r"^\s*switchport\s+mode\s+trunk", re.M)
_SHUT = re.compile(r"^\s*shutdown", re.M)

_VLAN_BLOCK = re.compile(r"(?ms)^\s*vlan\s+(\d+)\s*(.*?)^\s*exit\b")
_VLAN_NAME = re.compile(r"^\s*name\s+(.+)$", re.M)
_INT_ACCESS_VLAN = re.compile(r"^\s*switchport\s+access\s+vlan\s+(\d+)", re.M)

_STATIC_ROUTE = re.compile(r"^\s*ip\s+route\s+(\S+)\s+(\S+)\s+(\S+)", re.M)
_RIP = re.compile(r"(?ms)^\s*router\s+rip\s*(.*?)^(?:!\s*|router\s|\Z)")
_RIP_NETWORK = re.compile(r"^\s*network\s+(\S+)", re.M)

_OSPF = re.compile(r"(?ms)^\s*router\s+ospf\s+(\d+)\s*(.*?)^(?:!\s*|router\s|\Z)")
_OSPF_NET = re.compile(r"^\s*network\s+(\S+)\s+(\S+)\s+area\s+(\S+)", re.M)

_ACL = re.compile(
    r"^\s*access-list\s+(\d+)\s+(permit|deny)\s+(\S+)\s+(\S+)(?:\s+(\S+))?(?:\s+(\S+))?",
    re.M,
)


def parse(raw_running: str) -> ParsedConfig:
    cfg = ParsedConfig(vendor="CISCO", raw_running=raw_running)

    # hostname
    m = _HOST_RE.search(raw_running)
    if m:
        cfg.hostname = m.group(1)

    # interfaces
    ifaces = ParsedInterfaces()
    for m in _INT_START.finditer(raw_running):
        name = m.group(1)
        # blok interfejsu: od tej linii do następnego "interface" lub końca/!
        start = m.start()
        next_m = _INT_START.search(raw_running, m.end())
        end = next_m.start() if next_m else len(raw_running)
        block = raw_running[start:end]

        info = {"description": "", "ip": "", "mask": "", "mode": "", "status": "up"}
        d = _DESC_RE.search(block)
        if d:
            info["description"] = d.group(1).strip()
        ipm = _IP_RE.search(block)
        if ipm:
            info["ip"] = ipm.group(1)
            info["mask"] = ipm.group(2)
        if _NO_SWITCHPORT.search(block):
            info["mode"] = "routed"
        elif _MODE_TRUNK.search(block):
            info["mode"] = "trunk"
        elif _MODE_ACCESS.search(block):
            info["mode"] = "access"
        if _SHUT.search(block):
            info["status"] = "down"
        ifaces.items[name] = info
    cfg.interfaces = ifaces

    # VLANs (z sekcji "vlan X")
    vlans = ParsedVLANs()
    for vm in _VLAN_BLOCK.finditer(raw_running):
        vid = vm.group(1)
        block = vm.group(2)
        name = ""
        nm = _VLAN_NAME.search(block)
        if nm:
            name = nm.group(1).strip()
        vlans.items.setdefault(vid, {"name": name, "ports": []})
    # przypięcia portów po śladach w interfejsach
    for ifname, data in ifaces.items.items():
        # heurystyka aliasu: Gi0/1 itd.
        short = ifname.replace("GigabitEthernet", "Gi")
        for vlan_id in list(vlans.items.keys()):
            # sprawdź czy interfejs ma access vlan X
            # (szukamy w bloku interfejsu, więc zróbmy szybkie sprawdzenie raz jeszcze)
            # prościej: jeśli mode == access, spróbujemy znaleźć "switchport access vlan" w raw
            start = raw_running.find(f"interface {ifname}")
            end = raw_running.find("interface ", start + 1)
            if start != -1:
                block = raw_running[start : end if end != -1 else len(raw_running)]
                m = _INT_ACCESS_VLAN.search(block)
                if m and m.group(1) == vlan_id:
                    vlans.items[vlan_id]["ports"].append(short)
    cfg.vlans = vlans

    # Routing
    routing = ParsedRouting()
    for sm in _STATIC_ROUTE.finditer(raw_running):
        routing.static.append(
            {"dest": sm.group(1), "mask": sm.group(2), "nh": sm.group(3)}
        )
    rm = _RIP.search(raw_running)
    if rm:
        for net in _RIP_NETWORK.findall(rm.group(1)):
            routing.rip_networks.append(net)
    for om in _OSPF.finditer(raw_running):
        pid, block = om.group(1), om.group(2)
        for nm in _OSPF_NET.finditer(block):
            routing.ospf.append(
                {
                    "process": pid,
                    "network": nm.group(1),
                    "wildcard": nm.group(2),
                    "area": nm.group(3),
                }
            )
    cfg.routing = routing

    # ACLs
    acls = ParsedACLs()
    for am in _ACL.finditer(raw_running):
        acl, action, proto, src, wc, dest = am.groups()
        acls.rules.append(
            {
                "acl": acl,
                "action": action,
                "protocol": proto,
                "src": src,
                "wildcard": (wc or ""),
                "dest": (dest or "any"),
            }
        )
    cfg.acls = acls

    return cfg
