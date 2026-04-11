from typing import Iterable, List
from ipaddress import IPv4Network

from operations.Operation import Operation
from operations.OperationEnum import OperationEnum
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
            if op.operation == OperationEnum.SET_HOSTNAME:
                hostname = op.args["hostname"]
                cmds.append(f"set system host-name {hostname}")
            # === VLANS ===
            elif op.operation == OperationEnum.CREATE_VLAN:
                vid = op.args["vlan_id"]
                name = op.args.get("name")

                cmds.append(f"set vlans vlan-{vid} vlan-id {vid}")
                if name:
                    cmds.append(f'set vlans vlan-{vid} description "{name}"')

            elif op.operation == OperationEnum.DELETE_VLAN:
                cmds.append(f"delete vlans vlan-{op.args['vlan_id']}")

            elif op.operation == OperationEnum.RENAME_VLAN:
                vid = op.args["vlan_id"]
                name = op.args.get("name")

                if name:
                    cmds.append(f'set vlans vlan-{vid} description "{name}"')
                else:
                    cmds.append(f"delete vlans vlan-{vid} description")
            # === INTERFACES ===
            elif op.operation == OperationEnum.SET_INTERFACE_DESCRIPTION:
                iface = op.args["iface"]
                desc = op.args.get("description")

                if desc:
                    cmds.append(f'set interfaces {iface} description "{desc}"')
                else:
                    cmds.append(f"delete interfaces {iface} description")

            elif op.operation == OperationEnum.SET_INTERFACE_IP:
                iface = op.args["iface"]
                ip = op.args["ip"]
                mask = op.args["mask"]

                cidr = IPv4Network(f"0.0.0.0/{mask}").prefixlen
                cmds.append(f"delete interfaces {iface} unit 0 family inet address")
                cmds.append(
                    f"set interfaces {iface} unit 0 family inet address {ip}/{cidr}"
                )

            elif op.operation == OperationEnum.CLEAR_INTERFACE_IP:
                iface = op.args["iface"]
                cmds.append(f"delete interfaces {iface} unit 0 family inet address")

            elif op.operation == OperationEnum.SET_INTERFACE_STATUS:
                iface = op.args["iface"]
                enabled = op.args["enabled"]

                if enabled:
                    cmds.append(f"delete interfaces {iface} disable")
                else:
                    cmds.append(f"set interfaces {iface} disable")
            # === SWITCH INTERFACES ===
            elif op.operation in {
                OperationEnum.SET_SWITCHPORT_MODE_ACCESS,
                OperationEnum.SET_SWITCHPORT_MODE_TRUNK,
                OperationEnum.SET_SWITCHPORT_MODE_ROUTED,
                OperationEnum.SET_ACCESS_VLAN,
                OperationEnum.CLEAR_ACCESS_VLAN,
                OperationEnum.SET_TRUNK_ALLOWED_VLANS,
                OperationEnum.CLEAR_TRUNK_ALLOWED_VLANS,
            }:
                raise NotImplementedError(
                    "Switchport/VLAN operations not implemented for Junos yet"
                )
            # === ROUTING ===
            elif op.operation == OperationEnum.ADD_STATIC_ROUTE:
                prefix = _ipv4_prefix(op.args["dest"], op.args["mask"])
                cmds.append(
                    f"set routing-options static route "
                    f"{prefix} next-hop {op.args['nh']}"
                )
            elif op.operation == OperationEnum.DEL_STATIC_ROUTE:
                prefix = _ipv4_prefix(op.args["dest"], op.args["mask"])
                cmds.append(f"delete routing-options static route {prefix}")
            elif op.operation in (
                OperationEnum.ENABLE_RIP,
                OperationEnum.DISABLE_RIP,
                OperationEnum.ADD_RIP_NETWORK,
                OperationEnum.DEL_RIP_NETWORK,
            ):
                raise NotImplementedError("RIP not supported on Junos yet")
            elif op.operation == OperationEnum.ADD_OSPF_NETWORK:
                cmds.append(
                    f"set protocols ospf area {op.args['area']} "
                    f"network {op.args['network']}/{op.args['wildcard']}"
                )

            elif op.operation == OperationEnum.DEL_OSPF_NETWORK:
                cmds.append(
                    f"delete protocols ospf area {op.args['area']} "
                    f"network {op.args['network']}/{op.args['wildcard']}"
                )
            elif op.operation in (
                OperationEnum.ADD_ACL_RULE,
                OperationEnum.DEL_ACL_RULE,
                OperationEnum.BIND_ACL,
                OperationEnum.UNBIND_ACL,
            ):
                raise NotImplementedError(
                    "ASA ACL operations are not supported on Juniper Junos"
                )
            else:
                raise NotImplementedError(
                    f"{self.__class__.__name__} does not this operation"
                )

        return cmds


def _ipv4_prefix(address: str, mask: str) -> str:
    """Converts GUI route fields to Junos prefix notation, e.g. 10.0.0.0/24."""
    return str(IPv4Network(f"{address}/{mask}", strict=False))
