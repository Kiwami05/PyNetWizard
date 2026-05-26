import re
import shlex
from services.parsed_config import (
    ParsedConfig,
    ParsedInterfaces,
    ParsedVLANs,
    ParsedRouting,
    ParsedACLs,
    ParsedSRXPolicies,
)


# hostname
_HOSTNAME = re.compile(r"^set system host-name (\S+)", re.M)

# interfejsy L3
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

# interface description
# set interfaces ge-0/0/0 description "WAN uplink"
_IFACE_DESC = re.compile(
    r"^set interfaces (\S+) description (.+)$",
    re.M,
)

# logical unit description
# set interfaces ge-0/0/0 unit 0 description "WAN uplink"
_IFACE_UNIT_DESC = re.compile(
    r"^set interfaces (\S+) unit (\d+) description (.+)$",
    re.M,
)

# VLAN
# set vlans VLAN10 vlan-id 10
_VLAN = re.compile(
    r"^set vlans (\S+) vlan-id (\d+)",
    re.M,
)

# interface-mode
# set interfaces ge-0/0/1 unit 0 family ethernet-switching interface-mode access
_IFACE_SWITCH_MODE = re.compile(
    r"^set interfaces (\S+) unit (\d+) family ethernet-switching interface-mode (\S+)",
    re.M,
)

# VLAN membership
# set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members VLAN10
# set interfaces ge-0/0/2 unit 0 family ethernet-switching vlan members [ VLAN10 VLAN20 ]
_IFACE_VLAN_MEMBERS = re.compile(
    r"^set interfaces (\S+) unit (\d+) family ethernet-switching vlan members (.+)$",
    re.M,
)

# static routing
# set routing-options static route 0.0.0.0/0 next-hop 10.0.0.1
_STATIC_ROUTE = re.compile(
    r"^set routing-options static route (\S+) next-hop (\S+)",
    re.M,
)

# OSPF
# set protocols ospf area 0.0.0.0 interface ge-0/0/0.0
_OSPF_INTERFACE = re.compile(
    r"^set protocols ospf area (\S+) interface (\S+)",
    re.M,
)

# RIP
# set protocols rip group default neighbor ge-0/0/0.0
_RIP_INTERFACE = re.compile(
    r"^set protocols rip group (\S+) neighbor (\S+)",
    re.M,
)

# SRX security policies
# set security policies from-zone untrust to-zone trust policy ALLOW match source-address any
# set security policies from-zone untrust to-zone trust policy ALLOW then permit
_SRX_POLICY = re.compile(
    r"^set security policies from-zone (\S+) to-zone (\S+) policy (\S+) "
    r"(match|then) (.+)$",
    re.M,
)

_INTERFACE_TERSE_LINE = re.compile(r"^(\S+)\s+(up|down)\s+(up|down)\b")


def cidr_to_mask(cidr: int) -> str:
    cidr = int(cidr)
    bits = "1" * cidr + "0" * (32 - cidr)
    return ".".join(str(int(bits[i : i + 8], 2)) for i in range(0, 32, 8))


def clean_junos_value(value: str) -> str:
    value = value.strip()
    try:
        parts = shlex.split(value)
        if parts:
            return " ".join(parts)
    except ValueError:
        pass
    return value.strip('"')


def ensure_iface(ifaces: ParsedInterfaces, iface: str) -> dict:
    if iface not in ifaces.items:
        ifaces.items[iface] = {
            "description": "",
            "ip": "",
            "mask": "",
            "mode": "routed",
            "status": "up",
        }
    return ifaces.items[iface]


def interface_name_with_unit(iface: str, unit: str) -> str:
    return iface if unit == "0" else f"{iface}.{unit}"


def parse_junos_list(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].strip()
    try:
        return shlex.split(value)
    except ValueError:
        return [part for part in value.split() if part]


def vlan_member_to_id(member: str, vlan_name_to_id: dict[str, str]) -> str:
    return vlan_name_to_id.get(member, member)


def clean_policy_value(value: str) -> str:
    return " ".join(parse_junos_list(value))


def merge_interfaces_terse(ifaces: ParsedInterfaces, raw_terse: str) -> None:
    for line in raw_terse.splitlines():
        match = _INTERFACE_TERSE_LINE.match(line.strip())
        if not match:
            continue

        iface, admin, _link = match.groups()
        info = ensure_iface(ifaces, iface)
        info["status"] = "up" if admin == "up" else "down"


