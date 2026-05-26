from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class ParsedInterfaces:
    # { "GigabitEthernet0/0": {"description": "...", "ip": "x.x.x.x", "mask": "y.y.y.y", "mode": "access/trunk/routed", "status": "up/down"} }
    items: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ParsedVLANs:
    # { "10": {"name": "Management", "ports": ["Gi0/2", ...]} }
    items: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ParsedRouting:
    static: List[Dict[str, str]] = field(
        default_factory=list
    )  # [{"dest":"", "mask":"", "nh":""}, ...]
    rip_networks: List[str] = field(default_factory=list)
    rip_interfaces: List[Dict[str, str]] = field(
        default_factory=list
    )  # Juniper: [{"group":"default","interface":"ge-0/0/0.0"}]
    ospf: List[Dict[str, str]] = field(
        default_factory=list
    )  # [{"process":"1","network":"x.x.x.x","wildcard":"0.0.0.255","area":"0"}]


@dataclass
class ParsedACLs:
    # [{"acl":"10","action":"permit","protocol":"ip","src":"any","wildcard":"","dest":"any"}]
    rules: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ParsedSRXPolicies:
    # [{"name":"ALLOW-HTTPS","from_zone":"untrust","to_zone":"trust","src":"any","dst":"WEB-SRV","application":"junos-https","action":"permit"}]
    policies: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ParsedConfig:
    vendor: str
    hostname: Optional[str] = None
    raw_running: str = ""
    raw_startup: str = ""
    interfaces: ParsedInterfaces = field(default_factory=ParsedInterfaces)
    vlans: ParsedVLANs = field(default_factory=ParsedVLANs)
    routing: ParsedRouting = field(default_factory=ParsedRouting)
    acls: ParsedACLs = field(default_factory=ParsedACLs)
    srx_policies: ParsedSRXPolicies = field(default_factory=ParsedSRXPolicies)


_JUNOS_USER_BASE_PREFIXES = (
    "ge-",
    "xe-",
    "et-",
    "fe-",
    "ae",
    "reth",
    "st0",
    "gr-",
    "lt-",
    "irb",
    "vlan",
    "lo0",
    "fxp",
    "em",
    "me",
)
_JUNOS_HIDDEN_BASE_PREFIXES = (
    "cbp",
    "demux",
    "dsc",
    "esi",
    "fti",
    "gre",
    "ipip",
    "jsrv",
    "lc-",
    "lsi",
    "mif",
    "mtun",
    "pfe-",
    "pfh-",
    "pimd",
    "pime",
    "pip",
    "pp",
    "rbeb",
    "tap",
    "vtep",
)
_JUNOS_RESERVED_UNITS = {"16384", "16385", "16386"}


def _junos_split_interface_name(name: str) -> tuple[str, str | None]:
    if "." not in name:
        return name, None
    base, unit = name.rsplit(".", 1)
    return base, unit


def _junos_has_meaningful_config(conf: "ParsedConfig", name: str, data: Dict[str, Any]) -> bool:
    if data.get("description") or data.get("ip") or data.get("mask"):
        return True
    if data.get("mode") in {"access", "trunk"}:
        return True
    if data.get("access_vlan") or data.get("trunk_vlans") or data.get("trunk_allowed"):
        return True

    related_names = {name}
    base, unit = _junos_split_interface_name(name)
    if unit is None:
        related_names.add(f"{name}.0")
    elif unit == "0":
        related_names.add(base)

    for rip in conf.routing.rip_interfaces:
        if rip.get("interface") in related_names:
            return True
    for ospf in conf.routing.ospf:
        if ospf.get("type") == "interface" and ospf.get("interface") in related_names:
            return True

    return False


def is_user_visible_interface(
    conf: "ParsedConfig", name: str, data: Dict[str, Any] | None = None
) -> bool:
    if conf.vendor != "JUNIPER":
        return True

    data = data or conf.interfaces.items.get(name, {})
    base, unit = _junos_split_interface_name(name)
    meaningful = _junos_has_meaningful_config(conf, name, data)

    if unit is not None:
        if unit == "0":
            return False
        if unit in _JUNOS_RESERVED_UNITS and not meaningful:
            return False
        if base.startswith(_JUNOS_HIDDEN_BASE_PREFIXES):
            return meaningful
        return meaningful

    has_visible_logical_child = any(
        child_name.startswith(f"{name}.")
        and (child_unit := _junos_split_interface_name(child_name)[1]) not in (None, "0")
        and _junos_has_meaningful_config(conf, child_name, child_data)
        for child_name, child_data in conf.interfaces.items.items()
    )
    if has_visible_logical_child and not meaningful:
        return False

    if base.startswith(_JUNOS_HIDDEN_BASE_PREFIXES):
        return meaningful
    if base.startswith(_JUNOS_USER_BASE_PREFIXES):
        return True
    return meaningful


def iter_user_visible_interfaces(conf: "ParsedConfig") -> List[tuple[str, Dict[str, Any]]]:
    return [
        (name, data)
        for name, data in conf.interfaces.items.items()
        if is_user_visible_interface(conf, name, data)
    ]
