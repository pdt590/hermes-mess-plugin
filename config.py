"""Validated settings; profile-aware resolution is supplied by the adapter."""
from dataclasses import dataclass, field
from pathlib import Path
import math


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    database: Path = Path("messenger.sqlite")
    capacity: int = 1000
    retention_seconds: int = 604800
    timeout: float = 20.0
    processing_timeout: float = 600.0

    def __post_init__(self):
        if not isinstance(self.token, str) or not self.token.strip():
            raise ValueError("MANYCHAT_API_TOKEN is required")
        if any(char in self.token for char in "\r\n"):
            raise ValueError("MANYCHAT_API_TOKEN must be a single line")
        for name in ("capacity", "retention_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"Invalid {name}")
        for name in ("timeout", "processing_timeout"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"Invalid {name}")
        object.__setattr__(self, "database", Path(self.database).expanduser())

    @classmethod
    def from_platform(cls, config):
        from gateway.platforms._shared import extra_or_secret
        from hermes_constants import get_hermes_home
        extra = config.extra or {}
        def read(key, env, default):
            return extra_or_secret(extra, key, env, default)
        def integer(key, env, default):
            value = read(key, env, default)
            if isinstance(value, bool) or isinstance(value, float):
                raise ValueError(f"Invalid {key}")
            return int(value)
        def number(key, env, default):
            value = read(key, env, default)
            if isinstance(value, bool):
                raise ValueError(f"Invalid {key}")
            return float(value)
        return cls(
            token=read("token", "MANYCHAT_API_TOKEN", ""),
            database=read("database", "MESSENGER_DATABASE", Path(get_hermes_home()) / "plugin-data" / "messenger" / "inbox.sqlite"),
            capacity=integer("capacity", "MESSENGER_CAPACITY", 1000),
            retention_seconds=integer("retention_seconds", "MESSENGER_RETENTION_SECONDS", 604800),
            timeout=number("timeout", "MESSENGER_API_TIMEOUT", 20),
            processing_timeout=number("processing_timeout", "MESSENGER_PROCESSING_TIMEOUT", 600),
        )
