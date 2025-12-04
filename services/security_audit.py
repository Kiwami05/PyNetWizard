# services/security_audit.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, List, Dict


Severity = Literal["INFO", "WARNING", "CRITICAL"]


@dataclass
class SecurityFinding:
    id: str
    severity: Severity
    category: str
    message: str
    details: str
    recommendation: str
    suggested_commands: List[str]
    lines: List[int]


@dataclass
class ConfigBlock:
    kind: str  # "vty", "console", "interface", "acl", "named-acl", ...
    name: str
    start_line: int  # 1-based
    end_line: int  # 1-based
    lines: List[str]


@dataclass
class ParsedConfig:
    raw: str
    lines: List[str]  # 1-based index: line_num = index+1
    vty_blocks: List[ConfigBlock]
    console_blocks: List[ConfigBlock]
    interface_blocks: List[ConfigBlock]
    acl_blocks: List[ConfigBlock]
    named_acl_blocks: List[ConfigBlock]
    acl_usage: Dict[
        str, List[int]
    ]  # acl_name/number -> list of line numbers where used


# ==========================================================
#                 PARSOWANIE KONFIGURACJI
# ==========================================================


def parse_config(config_text: str) -> ParsedConfig:
    lines = config_text.splitlines()
    total = len(lines)

    vty_blocks: List[ConfigBlock] = []
    console_blocks: List[ConfigBlock] = []
    interface_blocks: List[ConfigBlock] = []
    acl_blocks: List[ConfigBlock] = []
    named_acl_blocks: List[ConfigBlock] = []
    acl_usage: Dict[str, List[int]] = {}

    # pomocnicze
    current_block: ConfigBlock | None = None

    def close_block(end_idx: int):
        nonlocal current_block
        if current_block is not None:
            current_block.end_line = end_idx
            current_block.lines = lines[current_block.start_line - 1 : end_idx]
            if current_block.kind == "vty":
                vty_blocks.append(current_block)
            elif current_block.kind == "console":
                console_blocks.append(current_block)
            elif current_block.kind == "interface":
                interface_blocks.append(current_block)
            elif current_block.kind == "acl":
                acl_blocks.append(current_block)
            elif current_block.kind == "named-acl":
                named_acl_blocks.append(current_block)
        current_block = None

    import re

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # wykrywanie końca bloku - IOS często używa "!"
        if stripped == "!" and current_block is not None:
            close_block(idx - 1)
            continue

        # nowe bloki
        if stripped.lower().startswith("line vty"):
            close_block(idx - 1)
            current_block = ConfigBlock(
                kind="vty",
                name=stripped,
                start_line=idx,
                end_line=idx,
                lines=[],
            )
            continue

        if stripped.lower().startswith("line con"):
            close_block(idx - 1)
            current_block = ConfigBlock(
                kind="console",
                name=stripped,
                start_line=idx,
                end_line=idx,
                lines=[],
            )
            continue

        if stripped.lower().startswith("interface "):
            close_block(idx - 1)
            current_block = ConfigBlock(
                kind="interface",
                name=stripped.split(None, 1)[1] if " " in stripped else stripped,
                start_line=idx,
                end_line=idx,
                lines=[],
            )
            continue

        # ACL klasyczne: "access-list 101 ..."
        if stripped.lower().startswith("access-list "):
            # treat each line as separate 1-line block (dla prostoty)
            acl_blocks.append(
                ConfigBlock(
                    kind="acl",
                    name=stripped,
                    start_line=idx,
                    end_line=idx,
                    lines=[line],
                )
            )

        # ACL nazwane: "ip access-list extended NAME" / "ip access-list standard NAME"
        if stripped.lower().startswith("ip access-list "):
            close_block(idx - 1)
            current_block = ConfigBlock(
                kind="named-acl",
                name=stripped,
                start_line=idx,
                end_line=idx,
                lines=[],
            )
            continue

        # zbieranie użycia ACL na interfejsach: "ip access-group XYZ in/out"
        m = re.search(
            r"\bip\s+access-group\s+(\S+)\s+(in|out)\b", stripped, re.IGNORECASE
        )
        if m:
            acl_name = m.group(1)
            acl_usage.setdefault(acl_name, []).append(idx)

    # zamknij otwarty blok na końcu pliku
    close_block(total)

    return ParsedConfig(
        raw=config_text,
        lines=lines,
        vty_blocks=vty_blocks,
        console_blocks=console_blocks,
        interface_blocks=interface_blocks,
        acl_blocks=acl_blocks,
        named_acl_blocks=named_acl_blocks,
        acl_usage=acl_usage,
    )


