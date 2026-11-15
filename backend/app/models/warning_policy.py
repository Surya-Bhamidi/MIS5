"""Causal episode notifications, independent of forecast fitting and labels."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class WarningConfig:
    confirmations: int = 2
    clear_confirmations: int = 2
    clear_ratio: float = .8
    cooldown_seconds: float = 300
    max_gap_seconds: float = 90
    max_hold_below_seconds: float = 120
    fast_ratio: float | None = None

    def __post_init__(self):
        if any(not isinstance(value,int) or isinstance(value,bool) or value<1 for value in (self.confirmations,self.clear_confirmations)):
            raise ValueError("Confirmation counts must be positive")
        if not 0 < self.clear_ratio <= 1 or self.cooldown_seconds < 0 or self.max_gap_seconds <= 0 or self.max_hold_below_seconds < 0:
            raise ValueError("Invalid warning timing or hysteresis")
        if not all(math.isfinite(v) for v in (self.clear_ratio,self.cooldown_seconds,self.max_gap_seconds,self.max_hold_below_seconds)):
            raise ValueError("Warning configuration must be finite")
        if self.fast_ratio is not None and (not math.isfinite(self.fast_ratio) or self.fast_ratio<1):
            raise ValueError("Fast-path ratio must be finite and at least one")


class WarningPolicy:
    def __init__(self, config=None):
        self.config = config or WarningConfig()
        self.last_time = None
        self.last_notification = -math.inf
        self.active = False
        self.above = self.below = 0
        self.context = None
        self.below_since = None
        self.episode_notified = False

    def update(self, timestamp, risk, threshold, context="default"):
        if not math.isfinite(timestamp) or (self.last_time is not None and timestamp <= self.last_time):
            raise ValueError("Warning timestamps must be finite and strictly increasing")
        if not math.isfinite(threshold) or threshold < 0:
            raise ValueError("Threshold must be finite and nonnegative")
        if risk is not None and (not math.isfinite(risk) or not 0 <= risk <= 1):
            raise ValueError("Risk must be a finite probability")
        if (self.last_time is not None and timestamp-self.last_time > self.config.max_gap_seconds) or context != self.context:
            self.active = False
            self.above = self.below = 0
            self.below_since = None
            self.episode_notified = False
        self.last_time, self.context = timestamp, context
        if risk is None:
            self.active = False
            self.above = self.below = 0
            self.below_since = None
            self.episode_notified = False
            return dict(warning=False, episode_start=False, notify=False, reason="insufficient_sensors")
        self.above = self.above+1 if risk >= threshold else 0
        self.below = self.below+1 if risk < threshold*self.config.clear_ratio else 0
        self.below_since = (timestamp if self.below_since is None else self.below_since) if risk < threshold else None
        notify = episode_start = False
        expired = self.below_since is not None and timestamp-self.below_since >= self.config.max_hold_below_seconds
        if self.active and (self.below >= self.config.clear_confirmations or expired):
            self.active = False
        fast = self.config.fast_ratio is not None and risk>=threshold and risk>=threshold*self.config.fast_ratio
        if not self.active and (self.above >= self.config.confirmations or fast):
            self.active = episode_start = True
            self.episode_notified = False
        # Cooldown limits outbound notifications, never the displayed risk state.
        # A pending episode may notify when cooldown expires if risk stays high.
        if self.active and not self.episode_notified and risk >= threshold and timestamp-self.last_notification >= self.config.cooldown_seconds:
            notify = self.episode_notified = True
            self.last_notification = timestamp
        reason = "notification_sent" if notify else "notification_cooldown" if self.active and not self.episode_notified else "episode_active" if self.active else "confirming_or_below_threshold"
        return dict(warning=self.active, episode_start=episode_start, notify=notify, reason=reason)
