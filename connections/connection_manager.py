from netmiko import (
    ConnectHandler,
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
    NetmikoBaseException,
)
from netmiko.base_connection import BaseConnection
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from devices.device import Device
from platforms.vendor import Vendor
from platforms.device_type import DeviceType
import logging
import os
import socket
import tempfile
import threading
from pathlib import Path


class DeviceConnectionError(ConnectionError):
    """Błąd połączenia gotowy do pokazania użytkownikowi."""


class ConnectionManager:
    """
    Klasa zarządzająca połączeniami SSH/Telnet do urządzeń sieciowych.
    Obsługuje poprawnie Cisco ASA/ASAv (pager 0, odmienne prompty).
    """

    def __init__(
        self,
        connection_type="ssh",
        timeout=10,
        log_path="./logs",
        verbose=False,
        persist_cisco_config=True,
    ):
        self.sessions: dict[str, BaseConnection] = {}
        self._last_errors: dict[str, Exception] = {}
        self.connection_type = connection_type
        self.timeout = int(timeout)
        self.verbose = verbose
        self.persist_cisco_config = persist_cisco_config
        self._lock = threading.RLock()

        # Tworzenie katalogu logów
        self.log_path = Path(log_path)
        self.log_path.mkdir(parents=True, exist_ok=True)

        # Przygotowanie ścieżki głównego pliku logów
        logfile = self.log_path / "netmiko.log"

        # Sprawdzanie uprawnień
        if logfile.exists() and not os.access(logfile, os.W_OK):
            try:
                new_name = logfile.with_name(f"{logfile.name}.old")
                logfile.rename(new_name)
                print(f"[WARN] Brak uprawnień do {logfile}, przeniesiono do {new_name}")
            except OSError:
                tmp_log = Path(tempfile.gettempdir()) / f"netmiko_{os.getuid()}.log"
                print(f"[WARN] Nie można pisać do {logfile}, używam {tmp_log}")
                logfile = tmp_log

        try:
            logfile.touch(exist_ok=True)
        except OSError:
            tmp_log = Path(tempfile.gettempdir()) / f"netmiko_{os.getuid()}.log"
            print(f"[WARN] Nie udało się utworzyć {logfile}, fallback do {tmp_log}")
            logfile = tmp_log

        logging.basicConfig(
            filename=str(logfile),
            level=logging.DEBUG if verbose else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )
        logging.info("=== PyNetWizard session started ===")

    def connect(self, device: Device) -> bool:
        with self._lock:
            if device.host in self.sessions:
                return True

            try:
                params = self._device_to_netmiko(device)
                conn = ConnectHandler(**params)

                # ASA
                if (
                    device.vendor == Vendor.CISCO
                    and device.device_type == DeviceType.FIREWALL
                ):
                    if not conn.check_enable_mode():
                        conn.enable()
                    conn.send_command_timing("pager 0")

                # JUNIPER
                elif device.vendor == Vendor.JUNIPER:
                    # Junos nie ma żadnych specjalnych kroków
                    pass

                # CISCO IOS
                else:
                    if not conn.check_enable_mode():
                        conn.enable()
                    conn.send_command("terminal length 0")
                    conn.send_command("terminal width 512")

                self.sessions[device.host] = conn
                self._last_errors.pop(device.host, None)
                logging.info(f"[CONNECTED] {device.host}")
                return True

            except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
                logging.error(f"[CONNECTION ERROR] {device.host}: {e}")
                self._last_errors[device.host] = self._build_connection_error(device, e)
                return False
            except (
                NoValidConnectionsError,
                SSHException,
                socket.gaierror,
                socket.timeout,
                TimeoutError,
                ConnectionRefusedError,
                OSError,
            ) as e:
                logging.error(f"[CONNECTION ERROR] {device.host}: {e}")
                self._last_errors[device.host] = self._build_connection_error(device, e)
                return False
            except NetmikoBaseException as e:
                logging.exception(f"[UNEXPECTED ERROR] {device.host}: {e}")
                self._last_errors[device.host] = self._build_connection_error(device, e)
                return False

    def disconnect(self, device: Device):
        """Zamyka połączenie."""
        with self._lock:
            if device.host in self.sessions:
                try:
                    self.sessions[device.host].disconnect()
                except (NetmikoBaseException, OSError, EOFError):
                    pass
                del self.sessions[device.host]
                logging.info(f"[DISCONNECTED] {device.host}")

    def is_connected(self, device: Device) -> bool:
        """Sprawdza, czy połączenie istnieje i działa."""
        with self._lock:
            conn = self.sessions.get(device.host)
            if not conn:
                return False
            try:
                conn.write_channel("\n")
                return True
            except (NetmikoBaseException, OSError, EOFError):
                self.disconnect(device)
                return False

    def has_session(self, device: Device) -> bool:
        """Zwraca stan cache'owany bez odpytywania kanału SSH/Telnet."""
        with self._lock:
            return device.host in self.sessions

    def send_command(self, device: Device, command: str) -> str:
        """Wysyła pojedyncze polecenie i zwraca wynik."""
        with self._lock:
            if not self.connect(device):
                raise self._last_errors.get(
                    device.host,
                    DeviceConnectionError(
                        f"Nie udało się połączyć z urządzeniem {device.host}."
                    ),
                )

            conn = self.sessions[device.host]
            logging.info(f"[COMMAND] {device.host}: {command}")

            # specjalny tryb ASA
            if (
                device.vendor == Vendor.CISCO
                and device.device_type == DeviceType.FIREWALL
            ):
                output = conn.send_command(
                    command,
                    expect_string=r"[>#]",
                    read_timeout=25,
                    delay_factor=2,
                    strip_prompt=False,
                    strip_command=False,
                )
            elif device.vendor == Vendor.JUNIPER:
                self._ensure_juniper_operational_mode(conn)
                output = conn.send_command(
                    command,
                    read_timeout=60,
                    strip_prompt=True,
                    strip_command=True,
                    cmd_verify=False,
                )
            else:
                output = conn.send_command(command, strip_prompt=False, read_timeout=20)
            return output.strip()

    def send_config(self, device: Device, commands: list[str]) -> str:
        """Wysyła listę komend konfiguracyjnych."""
        with self._lock:
            if not self.connect(device):
                raise self._last_errors.get(
                    device.host,
                    DeviceConnectionError(
                        f"Nie udało się połączyć z urządzeniem {device.host}."
                    ),
                )

            conn = self.sessions[device.host]
            logging.info(f"[CONFIG] {device.host}: {commands}")

            if device.vendor == Vendor.JUNIPER:
                output = conn.send_config_set(commands)
                try:
                    commit_output = conn.commit()
                    if commit_output:
                        output = f"{output}\n{commit_output}"
                except AttributeError:
                    save_output = conn.save_config()
                    if save_output:
                        output = f"{output}\n{save_output}"
                self._ensure_juniper_operational_mode(conn)
            elif self._has_hostname_change(commands):
                output = self._send_config_with_hostname_change(device, conn, commands)
            elif device.device_type == DeviceType.FIREWALL:
                output = conn.send_config_set(
                    commands,
                    read_timeout=30,
                    delay_factor=2,
                    exit_config_mode=False,  # ASA nie zawsze ma "end"
                )
                if self.persist_cisco_config:
                    try:
                        conn.save_config()
                    except NetmikoBaseException:
                        pass
            else:
                try:
                    output = conn.send_config_set(
                        commands,
                        read_timeout=60,
                        cmd_verify=False,
                    )
                    if self.persist_cisco_config:
                        conn.save_config()
                except NetmikoBaseException:
                    self.disconnect(device)
                    raise

            return output.strip()

    def _ensure_juniper_operational_mode(self, conn):
        """Polecenie `junos commit` może zakończyć sesję w trybie konfiguracyjnym; polecenia `show` muszą być wykonywane w trybie operacyjnym"""
        try:
            if conn.check_config_mode():
                conn.exit_config_mode()
        except NetmikoBaseException:
            try:
                conn.write_channel("\n")
                conn.exit_config_mode()
            except NetmikoBaseException:
                pass

    def _device_to_netmiko(self, device: Device) -> dict:
        """Mapuje obiekt Device na parametry Netmiko ConnectHandler."""
        if device.vendor == Vendor.CISCO:
            if device.device_type == DeviceType.FIREWALL:
                platform = "cisco_asa"
            else:
                platform = "cisco_ios"
        elif device.vendor == Vendor.JUNIPER:
            platform = "juniper_junos"
        else:
            platform = "generic_termserver"

        if self.connection_type == "telnet":
            platform = f"{platform}_telnet"

        params = {
            "device_type": platform,
            "host": device.host,
            "username": device.username,
            "password": device.password,
            "timeout": self.timeout,
            "secret": device.password,  # enable password
            "global_delay_factor": 2
            if device.device_type == DeviceType.FIREWALL
            else 1,
        }

        # Log sesji
        session_log = self.log_path / f"{device.host}_session.txt"
        try:
            session_log.touch(exist_ok=True)
        except OSError:
            tmp_log = Path(tempfile.gettempdir()) / f"{device.host}_session.txt"
            print(f"[WARN] Nie można pisać do {session_log}, używam {tmp_log}")
            session_log = tmp_log

        params["session_log"] = str(session_log)

        return params

    @staticmethod
    def _has_hostname_change(commands: list[str]) -> bool:
        return any(cmd.strip().startswith("hostname ") for cmd in commands)

    def _send_config_with_hostname_change(
        self, device: Device, conn: BaseConnection, commands: list[str]
    ) -> str:
        """
        Zmiana hostname zmienia prompt w trakcie sesji, więc dla Cisco
        używamy ścieżki timingowej bez oczekiwania na stary prompt.
        """
        output_parts: list[str] = []
        new_hostname = None

        conn.config_mode()
        for raw_cmd in commands:
            cmd = raw_cmd.strip()
            if not cmd:
                continue
            result = conn.send_command_timing(
                cmd,
                strip_prompt=False,
                strip_command=False,
            )
            if result:
                output_parts.append(result.strip())

            if cmd.startswith("hostname "):
                new_hostname = cmd.split(None, 1)[1].strip()
                if new_hostname:
                    conn.base_prompt = new_hostname

        if conn.check_config_mode():
            result = conn.send_command_timing(
                "end",
                strip_prompt=False,
                strip_command=False,
            )
            if result:
                output_parts.append(result.strip())

        if device.vendor == Vendor.CISCO:
            result = conn.send_command_timing(
                "write memory",
                strip_prompt=False,
                strip_command=False,
            )
            if result:
                output_parts.append(result.strip())

        # Po zmianie promptu najbezpieczniej odświeżyć sesję przed kolejnym odczytem.
        self.disconnect(device)

        return "\n".join(part for part in output_parts if part).strip()

    def _build_connection_error(
        self, device: Device, exc: Exception
    ) -> DeviceConnectionError:
        detail = self._root_exception(exc)
        detail_text = str(detail).strip() or type(detail).__name__
        lower_detail = detail_text.lower()
        protocol = "SSH" if self.connection_type == "ssh" else "Telnet"

        if isinstance(exc, NetmikoAuthenticationException):
            message = (
                f"Nie udało się zalogować do {device.host}. "
                "Sprawdź nazwę użytkownika, hasło i hasło enable."
            )
        elif self._is_name_resolution_error(
            detail, lower_detail
        ) or self._is_connection_refused_error(detail, lower_detail):
            message = (
                f"Nie udało się nawiązać połączenia z hostem {device.host}. "
                "Sprawdź nazwę hosta lub adres IP."
            )
        elif self._is_timeout_error(exc, detail, lower_detail):
            message = (
                f"Upłynął czas oczekiwania na połączenie z {device.host}. "
                "Urządzenie nie odpowiada albo jest nieosiągalne z tej sieci."
            )
        elif self._is_ssh_negotiation_error(detail, lower_detail):
            message = (
                f"Nie udało się zestawić sesji {protocol} z {device.host}. "
                "Urządzenie może używać innego protokołu, portu albo nieobsługiwanych parametrów połączenia."
            )
        else:
            message = f"Nie udało się połączyć z urządzeniem {device.host}."

        if detail_text and detail_text != message:
            message += f"\nSzczegóły techniczne: {detail_text}"
        return DeviceConnectionError(message)

    @staticmethod
    def _root_exception(exc: Exception) -> Exception:
        current = exc
        visited = set()
        while id(current) not in visited:
            visited.add(id(current))
            next_exc = getattr(current, "__cause__", None) or getattr(
                current, "__context__", None
            )
            if not next_exc:
                return current
            current = next_exc
        return current

    @staticmethod
    def _is_name_resolution_error(detail: Exception, lower_detail: str) -> bool:
        return isinstance(detail, socket.gaierror) or any(
            token in lower_detail
            for token in (
                "name or service not known",
                "temporary failure in name resolution",
                "nodename nor servname provided",
                "getaddrinfo failed",
                "could not resolve hostname",
            )
        )

    @staticmethod
    def _is_connection_refused_error(detail: Exception, lower_detail: str) -> bool:
        return isinstance(detail, ConnectionRefusedError) or any(
            token in lower_detail
            for token in (
                "connection refused",
                "actively refused",
                "unable to connect to port",
            )
        )

    @staticmethod
    def _is_timeout_error(exc: Exception, detail: Exception, lower_detail: str) -> bool:
        return (
            isinstance(exc, (NetmikoTimeoutException, socket.timeout, TimeoutError))
            or isinstance(detail, (socket.timeout, TimeoutError))
            or any(
                token in lower_detail
                for token in (
                    "timed out",
                    "timeout",
                    "operation timed out",
                    "no existing session",
                )
            )
        )

    @staticmethod
    def _is_ssh_negotiation_error(detail: Exception, lower_detail: str) -> bool:
        return isinstance(detail, (NoValidConnectionsError, SSHException)) or any(
            token in lower_detail
            for token in (
                "error reading ssh protocol banner",
                "incompatible ssh server",
                "kex",
                "cipher",
                "banner",
                "channel exception",
                "administratively prohibited",
            )
        )
