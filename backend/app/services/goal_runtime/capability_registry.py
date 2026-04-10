from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegisteredCapability:
    definition: object
    handler: object


class CapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, RegisteredCapability] = {}

    def register(self, definition, handler) -> None:
        self._items[definition.name] = RegisteredCapability(
            definition=definition,
            handler=handler,
        )

    def get(self, name: str) -> RegisteredCapability:
        return self._items[name]

    def items(self) -> tuple[tuple[str, RegisteredCapability], ...]:
        return tuple(self._items.items())
