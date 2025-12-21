from dataclasses import dataclass
from typing import Any, Dict

from operations.base import Operation


@dataclass(frozen=True, slots=True)
class SetHostname(Operation):
    OP = "SET_HOSTNAME"

    hostname: str = ""

    def __post_init__(self):
        # walidacja minimalna; renderer i tak może rzucić błąd,
        # ale lepiej trzymać domenę w ryzach już tutaj
        h = (self.hostname or "").strip()
        if not h:
            raise ValueError("hostname cannot be empty")
        object.__setattr__(self, "hostname", h)

    def describe(self) -> str:
        return f"Set hostname to '{self.hostname}'"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({"hostname": self.hostname})
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetHostname":
        return cls(
            op_id=str(data.get("op_id") or ""),
            hostname=str(data.get("hostname") or ""),
        )
