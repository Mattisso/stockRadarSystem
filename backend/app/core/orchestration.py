"""Runtime orchestration state for startup order, health, and background tasks."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ServiceState:
    name: str
    healthy: bool = False
    detail: str | None = None
    updated_at: datetime | None = None

    def mark(self, healthy: bool, detail: str | None = None) -> None:
        self.healthy = healthy
        self.detail = detail
        self.updated_at = datetime.now(UTC)


@dataclass
class RuntimeOrchestrator:
    """Tracks service lifecycle state and background tasks for the app."""

    services: dict[str, ServiceState] = field(default_factory=dict)
    tasks: dict[str, asyncio.Task] = field(default_factory=dict)

    def ensure_service(self, name: str) -> ServiceState:
        if name not in self.services:
            self.services[name] = ServiceState(name=name)
        return self.services[name]

    def mark_service(self, name: str, healthy: bool, detail: str | None = None) -> None:
        self.ensure_service(name).mark(healthy=healthy, detail=detail)

    def register_task(self, name: str, task: asyncio.Task) -> None:
        self.tasks[name] = task

    async def shutdown_tasks(self) -> None:
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        for task in self.tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass

    def snapshot(self) -> dict:
        return {
            "services": {
                name: {
                    "healthy": state.healthy,
                    "detail": state.detail,
                    "updated_at": state.updated_at.isoformat() if state.updated_at else None,
                }
                for name, state in self.services.items()
            },
            "background_tasks": {
                name: {
                    "done": task.done(),
                    "cancelled": task.cancelled(),
                }
                for name, task in self.tasks.items()
            },
        }
