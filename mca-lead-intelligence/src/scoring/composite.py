"""Composite scoring combining FIT, INTENT, and TIMING dimensions.

Version 4.0: Time-Weighted Scoring Engine

Formula:
1. Time-Weighted INTENT = Σ(Signal_Base_Value × e^(-λ × signal_age_days))
2. Composite Score = (FIT × 0.40) + (Time-Weighted INTENT × 0.40) + (TIMING × 0.20)
3. FINAL SCORE = Composite Score × Lead_Freshness_Multiplier
4. Priority = P1 if FINAL SCORE ≥ 75, P2 if ≥ 60, P3 if ≥ 45, P4 if ≥ 30, else P5
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from src.models.lead import LeadCreate, PriorityLevel, ScoreBreakdown
from src.models.signal import SignalCreate
from src.scoring.fit import FITScoreResult, fit_scorer
from src.scoring.freshness import FreshnessFlag, FreshnessResult, freshness_calculator
from src.scoring.intent import INTENTScoreResult, IntentPathway, IntentSignal, intent_scorer
from src.scoring.timing import TIMINGScoreResult, timing_scorer
from src.utils.config import config


@dataclass
class CompositeScoreResult:
    """Result of composite scoring (v4.0)."""

    # Dimension scores (0-100 each)
    fit_score: int = 0
    intent_score: int = 0
    timing_score: int = 0

    # Composite and final scores
    composite_score: Decimal = Decimal("0.00")
    final_score: Decimal = Decimal("0.00")
    priority_level: PriorityLevel = PriorityLevel.P5

    # Freshness (v4.0)
    freshness_flag: FreshnessFlag = FreshnessFlag.STANDARD
    freshness_multiplier: float = 1.0
    freshness_label: str = ""

    # Intent pathway
    intent_pathway: IntentPathway = IntentPathway.GENERAL
    intent_pathway_message: str = ""

    # Component results
    fit_result: Optional[FITScoreResult] = None
    intent_result: Optional[INTENTScoreResult] = None
    timing_result: Optional[TIMINGScoreResult] = None
    freshness_result: Optional[FreshnessResult] = None

    # Adjustments applied
    adjustments: list[dict[str, Any]] = field(default_factory=list)

    # Full breakdown for explainability
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)

    # v4.0 specific fields
    signal_age_days: float = 0.0
    ucc_months_old: Optional[float] = None

    @property
    def is_hot_lead(self) -> bool:
        """Check if this is a hot lead (P1 or HOT freshness)."""
        return self.priority_level == PriorityLevel.P1 or self.freshness_flag == FreshnessFlag.HOT


class CompositeScorer:
    """Calculate composite scores from all dimensions.

    Version 4.0: Time-Weighted Scoring Engine with Freshness Multiplier.
    """

    def __init__(self) -> None:
        """Initialize the composite scorer."""
        self._weights = config.scoring.get("weights", {})
        self._thresholds = config.get_priority_thresholds()
        self._adjustments_config = config.scoring.get("adjustments", {})
        self._geo_config = config.scoring.get("geographic_propensity", {})

    def score(
        self,
        business_name: str,
        signal: SignalCreate | None = None,
        signal_date: datetime | None = None,
        dba_name: str | None = None,
        formation_date: date | None = None,
        time_in_business_months: int | None = None,
        industry: str | None = None,
        state: str | None = None,
        is_mca_related: bool = False,
        mca_lender: str | None = None,
        signal_count: int = 1,
        intent_signals: list[IntentSignal] | None = None,
        ucc_months_old: float | None = None,
        estimated_monthly_revenue: int | None = None,
        employee_count: int | None = None,
    ) -> CompositeScoreResult:
        """Calculate composite score for a lead using v4.0 formula.

        Args:
            business_name: Legal business name
            signal: The signal that generated this lead
            signal_date: Signal date (used if signal not provided)
            dba_name: DBA/trade name
            formation_date: Business formation date
            time_in_business_months: Pre-calculated months
            industry: Pre-classified industry
            state: Business state (for geographic bonus)
            is_mca_related: Whether signal is MCA-related
            mca_lender: Matched MCA lender name
            signal_count: Number of signals for this business
            intent_signals: List of intent signals for INTENT scoring
            ucc_months_old: Months since UCC filing
            estimated_monthly_revenue: Known monthly revenue
            employee_count: Number of employees

        Returns:
            CompositeScoreResult with all scores and breakdown
        """
        result = CompositeScoreResult()

        # Determine signal date
        if signal_date is None and signal:
            signal_date = signal.signal_date
        if signal_date is None:
            signal_date = datetime.now()

        # Calculate signal age
        result.signal_age_days = (datetime.now() - signal_date).total_seconds() / 86400
        result.ucc_months_old = ucc_months_old

        # =================================================================
        # Step 1: Calculate FIT score
        # =================================================================
        fit_result = fit_scorer.score(
            business_name=business_name,
            dba_name=dba_name,
            formation_date=formation_date,
            time_in_business_months=time_in_business_months,
            industry=industry,
            estimated_monthly_revenue=estimated_monthly_revenue,
            employee_count=employee_count,
        )
        result.fit_score = fit_result.fit_score
        result.fit_result = fit_result

        # =================================================================
        # Step 2: Calculate Time-Weighted INTENT score
        # =================================================================
        if intent_signals:
            intent_result = intent_scorer.score(intent_signals)
            result.intent_score = intent_result.intent_score
            result.intent_result = intent_result
            result.intent_pathway = intent_result.pathway
            result.intent_pathway_message = intent_result.pathway_message
        else:
            # Create intent signal from UCC if applicable
            if is_mca_related and ucc_months_old is not None:
                ucc_signal = intent_scorer.create_signal_from_ucc(
                    ucc_filing_date=signal_date,
                    is_mca_related=is_mca_related,
                    ucc_months_old=ucc_months_old,
                )
                if ucc_signal:
                    intent_result = intent_scorer.score([ucc_signal])
                    result.intent_score = intent_result.intent_score
                    result.intent_result = intent_result
                    result.intent_pathway = intent_result.pathway
                    result.intent_pathway_message = intent_result.pathway_message

        # =================================================================
        # Step 3: Calculate TIMING score
        # =================================================================
        timing_result = timing_scorer.score(
            signal_date=signal_date,
            industry=industry or fit_result.industry_name,
            ucc_months_old=ucc_months_old,
        )
        result.timing_score = timing_result.timing_score
        result.timing_result = timing_result

        # =================================================================
        # Step 4: Calculate Composite Score (weighted)
        # =================================================================
        fit_weight = self._weights.get("fit", 0.40)
        intent_weight = self._weights.get("intent", 0.40)
        timing_weight = self._weights.get("timing", 0.20)

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
            state=state,
        )
        weighted_score += adjustments_total

        # Clamp to 0-100
        result.composite_score = Decimal(str(min(max(weighted_score, 0), 100))).quantize(
            Decimal("0.01")
        )

        # =================================================================
        # Step 5: Apply Freshness Multiplier
        # =================================================================
        freshness_result = freshness_calculator.calculate_freshness(signal_date)
        result.freshness_result = freshness_result
        result.freshness_flag = freshness_result.flag
        result.freshness_multiplier = freshness_result.multiplier
        result.freshness_label = freshness_result.label

        # Calculate final score with freshness multiplier
        final_score = float(result.composite_score) * freshness_result.multiplier
        final_score = min(100.0, max(0.0, final_score))
        result.final_score = Decimal(str(final_score)).quantize(Decimal("0.01"))

        # =================================================================
        # Step 6: Determine Priority Level (based on FINAL score)
        # =================================================================
        result.priority_level = self._determine_priority(float(result.final_score))

        # =================================================================
        # Build Score Breakdown
        # =================================================================
        result.breakdown = self._build_breakdown(result, is_mca_related, mca_lender)

        return result

    def _apply_adjustments(
        self,
        result: CompositeScoreResult,
        is_mca_related: bool,
        signal_count: int,
        state: str | None,
    ) -> float:
        """Apply score adjustments/bonuses.

        Args:
            result: Result object to record adjustments
            is_mca_related: Whether MCA-related
            signal_count: Number of signals
            state: Business state for geographic bonus

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
        for tier in sorted(multi_signal_config, key=lambda x: x.get("count", 0), reverse=True):
            if signal_count >= tier.get("count", 0):
                bonus = tier.get("bonus", 0)
                total += bonus
                result.adjustments.append({
                    "name": "multi_signal_bonus",
                    "points": bonus,
                    "reason": f"{signal_count} signals detected",
                })
                break  # Use highest matching tier

        # Geographic bonus (v4.0)
        if state:
            geo_bonus = self._get_geographic_bonus(state)
            if geo_bonus > 0:
                total += geo_bonus
                result.adjustments.append({
                    "name": "geographic_bonus",
                    "points": geo_bonus,
                    "reason": f"High-volume state: {state}",
                })

        return total

    def _get_geographic_bonus(self, state: str) -> int:
        """Get geographic bonus for a state.

        Args:
            state: State abbreviation

        Returns:
            Bonus points
        """
        state_upper = state.upper()

        for tier_name in ["tier1", "tier2", "tier3"]:
            tier = self._geo_config.get(tier_name, {})
            states = tier.get("states", [])
            if state_upper in states:
                return tier.get("bonus", 0)

        return 0

    def _determine_priority(self, score: float) -> PriorityLevel:
        """Determine priority level from final score.

        Args:
            score: Final score (0-100, after freshness multiplier)

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

    def _build_breakdown(
        self,
        result: CompositeScoreResult,
        is_mca_related: bool,
        mca_lender: str | None,
    ) -> ScoreBreakdown:
        """Build score breakdown for explainability.

        Args:
            result: CompositeScoreResult
            is_mca_related: Whether MCA-related
            mca_lender: Matched lender name

        Returns:
            ScoreBreakdown object
        """
        breakdown = ScoreBreakdown(
            # FIT components
            industry_propensity=result.fit_result.industry_propensity if result.fit_result else 0,
            industry_name=result.fit_result.industry_name if result.fit_result else None,
            time_in_business_score=result.fit_result.time_in_business_score if result.fit_result else 0,
            time_in_business_months=result.fit_result.time_in_business_months if result.fit_result else None,

            # MCA info
            is_mca_related=is_mca_related,
            mca_lender=mca_lender,

            # Flags
            is_nurture=result.fit_result.is_nurture if result.fit_result else False,
            nurture_reason=result.fit_result.nurture_reason if result.fit_result else None,

            # Timing
            signal_age_days=int(result.signal_age_days),
        )

        return breakdown

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
            composite_score=score_result.final_score,  # Use final score (with freshness)
            priority_level=score_result.priority_level,
            score_breakdown=score_result.breakdown,
        )

    def get_priority_matrix_result(
        self,
        fit_score: int,
        intent_score: int,
        timing_score: int,
    ) -> PriorityLevel:
        """Determine priority using the priority matrix.

        Cross-reference Fit, Intent, and Timing to determine priority.

        Args:
            fit_score: FIT dimension score (0-100)
            intent_score: INTENT dimension score (0-100)
            timing_score: TIMING dimension score (0-100)

        Returns:
            PriorityLevel based on matrix
        """
        # Classify each dimension
        fit_level = "high" if fit_score >= 60 else "med" if fit_score >= 40 else "low"
        intent_level = "high" if intent_score >= 60 else "med" if intent_score >= 40 else "low"
        timing_level = "high" if timing_score >= 60 else "med" if timing_score >= 40 else "low"

        # Priority matrix from v4.0 spec
        matrix = {
            ("high", "high", "high"): PriorityLevel.P1,
            ("high", "high", "med"): PriorityLevel.P1,
            ("high", "high", "low"): PriorityLevel.P2,
            ("high", "med", "high"): PriorityLevel.P1,
            ("high", "med", "med"): PriorityLevel.P2,
            ("high", "med", "low"): PriorityLevel.P3,
            ("high", "low", "high"): PriorityLevel.P2,
            ("high", "low", "med"): PriorityLevel.P3,
            ("high", "low", "low"): PriorityLevel.P4,
            ("med", "high", "high"): PriorityLevel.P1,
            ("med", "high", "med"): PriorityLevel.P2,
            ("med", "high", "low"): PriorityLevel.P3,
            ("med", "med", "high"): PriorityLevel.P2,
            ("med", "med", "med"): PriorityLevel.P3,
            ("med", "med", "low"): PriorityLevel.P4,
            ("med", "low", "high"): PriorityLevel.P3,
            ("med", "low", "med"): PriorityLevel.P4,
            ("med", "low", "low"): PriorityLevel.P5,
            ("low", "high", "high"): PriorityLevel.P3,
            ("low", "high", "med"): PriorityLevel.P4,
            ("low", "high", "low"): PriorityLevel.P5,
            ("low", "med", "high"): PriorityLevel.P4,
            ("low", "med", "med"): PriorityLevel.P4,
            ("low", "med", "low"): PriorityLevel.P5,
            ("low", "low", "high"): PriorityLevel.P4,
            ("low", "low", "med"): PriorityLevel.P5,
            ("low", "low", "low"): PriorityLevel.P5,
        }

        return matrix.get((fit_level, intent_level, timing_level), PriorityLevel.P5)


# Singleton instance
composite_scorer = CompositeScorer()