# ==========================================================
#                       REGUŁY
# ==========================================================


def run_security_audit(config_text: str) -> List[SecurityFinding]:
    pc = parse_config(config_text)
    findings: List[SecurityFinding] = []

    # zbiorczo odpalamy reguły
    findings.extend(rule_enable_password(pc))
    findings.extend(rule_service_password_encryption(pc))
    findings.extend(rule_plaintext_passwords(pc))
    findings.extend(rule_aaa_new_model(pc))
    findings.extend(rule_vty_telnet(pc))
    findings.extend(rule_ssh_missing(pc))
    findings.extend(rule_exec_timeout(pc))
    findings.extend(rule_console_password(pc))
    findings.extend(rule_unused_interfaces(pc))
    findings.extend(rule_dynamic_switchport(pc))
    findings.extend(rule_acl_permit_any_any(pc))
    findings.extend(rule_acl_unused(pc))
    findings.extend(rule_banner(pc))
    findings.extend(rule_snmp_public_private(pc))
    findings.extend(rule_ip_http_server(pc))
    findings.extend(rule_ip_source_route(pc))
    findings.extend(rule_cdp_run(pc))

    # jeśli nic nie znaleziono – sanity info
    if not findings:
        findings.append(
            SecurityFinding(
                id="NO_ISSUES_FOUND",
                severity="INFO",
                category="General",
                message="Nie wykryto oczywistych problemów bezpieczeństwa.",
                details="Konfiguracja nie zawiera znanych wzorców niebezpiecznych ustawień.",
                recommendation="Przejrzyj konfigurację ręcznie, aby potwierdzić zgodność z polityką bezpieczeństwa.",
                suggested_commands=[],
                lines=[],
            )
        )

    return findings


# -------------------- 1. HASŁA ----------------------------


def rule_enable_password(pc: ParsedConfig) -> List[SecurityFinding]:
    findings = []
    for i, line in enumerate(pc.lines, start=1):
        stripped = line.strip().lower()
        if stripped.startswith("enable password"):
            findings.append(
                SecurityFinding(
                    id="ENABLE_PASSWORD_INSTEAD_OF_SECRET",
                    severity="CRITICAL",
                    category="Hasła",
                    message="Użyto 'enable password' zamiast 'enable secret'.",
                    details=f"Linia {i}: {line.strip()}",
                    recommendation=(
                        "Zastąp 'enable password' przez 'enable secret', "
                        "ponieważ hasła typu 'enable password' są słabo zabezpieczone."
                    ),
                    suggested_commands=[
                        "conf t",
                        "no enable password",
                        "enable secret <silne_haslo>",
                        "end",
                        "write memory",
                    ],
                    lines=[i],
                )
            )
    return findings


def rule_service_password_encryption(pc: ParsedConfig) -> List[SecurityFinding]:
    for i, line in enumerate(pc.lines, start=1):
        if line.strip().lower().startswith("service password-encryption"):
            return []
    # jeśli nie znaleziono:
    return [
        SecurityFinding(
            id="NO_SERVICE_PASSWORD_ENCRYPTION",
            severity="WARNING",
            category="Hasła",
            message="Brak 'service password-encryption'.",
            details="Hasła mogą być przechowywane w konfiguracji w postaci jawnej.",
            recommendation=(
                "Włącz 'service password-encryption', aby zaszyfrować hasła w konfiguracji."
            ),
            suggested_commands=[
                "conf t",
                "service password-encryption",
                "end",
                "write memory",
            ],
            lines=[],
        )
    ]


