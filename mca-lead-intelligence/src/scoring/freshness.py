"""Lead Freshness System for MCA Lead Intelligence.

Version 4.0 introduces a freshness multiplier system:
- Every lead receives a Freshness Flag based on signal age
- A global multiplier (0.1x to 1.3x) is applied to the final composite score
- This creates significant separation between fresh and aged leads
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from src.utils.config import config


class FreshnessFlag(Enum):
    """Lead freshness classification flags."""

    HOT = "hot"  # 0-48 hours, 1.30x
    WARM = "warm"  # 2-7 days, 1.15x
    STANDARD = "standard"  # 7-14 days, 1.00x
    COOLING = "cooling"  # 14-30 days, 0.85x
    COLD = "cold"  # 30-60 days, 0.65x
    STALE = "stale"  # 60-90 days, 0.45x
    DEAD = "dead"  # 90-180 days, 0.25x
    EXPIRED = "expired"  # 180+ days, 0.10x


@dataclass
class FreshnessResult:
    """Result of freshness calculation."""

    flag: FreshnessFlag
    multiplier: float
    label: str
    action: str
    signal_age_days: float
    signal_age_hours: float

    @property
    def display_label(self) -> str:
        """Get the display label with emoji."""
        return self.label


# Default freshness configuration (fallback)
DEFAULT_FRESHNESS_CONFIG = {
    FreshnessFlag.HOT: {
        "max_hours": 48,
        "multiplier": 1.30,
        "label": "🔥 HOT",
        "action": "DROP EVERYTHING. Contact immediately.",
    },
    FreshnessFlag.WARM: {
        "max_days": 7,
        "multiplier": 1.15,
        "label": "⚡ WARM",
        "action": "High priority. Contact within 24 hours.",
    },
    FreshnessFlag.STANDARD: {
        "max_days": 14,
        "multiplier": 1.00,
        "label": "● STANDARD",
        "action": "Normal priority. Work through queue.",
    },
    FreshnessFlag.COOLING: {
        "max_days": 30,
        "multiplier": 0.85,
        "label": "❄ COOLING",
        "action": "Lower priority. May need re-engagement strategy.",
    },
    FreshnessFlag.COLD: {
        "max_days": 60,
        "multiplier": 0.65,
        "label": "◌ COLD",
        "action": "Low priority. Situation may have changed.",
    },
    FreshnessFlag.STALE: {
        "max_days": 90,
        "multiplier": 0.45,
        "label": "○ STALE",
        "action": "Nurture only. Signal likely resolved.",
    },
    FreshnessFlag.DEAD: {
        "max_days": 180,
        "multiplier": 0.25,
        "label": "✕ DEAD",
        "action": "Archive. Opportunity window closed.",
    },
    FreshnessFlag.EXPIRED: {
        "max_days": 999999,
        "multiplier": 0.10,
        "label": "∅ EXPIRED",
        "action": "Remove from active pipeline.",
    },
}


class FreshnessCalculator:
    """Calculate lead freshness flags and multipliers."""

    def __init__(self) -> None:
        """Initialize the freshness calculator with configuration."""
        self._freshness_config = config.scoring.get("freshness", {}).get("flags", {})
        self._config = self._load_config()

    def _load_config(self) -> dict[FreshnessFlag, dict]:
        """Load freshness configuration from config or use defaults."""
        loaded_config = {}

        for flag in FreshnessFlag:
            config_entry = self._freshness_config.get(flag.value, {})
            default_entry = DEFAULT_FRESHNESS_CONFIG.get(flag, {})

            loaded_config[flag] = {
                "max_hours": config_entry.get("max_hours", default_entry.get("max_hours")),
                "max_days": config_entry.get("max_days", default_entry.get("max_days")),
                "multiplier": config_entry.get("multiplier", default_entry.get("multiplier", 1.0)),
                "label": config_entry.get("label", default_entry.get("label", flag.value)),
                "action": config_entry.get("action", default_entry.get("action", "")),
            }

        return loaded_config

    def calculate_freshness(
        self,
        signal_date: datetime,
        reference_date: datetime | None = None,
    ) -> FreshnessResult:
        """Calculate freshness flag and multiplier for a signal.

        Args:
            signal_date: When the signal was detected
            reference_date: Reference date (defaults to now)

        Returns:
            FreshnessResult with flag, multiplier, and metadata
        """
        if reference_date is None:
            reference_date = datetime.now()

        # Calculate age
        delta = reference_date - signal_date
        age_hours = max(0.0, delta.total_seconds() / 3600)
        age_days = age_hours / 24

        # Find matching flag
        flag = self._determine_flag(age_hours, age_days)
        flag_config = self._config.get(flag, DEFAULT_FRESHNESS_CONFIG[FreshnessFlag.STANDARD])

        return FreshnessResult(
            flag=flag,
            multiplier=flag_config.get("multiplier", 1.0),
            label=flag_config.get("label", flag.value),
            action=flag_config.get("action", ""),
            signal_age_days=age_days,
            signal_age_hours=age_hours,
        )

    def _determine_flag(self, age_hours: float, age_days: float) -> FreshnessFlag:
        """Determine the freshness flag based on signal age.

        Args:
            age_hours: Signal age in hours
            age_days: Signal age in days

        Returns:
            The appropriate FreshnessFlag
        """
        # Check in order from freshest to oldest

        # HOT: Check hours (0-48 hours)
        hot_config = self._config.get(FreshnessFlag.HOT, {})
        if hot_config.get("max_hours") and age_hours <= hot_config["max_hours"]:
            return FreshnessFlag.HOT

        # For the rest, check days
        for flag in [
            FreshnessFlag.WARM,
            FreshnessFlag.STANDARD,
            FreshnessFlag.COOLING,
            FreshnessFlag.COLD,
            FreshnessFlag.STALE,
            FreshnessFlag.DEAD,
        ]:
            flag_config = self._config.get(flag, {})
            max_days = flag_config.get("max_days")
            if max_days and age_days <= max_days:
                return flag

        return FreshnessFlag.EXPIRED

    def apply_freshness_multiplier(
        self,
        composite_score: float,
        signal_date: datetime,
        reference_date: datetime | None = None,
    ) -> tuple[float, FreshnessResult]:
        """Apply freshness multiplier to a composite score.

        Args:
            composite_score: The base composite score (0-100)
            signal_date: When the signal was detected
            reference_date: Reference date (defaults to now)

        Returns:
            Tuple of (final_score, FreshnessResult)
        """
        freshness = self.calculate_freshness(signal_date, reference_date)
        final_score = composite_score * freshness.multiplier

        # Clamp to 0-100 (can exceed 100 with HOT multiplier, but we cap it)
        final_score = min(100.0, max(0.0, final_score))

        return final_score, freshness

    def get_multiplier(self, flag: FreshnessFlag) -> float:
        """Get the multiplier for a freshness flag.

        Args:
            flag: The freshness flag

        Returns:
            The multiplier value
        """
        flag_config = self._config.get(flag, {})
        return flag_config.get("multiplier", 1.0)

    def get_flag_label(self, flag: FreshnessFlag) -> str:
        """Get the display label for a freshness flag.

        Args:
            flag: The freshness flag

        Returns:
            The display label with emoji
        """
        flag_config = self._config.get(flag, {})
        return flag_config.get("label", flag.value)

    def get_broker_action(self, flag: FreshnessFlag) -> str:
        """Get the recommended broker action for a freshness flag.

        Args:
            flag: The freshness flag

        Returns:
            The recommended action string
        """
        flag_config = self._config.get(flag, {})
        return flag_config.get("action", "")


# Singleton instance
freshness_calculator = FreshnessCalculator()
