# services/security_audit.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple


Severity = Literal["INFO", "WARNING", "CRITICAL"]


RulesWarnings = List[str]


def get_rules_file_path() -> Path:
    """Returns the default location of the user rules file (multi-document YAML)."""

    # Plik trzymamy w katalogu głównym projektu (obok main.py / pyproject.toml),
    # żeby był przenośny (niezależny od OS i profilu użytkownika).
    return _find_project_root(Path(__file__).resolve()) / "security_rules.yml"


def _find_project_root(start: Path) -> Path:
    """Best-effort: find repo/project root by walking upwards.

    We stop at the first directory that looks like the project root.
    """

    for p in [start.parent, *start.parents]:
        if (p / "pyproject.toml").exists() or (p / "main.py").exists():
            return p
    # Fallback: directory two levels up from this file (services/ -> project root)
    try:
        return start.parents[1]
    except Exception:
        return start.parent


DEFAULT_RULES_YAML = """# PyNetWizard - Security Audit Rules (multi-document YAML)
#
# To jest plik reguł dla audytu bezpieczeństwa.
# - Każdy dokument (oddzielony linią '---') to jedna reguła lub override.
# - Jeśli jeden dokument jest uszkodzony, aplikacja spróbuje wczytać pozostałe.
#
# Typy dokumentów:
# 1) override
#    - pozwala wyłączyć/włączyć regułę wbudowaną lub zmienić jej parametry.
#
# 2) rule
#    - prosta reguła oparta o "contains"/"not_contains"/"regex" na surowym tekście konfiguracji.
#
# Wskazówka: regex jest domyślnie case-insensitive (chyba że case_sensitive: true).
#
# Vendor/platform:
# - Jeśli audyt jest uruchamiany z kontekstu urządzenia w aplikacji, platforma (vendor)
#   może być przekazana z GUI (np. 'cisco_ios' lub 'junos').
# - Jeśli audyt jest uruchamiany na pliku bez kontekstu urządzenia, aplikacja spróbuje
#   wykryć platformę heurystycznie po tekście konfiguracji.
# - Możesz ograniczyć regułę/override do platform przez pole 'vendors'.

---
type: override
id: CDP_ENABLED
enabled: true

# ---------------------------------------------------------
# Preset Junos
#
# Reguły wbudowane są IOS-centric, więc na JunOS część z nich generuje false-positive
# (szczególnie te, które sprawdzają "brak ..." dla komend IOS).
# Poniższe override'y wyłączają takie reguły, gdy vendor=junos.
#
# Domyślne reguły Junos poniżej są dopasowane do wyjścia:
#   show configuration | display set
# ---------------------------------------------------------

---
type: override
id: NO_SERVICE_PASSWORD_ENCRYPTION
vendors: [junos]
enabled: false

---
type: override
id: NO_AAA_NEW_MODEL
vendors: [junos]
enabled: false

---
type: override
id: SSH_NOT_FULLY_CONFIGURED
vendors: [junos]
enabled: false

---
type: override
id: NO_BANNER
vendors: [junos]
enabled: false

---
type: override
id: CDP_ENABLED
vendors: [junos]
enabled: false

# =====================
#  Junos - dostępy / usługi
# =====================

---
type: rule
id: JUNOS_TELNET_SERVICE_ENABLED
vendors: [junos]
severity: CRITICAL
category: Junos
message: "Junos: włączony Telnet"
when:
  regex: '^set\\s+system\\s+services\\s+telnet\\b'
details: "Usługa Telnet jest uznawana za niebezpieczną (brak szyfrowania)."
recommendation: "Wyłącz Telnet i używaj SSH."
suggested_commands:
  - "delete system services telnet"

---
type: rule
id: JUNOS_FTP_SERVICE_ENABLED
vendors: [junos]
severity: CRITICAL
category: Junos
message: "Junos: włączony FTP"
when:
  regex: '^set\\s+system\\s+services\\s+ftp\\b'
details: "Wykryto usługę FTP (brak szyfrowania)."
recommendation: "Wyłącz FTP lub zastąp bezpiecznym mechanizmem transferu (np. SCP/SFTP)."
suggested_commands:
  - "delete system services ftp"

---
type: rule
id: JUNOS_RLOGIN_SERVICE_ENABLED
vendors: [junos]
severity: CRITICAL
category: Junos
message: "Junos: włączony rlogin"
when:
  regex: '^set\\s+system\\s+services\\s+rlogin\\b'
details: "Wykryto usługę rlogin (brak szyfrowania)."
recommendation: "Wyłącz rlogin i używaj SSH."
suggested_commands:
  - "delete system services rlogin"

---
type: rule
id: JUNOS_RSH_SERVICE_ENABLED
vendors: [junos]
severity: CRITICAL
category: Junos
message: "Junos: włączony rsh"
when:
  regex: '^set\\s+system\\s+services\\s+rsh\\b'
details: "Wykryto usługę rsh (brak szyfrowania)."
recommendation: "Wyłącz rsh i używaj SSH."
suggested_commands:
  - "delete system services rsh"

---
type: rule
id: JUNOS_TFTP_SERVICE_ENABLED
vendors: [junos]
severity: WARNING
category: Junos
message: "Junos: włączony TFTP"
when:
  regex: '^set\\s+system\\s+services\\s+tftp\\b'
details: "Wykryto usługę TFTP (brak szyfrowania)."
recommendation: "Wyłącz TFTP lub ogranicz jego użycie do zamkniętych, zaufanych sieci."
suggested_commands:
  - "delete system services tftp"

---
type: rule
id: JUNOS_WEB_MANAGEMENT_HTTP_ENABLED
vendors: [junos]
severity: WARNING
category: Junos
message: "Junos: włączony J-Web po HTTP"
when:
  regex: '^set\\s+system\\s+services\\s+web-management\\s+http\\b'
details: "Wykryto web-management http (brak szyfrowania)."
recommendation: "Wyłącz HTTP dla J-Web; jeśli korzystasz z GUI, używaj HTTPS."
suggested_commands:
  - "delete system services web-management http"

# =====================
#  Junos - SSH
# =====================

---
type: rule
id: JUNOS_SSH_ROOT_LOGIN_ALLOW
vendors: [junos]
severity: CRITICAL
category: Junos
message: "Junos: dopuszczone logowanie root po SSH"
when:
  regex: '^set\\s+system\\s+services\\s+ssh\\s+root-login\\s+allow\\b'
details: "Wykryto 'root-login allow' w konfiguracji SSH."
recommendation: "Rozważ ustawienie 'root-login deny' albo ograniczenie dostępu zgodnie z polityką."
suggested_commands:
  - "set system services ssh root-login deny"

---
type: rule
id: JUNOS_SSH_PROTOCOL_V1
vendors: [junos]
severity: CRITICAL
category: Junos
message: "Junos: SSH w wersji v1"
when:
  regex: '^set\\s+system\\s+services\\s+ssh\\s+protocol-version\\s+v1\\b'
details: "SSH v1 jest uznawane za niebezpieczne i przestarzałe."
recommendation: "Ustaw SSH na v2 (lub usuń konfigurację v1)."
suggested_commands:
  - "set system services ssh protocol-version v2"

---
type: rule
id: JUNOS_SSH_KEYS_ONLY_RECOMMENDED
vendors: [junos]
severity: INFO
category: Junos
message: "Junos: rozważ wymuszenie logowania kluczami (no-passwords)"
when:
  contains:
    - "set system services ssh"
  not_contains:
    - "set system services ssh no-passwords"
  operator: all
  case_sensitive: false
details: "SSH jest włączone, ale nie wykryto 'no-passwords'. To może oznaczać dopuszczone logowanie hasłem."
recommendation: "Jeśli polityka tego wymaga, wymuś logowanie kluczami (no-passwords) i usuń hasła lokalne."
suggested_commands:
  - "set system services ssh no-passwords"

# =====================
#  Junos - SNMP
# =====================

---
type: rule
id: JUNOS_SNMP_PUBLIC_PRIVATE
vendors: [junos]
severity: CRITICAL
category: Junos
message: "Junos: SNMP community public/private"
when:
  regex: '^set\\s+snmp\\s+community\\s+(public|private)\\b'
details: "Wykryto community SNMP o domyślnej nazwie public/private."
recommendation: "Zmień community na nieoczywiste, ogranicz dostęp (clients), rozważ SNMPv3."
suggested_commands:
  - "delete snmp community public"
  - "delete snmp community private"
"""


