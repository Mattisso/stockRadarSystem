"""Deterministic subscription-source registry for Polygon market data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubscriptionSourceState:
    source: str
    symbols: tuple[str, ...]
    sticky: bool


class SubscriptionRegistry:
    """Track desired subscriptions across multiple sources.

    The registry preserves source insertion order, deduplicates symbols within
    and across sources, and increments a generation counter only when the
    effective subscription set changes.
    """

    def __init__(
        self,
        *,
        initial_sources: dict[str, list[str]] | None = None,
        sticky_sources: set[str] | None = None,
    ) -> None:
        self._sources: dict[str, tuple[str, ...]] = {}
        self._sticky_sources: set[str] = set(sticky_sources or set())
        self._generation_id = 0
        if initial_sources:
            for source, symbols in initial_sources.items():
                self._sources[source] = self._normalize_symbols(symbols)

    @property
    def generation_id(self) -> int:
        return self._generation_id

    def update_source(self, source: str, symbols: list[str], *, sticky: bool | None = None) -> bool:
        previous_effective = self.current_symbols()
        normalized = self._normalize_symbols(symbols)
        self._sources[source] = normalized
        if sticky is True:
            self._sticky_sources.add(source)
        elif sticky is False:
            self._sticky_sources.discard(source)
        changed = self.current_symbols() != previous_effective
        if changed:
            self._generation_id += 1
        return changed

    def clear_source(self, source: str) -> bool:
        if source not in self._sources:
            return False
        return self.update_source(source, [], sticky=source in self._sticky_sources)

    def current_symbols(self) -> list[str]:
        seen: set[str] = set()
        symbols: list[str] = []
        for source_symbols in self._sources.values():
            for symbol in source_symbols:
                if symbol in seen:
                    continue
                seen.add(symbol)
                symbols.append(symbol)
        return symbols

    def sticky_symbols(self) -> list[str]:
        seen: set[str] = set()
        symbols: list[str] = []
        for source, source_symbols in self._sources.items():
            if source not in self._sticky_sources:
                continue
            for symbol in source_symbols:
                if symbol in seen:
                    continue
                seen.add(symbol)
                symbols.append(symbol)
        return symbols

    def source_symbols(self, source: str) -> list[str]:
        return list(self._sources.get(source, ()))

    def source_states(self) -> list[SubscriptionSourceState]:
        return [
            SubscriptionSourceState(
                source=source,
                symbols=symbols,
                sticky=source in self._sticky_sources,
            )
            for source, symbols in self._sources.items()
        ]

    @staticmethod
    def _normalize_symbols(symbols: list[str]) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for raw_symbol in symbols:
            symbol = raw_symbol.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            ordered.append(symbol)
        return tuple(ordered)
