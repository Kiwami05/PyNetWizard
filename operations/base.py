from dataclasses import dataclass, field
from typing import Any, Dict, ClassVar
import uuid


@dataclass(frozen=True, slots=True)
class Operation:
    """
    Vendor-neutral "intent" operation.
    Renderer przekształca Operation -> list[str] komend CLI dla konkretnego vendora.
    """

    # Stały identyfikator typu (używany do serializacji / debug)
    OP: ClassVar[str] = "OPERATION"

    # Unikalne ID instancji (ułatwia debug i mapowanie w GUI)
    op_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def describe(self) -> str:
        """Ludzki opis operacji (do GUI/logów)."""
        return self.OP

    def to_dict(self) -> Dict[str, Any]:
        """
        Minimalna serializacja (np. gdy kiedyś zechcesz zapisywać sesję/bufor).
        Zawsze zawiera 'type' = OP.
        """
        return {"type": self.OP, "op_id": self.op_id}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Operation":
        """
        Bazowa deserializacja nie ma sensu (bo nie wiemy, jaki to konkretny typ).
        Konkretne operacje implementują własne from_dict().
        """
        raise NotImplementedError("Use a concrete Operation.from_dict().")
