"""FIT dimension scoring for MCA leads.

FIT scoring measures how well a business fits the MCA customer profile:
- Industry Propensity: How likely this industry is to need/use MCA
- Time in Business: Maturity indicator and risk factor
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from src.scoring.industry_classifier import IndustryClassification, industry_classifier
from src.utils.config import config


@dataclass
class FITScoreResult:
    """Result of FIT dimension scoring."""

    # Raw scores
    industry_propensity: int = 0  # 0-10
    time_in_business_score: int = 0  # 0-5

    # Derived values
    industry_name: Optional[str] = None
    industry_confidence: float = 0.0
    time_in_business_months: Optional[int] = None

    # Flags
    is_nurture: bool = False
    nurture_reason: Optional[str] = None

    # Final scores
    raw_total: int = 0  # Sum of raw scores (0-15)
    scaled_score: int = 0  # Scaled to 0-100

    # Details for explainability
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def fit_score(self) -> int:
        """Return the final FIT score (0-100)."""
        return self.scaled_score


class FITScorer:
    """Calculate FIT dimension scores for businesses."""

    # Maximum raw points for scaling
    MAX_INDUSTRY_POINTS = 10
    MAX_TIB_POINTS = 5
    MAX_RAW_POINTS = MAX_INDUSTRY_POINTS + MAX_TIB_POINTS  # 15

    def __init__(self) -> None:
        """Initialize the FIT scorer with configuration."""
        self._config = config.get_fit_components()
        self._tib_thresholds = config.get_tib_thresholds()

    def score(
        self,
        business_name: str,
        dba_name: str | None = None,
        formation_date: date | None = None,
        time_in_business_months: int | None = None,
        industry: str | None = None,
    ) -> FITScoreResult:
        """Calculate FIT score for a business.

        Args:
            business_name: Legal business name
            dba_name: DBA/trade name if available
            formation_date: Date business was formed
            time_in_business_months: Pre-calculated months in business
            industry: Pre-classified industry (skips classification if provided)

        Returns:
            FITScoreResult with all score components
        """
        result = FITScoreResult()

        # Score industry propensity
        self._score_industry(result, business_name, dba_name, industry)

        # Score time in business
        self._score_time_in_business(result, formation_date, time_in_business_months)

        # Calculate totals
        result.raw_total = result.industry_propensity + result.time_in_business_score
        result.scaled_score = self._scale_to_100(result.raw_total)

        # Build details for explainability
        result.details = {
            "industry_propensity": {
                "raw_score": result.industry_propensity,
                "max_score": self.MAX_INDUSTRY_POINTS,
                "industry": result.industry_name,
                "confidence": result.industry_confidence,
            },
            "time_in_business": {
                "raw_score": result.time_in_business_score,
                "max_score": self.MAX_TIB_POINTS,
                "months": result.time_in_business_months,
            },
            "scaling": {
                "raw_total": result.raw_total,
                "max_raw": self.MAX_RAW_POINTS,
                "scaled_score": result.scaled_score,
            },
        }

        return result

    def _score_industry(
        self,
        result: FITScoreResult,
        business_name: str,
        dba_name: str | None,
        pre_classified: str | None,
    ) -> None:
        """Score industry propensity.

        Args:
            result: FITScoreResult to update
            business_name: Business name for classification
            dba_name: DBA name for classification
            pre_classified: Pre-classified industry if available
        """
        if pre_classified:
            # Use pre-classified industry
            propensity = industry_classifier.get_propensity(pre_classified)
            result.industry_propensity = propensity
            result.industry_name = pre_classified
            result.industry_confidence = 1.0
        else:
            # Classify from business name
            classification = industry_classifier.classify(business_name, dba_name)
            result.industry_propensity = classification.propensity
            result.industry_name = classification.industry
            result.industry_confidence = classification.confidence

    def _score_time_in_business(
        self,
        result: FITScoreResult,
        formation_date: date | None,
        time_in_business_months: int | None,
    ) -> None:
        """Score time in business.

        Args:
            result: FITScoreResult to update
            formation_date: Business formation date
            time_in_business_months: Pre-calculated months
        """
        # Calculate months if formation date provided
        if time_in_business_months is None and formation_date:
            today = date.today()
            months = (today.year - formation_date.year) * 12
            months += today.month - formation_date.month
            time_in_business_months = max(0, months)

        result.time_in_business_months = time_in_business_months

        if time_in_business_months is None:
            # Unknown TIB - give middle score
            result.time_in_business_score = 2
            return

        # Find matching threshold
        for threshold in self._tib_thresholds:
            min_months = threshold.get("min_months", 0)
            points = threshold.get("points", 0)

            if time_in_business_months >= min_months:
                result.time_in_business_score = points

                # Check for nurture flag
                if threshold.get("flag") == "nurture":
                    result.is_nurture = True
                    result.nurture_reason = threshold.get(
                        "nurture_reason",
                        "Time in business below threshold",
                    )
                break

    def _scale_to_100(self, raw_score: int) -> int:
        """Scale raw score (0-15) to 0-100.

        Args:
            raw_score: Raw score sum

        Returns:
            Scaled score (0-100)
        """
        if self.MAX_RAW_POINTS == 0:
            return 0
        return round((raw_score / self.MAX_RAW_POINTS) * 100)

    def score_batch(
        self,
        businesses: list[dict[str, Any]],
    ) -> list[FITScoreResult]:
        """Score multiple businesses.

        Args:
            businesses: List of dicts with keys:
                - business_name (required)
                - dba_name (optional)
                - formation_date (optional)
                - time_in_business_months (optional)
                - industry (optional)

        Returns:
            List of FITScoreResult objects
        """
        results = []
        for biz in businesses:
            result = self.score(
                business_name=biz.get("business_name", ""),
                dba_name=biz.get("dba_name"),
                formation_date=biz.get("formation_date"),
                time_in_business_months=biz.get("time_in_business_months"),
                industry=biz.get("industry"),
            )
            results.append(result)
        return results


# Singleton instance
fit_scorer = FITScorer()