def rule_plaintext_passwords(pc: ParsedConfig) -> List[SecurityFinding]:
    import re

    findings = []
    pat_plain = re.compile(r"\bpassword\s+([^7\s].*)$", re.IGNORECASE)
    for i, line in enumerate(pc.lines, start=1):
        stripped = line.strip()
        # pomijamy enable password (jest osobna reguła)
        if stripped.lower().startswith("enable password"):
            continue
        m = pat_plain.search(stripped)
        if m:
            findings.append(
                SecurityFinding(
                    id="PLAINTEXT_PASSWORD",
                    severity="CRITICAL",
                    category="Hasła",
                    message="Wykryto hasło w postaci jawnej.",
                    details=f"Linia {i}: {stripped}",
                    recommendation=(
                        "Zastosuj 'service password-encryption' lub używaj mechanizmów AAA, "
                        "aby nie przechowywać haseł w postaci jawnej."
                    ),
                    suggested_commands=[
                        "conf t",
                        "! Zmień hasło na zaszyfrowane / AAA",
                        "end",
                        "write memory",
                    ],
                    lines=[i],
                )
            )
    return findings


def rule_aaa_new_model(pc: ParsedConfig) -> List[SecurityFinding]:
    for line in pc.lines:
        if line.strip().lower().startswith("aaa new-model"):
            return []
    return [
        SecurityFinding(
            id="NO_AAA_NEW_MODEL",
            severity="INFO",
            category="AAA",
            message="Brak 'aaa new-model'.",
            details="Uwierzytelnianie nie jest oparte na AAA; używane mogą być lokalne hasła.",
            recommendation=(
                "Rozważ włączenie AAA (aaa new-model) oraz integrację z serwerem RADIUS/TACACS+ "
                "zgodnie z polityką bezpieczeństwa."
            ),
            suggested_commands=[
                "conf t",
                "aaa new-model",
                "! Dalsza konfiguracja AAA wg polityki",
                "end",
                "write memory",
            ],
            lines=[],
        )
    ]


# ---------------- 2. VTY / SSH / CLI ACCESS ----------------


def rule_vty_telnet(pc: ParsedConfig) -> List[SecurityFinding]:
    findings = []
    import re

    for block in pc.vty_blocks:
        text = "\n".join(block.lines).lower()
        has_transport = False
        has_ssh = False
        has_telnet = False

        for idx, line in enumerate(block.lines, start=block.start_line):
            s = line.strip().lower()
            if s.startswith("transport input"):
                has_transport = True
                if "ssh" in s:
                    has_ssh = True
                if "telnet" in s:
                    has_telnet = True

        if has_telnet:
            findings.append(
                SecurityFinding(
                    id="VTY_TELNET_ENABLED",
                    severity="CRITICAL",
                    category="VTY",
                    message="Telnet jest dozwolony na liniach VTY.",
                    details=f"Blok: {block.name}\n{text}",
                    recommendation=(
                        "Wyłącz Telnet na liniach VTY i wymuś użycie SSH (transport input ssh)."
                    ),
                    suggested_commands=[
                        "conf t",
                        block.name,
                        "transport input ssh",
                        "end",
                        "write memory",
                    ],
                    lines=list(range(block.start_line, block.end_line + 1)),
                )
            )
        elif has_transport and not has_ssh:
            findings.append(
                SecurityFinding(
                    id="VTY_NO_SSH_IN_TRANSPORT",
                    severity="WARNING",
                    category="VTY",
                    message="Transport input na liniach VTY nie zawiera SSH.",
                    details=f"Blok: {block.name}\n{text}",
                    recommendation=(
                        "Dodaj SSH do transport input na liniach VTY (np. 'transport input ssh')."
                    ),
                    suggested_commands=[
                        "conf t",
                        block.name,
                        "transport input ssh",
                        "end",
                        "write memory",
                    ],
                    lines=list(range(block.start_line, block.end_line + 1)),
                )
            )

    return findings


def rule_ssh_missing(pc: ParsedConfig) -> List[SecurityFinding]:
    has_crypto_key = any(
        line.strip().lower().startswith("crypto key generate rsa") for line in pc.lines
    )
    has_ip_ssh = any(line.strip().lower().startswith("ip ssh ") for line in pc.lines)
    if has_crypto_key and has_ip_ssh:
        return []

    details_parts = []
    if not has_crypto_key:
        details_parts.append("Brak 'crypto key generate rsa'.")
    if not has_ip_ssh:
        details_parts.append("Brak ustawień 'ip ssh ...'.")

    return [
        SecurityFinding(
            id="SSH_NOT_FULLY_CONFIGURED",
            severity="WARNING",
            category="SSH",
            message="SSH może nie być w pełni skonfigurowane.",
            details="\n".join(details_parts),
            recommendation=(
                "Upewnij się, że wygenerowano klucze RSA oraz skonfigurowano SSH, "
                "np. 'crypto key generate rsa', 'ip ssh version 2'."
            ),
            suggested_commands=[
                "conf t",
                "crypto key generate rsa modulus 2048",
                "ip ssh version 2",
                "end",
                "write memory",
            ],
            lines=[],
        )
    ]


