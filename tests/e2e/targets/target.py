from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar, TypeVar, cast

import pytest

T = TypeVar("T")


class Target(ABC):
    name: ClassVar[str]

    def __init__(self) -> None:
        self.features: dict[object, object] = {}

    def feature(self, kind: Callable[..., T]) -> T:
        if kind not in self.features:
            pytest.skip(f"{self.name} does not implement {kind}")
        return cast(T, self.features[kind])

    @property
    @abstractmethod
    def base_url(self) -> str:
        ...

    @abstractmethod
    def up(self) -> None:
        ...

    @abstractmethod
    def down(self) -> None:
        ...

    @abstractmethod
    def shell(self, command: str) -> str:
        ...
