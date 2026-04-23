import ipaddress


def is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def is_valid_netmask(mask: str) -> bool:
    try:
        parts = [int(p) for p in mask.split(".")]
        if len(parts) != 4:
            return False
        bits = "".join(f"{p:08b}" for p in parts)
        return "01" not in bits
    except (TypeError, ValueError):
        return False


def is_valid_wildcard(wildcard: str) -> bool:
    try:
        parts = [int(p) for p in wildcard.split(".")]
        if len(parts) != 4:
            return False
        for part in parts:
            if part < 0 or part > 255:
                return False
        return True
    except (TypeError, ValueError):
        return False


def wildcard_to_mask(wildcard: str) -> str:
    parts = [255 - int(part) for part in wildcard.split(".")]
    return ".".join(str(part) for part in parts)
