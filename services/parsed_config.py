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
    static: List[Dict[str, str]] = field(default_factory=list)  # [{"dest":"", "mask":"", "nh":""}, ...]
    rip_networks: List[str] = field(default_factory=list)
    ospf: List[Dict[str, str]] = field(default_factory=list)    # [{"process":"1","network":"x.x.x.x","wildcard":"0.0.0.255","area":"0"}]

@dataclass
class ParsedACLs:
    # [{"acl":"10","action":"permit","protocol":"ip","src":"any","wildcard":"","dest":"any"}]
    rules: List[Dict[str, str]] = field(default_factory=list)

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
