from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DbConnectionState(str, Enum):
    CONNECTING = "connecting"
    ONLINE = "online"
    OFFLINE = "offline"
    RECONNECTING = "reconnecting"
    DEMO = "demo"


@dataclass(frozen=True)
class DbConnectionSnapshot:
    state: DbConnectionState
    last_error: str | None = None
    last_success_at: datetime | None = None
    retry_attempt: int = 0

    @property
    def is_live_allowed(self) -> bool:
        return self.state in {DbConnectionState.ONLINE, DbConnectionState.DEMO}

    @property
    def is_database_online(self) -> bool:
        return self.state == DbConnectionState.ONLINE
