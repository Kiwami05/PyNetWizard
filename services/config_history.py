import os
import datetime
from dataclasses import dataclass
from pathlib import Path
from devices.Device import Device


BASE_DIR_NAME = "config_history"


@dataclass
class ConfigSnapshot:
    path: str
    timestamp: datetime.datetime
    kind: str  # np. "running", "startup", "manual"
    size: int


def _base_dir() -> str:
    return os.path.join(os.getcwd(), BASE_DIR_NAME)


def _safe_host(host: str) -> str:
    # uproszczone sanity - bez /, \, :
    return (
        host.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace("|", "_")
        .replace("<", "_")
        .replace(">", "_")
        .strip()
    )


def device_dir(device: Device) -> str:
    return os.path.join(_base_dir(), _safe_host(device.host))


def ensure_device_dir(device: Device) -> str:
    d = device_dir(device)
    os.makedirs(d, exist_ok=True)
    return d


def save_snapshot(device: Device, raw_config: str, kind: str = "running") -> str:
    """
    Zapisuje snapshot konfiguracji do pliku.
    Zwraca pełną ścieżkę lub pusty string, jeśli brak danych.
    """
    if not raw_config:
        return ""

    d = ensure_device_dir(device)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{kind}.txt"
    path = os.path.join(d, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw_config)
    except OSError:
        return ""
    return path


def list_snapshots(device: Device) -> list[ConfigSnapshot]:
    d = device_dir(device)
    p = Path(d)
    if not p.is_dir():
        return []

    snaps = []
    for file in p.glob("*.txt"):
        # Najpierw oddzielamy rozszerzenie
        stem = file.stem  # np. '20250211_203322_running'
        parts = stem.split("_")

        if len(parts) < 3:
            # pliki niezgodne z formatem
            kind = "unknown"
            ts = datetime.datetime.fromtimestamp(file.stat().st_mtime)
        else:
            # Pierwsze dwa segmenty to timestamp
            ts_str = "_".join(parts[:2])  # '20250211_203322'
            kind = "_".join(parts[2:])  # 'running'

            try:
                ts = datetime.datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            except ValueError:
                ts = datetime.datetime.fromtimestamp(file.stat().st_mtime)

        snaps.append(
            ConfigSnapshot(
                path=str(file),
                timestamp=ts,
                kind=kind,
                size=file.stat().st_size,
            )
        )

    snaps.sort(key=lambda s: s.timestamp, reverse=True)
    return snaps