def ensure_rules_file_exists() -> Tuple[Path, str | None]:
    """Public helper used by GUI.

    Returns (path, warning). Warning is None on success.
    """

    path = get_rules_file_path()
    w = _ensure_default_rules_file(path)
    return path, w


def _ensure_default_rules_file(path: Path) -> str | None:
    if path.exists():
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_RULES_YAML, encoding="utf-8")
        return None
    except Exception as e:
        return f"Nie udało się utworzyć domyślnego pliku reguł: {path} ({type(e).__name__}: {e})"


def _split_multi_document_yaml(text: str) -> List[str]:
    """Split multi-doc YAML into separate documents.

    We only treat a line that is exactly '---' (optionally with surrounding whitespace)
    as a document separator.
    """

    import re

    # Normalize newlines
    src = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"(?m)^\s*---\s*$", src)
    # Keep non-empty docs
    docs = [p.strip() for p in parts if p.strip()]
    return docs


@dataclass
class YamlRule:
    id: str
    vendors: List[str] | None
    severity: Severity
    category: str
    message: str
    details: str
    recommendation: str
    suggested_commands: List[str]
    when: Dict[str, Any]


@dataclass
class BuiltinOverride:
    id: str
    vendors: List[str] | None = None
    enabled: bool | None = None
    severity: Severity | None = None
    category: str | None = None
    message: str | None = None
    details: str | None = None
    recommendation: str | None = None
    suggested_commands: List[str] | None = None