def rule_exec_timeout(pc: ParsedConfig) -> List[SecurityFinding]:
    findings = []
    import re

    pat = re.compile(r"\bexec-timeout\s+0\s+0\b", re.IGNORECASE)

    for block in pc.vty_blocks + pc.console_blocks:
        bad_lines = []
        for idx, line in enumerate(block.lines, start=block.start_line):
            if pat.search(line):
                bad_lines.append(idx)

        if bad_lines:
            findings.append(
                SecurityFinding(
                    id="EXEC_TIMEOUT_0_0",
                    severity="WARNING",
                    category="VTY/Console",
                    message="Wykryto 'exec-timeout 0 0' (brak timeoutu sesji).",
                    details=f"Blok: {block.name}\nLinie: {bad_lines}",
                    recommendation=(
                        "Ustaw sensowny 'exec-timeout' (np. 10 minut) zamiast 0 0."
                    ),
                    suggested_commands=[
                        "conf t",
                        block.name,
                        "exec-timeout 10 0",
                        "end",
                        "write memory",
                    ],
                    lines=bad_lines,
                )
            )

    return findings


def rule_console_password(pc: ParsedConfig) -> List[SecurityFinding]:
    findings = []
    import re

    for block in pc.console_blocks:
        has_password = any(
            line.strip().lower().startswith("password ") for line in block.lines
        )
        if not has_password:
            findings.append(
                SecurityFinding(
                    id="CONSOLE_NO_PASSWORD",
                    severity="CRITICAL",
                    category="Console",
                    message="Linia konsoli nie ma ustawionego hasła.",
                    details=f"Blok: {block.name}",
                    recommendation=(
                        "Ustaw hasło na konsolę oraz rozważ użycie AAA do uwierzytelniania."
                    ),
                    suggested_commands=[
                        "conf t",
                        block.name,
                        "password <silne_haslo>",
                        "login",
                        "end",
                        "write memory",
                    ],
                    lines=list(range(block.start_line, block.end_line + 1)),
                )
            )
    return findings


# ---------------- 3. INTERFEJSY / PORTY --------------------


def rule_unused_interfaces(pc: ParsedConfig) -> List[SecurityFinding]:
    findings = []

    for block in pc.interface_blocks:
        # pomijamy np. Loopback, VLAN, Tunnel etc. – skupmy się na fizycznych
        name_lower = block.name.lower()
        if any(
            prefix in name_lower
            for prefix in ("loopback", "vlan", "tunnel", "port-channel")
        ):
            continue

        has_ip = any("ip address" in line.lower() for line in block.lines)
        has_switchport = any("switchport " in line.lower() for line in block.lines)
        has_desc = any(
            line.strip().lower().startswith("description ") for line in block.lines
        )
        has_shutdown = any(
            line.strip().lower().startswith("shutdown") for line in block.lines
        )

        if not has_ip and not has_switchport and not has_desc and not has_shutdown:
            findings.append(
                SecurityFinding(
                    id="INTERFACE_UNUSED_NOT_SHUTDOWN",
                    severity="INFO",
                    category="Interfejsy",
                    message=f"Możliwy nieużywany interfejs {block.name} nie jest wyłączony.",
                    details=(
                        f"Blok 'interface {block.name}' nie zawiera adresu IP, konfiguracji switchport, "
                        f"opisu ani 'shutdown'."
                    ),
                    recommendation="Rozważ wyłączenie nieużywanych interfejsów (shutdown).",
                    suggested_commands=[
                        "conf t",
                        f"interface {block.name}",
                        "description UNUSED_PORT",
                        "shutdown",
                        "end",
                        "write memory",
                    ],
                    lines=list(range(block.start_line, block.end_line + 1)),
                )
            )

    return findings


