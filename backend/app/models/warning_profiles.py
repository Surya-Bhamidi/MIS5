"""Explicit operational tradeoffs; responsiveness is the conservative default."""
from app.models.warning_policy import WarningConfig

PROFILES={
    'responsive':WarningConfig(confirmations=1,clear_confirmations=1,clear_ratio=1.,
                               cooldown_seconds=0.,max_hold_below_seconds=0.),
    'confirmed':WarningConfig(),
}


def profile_config(name):
    if name not in PROFILES:raise ValueError('Unknown warning profile')
    return PROFILES[name]
