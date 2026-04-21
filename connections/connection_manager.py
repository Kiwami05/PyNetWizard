from netmiko import (
    ConnectHandler,
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
    NetmikoBaseException,
)
from netmiko.base_connection import BaseConnection
from devices.device import Device
from platforms.vendor import Vendor
from platforms.device_type import DeviceType
import logging
import os
import tempfile
import threading
from pathlib import Path


class ConnectionManager:
    """
    Klasa zarządzająca połączeniami SSH/Telnet do urządzeń sieciowych.
    Obsługuje poprawnie Cisco ASA/ASAv (pager 0, odmienne prompty).
    """

    def __init__(
        self, connection_type="ssh", timeout=10, log_path="./logs", verbose=False
    ):
        self.sessions: dict[str, BaseConnection] = {}
        self.connection_type = connection_type
        self.timeout = int(timeout)
        self.verbose = verbose
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
                logging.info(f"[CONNECTED] {device.host}")
                return True

            except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
                logging.error(f"[CONNECTION ERROR] {device.host}: {e}")
                return False
            except NetmikoBaseException as e:
                logging.exception(f"[UNEXPECTED ERROR] {device.host}: {e}")
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
                raise ConnectionError(f"Nie udało się połączyć z {device.host}")

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
                raise ConnectionError(f"Nie udało się połączyć z {device.host}")

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
            elif device.device_type == DeviceType.FIREWALL:
                output = conn.send_config_set(
                    commands,
                    read_timeout=30,
                    delay_factor=2,
                    exit_config_mode=False,  # ASA nie zawsze ma "end"
                )
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
