"""Composite scoring combining FIT, INTENT, and TIMING dimensions.

Phase 1: FIT only (100% weight)
Phase 2: FIT + INTENT
Phase 3: FIT + INTENT + TIMING
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from src.models.lead import LeadCreate, PriorityLevel, ScoreBreakdown
from src.models.signal import SignalCreate
from src.scoring.fit import FITScoreResult, fit_scorer
from src.utils.config import config


@dataclass
class CompositeScoreResult:
    """Result of composite scoring."""

    # Dimension scores
    fit_score: int = 0
    intent_score: int = 0  # Phase 2
    timing_score: int = 0  # Phase 3

    # Composite
    composite_score: Decimal = Decimal("0.00")
    priority_level: PriorityLevel = PriorityLevel.P5

    # Components
    fit_result: Optional[FITScoreResult] = None

    # Adjustments applied
    adjustments: list[dict[str, Any]] = field(default_factory=list)

    # Full breakdown for explainability
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)


class CompositeScorer:
    """Calculate composite scores from all dimensions."""

    def __init__(self) -> None:
        """Initialize the composite scorer."""
        self._weights = config.scoring.get("weights", {})
        self._thresholds = config.get_priority_thresholds()
        self._adjustments_config = config.scoring.get("adjustments", {})

    def score(
        self,
        business_name: str,
        signal: SignalCreate | None = None,
        dba_name: str | None = None,
        formation_date: date | None = None,
        time_in_business_months: int | None = None,
        industry: str | None = None,
        is_mca_related: bool = False,
        mca_lender: str | None = None,
        signal_count: int = 1,
    ) -> CompositeScoreResult:
        """Calculate composite score for a lead.

        Args:
            business_name: Legal business name
            signal: The signal that generated this lead
            dba_name: DBA/trade name
            formation_date: Business formation date
            time_in_business_months: Pre-calculated months
            industry: Pre-classified industry
            is_mca_related: Whether signal is MCA-related
            mca_lender: Matched MCA lender name
            signal_count: Number of signals for this business

        Returns:
            CompositeScoreResult with all scores and breakdown
        """
        result = CompositeScoreResult()

        # Calculate FIT score
        fit_result = fit_scorer.score(
            business_name=business_name,
            dba_name=dba_name,
            formation_date=formation_date,
            time_in_business_months=time_in_business_months,
            industry=industry,
        )
        result.fit_score = fit_result.fit_score
        result.fit_result = fit_result

        # Build score breakdown
        result.breakdown = ScoreBreakdown(
            industry_propensity=fit_result.industry_propensity,
            industry_name=fit_result.industry_name,
            time_in_business_score=fit_result.time_in_business_score,
            time_in_business_months=fit_result.time_in_business_months,
            is_mca_related=is_mca_related,
            mca_lender=mca_lender,
            is_nurture=fit_result.is_nurture,
            nurture_reason=fit_result.nurture_reason,
        )

        # Calculate signal age if signal provided
        if signal:
            signal_age_days = (datetime.now() - signal.signal_date).days
            result.breakdown.signal_age_days = signal_age_days

        # Phase 1: Composite = FIT only
        # Apply weights (currently FIT = 1.0, others = 0.0)
        fit_weight = self._weights.get("fit", 1.0)
        intent_weight = self._weights.get("intent", 0.0)
        timing_weight = self._weights.get("timing", 0.0)

        weighted_score = (
            result.fit_score * fit_weight +
            result.intent_score * intent_weight +
            result.timing_score * timing_weight
        )

        # Apply adjustments
        adjustments_total = self._apply_adjustments(
            result,
            is_mca_related=is_mca_related,
            signal_count=signal_count,
        )
        weighted_score += adjustments_total

        # Clamp to 0-100
        result.composite_score = Decimal(str(min(max(weighted_score, 0), 100))).quantize(
            Decimal("0.01")
        )

        # Determine priority level
        result.priority_level = self._determine_priority(float(result.composite_score))

        return result

    def _apply_adjustments(
        self,
        result: CompositeScoreResult,
        is_mca_related: bool,
        signal_count: int,
    ) -> float:
        """Apply score adjustments/bonuses.

        Args:
            result: Result object to record adjustments
            is_mca_related: Whether MCA-related
            signal_count: Number of signals

        Returns:
            Total adjustment points
        """
        total = 0.0

        # MCA-related bonus
        if is_mca_related:
            bonus = self._adjustments_config.get("mca_related_bonus", 0)
            if bonus:
                total += bonus
                result.adjustments.append({
                    "name": "mca_related_bonus",
                    "points": bonus,
                    "reason": "MCA-related signal detected",
                })

        # Multi-signal bonus
        multi_signal_config = self._adjustments_config.get("multi_signal_bonus", [])
        for tier in multi_signal_config:
            if signal_count >= tier.get("count", 0):
                bonus = tier.get("bonus", 0)
                total += bonus
                result.adjustments.append({
                    "name": "multi_signal_bonus",
                    "points": bonus,
                    "reason": f"{signal_count} signals detected",
                })
                break  # Use highest matching tier

        return total

    def _determine_priority(self, score: float) -> PriorityLevel:
        """Determine priority level from composite score.

        Args:
            score: Composite score (0-100)

        Returns:
            PriorityLevel enum value
        """
        for level in ["p1", "p2", "p3", "p4", "p5"]:
            threshold = self._thresholds.get(level, {})
            min_score = threshold.get("min_score", 0)
            max_score = threshold.get("max_score", 100)

            if min_score <= score <= max_score:
                return PriorityLevel(level.upper())

        return PriorityLevel.P5

    def create_lead(
        self,
        business_id: uuid.UUID,
        signal_ids: list[uuid.UUID],
        score_result: CompositeScoreResult,
    ) -> LeadCreate:
        """Create a LeadCreate object from scoring result.

        Args:
            business_id: UUID of the business
            signal_ids: List of signal UUIDs
            score_result: CompositeScoreResult from scoring

        Returns:
            LeadCreate ready for database insertion
        """
        return LeadCreate(
            business_id=business_id,
            signal_ids=signal_ids,
            fit_score=score_result.fit_score,
            intent_score=score_result.intent_score,
            timing_score=score_result.timing_score,
            composite_score=score_result.composite_score,
            priority_level=score_result.priority_level,
            score_breakdown=score_result.breakdown,
        )


# Singleton instance
composite_scorer = CompositeScorer()