def _load_user_rules() -> Tuple[
    Dict[str, BuiltinOverride], List[YamlRule], RulesWarnings
]:
    """Load multi-document YAML rules.

    The loader is intentionally tolerant:
    - If a document fails to parse, we skip it and store a warning.
    - If a document is missing required fields, we skip it and store a warning.

    Returns:
        overrides: mapping builtin_id -> BuiltinOverride
        yaml_rules: list of custom rules
        warnings: list of warning strings
    """

    warnings: RulesWarnings = []

    path = get_rules_file_path()
    w = _ensure_default_rules_file(path)
    if w:
        warnings.append(w)
    overrides: Dict[str, BuiltinOverride] = {}
    yaml_rules: List[YamlRule] = []

    try:
        import yaml  # type: ignore
    except Exception:
        warnings.append(
            "Nie znaleziono biblioteki PyYAML. Reguły z pliku YAML nie zostaną wczytane. "
            "Zainstaluj zależność 'pyyaml' i uruchom ponownie."
        )
        return overrides, yaml_rules, warnings

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        warnings.append(
            f"Nie udało się wczytać pliku reguł: {path} ({type(e).__name__}: {e})"
        )
        return overrides, yaml_rules, warnings

    docs = _split_multi_document_yaml(text)
    if not docs:
        return overrides, yaml_rules, warnings

    for doc_idx, doc_text in enumerate(docs, start=1):
        try:
            data = yaml.safe_load(doc_text)
        except Exception as e:
            warnings.append(
                f"Dokument #{doc_idx}: błąd parsowania YAML ({type(e).__name__}: {e}). Dokument pominięty."
            )
            continue

        # Dokument może być pusty (np. komentarze przed pierwszym '---').
        # W takim przypadku po prostu go pomijamy bez ostrzeżenia.
        if data is None:
            continue

        if not isinstance(data, dict):
            warnings.append(
                f"Dokument #{doc_idx}: oczekiwano mapy (key: value). Dokument pominięty."
            )
            continue

        doc_type = str(data.get("type", "rule")).strip().lower()
        rid = data.get("id")
        if not rid or not isinstance(rid, str):
            warnings.append(
                f"Dokument #{doc_idx}: brak poprawnego pola 'id'. Dokument pominięty."
            )
            continue

        if doc_type == "override":
            try:
                vendors = data.get("vendors")
                if isinstance(vendors, str):
                    vendors = [vendors]
                if vendors is not None and not isinstance(vendors, list):
                    vendors = None

                ov = BuiltinOverride(
                    id=rid,
                    vendors=[str(x) for x in vendors]
                    if isinstance(vendors, list)
                    else None,
                    enabled=data.get("enabled"),
                    severity=data.get("severity"),
                    category=data.get("category"),
                    message=data.get("message"),
                    details=data.get("details"),
                    recommendation=data.get("recommendation"),
                    suggested_commands=data.get("suggested_commands"),
                )
            except Exception as e:
                warnings.append(
                    f"Dokument #{doc_idx} (override {rid}): błąd danych ({type(e).__name__}: {e}). Dokument pominięty."
                )
                continue
            overrides[rid] = ov
            continue

        # default: custom rule
        when = data.get("when")
        if not isinstance(when, dict):
            warnings.append(
                f"Dokument #{doc_idx} (rule {rid}): brak poprawnego pola 'when'. Dokument pominięty."
            )
            continue

        vendors = data.get("vendors")
        if isinstance(vendors, str):
            vendors = [vendors]
        if vendors is not None and not isinstance(vendors, list):
            warnings.append(
                f"Dokument #{doc_idx} (rule {rid}): vendors musi być listą lub stringiem. Ignoruję vendors."
            )
            vendors = None

        severity = data.get("severity", "WARNING")
        if severity not in ("INFO", "WARNING", "CRITICAL"):
            warnings.append(
                f"Dokument #{doc_idx} (rule {rid}): niepoprawne severity '{severity}'. Używam WARNING."
            )
            severity = "WARNING"

        category = str(data.get("category", "Custom"))
        message = str(data.get("message", rid))
        details = str(data.get("details", ""))
        recommendation = str(data.get("recommendation", ""))
        suggested_commands = data.get("suggested_commands", [])
        if isinstance(suggested_commands, str):
            suggested_commands = [suggested_commands]
        if not isinstance(suggested_commands, list):
            warnings.append(
                f"Dokument #{doc_idx} (rule {rid}): suggested_commands musi być listą. Używam pustej listy."
            )
            suggested_commands = []

        yaml_rules.append(
            YamlRule(
                id=rid,
                vendors=[str(x) for x in vendors]
                if isinstance(vendors, list)
                else None,
                severity=severity,  # type: ignore[arg-type]
                category=category,
                message=message,
                details=details,
                recommendation=recommendation,
                suggested_commands=[str(x) for x in suggested_commands],
                when=when,
            )
        )

    return overrides, yaml_rules, warnings