def parse(raw_config: str, raw_terse: str | None = None) -> ParsedConfig:
    cfg = ParsedConfig(vendor="JUNIPER", raw_running=raw_config)

    # hostname
    m = _HOSTNAME.search(raw_config)
    if m:
        cfg.hostname = m.group(1)

    # VLANy
    vlans = ParsedVLANs()
    vlan_name_to_id: dict[str, str] = {}

    for m in _VLAN.finditer(raw_config):
        name, vid = m.groups()
        vlans.items[vid] = {
            "name": name,
            "ports": [],
        }
        vlan_name_to_id[name] = vid

    cfg.vlans = vlans

    # interfejsy
    ifaces = ParsedInterfaces()

    # adresy IP
    for m in _IFACE_INET.finditer(raw_config):
        iface, unit, addr = m.groups()
        ip, cidr = addr.split("/")
        mask = cidr_to_mask(int(cidr))

        info = ensure_iface(ifaces, interface_name_with_unit(iface, unit))
        info["ip"] = ip
        info["mask"] = mask

    # interface disable
    for m in _IFACE_DISABLE.finditer(raw_config):
        iface = m.group(1)
        ensure_iface(ifaces, iface)["status"] = "down"

    for m in _IFACE_UNIT_DESC.finditer(raw_config):
        iface, unit, desc = m.groups()
        info = ensure_iface(ifaces, interface_name_with_unit(iface, unit))
        if not info.get("description"):
            info["description"] = clean_junos_value(desc)

    for m in _IFACE_DESC.finditer(raw_config):
        iface, desc = m.groups()
        ensure_iface(ifaces, iface)["description"] = clean_junos_value(desc)

    # switchport mode
    for m in _IFACE_SWITCH_MODE.finditer(raw_config):
        iface, unit, mode = m.groups()
        if unit != "0":
            continue
        mode = mode.lower()
        if mode in ("access", "trunk"):
            ensure_iface(ifaces, iface)["mode"] = mode

    # VLAN membership
    for m in _IFACE_VLAN_MEMBERS.finditer(raw_config):
        iface, unit, members_raw = m.groups()
        if unit != "0":
            continue

        info = ensure_iface(ifaces, iface)
        members = [
            vlan_member_to_id(member, vlan_name_to_id)
            for member in parse_junos_list(members_raw)
        ]
        members = [member for member in members if member]

        if not members:
            continue

        mode = (info.get("mode") or "").lower()
        if mode == "trunk":
            existing = [str(v) for v in info.get("trunk_vlans", [])]
            for member in members:
                if member not in existing:
                    existing.append(member)
            info["trunk_vlans"] = existing
        else:
            if mode not in ("access", "trunk"):
                info["mode"] = "access"
            info["access_vlan"] = members[0]

        for member in members:
            vlan = vlans.items.get(member)
            if vlan is not None and iface not in vlan["ports"]:
                vlan["ports"].append(iface)

    if raw_terse:
        merge_interfaces_terse(ifaces, raw_terse)

    cfg.interfaces = ifaces

    # Routing
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

    for m in _OSPF_INTERFACE.finditer(raw_config):
        area, iface = m.groups()
        routing.ospf.append(
            {
                "type": "interface",
                "area": area,
                "interface": iface,
            }
        )

    routing.rip_interfaces = []
    for m in _RIP_INTERFACE.finditer(raw_config):
        group, iface = m.groups()
        routing.rip_interfaces.append(
            {
                "group": group,
                "interface": iface,
            }
        )

    cfg.routing = routing

    # ACLe (puste)
    cfg.acls = ParsedACLs()

    # Polityki SRX
    policies: dict[tuple[str, str, str], dict[str, str]] = {}
    for m in _SRX_POLICY.finditer(raw_config):
        from_zone, to_zone, name, section, detail = m.groups()
        key = (from_zone, to_zone, name)
        policy = policies.setdefault(
            key,
            {
                "name": name,
                "from_zone": from_zone,
                "to_zone": to_zone,
                "src": "",
                "dst": "",
                "application": "",
                "action": "",
            },
        )

        if section == "match":
            field, _, value = detail.partition(" ")
            value = clean_policy_value(value)
            if field == "source-address":
                policy["src"] = value
            elif field == "destination-address":
                policy["dst"] = value
            elif field == "application":
                policy["application"] = value
        elif section == "then":
            action = detail.split()[0] if detail.split() else ""
            if action in {"permit", "deny", "reject"}:
                policy["action"] = action

    cfg.srx_policies = ParsedSRXPolicies(
        policies=sorted(
            policies.values(),
            key=lambda item: (item["from_zone"], item["to_zone"], item["name"]),
        )
    )

    return cfg
