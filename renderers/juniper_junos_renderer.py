from typing import Iterable, List
from ipaddress import IPv4Network

from operations.operation import Operation
from operations.operation_type import OperationType
from renderers.base import OperationRenderer


class JuniperJunosRenderer(OperationRenderer):
    """
    Renderer operacji dla Juniper Junos.
    """

    def render(self, operations: Iterable[Operation]) -> List[str]:
        cmds: List[str] = []

        ops = list(operations)
        if not ops:
            return cmds

        for op in ops:
            if op.operation_type == OperationType.SET_HOSTNAME:
                hostname = op.args["hostname"]
                cmds.append(f"set system host-name {hostname}")
            # VLANy
            elif op.operation_type == OperationType.CREATE_VLAN:
                vid = op.args["vlan_id"]
                name = op.args.get("name")
                vlan_name = _junos_vlan_name(vid, name)

                cmds.append(f"set vlans {vlan_name} vlan-id {vid}")

            elif op.operation_type == OperationType.DELETE_VLAN:
                vid = op.args["vlan_id"]
                vlan_name = _junos_vlan_name(vid, op.args.get("vlan_name"))
                cmds.append(f"delete vlans {vlan_name}")

            elif op.operation_type == OperationType.RENAME_VLAN:
                vid = op.args["vlan_id"]
                name = op.args.get("name")
                old_name = op.args.get("old_name")
                old_vlan_name = _junos_vlan_name(vid, old_name)
                new_vlan_name = _junos_vlan_name(vid, name)

                if old_vlan_name != new_vlan_name:
                    cmds.append(f"delete vlans {old_vlan_name}")
                cmds.append(f"set vlans {new_vlan_name} vlan-id {vid}")
            # Interfejsy
            elif op.operation_type == OperationType.SET_INTERFACE_DESCRIPTION:
                iface = op.args["iface"]
                desc = op.args.get("description")
                iface_path = _junos_interface_path(iface)

                if desc:
                    cmds.append(f'set interfaces {iface_path} description "{desc}"')
                else:
                    cmds.append(f"delete interfaces {iface_path} description")

            elif op.operation_type == OperationType.SET_INTERFACE_IP:
                iface = op.args["iface"]
                ip = op.args["ip"]
                mask = op.args["mask"]
                base_iface, unit = _junos_interface_base_unit(iface)
                old_ip = op.args.get("old_ip")
                old_mask = op.args.get("old_mask")

                cidr = IPv4Network(f"0.0.0.0/{mask}").prefixlen
                delete_cmd = _junos_delete_interface_ip_command(
                    base_iface, unit, old_ip, old_mask
                )
                if delete_cmd:
                    cmds.append(delete_cmd)
                cmds.append(
                    f"set interfaces {base_iface} unit {unit} family inet address {ip}/{cidr}"
                )

            elif op.operation_type == OperationType.CLEAR_INTERFACE_IP:
                iface = op.args["iface"]
                base_iface, unit = _junos_interface_base_unit(iface)
                old_ip = op.args.get("old_ip")
                old_mask = op.args.get("old_mask")
                delete_cmd = _junos_delete_interface_ip_command(
                    base_iface, unit, old_ip, old_mask
                )
                if delete_cmd:
                    cmds.append(delete_cmd)

            elif op.operation_type == OperationType.SET_INTERFACE_STATUS:
                iface = op.args["iface"]
                enabled = op.args["enabled"]
                iface_path = _junos_interface_path(iface)

                if enabled:
                    cmds.append(f"delete interfaces {iface_path} disable")
                else:
                    cmds.append(f"set interfaces {iface_path} disable")
            # Interfejsy switcha
            elif op.operation_type == OperationType.SET_SWITCHPORT_MODE_ACCESS:
                iface = op.args["iface"]
                cmds.append(
                    f"set interfaces {iface} unit 0 family ethernet-switching "
                    f"interface-mode access"
                )
            elif op.operation_type == OperationType.SET_SWITCHPORT_MODE_TRUNK:
                iface = op.args["iface"]
                cmds.append(
                    f"set interfaces {iface} unit 0 family ethernet-switching "
                    f"interface-mode trunk"
                )
            elif op.operation_type == OperationType.SET_SWITCHPORT_MODE_ROUTED:
                iface = op.args["iface"]
                cmds.append(
                    f"delete interfaces {iface} unit 0 family ethernet-switching"
                )
            elif op.operation_type == OperationType.SET_ACCESS_VLAN:
                iface = op.args["iface"]
                vlan = _junos_vlan_name(op.args["vlan_id"], op.args.get("vlan_name"))
                cmds.append(
                    f"set interfaces {iface} unit 0 family ethernet-switching "
                    f"interface-mode access"
                )
                cmds.append(
                    f"delete interfaces {iface} unit 0 family ethernet-switching "
                    f"vlan members"
                )
                cmds.append(
                    f"set interfaces {iface} unit 0 family ethernet-switching "
                    f"vlan members {vlan}"
                )
            elif op.operation_type == OperationType.CLEAR_ACCESS_VLAN:
                iface = op.args["iface"]
                cmds.append(
                    f"delete interfaces {iface} unit 0 family ethernet-switching "
                    f"vlan members"
                )
            elif op.operation_type == OperationType.SET_TRUNK_ALLOWED_VLANS:
                iface = op.args["iface"]
                vlan_names = op.args.get("vlan_names") or {}
                vlans = [
                    _junos_vlan_name(vlan, vlan_names.get(int(vlan)))
                    for vlan in op.args["vlans"]
                ]
                cmds.append(
                    f"set interfaces {iface} unit 0 family ethernet-switching "
                    f"interface-mode trunk"
                )
                cmds.append(
                    f"delete interfaces {iface} unit 0 family ethernet-switching "
                    f"vlan members"
                )
                if vlans:
                    cmds.append(
                        f"set interfaces {iface} unit 0 family ethernet-switching "
                        f"vlan members [ {' '.join(vlans)} ]"
                    )
            elif op.operation_type == OperationType.CLEAR_TRUNK_ALLOWED_VLANS:
                iface = op.args["iface"]
                cmds.append(
                    f"delete interfaces {iface} unit 0 family ethernet-switching "
                    f"vlan members"
                )
            # Ruting
            elif op.operation_type == OperationType.ADD_STATIC_ROUTE:
                prefix = _ipv4_prefix(op.args["dest"], op.args["mask"])
                cmds.append(
                    f"set routing-options static route "
                    f"{prefix} next-hop {op.args['nh']}"
                )
            elif op.operation_type == OperationType.DEL_STATIC_ROUTE:
                prefix = _ipv4_prefix(op.args["dest"], op.args["mask"])
                cmds.append(f"delete routing-options static route {prefix}")
            elif op.operation_type == OperationType.ADD_RIP_INTERFACE:
                cmds.append(
                    f"set protocols rip group {op.args['group']} "
                    f"neighbor {op.args['interface']}"
                )
            elif op.operation_type == OperationType.DEL_RIP_INTERFACE:
                cmds.append(
                    f"delete protocols rip group {op.args['group']} "
                    f"neighbor {op.args['interface']}"
                )
            elif op.operation_type == OperationType.ADD_OSPF_INTERFACE:
                cmds.append(
                    f"set protocols ospf area {op.args['area']} "
                    f"interface {op.args['interface']}"
                )
            elif op.operation_type == OperationType.DEL_OSPF_INTERFACE:
                cmds.append(
                    f"delete protocols ospf area {op.args['area']} "
                    f"interface {op.args['interface']}"
                )
            elif op.operation_type in (
                OperationType.ENABLE_RIP,
                OperationType.DISABLE_RIP,
                OperationType.ADD_RIP_NETWORK,
                OperationType.DEL_RIP_NETWORK,
            ):
                raise NotImplementedError("Cisco-style RIP is not supported on Junos")
            elif op.operation_type in (
                OperationType.ADD_OSPF_NETWORK,
                OperationType.DEL_OSPF_NETWORK,
            ):
                raise NotImplementedError("Cisco-style OSPF is not supported on Junos")
            # Polityki SRX
            elif op.operation_type == OperationType.ADD_SRX_POLICY:
                from_zone = op.args["from_zone"]
                to_zone = op.args["to_zone"]
                name = op.args["name"]
                base = (
                    f"set security policies from-zone {from_zone} "
                    f"to-zone {to_zone} policy {name}"
                )
                cmds.append(f"{base} match source-address {op.args['src']}")
                cmds.append(f"{base} match destination-address {op.args['dst']}")
                cmds.append(f"{base} match application {op.args['application']}")
                cmds.append(f"{base} then {op.args['action']}")
            elif op.operation_type == OperationType.DEL_SRX_POLICY:
                cmds.append(
                    f"delete security policies from-zone {op.args['from_zone']} "
                    f"to-zone {op.args['to_zone']} policy {op.args['name']}"
                )
            elif op.operation_type in (
                OperationType.ADD_ACL_RULE,
                OperationType.DEL_ACL_RULE,
                OperationType.BIND_ACL,
                OperationType.UNBIND_ACL,
            ):
                raise NotImplementedError(
                    "ASA ACL operations are not supported on Juniper Junos"
                )
            else:
                raise NotImplementedError(
                    f"{self.__class__.__name__} does not this operation"
                )

        return _dedupe_adjacent(cmds)