def _apply_builtin_overrides(
    findings: List[SecurityFinding],
    overrides: Dict[str, BuiltinOverride],
    vendor: str | None,
) -> List[SecurityFinding]:
    """Apply user overrides to findings coming from builtin rules."""

    out: List[SecurityFinding] = []
    for f in findings:
        ov = overrides.get(f.id)
        if ov is not None:
            if ov.vendors and (vendor is None or vendor not in ov.vendors):
                # override dotyczy innego vendora (lub vendor nie został wykryty)
                out.append(f)
                continue
            if ov.enabled is False:
                continue
            if isinstance(ov.severity, str) and ov.severity in (
                "INFO",
                "WARNING",
                "CRITICAL",
            ):
                f.severity = ov.severity  # type: ignore[misc]
            if isinstance(ov.category, str):
                f.category = ov.category
            if isinstance(ov.message, str):
                f.message = ov.message
            if isinstance(ov.details, str):
                f.details = ov.details
            if isinstance(ov.recommendation, str):
                f.recommendation = ov.recommendation
            if isinstance(ov.suggested_commands, list):
                f.suggested_commands = [str(x) for x in ov.suggested_commands]
        out.append(f)
    return out


def _eval_when(config_text: str, when: Dict[str, Any]) -> Tuple[bool, RulesWarnings]:
    """Evaluate a simple 'when' block against raw config text.

    Supported keys:
      - contains / not_contains: string or list[string]
      - regex: string or list[string]
      - operator: any|all (default any) – applies within each list
      - case_sensitive: bool (default false)
    """

    import re

    warnings: RulesWarnings = []

    case_sensitive = bool(when.get("case_sensitive", False))
    flags = 0 if case_sensitive else re.IGNORECASE | re.MULTILINE
    op = str(when.get("operator", "any")).strip().lower()
    op_any = op != "all"

    # normalize config for contains checks
    cfg = config_text if case_sensitive else config_text.lower()

    def _as_list(v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [
                str(x) for x in v if isinstance(x, (str, int, float)) and str(x).strip()
            ]
        return []

    contains = _as_list(when.get("contains"))
    not_contains = _as_list(when.get("not_contains"))
    regexes = _as_list(when.get("regex"))

    if contains:
        needles = contains if case_sensitive else [c.lower() for c in contains]
        results = [(n in cfg) for n in needles]
        if (any(results) if op_any else all(results)) is False:
            return False, warnings

    if not_contains:
        needles = not_contains if case_sensitive else [c.lower() for c in not_contains]
        results = [(n not in cfg) for n in needles]
        if (any(results) if op_any else all(results)) is False:
            return False, warnings

    if regexes:
        compiled: List[re.Pattern[str]] = []
        for r in regexes:
            try:
                compiled.append(re.compile(r, flags))
            except re.error as e:
                warnings.append(f"Niepoprawny regex '{r}': {e}")
                return False, warnings
        results = [bool(p.search(config_text)) for p in compiled]
        if (any(results) if op_any else all(results)) is False:
            return False, warnings

    return True, warnings


def _run_yaml_rules(
    config_text: str, rules: List[YamlRule], vendor: str | None
) -> Tuple[List[SecurityFinding], RulesWarnings]:
    findings: List[SecurityFinding] = []
    warnings: RulesWarnings = []

    for rule in rules:
        if rule.vendors and (vendor is None or vendor not in rule.vendors):
            continue
        matched, w = _eval_when(config_text, rule.when)
        if w:
            warnings.append(f"Reguła {rule.id}: " + "; ".join(w))
        if not matched:
            continue

        findings.append(
            SecurityFinding(
                id=rule.id,
                severity=rule.severity,
                category=rule.category,
                message=rule.message,
                details=rule.details or "(brak dodatkowych szczegółów)",
                recommendation=rule.recommendation or "(brak rekomendacji)",
                suggested_commands=rule.suggested_commands,
                lines=[],
            )
        )

    return findings, warnings


def _detect_vendor(config_text: str) -> str | None:
    """Heurystyczne wykrycie platformy po tekście konfiguracji."""

    import re

    txt = config_text[:20000]  # heurystyka – nie potrzebujemy całego pliku

    # Junos (set-style)
    if re.search(r"(?m)^\s*set\s+\S+", txt):
        return "junos"
    # Junos (hierarchical)
    if re.search(r"(?m)^\s*(system|interfaces|security)\s*\{", txt):
        return "junos"

    # Cisco/IOS-like
    if re.search(r"(?m)^\s*line\s+vty\b", txt) or re.search(
        r"(?m)^\s*interface\b", txt
    ):
        return "cisco_ios"

    return None


def _normalize_vendor(vendor_hint: str | None) -> str | None:
    """Normalize vendor/platform identifiers coming from GUI.

    Accepted normalized values:
      - 'cisco_ios'
      - 'junos'
    """

    if not vendor_hint:
        return None
    v = str(vendor_hint).strip().lower()
    if v in {"cisco", "ios", "iosxe", "ios-xe", "cisco_ios"}:
        return "cisco_ios"
    if v in {"juniper", "junos", "juniper_junos"}:
        return "junos"
    return None


# ==========================================================
#                         MODELE
# ==========================================================


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


def run_security_audit(
    config_text: str, vendor_hint: str | None = None
) -> List[SecurityFinding]:
    """Run security audit.

    Args:
        config_text: Raw configuration text.
        vendor_hint: Optional platform identifier (e.g. passed from GUI based on selected device).
            If not provided, we will try a best-effort heuristic detection based on config content.
    """

    vendor = _normalize_vendor(vendor_hint) or _detect_vendor(config_text)

    # 1) User rules (multi-document YAML)
    overrides, yaml_rules, rules_warnings = _load_user_rules()

    findings: List[SecurityFinding] = []

    # 2) Builtin rules
    # Obecne reguły wbudowane są IOS-centric (Cisco). Jeśli wiemy, że vendor=junos,
    # to ich nie uruchamiamy, żeby nie generować false-positive ("brak no cdp run" itd.).
    if vendor in (None, "cisco_ios"):
        pc = parse_config(config_text)

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

        # Apply overrides to builtin findings
        findings = _apply_builtin_overrides(findings, overrides, vendor)

    # 3) Custom YAML rules (raw-text matching)
    yaml_findings, yaml_warnings = _run_yaml_rules(config_text, yaml_rules, vendor)
    findings.extend(yaml_findings)

    all_warnings = [*rules_warnings, *yaml_warnings]

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

    # Report issues with YAML rules file (if any)
    if all_warnings:
        path = get_rules_file_path()
        findings.append(
            SecurityFinding(
                id="RULES_FILE_PROBLEMS",
                severity="WARNING",
                category="Rules",
                message="Wykryto problemy z plikiem reguł YAML (wczytano to, co się dało).",
                details="Plik: "
                + str(path)
                + "\n\n"
                + "\n".join(f"- {w}" for w in all_warnings),
                recommendation=(
                    "Popraw składnię/dane w pliku reguł. Jeśli plik jest nowy, zacznij od edycji domyślnego szablonu."
                ),
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
