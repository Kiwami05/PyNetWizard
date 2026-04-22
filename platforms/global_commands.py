from dataclasses import dataclass

from platforms.vendor import Vendor


@dataclass(frozen=True)
class GlobalCommandProfile:
    running_config_command: str
    startup_config_command: str | None
    save_command: str | None
    erase_command: str | None
    load_startup_command: str | None
    running_label: str
    startup_label: str | None
    memory_label: str | None


CISCO_GLOBAL_COMMANDS = GlobalCommandProfile(
    running_config_command="show running-config",
    startup_config_command="show startup-config",
    save_command="write memory",
    erase_command="write erase",
    load_startup_command="copy startup-config running-config",
    running_label="Running-config",
    startup_label="Startup-config",
    memory_label="Pamięć NVRAM",
)


JUNIPER_GLOBAL_COMMANDS = GlobalCommandProfile(
    running_config_command="show configuration | display set",
    startup_config_command=None,
    save_command=None,
    erase_command=None,
    load_startup_command=None,
    running_label="Konfiguracja Junos",
    startup_label=None,
    memory_label=None,
)


def global_commands_for_device(device) -> GlobalCommandProfile:
    if device and device.vendor == Vendor.JUNIPER:
        return JUNIPER_GLOBAL_COMMANDS
    return CISCO_GLOBAL_COMMANDS