def rule_dynamic_switchport(pc: ParsedConfig) -> List[SecurityFinding]:
    findings = []
    import re

    pat = re.compile(r"\bswitchport mode dynamic\b", re.IGNORECASE)

    for block in pc.interface_blocks:
        bad_lines = []
        for idx, line in enumerate(block.lines, start=block.start_line):
            if pat.search(line):
                bad_lines.append(idx)

        if bad_lines:
            findings.append(
                SecurityFinding(
                    id="DYNAMIC_SWITCHPORT_MODE",
                    severity="WARNING",
                    category="Switching",
                    message=f"Interfejs {block.name} używa 'switchport mode dynamic'.",
                    details=f"Linie: {bad_lines}",
                    recommendation=(
                        "Unikaj 'switchport mode dynamic'. Ustaw port jako access lub trunk zgodnie z projektem."
                    ),
                    suggested_commands=[
                        "conf t",
                        f"interface {block.name}",
                        "! np. dla portu access:",
                        "switchport mode access",
                        "end",
                        "write memory",
                    ],
                    lines=bad_lines,
                )
            )

    return findings


# ---------------- 4. ACL / FILTRY RUCHU --------------------


def rule_acl_permit_any_any(pc: ParsedConfig) -> List[SecurityFinding]:
    findings = []
    import re

    pat_any_any = re.compile(r"\bpermit\s+ip\s+any\s+any\b", re.IGNORECASE)

    # klasyczne ACL
    for block in pc.acl_blocks:
        line = block.lines[0]
        if pat_any_any.search(line):
            findings.append(
                SecurityFinding(
                    id="ACL_PERMIT_IP_ANY_ANY",
                    severity="WARNING",
                    category="ACL",
                    message="ACL zawiera 'permit ip any any'.",
                    details=f"Linia {block.start_line}: {line.strip()}",
                    recommendation=(
                        "Ogranicz ACL tak, aby nie używać 'permit ip any any' lub "
                        "stosuj ją tylko w kontrolowanym kontekście."
                    ),
                    suggested_commands=[
                        "! Zmień ACL, aby zawęzić zakres dopuszczanego ruchu.",
                    ],
                    lines=[block.start_line],
                )
            )

    # named ACL (szukamy w zawartości bloku)
    for block in pc.named_acl_blocks:
        for idx_offset, line in enumerate(block.lines, start=0):
            if pat_any_any.search(line):
                line_num = block.start_line + idx_offset
                findings.append(
                    SecurityFinding(
                        id="ACL_PERMIT_IP_ANY_ANY_NAMED",
                        severity="WARNING",
                        category="ACL",
                        message="Named ACL zawiera 'permit ip any any'.",
                        details=f"Linia {line_num}: {line.strip()}",
                        recommendation=(
                            "Ogranicz ACL tak, aby nie używać 'permit ip any any' lub "
                            "stosuj ją tylko w kontrolowanym kontekście."
                        ),
                        suggested_commands=[
                            "! Zmień ACL, aby zawęzić zakres dopuszczanego ruchu.",
                        ],
                        lines=[line_num],
                    )
                )

    return findings


def rule_acl_unused(pc: ParsedConfig) -> List[SecurityFinding]:
    findings = []

    # proste wyciąganie nazw/numerów ACL
    import re

    acl_names: set[str] = set()

    for block in pc.acl_blocks:
        # "access-list 101 permit ..."
        parts = block.lines[0].strip().split()
        if len(parts) >= 3:
            acl_names.add(parts[1])

    for block in pc.named_acl_blocks:
        # "ip access-list extended NAME"
        parts = block.lines[0].strip().split()
        if len(parts) >= 4:
            acl_names.add(parts[3])

    used = set(pc.acl_usage.keys())
    unused = acl_names - used

    for acl in sorted(unused):
        findings.append(
            SecurityFinding(
                id="UNUSED_ACL",
                severity="INFO",
                category="ACL",
                message=f"ACL '{acl}' nie została przypięta do żadnego interfejsu.",
                details=f"Nazwa / numer ACL: {acl}",
                recommendation="Rozważ usunięcie nieużywanych ACL lub ich zastosowanie zgodnie z projektem.",
                suggested_commands=[
                    "conf t",
                    f"! usuń lub dostosuj ACL {acl}",
                    "end",
                    "write memory",
                ],
                lines=[],
            )
        )

    return findings


# ---------------- 5. GLOBALNE USTAWIENIA -------------------


