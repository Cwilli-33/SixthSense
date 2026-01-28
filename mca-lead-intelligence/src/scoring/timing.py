"""TIMING dimension scoring for MCA leads.

Version 4.0: TIMING weight reduced from 30% to 20%
- Timing is now embedded in Intent decay
- Additional timing captured via Freshness Multiplier

TIMING components:
- Seasonal timing (4-6 weeks before industry peak = max points)
- Signal recency (< 48 hours = max points)
- Refinance window (4-6 months = optimal)
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Optional

from src.utils.config import config


class SeasonalTiming(Enum):
    """Seasonal timing classifications."""

    PRE_PEAK_OPTIMAL = "pre_peak_optimal"  # 4-6 weeks before
    PRE_PEAK_GOOD = "pre_peak_good"  # 6-8 weeks before
    PRE_PEAK_EARLY = "pre_peak_early"  # 8-12 weeks before
    DURING_PEAK = "during_peak"
    OFF_SEASON = "off_season"


# Industry peak seasons (month numbers, 1-12)
INDUSTRY_PEAK_SEASONS = {
    "restaurants": [5, 6, 7, 12],  # Summer + holidays
    "retail": [11, 12],  # Holiday shopping
    "hvac": [6, 7, 8, 12, 1],  # Summer cooling + winter heating
    "landscaping": [4, 5, 6, 7, 8],  # Spring/summer
    "construction": [4, 5, 6, 7, 8, 9],  # Spring through fall
    "fitness": [1, 2],  # New Year resolutions
    "tax_prep": [2, 3, 4],  # Tax season
    "pool_services": [5, 6, 7, 8],  # Summer
    "auto_services": [3, 4, 5, 9, 10],  # Pre-summer + pre-winter
    "trucking": [9, 10, 11, 12],  # Holiday shipping
    "healthcare": [1, 2, 10, 11, 12],  # Flu season + end of year
    "salon_spa": [4, 5, 11, 12],  # Prom/wedding + holidays
}

# Seasonal timing calendar for targeting
SEASONAL_CALENDAR = {
    1: ["fitness", "tax_prep", "restaurants"],
    2: ["hvac", "construction", "landscaping"],
    3: ["construction", "landscaping", "hvac"],
    4: ["construction", "landscaping", "restaurants"],
    5: ["hvac", "restaurants", "construction"],
    6: ["hvac", "construction", "restaurants"],
    7: ["hvac", "restaurants", "retail"],
    8: ["restaurants", "retail", "healthcare"],
    9: ["restaurants", "retail", "hvac"],
    10: ["restaurants", "retail", "hvac"],
    11: ["retail", "hvac", "fitness"],
    12: ["retail", "tax_prep", "fitness"],
}


@dataclass
class TIMINGScoreResult:
    """Result of TIMING dimension scoring."""

    # Component scores
    seasonal_score: int = 0  # 0-30
    recency_score: int = 0  # 0-30
    refinance_window_score: int = 0  # 0-15

    # Derived values
    seasonal_timing: Optional[SeasonalTiming] = None
    signal_age_days: float = 0.0
    ucc_months_old: Optional[float] = None

    # Final scores
    raw_total: int = 0  # Sum of raw scores (0-75)
    scaled_score: int = 0  # Scaled to 0-100

    # Details for explainability
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def timing_score(self) -> int:
        """Return the final TIMING score (0-100)."""
        return self.scaled_score


class TIMINGScorer:
    """Calculate TIMING dimension scores."""

    MAX_SEASONAL_POINTS = 30
    MAX_RECENCY_POINTS = 30
    MAX_REFINANCE_POINTS = 15
    MAX_RAW_POINTS = MAX_SEASONAL_POINTS + MAX_RECENCY_POINTS + MAX_REFINANCE_POINTS  # 75

    def __init__(self) -> None:
        """Initialize the TIMING scorer with configuration."""
        self._timing_config = config.scoring.get("timing_components", {})
        self._ucc_window_config = config.scoring.get("ucc_refinance_window", {}).get("windows", [])

    def score(
        self,
        signal_date: datetime,
        industry: str | None = None,
        ucc_months_old: float | None = None,
        reference_date: datetime | None = None,
    ) -> TIMINGScoreResult:
        """Calculate TIMING score.

        Args:
            signal_date: When the signal was detected
            industry: Business industry for seasonal timing
            ucc_months_old: Months since UCC filing (for refinance window)
            reference_date: Reference date (defaults to now)

        Returns:
            TIMINGScoreResult with all scores and breakdown
        """
        if reference_date is None:
            reference_date = datetime.now()

        result = TIMINGScoreResult()

        # Calculate signal age
        delta = reference_date - signal_date
        result.signal_age_days = max(0.0, delta.total_seconds() / 86400)

        # Score components
        self._score_seasonal(result, industry, reference_date)
        self._score_recency(result)
        self._score_refinance_window(result, ucc_months_old)

        # Calculate totals
        result.raw_total = (
            result.seasonal_score +
            result.recency_score +
            result.refinance_window_score
        )
        result.scaled_score = self._scale_to_100(result.raw_total)

        # Build details
        result.details = {
            "seasonal": {
                "score": result.seasonal_score,
                "max": self.MAX_SEASONAL_POINTS,
                "timing": result.seasonal_timing.value if result.seasonal_timing else None,
                "industry": industry,
            },
            "recency": {
                "score": result.recency_score,
                "max": self.MAX_RECENCY_POINTS,
                "signal_age_days": round(result.signal_age_days, 1),
            },
            "refinance_window": {
                "score": result.refinance_window_score,
                "max": self.MAX_REFINANCE_POINTS,
                "ucc_months_old": ucc_months_old,
            },
            "scaling": {
                "raw_total": result.raw_total,
                "max_raw": self.MAX_RAW_POINTS,
                "scaled_score": result.scaled_score,
            },
        }

        return result

    def _score_seasonal(
        self,
        result: TIMINGScoreResult,
        industry: str | None,
        reference_date: datetime,
    ) -> None:
        """Score seasonal timing component.

        Args:
            result: TIMINGScoreResult to update
            industry: Business industry
            reference_date: Current date for seasonal calculation
        """
        if not industry:
            # Default to moderate score for unknown industry
            result.seasonal_score = 15
            result.seasonal_timing = SeasonalTiming.OFF_SEASON
            return

        industry_lower = industry.lower().replace(" ", "_")
        peak_months = INDUSTRY_PEAK_SEASONS.get(industry_lower, [])

        if not peak_months:
            # No peak season data for this industry
            result.seasonal_score = 15
            result.seasonal_timing = SeasonalTiming.OFF_SEASON
            return

        current_month = reference_date.month

        # Check if we're in peak season
        if current_month in peak_months:
            result.seasonal_score = 15
            result.seasonal_timing = SeasonalTiming.DURING_PEAK
            return

        # Calculate weeks until next peak
        weeks_to_peak = self._calculate_weeks_to_peak(current_month, peak_months)

        if weeks_to_peak <= 6:  # 4-6 weeks before peak
            result.seasonal_score = 30
            result.seasonal_timing = SeasonalTiming.PRE_PEAK_OPTIMAL
        elif weeks_to_peak <= 8:  # 6-8 weeks before peak
            result.seasonal_score = 25
            result.seasonal_timing = SeasonalTiming.PRE_PEAK_GOOD
        elif weeks_to_peak <= 12:  # 8-12 weeks before peak
            result.seasonal_score = 18
            result.seasonal_timing = SeasonalTiming.PRE_PEAK_EARLY
        else:  # Off-season
            result.seasonal_score = 8
            result.seasonal_timing = SeasonalTiming.OFF_SEASON

    def _calculate_weeks_to_peak(
        self,
        current_month: int,
        peak_months: list[int],
    ) -> int:
        """Calculate weeks until the next peak season.

        Args:
            current_month: Current month (1-12)
            peak_months: List of peak season months

        Returns:
            Approximate weeks until next peak
        """
        min_weeks = 52  # Default to a year

        for peak_month in peak_months:
            if peak_month > current_month:
                months_diff = peak_month - current_month
            else:
                months_diff = 12 - current_month + peak_month

            weeks = months_diff * 4  # Approximate
            if weeks < min_weeks:
                min_weeks = weeks

        return min_weeks

    def _score_recency(self, result: TIMINGScoreResult) -> None:
        """Score signal recency component.

        Args:
            result: TIMINGScoreResult to update (uses signal_age_days)
        """
        recency_config = self._timing_config.get("signal_recency", {}).get("thresholds", [])

        age_days = result.signal_age_days
        age_hours = age_days * 24

        # Check thresholds in order
        for threshold in recency_config:
            max_hours = threshold.get("max_hours")
            max_days = threshold.get("max_days")

            if max_hours and age_hours <= max_hours:
                result.recency_score = threshold.get("points", 0)
                return
            elif max_days and age_days <= max_days:
                result.recency_score = threshold.get("points", 0)
                return

        # Default scoring if no config
        if age_days <= 2:  # < 48 hours
            result.recency_score = 30
        elif age_days <= 7:
            result.recency_score = 25
        elif age_days <= 14:
            result.recency_score = 18
        elif age_days <= 30:
            result.recency_score = 10
        elif age_days <= 60:
            result.recency_score = 5
        else:
            result.recency_score = 0

    def _score_refinance_window(
        self,
        result: TIMINGScoreResult,
        ucc_months_old: float | None,
    ) -> None:
        """Score refinance window component.

        Args:
            result: TIMINGScoreResult to update
            ucc_months_old: Months since UCC filing
        """
        result.ucc_months_old = ucc_months_old

        if ucc_months_old is None:
            # No UCC data, no refinance window score
            result.refinance_window_score = 0
            return

        refinance_config = self._timing_config.get("refinance_window", {}).get("thresholds", [])

        # Check thresholds
        for threshold in refinance_config:
            min_months = threshold.get("ucc_months", 0)
            max_months = threshold.get("max_ucc_months", 999)

            if min_months <= ucc_months_old < max_months:
                result.refinance_window_score = threshold.get("points", 0)
                return

        # Default scoring based on v4.0 curve if no config match
        if 4 <= ucc_months_old < 5:
            result.refinance_window_score = 15  # OPTIMAL
        elif 5 <= ucc_months_old < 6:
            result.refinance_window_score = 12  # OPTIMAL
        elif 6 <= ucc_months_old < 7:
            result.refinance_window_score = 8  # GOOD
        elif 3 <= ucc_months_old < 4:
            result.refinance_window_score = 5  # EARLY
        elif 7 <= ucc_months_old < 9:
            result.refinance_window_score = 5  # LATE
        else:
            result.refinance_window_score = 0

    def _scale_to_100(self, raw_score: int) -> int:
        """Scale raw score (0-75) to 0-100.

        Args:
            raw_score: Raw score sum

        Returns:
            Scaled score (0-100)
        """
        if self.MAX_RAW_POINTS == 0:
            return 0
        return round((raw_score / self.MAX_RAW_POINTS) * 100)

    def get_target_industries_for_month(self, month: int) -> list[str]:
        """Get industries to target for a specific month.

        Args:
            month: Month number (1-12)

        Returns:
            List of industry names to target
        """
        return SEASONAL_CALENDAR.get(month, [])

    def is_pre_peak(self, industry: str, reference_date: datetime | None = None) -> bool:
        """Check if we're in pre-peak timing for an industry.

        Args:
            industry: Industry name
            reference_date: Reference date (defaults to now)

        Returns:
            True if in pre-peak window (4-12 weeks before peak)
        """
        if reference_date is None:
            reference_date = datetime.now()

        industry_lower = industry.lower().replace(" ", "_")
        peak_months = INDUSTRY_PEAK_SEASONS.get(industry_lower, [])

        if not peak_months:
            return False

        current_month = reference_date.month

        if current_month in peak_months:
            return False

        weeks_to_peak = self._calculate_weeks_to_peak(current_month, peak_months)
        return weeks_to_peak <= 12


# Singleton instance
timing_scorer = TIMINGScorer()