def _ipv4_prefix(address: str, mask: str) -> str:
    """Konwertuje pola tras w interfejsie graficznym na notację prefiksową Junos, np. 10.0.0.0/24."""
    return str(IPv4Network(f"{address}/{mask}", strict=False))


def _junos_vlan_name(vlan_id, configured_name: str | None = None) -> str:
    """Zgodne z aktualnymi zasadami nazewnictwa obiektów VLAN w systemie Junos stosowanymi przez aplikację"""
    if configured_name:
        return configured_name
    return f"vlan-{vlan_id}"


def _junos_interface_base_unit(iface: str) -> tuple[str, str]:
    if "." not in iface:
        return iface, "0"
    base, unit = iface.rsplit(".", 1)
    if unit.isdigit():
        return base, unit
    return iface, "0"


def _junos_interface_path(iface: str) -> str:
    base, unit = _junos_interface_base_unit(iface)
    if unit == "0" and base == iface:
        return iface
    return f"{base} unit {unit}"


def _junos_delete_interface_ip_command(
    base_iface: str, unit: str, old_ip: str | None, old_mask: str | None
) -> str | None:
    if old_ip and old_mask:
        cidr = IPv4Network(f"0.0.0.0/{old_mask}").prefixlen
        return (
            f"delete interfaces {base_iface} unit {unit} family inet address "
            f"{old_ip}/{cidr}"
        )
    return None


def _dedupe_adjacent(commands: list[str]) -> list[str]:
    deduped: list[str] = []
    for command in commands:
        if not deduped or deduped[-1] != command:
            deduped.append(command)
    return deduped