def rule_banner(pc: ParsedConfig) -> List[SecurityFinding]:
    has_login = any("banner login" in line.lower() for line in pc.lines)
    has_motd = any("banner motd" in line.lower() for line in pc.lines)
    if has_login or has_motd:
        return []

    return [
        SecurityFinding(
            id="NO_BANNER",
            severity="INFO",
            category="Bannery",
            message="Brak skonfigurowanego bannera login/motd.",
            details="Nie wykryto 'banner login' ani 'banner motd'.",
            recommendation=(
                "Dodaj banner z informacją o polityce dostępu (np. ostrzeżenie o monitorowaniu systemu)."
            ),
            suggested_commands=[
                "conf t",
                "banner login ^",
                "UWAGA: Dostęp tylko dla uprawnionych użytkowników.",
                "^",
                "end",
                "write memory",
            ],
            lines=[],
        )
    ]


def rule_snmp_public_private(pc: ParsedConfig) -> List[SecurityFinding]:
    findings = []
    import re

    pat = re.compile(r"snmp-server\s+community\s+(public|private)\b", re.IGNORECASE)
    for i, line in enumerate(pc.lines, start=1):
        m = pat.search(line)
        if m:
            findings.append(
                SecurityFinding(
                    id="SNMP_PUBLIC_PRIVATE",
                    severity="CRITICAL",
                    category="SNMP",
                    message=f"SNMP community '{m.group(1)}' jest skonfigurowane.",
                    details=f"Linia {i}: {line.strip()}",
                    recommendation=(
                        "Zmień community na unikalne, losowe wartości i ogranicz dostęp "
                        "za pomocą ACL lub rozważ SNMPv3."
                    ),
                    suggested_commands=[
                        "conf t",
                        f"no {line.strip()}",
                        "snmp-server community <silne_community> RO",
                        "end",
                        "write memory",
                    ],
                    lines=[i],
                )
            )
    return findings


def rule_ip_http_server(pc: ParsedConfig) -> List[SecurityFinding]:
    for i, line in enumerate(pc.lines, start=1):
        s = line.strip().lower()
        if s.startswith("ip http server"):
            return [
                SecurityFinding(
                    id="IP_HTTP_SERVER_ENABLED",
                    severity="WARNING",
                    category="HTTP",
                    message="Serwer HTTP (ip http server) jest włączony.",
                    details=f"Linia {i}: {line.strip()}",
                    recommendation="Wyłącz serwer HTTP, jeśli nie jest wymagany (no ip http server).",
                    suggested_commands=[
                        "conf t",
                        "no ip http server",
                        "end",
                        "write memory",
                    ],
                    lines=[i],
                )
            ]
    return []


def rule_ip_source_route(pc: ParsedConfig) -> List[SecurityFinding]:
    for i, line in enumerate(pc.lines, start=1):
        s = line.strip().lower()
        if s.startswith("ip source-route"):
            return [
                SecurityFinding(
                    id="IP_SOURCE_ROUTE_ENABLED",
                    severity="CRITICAL",
                    category="Routing",
                    message="'ip source-route' jest włączone.",
                    details=f"Linia {i}: {line.strip()}",
                    recommendation="Wyłącz 'ip source-route', aby uniemożliwić source routing.",
                    suggested_commands=[
                        "conf t",
                        "no ip source-route",
                        "end",
                        "write memory",
                    ],
                    lines=[i],
                )
            ]
    return []


def rule_cdp_run(pc: ParsedConfig) -> List[SecurityFinding]:
    # Jeśli polityka wymaga wyłączenia CDP globalnie
    has_no_cdp = any(line.strip().lower() == "no cdp run" for line in pc.lines)
    if has_no_cdp:
        return []

    return [
        SecurityFinding(
            id="CDP_ENABLED",
            severity="INFO",
            category="CDP",
            message="CDP jest włączone (brak 'no cdp run').",
            details="Protokół Cisco Discovery Protocol jest aktywny.",
            recommendation=(
                "Jeśli CDP nie jest wymagane, wyłącz je globalnie komendą 'no cdp run' "
                "lub selektywnie na interfejsach."
            ),
            suggested_commands=[
                "conf t",
                "no cdp run",
                "end",
                "write memory",
            ],
            lines=[],
        )
    ]
