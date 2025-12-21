from abc import ABC, abstractmethod
from typing import Iterable, List

from operations.base import Operation


class OperationRenderer(ABC):
    """
    Renderer przekształca vendor-neutral Operation -> listę komend CLI
    dla konkretnego systemu operacyjnego urządzenia.
    """

    @abstractmethod
    def render(self, operations: Iterable[Operation]) -> List[str]:
        """
        Renderuje listę operacji, do listy komend CLI.
        """
        raise NotImplementedError

    def render_one(self, op: Operation) -> List[str]:
        """
        Pomocnicza metoda do renderowania pojedynczej operacji.
        Domyślnie woła render([op]).
        """
        return self.render([op])
