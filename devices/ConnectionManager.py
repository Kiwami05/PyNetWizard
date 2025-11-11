from netmiko import (
    ConnectHandler,
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
)
from devices.Device import Device
from devices.Vendor import Vendor
import logging
import os
import tempfile


class ConnectionManager:
    """
    Klasa zarządzająca połączeniami SSH/Telnet do urządzeń sieciowych.
    Automatycznie obsługuje problemy z dostępem do plików logów (np. po wcześniejszym
    uruchomieniu jako root).
    """

    def __init__(
        self, connection_type="ssh", timeout=10, log_path="./logs", verbose=False
    ):
        self.sessions: dict[str, ConnectHandler] = {}
        self.connection_type = connection_type
        self.timeout = int(timeout)
        self.verbose = verbose

        # --- Tworzenie katalogu logów ---
        os.makedirs(log_path, exist_ok=True)
        self.log_path = log_path

        # --- Przygotowanie ścieżki głównego pliku logów ---
        logfile = os.path.join(log_path, "netmiko.log")

        # 🧩 Sprawdź, czy plik logu istnieje i czy jest zapisywalny
        if os.path.exists(logfile) and not os.access(logfile, os.W_OK):
            try:
                # Jeśli nie możemy pisać — zmień nazwę (zachowaj oryginał)
                new_name = logfile + ".old"
                os.rename(logfile, new_name)
                print(f"[WARN] Brak uprawnień do {logfile}, przeniesiono do {new_name}")
            except Exception:
                # Jeśli rename się nie uda — utwórz nowy log w katalogu tymczasowym
                tmp_log = os.path.join(
                    tempfile.gettempdir(), f"netmiko_{os.getuid()}.log"
                )
                print(f"[WARN] Nie można pisać do {logfile}, używam {tmp_log}")
                logfile = tmp_log

        # 🧩 Jeśli pliku nie ma, spróbuj utworzyć nowy (w razie błędu fallback do /tmp)
        try:
            open(logfile, "a").close()
        except Exception:
            tmp_log = os.path.join(tempfile.gettempdir(), f"netmiko_{os.getuid()}.log")
            print(f"[WARN] Nie udało się utworzyć {logfile}, fallback do {tmp_log}")
            logfile = tmp_log

        # --- Konfiguracja loggera ---
        logging.basicConfig(
            filename=logfile,
            level=logging.DEBUG if verbose else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )
        logging.info("=== PyNetWizard session started ===")

    # ==============================================================
    #                        GŁÓWNE API
    # ==============================================================

    def connect(self, device: Device) -> bool:
        """Nawiązuje połączenie i zapisuje sesję."""
        if device.host in self.sessions:
            return True  # już połączony

        try:
            params = self._device_to_netmiko(device)
            conn = ConnectHandler(**params)
            if not conn.check_enable_mode():
                conn.enable()
            self.sessions[device.host] = conn
            logging.info(f"[CONNECTED] {device.host}")
            return True
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
            logging.error(f"[CONNECTION ERROR] {device.host}: {e}")
            return False
        except Exception as e:
            logging.exception(f"[UNEXPECTED ERROR] {device.host}: {e}")
            return False

    def disconnect(self, device: Device):
        """Zamyka połączenie."""
        if device.host in self.sessions:
            try:
                self.sessions[device.host].disconnect()
            except Exception:
                pass
            del self.sessions[device.host]
            logging.info(f"[DISCONNECTED] {device.host}")

    def is_connected(self, device: Device) -> bool:
        """Sprawdza, czy połączenie istnieje i działa."""
        conn = self.sessions.get(device.host)
        if not conn:
            return False
        try:
            conn.write_channel("\n")
            return True
        except Exception:
            self.disconnect(device)
            return False

    def send_command(self, device: Device, command: str) -> str:
        """Wysyła pojedyncze polecenie i zwraca wynik."""
        if not self.connect(device):
            raise ConnectionError(f"Nie udało się połączyć z {device.host}")
        conn = self.sessions[device.host]
        logging.info(f"[COMMAND] {device.host}: {command}")
        output = conn.send_command(command, strip_prompt=False, read_timeout=20)
        return output.strip()

    def send_config(self, device: Device, commands: list[str]) -> str:
        """Wysyła listę komend konfiguracyjnych."""
        if not self.connect(device):
            raise ConnectionError(f"Nie udało się połączyć z {device.host}")
        conn = self.sessions[device.host]
        logging.info(f"[CONFIG] {device.host}: {commands}")
        output = conn.send_config_set(commands)
        conn.save_config()
        return output.strip()

    # ==============================================================
    #                        POMOCNICZE
    # ==============================================================

    def _device_to_netmiko(self, device: Device) -> dict:
        """Mapuje obiekt Device na parametry Netmiko ConnectHandler."""
        if device.vendor == Vendor.CISCO:
            platform = "cisco_ios"
        elif device.vendor == Vendor.JUNIPER:
            platform = "juniper"
        else:
            platform = "generic_termserver"

        params = {
            "device_type": f"{platform}_{self.connection_type}"
            if self.connection_type == "telnet"
            else platform,
            "host": device.host,
            "username": device.username,
            "password": device.password,
            "timeout": self.timeout,
            "secret": device.password,  # enable
        }

        # --- Bezpieczne tworzenie logu sesji (może być w /tmp jeśli katalog logów niedostępny)
        session_log = os.path.join(self.log_path, f"{device.host}_session.txt")
        try:
            open(session_log, "a").close()
        except Exception:
            tmp_log = os.path.join(tempfile.gettempdir(), f"{device.host}_session.txt")
            print(f"[WARN] Nie można pisać do {session_log}, używam {tmp_log}")
            session_log = tmp_log

        params["session_log"] = session_log

        return params
