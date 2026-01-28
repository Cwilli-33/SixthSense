"""Exponential Decay Engine for time-weighted signal scoring.

Version 4.0 introduces exponential decay for intent signals:
Signal_Value(t) = Base_Value × e^(-λt)

Where:
- t = signal age in days
- λ (lambda) = ln(2) / half_life
- half_life = signal-specific decay rate in days
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from src.utils.config import config


class DecayClass(Enum):
    """Signal decay classifications based on signal type."""

    RAPID = "rapid"  # 7 days half-life
    RAPID_EXTENDED = "rapid_extended"  # 10 days half-life
    STANDARD = "standard"  # 21 days half-life
    STANDARD_EXTENDED = "standard_extended"  # 30 days half-life
    EXTENDED = "extended"  # 45 days half-life
    EXTENDED_LONG = "extended_long"  # 60 days half-life
    STRUCTURAL = "structural"  # 90 days half-life


@dataclass
class DecayResult:
    """Result of decay calculation."""

    base_value: float
    decayed_value: float
    decay_factor: float  # 0-1, multiplier applied
    signal_age_days: float
    half_life_days: int
    decay_class: DecayClass
    is_expired: bool = False  # True if decayed below threshold


class DecayEngine:
    """Calculate exponential decay for time-weighted signals."""

    # Default half-lives in days (fallback if config not available)
    DEFAULT_HALF_LIVES = {
        DecayClass.RAPID: 7,
        DecayClass.RAPID_EXTENDED: 10,
        DecayClass.STANDARD: 21,
        DecayClass.STANDARD_EXTENDED: 30,
        DecayClass.EXTENDED: 45,
        DecayClass.EXTENDED_LONG: 60,
        DecayClass.STRUCTURAL: 90,
    }

    # Minimum decay factor before signal is considered expired
    EXPIRATION_THRESHOLD = 0.05  # 5% of original value

    def __init__(self) -> None:
        """Initialize the decay engine with configuration."""
        self._decay_config = config.scoring.get("decay_classes", {})
        self._half_lives = self._load_half_lives()
        self._lambdas = self._calculate_lambdas()

    def _load_half_lives(self) -> dict[DecayClass, int]:
        """Load half-lives from config or use defaults."""
        half_lives = {}
        for decay_class in DecayClass:
            config_entry = self._decay_config.get(decay_class.value, {})
            half_life = config_entry.get(
                "half_life_days",
                self.DEFAULT_HALF_LIVES.get(decay_class, 30),
            )
            half_lives[decay_class] = half_life
        return half_lives

    def _calculate_lambdas(self) -> dict[DecayClass, float]:
        """Calculate lambda values for each decay class.

        λ = ln(2) / half_life_days
        """
        lambdas = {}
        ln2 = math.log(2)
        for decay_class, half_life in self._half_lives.items():
            lambdas[decay_class] = ln2 / half_life
        return lambdas

    def calculate_decay_factor(
        self,
        signal_age_days: float,
        decay_class: DecayClass,
    ) -> float:
        """Calculate the decay factor for a signal.

        Args:
            signal_age_days: Age of signal in days
            decay_class: The decay classification

        Returns:
            Decay factor (0-1) to multiply base value by
        """
        if signal_age_days <= 0:
            return 1.0

        lambda_val = self._lambdas.get(decay_class, 0.023)  # Default to standard
        decay_factor = math.exp(-lambda_val * signal_age_days)

        return max(0.0, min(1.0, decay_factor))

    def apply_decay(
        self,
        base_value: float,
        signal_age_days: float,
        decay_class: DecayClass | str,
    ) -> DecayResult:
        """Apply exponential decay to a signal value.

        Args:
            base_value: Original signal point value
            signal_age_days: Age of signal in days
            decay_class: The decay classification (enum or string)

        Returns:
            DecayResult with decayed value and metadata
        """
        # Convert string to enum if needed
        if isinstance(decay_class, str):
            try:
                decay_class = DecayClass(decay_class)
            except ValueError:
                decay_class = DecayClass.STANDARD

        decay_factor = self.calculate_decay_factor(signal_age_days, decay_class)
        decayed_value = base_value * decay_factor
        is_expired = decay_factor < self.EXPIRATION_THRESHOLD

        return DecayResult(
            base_value=base_value,
            decayed_value=decayed_value,
            decay_factor=decay_factor,
            signal_age_days=signal_age_days,
            half_life_days=self._half_lives.get(decay_class, 30),
            decay_class=decay_class,
            is_expired=is_expired,
        )

    def calculate_signal_age(
        self,
        signal_date: datetime,
        reference_date: datetime | None = None,
    ) -> float:
        """Calculate signal age in days.

        Args:
            signal_date: When the signal was detected
            reference_date: Reference date (defaults to now)

        Returns:
            Age in days (float for partial days)
        """
        if reference_date is None:
            reference_date = datetime.now()

        delta = reference_date - signal_date
        return max(0.0, delta.total_seconds() / 86400)  # seconds in a day

    def get_decay_percentage_at_days(
        self,
        days: int,
        decay_class: DecayClass,
    ) -> float:
        """Get the decay percentage at a specific number of days.

        Useful for reference tables.

        Args:
            days: Number of days since signal
            decay_class: The decay classification

        Returns:
            Percentage of original value remaining (0-100)
        """
        decay_factor = self.calculate_decay_factor(float(days), decay_class)
        return decay_factor * 100

    def get_half_life(self, decay_class: DecayClass) -> int:
        """Get the half-life for a decay class.

        Args:
            decay_class: The decay classification

        Returns:
            Half-life in days
        """
        return self._half_lives.get(decay_class, 30)

    def get_lambda(self, decay_class: DecayClass) -> float:
        """Get the lambda value for a decay class.

        Args:
            decay_class: The decay classification

        Returns:
            Lambda value for exponential decay
        """
        return self._lambdas.get(decay_class, 0.023)

    def estimate_days_to_threshold(
        self,
        decay_class: DecayClass,
        threshold: float = 0.1,
    ) -> float:
        """Estimate days until signal decays to a threshold.

        Args:
            decay_class: The decay classification
            threshold: Target decay factor (default 10%)

        Returns:
            Estimated days to reach threshold
        """
        lambda_val = self._lambdas.get(decay_class, 0.023)
        if lambda_val <= 0:
            return float("inf")

        # Solve: threshold = e^(-λt) for t
        # ln(threshold) = -λt
        # t = -ln(threshold) / λ
        return -math.log(threshold) / lambda_val


# Singleton instance
decay_engine = DecayEngine()
