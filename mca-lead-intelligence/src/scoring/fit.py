"""FIT dimension scoring for MCA leads.

Version 4.0: Data-Calibrated FIT Scoring
Based on analysis of 7,634 historical MCA transactions.

FIT scoring measures how well a business fits the MCA customer profile:
- Estimated Revenue Tier (0-35 points)
- Revenue Consistency Profile (0-30 points)
- Revenue Quality Profile (0-20 points) - CC processing likelihood
- Industry Propensity (0-10 points) - CALIBRATED from deal data
- Time in Business (0-5 points) - CALIBRATED from deal data

Total: 100 points
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from src.scoring.industry_classifier import IndustryClassification, industry_classifier
from src.utils.config import config


# Revenue consistency profiles by industry
CONSISTENCY_PROFILES = {
    "highly_recurring": {
        "points": 30,
        "industries": [
            "healthcare", "dental", "veterinary", "salon_spa",
            "fitness", "childcare", "medical",
        ],
    },
    "steady": {
        "points": 25,
        "industries": [
            "restaurants", "retail", "auto_services", "pharmacy",
        ],
    },
    "seasonal_predictable": {
        "points": 18,
        "industries": [
            "hvac", "landscaping", "pool_services", "tax_prep",
        ],
    },
    "moderately_lumpy": {
        "points": 12,
        "industries": [
            "residential_construction", "consulting", "catering",
        ],
    },
    "highly_lumpy": {
        "points": 5,
        "industries": [
            "commercial_construction", "real_estate", "construction",
        ],
    },
}

# Revenue quality (CC processing) profiles by industry
QUALITY_PROFILES = {
    "very_high_cc": {  # 70%+ CC
        "points": 20,
        "industries": [
            "restaurants", "retail", "salon_spa", "hotels",
        ],
    },
    "high_cc": {  # 50-70% CC
        "points": 16,
        "industries": [
            "healthcare", "fitness", "auto_services", "veterinary",
            "medical", "dental",
        ],
    },
    "moderate_cc": {  # 30-50% CC
        "points": 12,
        "industries": [
            "professional_services", "hvac",
        ],
    },
    "low_cc": {  # 10-30% CC
        "points": 6,
        "industries": [
            "wholesale", "consulting",
        ],
    },
    "very_low_cc": {  # <10% CC
        "points": 2,
        "industries": [
            "construction", "trucking", "manufacturing",
        ],
    },
}

# Revenue per employee estimates by industry (monthly)
INDUSTRY_REVENUE_MULTIPLIERS = {
    "healthcare": 32000,
    "medical": 32000,
    "dental": 32000,
    "professional_services": 27000,
    "technology": 24000,
    "consulting": 30000,
    "hvac": 16000,
    "auto_services": 14000,
    "construction": 14000,
    "salon_spa": 12000,
    "restaurants": 11000,
    "retail": 10000,
    "trucking": 10000,
    "landscaping": 8000,
    "cleaning": 6000,
}


@dataclass
class FITScoreResult:
    """Result of FIT dimension scoring."""

    # Component scores (v4.0)
    estimated_revenue_score: int = 0  # 0-35
    revenue_consistency_score: int = 0  # 0-30
    revenue_quality_score: int = 0  # 0-20
    industry_propensity: int = 0  # 0-10
    time_in_business_score: int = 0  # 0-5

    # Derived values
    industry_name: Optional[str] = None
    industry_confidence: float = 0.0
    time_in_business_months: Optional[int] = None
    estimated_monthly_revenue: Optional[int] = None

    # Revenue profile
    consistency_profile: Optional[str] = None
    quality_profile: Optional[str] = None

    # Flags
    is_nurture: bool = False
    nurture_reason: Optional[str] = None
    is_undersize: bool = False
    has_cash_flow_risk: bool = False
    needs_verification: bool = False

    # Final scores
    raw_total: int = 0  # Sum of raw scores (0-100)
    scaled_score: int = 0  # Scaled to 0-100 (same as raw for v4.0)

    # Details for explainability
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def fit_score(self) -> int:
        """Return the final FIT score (0-100)."""
        return self.scaled_score


class FITScorer:
    """Calculate FIT dimension scores for businesses.

    Version 4.0: Expanded to include revenue-based scoring.
    """

    # Maximum raw points for each component
    MAX_REVENUE_POINTS = 35
    MAX_CONSISTENCY_POINTS = 30
    MAX_QUALITY_POINTS = 20
    MAX_INDUSTRY_POINTS = 10
    MAX_TIB_POINTS = 5
    MAX_RAW_POINTS = 100  # Total

    def __init__(self) -> None:
        """Initialize the FIT scorer with configuration."""
        self._config = config.get_fit_components()
        self._tib_thresholds = config.get_tib_thresholds()
        self._revenue_config = config.scoring.get("fit_components", {}).get("estimated_revenue", {})
        self._consistency_config = config.scoring.get("fit_components", {}).get("revenue_consistency", {})
        self._quality_config = config.scoring.get("fit_components", {}).get("revenue_quality", {})

    def score(
        self,
        business_name: str,
        dba_name: str | None = None,
        formation_date: date | None = None,
        time_in_business_months: int | None = None,
        industry: str | None = None,
        estimated_monthly_revenue: int | None = None,
        employee_count: int | None = None,
    ) -> FITScoreResult:
        """Calculate FIT score for a business.

        Args:
            business_name: Legal business name
            dba_name: DBA/trade name if available
            formation_date: Date business was formed
            time_in_business_months: Pre-calculated months in business
            industry: Pre-classified industry (skips classification if provided)
            estimated_monthly_revenue: Known monthly revenue
            employee_count: Number of employees (for revenue estimation)

        Returns:
            FITScoreResult with all score components
        """
        result = FITScoreResult()

        # First, classify industry (needed for other scores)
        self._score_industry(result, business_name, dba_name, industry)

        # Estimate revenue if not provided
        if estimated_monthly_revenue is None and employee_count and result.industry_name:
            estimated_monthly_revenue = self._estimate_revenue(
                result.industry_name,
                employee_count,
            )

        result.estimated_monthly_revenue = estimated_monthly_revenue

        # Score all components
        self._score_estimated_revenue(result, estimated_monthly_revenue)
        self._score_revenue_consistency(result)
        self._score_revenue_quality(result)
        self._score_time_in_business(result, formation_date, time_in_business_months)

        # Calculate totals
        result.raw_total = (
            result.estimated_revenue_score +
            result.revenue_consistency_score +
            result.revenue_quality_score +
            result.industry_propensity +
            result.time_in_business_score
        )
        result.scaled_score = min(100, result.raw_total)  # Cap at 100

        # Set flags based on profiles
        self._set_flags(result)

        # Build details for explainability
        result.details = {
            "estimated_revenue": {
                "score": result.estimated_revenue_score,
                "max": self.MAX_REVENUE_POINTS,
                "monthly_revenue": result.estimated_monthly_revenue,
            },
            "revenue_consistency": {
                "score": result.revenue_consistency_score,
                "max": self.MAX_CONSISTENCY_POINTS,
                "profile": result.consistency_profile,
            },
            "revenue_quality": {
                "score": result.revenue_quality_score,
                "max": self.MAX_QUALITY_POINTS,
                "profile": result.quality_profile,
            },
            "industry_propensity": {
                "score": result.industry_propensity,
                "max": self.MAX_INDUSTRY_POINTS,
                "industry": result.industry_name,
                "confidence": result.industry_confidence,
            },
            "time_in_business": {
                "score": result.time_in_business_score,
                "max": self.MAX_TIB_POINTS,
                "months": result.time_in_business_months,
            },
            "scaling": {
                "raw_total": result.raw_total,
                "max_raw": self.MAX_RAW_POINTS,
                "scaled_score": result.scaled_score,
            },
            "flags": {
                "is_nurture": result.is_nurture,
                "nurture_reason": result.nurture_reason,
                "is_undersize": result.is_undersize,
                "has_cash_flow_risk": result.has_cash_flow_risk,
                "needs_verification": result.needs_verification,
            },
        }

        return result

    def _estimate_revenue(self, industry: str, employee_count: int) -> int:
        """Estimate monthly revenue from industry and employee count.

        Args:
            industry: Industry name
            employee_count: Number of employees

        Returns:
            Estimated monthly revenue
        """
        industry_lower = industry.lower().replace(" ", "_")
        rev_per_employee = INDUSTRY_REVENUE_MULTIPLIERS.get(industry_lower, 10000)
        return rev_per_employee * employee_count

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

    def _score_estimated_revenue(
        self,
        result: FITScoreResult,
        estimated_monthly_revenue: int | None,
    ) -> None:
        """Score estimated revenue tier.

        Args:
            result: FITScoreResult to update
            estimated_monthly_revenue: Estimated monthly revenue
        """
        if estimated_monthly_revenue is None:
            # Unknown revenue - give moderate score
            result.estimated_revenue_score = 15
            return

        # Check revenue tiers from config
        revenue_tiers = self._revenue_config.get("tiers", [])
        for tier in revenue_tiers:
            min_monthly = tier.get("min_monthly", 0)
            if estimated_monthly_revenue >= min_monthly:
                result.estimated_revenue_score = tier.get("points", 0)
                if tier.get("flag") == "undersize":
                    result.is_undersize = True
                return

        # Default scoring if no config
        if estimated_monthly_revenue >= 150000:
            result.estimated_revenue_score = 35
        elif estimated_monthly_revenue >= 100000:
            result.estimated_revenue_score = 30
        elif estimated_monthly_revenue >= 75000:
            result.estimated_revenue_score = 25
        elif estimated_monthly_revenue >= 50000:
            result.estimated_revenue_score = 20
        elif estimated_monthly_revenue >= 25000:
            result.estimated_revenue_score = 12
        else:
            result.estimated_revenue_score = 5
            result.is_undersize = True

    def _score_revenue_consistency(self, result: FITScoreResult) -> None:
        """Score revenue consistency based on industry.

        Args:
            result: FITScoreResult to update
        """
        if not result.industry_name:
            result.revenue_consistency_score = 15  # Unknown industry
            return

        industry_lower = result.industry_name.lower().replace(" ", "_")

        # Find matching profile
        for profile_name, profile_data in CONSISTENCY_PROFILES.items():
            if industry_lower in profile_data["industries"]:
                result.revenue_consistency_score = profile_data["points"]
                result.consistency_profile = profile_name
                return

        # Default to steady
        result.revenue_consistency_score = 15
        result.consistency_profile = "unknown"

    def _score_revenue_quality(self, result: FITScoreResult) -> None:
        """Score revenue quality (CC processing) based on industry.

        Args:
            result: FITScoreResult to update
        """
        if not result.industry_name:
            result.revenue_quality_score = 10  # Unknown industry
            return

        industry_lower = result.industry_name.lower().replace(" ", "_")

        # Find matching profile
        for profile_name, profile_data in QUALITY_PROFILES.items():
            if industry_lower in profile_data["industries"]:
                result.revenue_quality_score = profile_data["points"]
                result.quality_profile = profile_name
                return

        # Default to moderate
        result.revenue_quality_score = 10
        result.quality_profile = "unknown"

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

    def _set_flags(self, result: FITScoreResult) -> None:
        """Set additional flags based on scoring.

        Args:
            result: FITScoreResult to update
        """
        # Cash flow risk for highly lumpy industries
        if result.consistency_profile == "highly_lumpy":
            result.has_cash_flow_risk = True

        # Verification needed for very low CC industries
        if result.quality_profile == "very_low_cc":
            result.needs_verification = True

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
                - estimated_monthly_revenue (optional)
                - employee_count (optional)

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
                estimated_monthly_revenue=biz.get("estimated_monthly_revenue"),
                employee_count=biz.get("employee_count"),
            )
            results.append(result)
        return results


# Singleton instance
fit_scorer = FITScorer()
