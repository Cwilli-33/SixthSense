"""INTENT dimension scoring for MCA leads.

Version 4.0: Time-Weighted Intent Scoring
- Every Intent signal is time-weighted using exponential decay
- Different signal types have different decay rates
- UCC filings follow an optimal window curve (peak at 4-6 months)

Intent signals indicate whether a business might need or want capital:
- Growth signals (hiring, expansion, contracts)
- Refinance eligibility (UCC in optimal window)
- Operational signals (seasonal, equipment, inventory)
- Stress signals (liens, judgments)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from src.scoring.decay import DecayClass, DecayResult, decay_engine
from src.utils.config import config


class IntentSignalType(Enum):
    """Types of intent signals."""

    # Growth signals
    ACTIVE_HIRING_5PLUS = "active_hiring_5plus"
    ACTIVE_HIRING_2TO4 = "active_hiring_2to4"
    ACTIVE_HIRING_1 = "active_hiring_1"
    NEW_LOCATION = "new_location"
    FRANCHISE_EXPANSION = "franchise_expansion"
    CONTRACT_WIN = "contract_win"
    EQUIPMENT_PURCHASE = "equipment_purchase"
    EXPANSION_LANGUAGE = "expansion_language"

    # Refinance signals
    UCC_OPTIMAL_WINDOW = "ucc_optimal_window"
    UCC_EARLY_WINDOW = "ucc_early_window"
    UCC_LATE_WINDOW = "ucc_late_window"
    UCC_TERMINATION = "ucc_termination"
    MULTIPLE_MCA_UCCS = "multiple_mca_uccs"

    # Operational signals
    SEASONAL_PRE_PEAK = "seasonal_pre_peak"
    RENOVATION_ACTIVITY = "renovation_activity"
    INVENTORY_RESTOCKING = "inventory_restocking"
    FLEET_VEHICLE_NEEDS = "fleet_vehicle_needs"
    TECHNOLOGY_UPGRADE = "technology_upgrade"

    # Stress signals
    TAX_LIEN = "tax_lien"
    JUDGMENT_FILED = "judgment_filed"
    EMERGENCY_PROMOTIONS = "emergency_promotions"
    REDUCED_HOURS = "reduced_hours"
    NEGATIVE_REVIEW_SPIKE = "negative_review_spike"

    # General UCC signals
    UCC_MCA_LENDER = "ucc_mca_lender"  # UCC from known MCA lender
    UCC_GENERAL = "ucc_general"  # General UCC filing

    # SEC filing signals
    SEC_FINANCING = "sec_financing"  # SEC filing indicating financing activity
    SEC_8K_MATERIAL = "sec_8k_material"  # Material event disclosure


class IntentPathway(Enum):
    """Intent pathway tags for outreach messaging."""

    GROWTH = "growth"
    OPERATIONAL = "operational"
    REFINANCE = "refinance"
    STRESS = "stress"
    GENERAL = "general"


@dataclass
class IntentSignal:
    """Represents a detected intent signal."""

    signal_type: IntentSignalType
    signal_date: datetime
    base_points: int
    decay_class: DecayClass
    raw_data: dict[str, Any] = field(default_factory=dict)

    # For UCC signals
    ucc_months_old: Optional[float] = None


@dataclass
class DecayedSignal:
    """A signal with decay applied."""

    signal: IntentSignal
    decay_result: DecayResult
    effective_points: float


@dataclass
class INTENTScoreResult:
    """Result of INTENT dimension scoring."""

    # Final scores
    raw_total: float = 0.0  # Sum of base points
    time_weighted_total: float = 0.0  # Sum of decayed points
    scaled_score: int = 0  # Scaled to 0-100

    # Signal breakdown
    signals: list[DecayedSignal] = field(default_factory=list)
    signal_count: int = 0

    # Pathway determination
    pathway: IntentPathway = IntentPathway.GENERAL
    pathway_message: str = ""

    # Category scores
    growth_points: float = 0.0
    refinance_points: float = 0.0
    operational_points: float = 0.0
    stress_points: float = 0.0

    # Details for explainability
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def intent_score(self) -> int:
        """Return the final INTENT score (0-100)."""
        return self.scaled_score


# Signal configuration with base points and decay classes
SIGNAL_CONFIG = {
    # Growth signals (max 35 points)
    IntentSignalType.ACTIVE_HIRING_5PLUS: {"base_points": 20, "decay_class": DecayClass.RAPID, "category": "growth"},
    IntentSignalType.NEW_LOCATION: {"base_points": 20, "decay_class": DecayClass.STANDARD, "category": "growth"},
    IntentSignalType.FRANCHISE_EXPANSION: {"base_points": 18, "decay_class": DecayClass.STANDARD, "category": "growth"},
    IntentSignalType.CONTRACT_WIN: {"base_points": 15, "decay_class": DecayClass.STANDARD, "category": "growth"},
    IntentSignalType.ACTIVE_HIRING_2TO4: {"base_points": 12, "decay_class": DecayClass.RAPID, "category": "growth"},
    IntentSignalType.EQUIPMENT_PURCHASE: {"base_points": 12, "decay_class": DecayClass.STANDARD, "category": "growth"},
    IntentSignalType.EXPANSION_LANGUAGE: {"base_points": 10, "decay_class": DecayClass.RAPID, "category": "growth"},
    IntentSignalType.ACTIVE_HIRING_1: {"base_points": 5, "decay_class": DecayClass.RAPID, "category": "growth"},

    # Refinance signals (max 25 points)
    IntentSignalType.UCC_OPTIMAL_WINDOW: {"base_points": 25, "decay_class": DecayClass.EXTENDED, "category": "refinance"},
    IntentSignalType.UCC_TERMINATION: {"base_points": 20, "decay_class": DecayClass.EXTENDED, "category": "refinance"},
    IntentSignalType.UCC_LATE_WINDOW: {"base_points": 18, "decay_class": DecayClass.EXTENDED, "category": "refinance"},
    IntentSignalType.MULTIPLE_MCA_UCCS: {"base_points": 15, "decay_class": DecayClass.EXTENDED, "category": "refinance"},
    IntentSignalType.UCC_EARLY_WINDOW: {"base_points": 10, "decay_class": DecayClass.EXTENDED, "category": "refinance"},

    # Operational signals (max 25 points)
    IntentSignalType.SEASONAL_PRE_PEAK: {"base_points": 15, "decay_class": DecayClass.STANDARD, "category": "operational"},
    IntentSignalType.RENOVATION_ACTIVITY: {"base_points": 12, "decay_class": DecayClass.STANDARD, "category": "operational"},
    IntentSignalType.INVENTORY_RESTOCKING: {"base_points": 10, "decay_class": DecayClass.RAPID, "category": "operational"},
    IntentSignalType.FLEET_VEHICLE_NEEDS: {"base_points": 10, "decay_class": DecayClass.STANDARD, "category": "operational"},
    IntentSignalType.TECHNOLOGY_UPGRADE: {"base_points": 8, "decay_class": DecayClass.STANDARD, "category": "operational"},

    # Stress signals (max 15 points)
    IntentSignalType.TAX_LIEN: {"base_points": 12, "decay_class": DecayClass.EXTENDED, "category": "stress"},
    IntentSignalType.JUDGMENT_FILED: {"base_points": 10, "decay_class": DecayClass.EXTENDED, "category": "stress"},
    IntentSignalType.EMERGENCY_PROMOTIONS: {"base_points": 8, "decay_class": DecayClass.RAPID, "category": "stress"},
    IntentSignalType.REDUCED_HOURS: {"base_points": 8, "decay_class": DecayClass.RAPID, "category": "stress"},
    IntentSignalType.NEGATIVE_REVIEW_SPIKE: {"base_points": 5, "decay_class": DecayClass.RAPID, "category": "stress"},
}


class INTENTScorer:
    """Calculate time-weighted INTENT dimension scores."""

    MAX_RAW_POINTS = 100  # Maximum raw points for scaling

    def __init__(self) -> None:
        """Initialize the INTENT scorer with configuration."""
        self._intent_config = config.scoring.get("intent_signals", {})
        self._ucc_window_config = config.scoring.get("ucc_refinance_window", {}).get("windows", [])
        self._pathway_config = config.scoring.get("intent_pathways", {})
        self._signal_config = self._load_signal_config()

    def _load_signal_config(self) -> dict[IntentSignalType, dict]:
        """Load signal configuration from config or use defaults."""
        loaded_config = {}

        for signal_type in IntentSignalType:
            default = SIGNAL_CONFIG.get(signal_type, {"base_points": 0, "decay_class": DecayClass.STANDARD})

            # Try to find in config
            category = default.get("category", "growth")
            category_config = self._intent_config.get(category, {})
            signal_config = category_config.get(signal_type.value, {})

            loaded_config[signal_type] = {
                "base_points": signal_config.get("base_points", default["base_points"]),
                "decay_class": DecayClass(signal_config.get("decay_class", default["decay_class"].value)),
                "category": category,
            }

        return loaded_config

    def score(
        self,
        signals: list[IntentSignal],
        reference_date: datetime | None = None,
    ) -> INTENTScoreResult:
        """Calculate time-weighted INTENT score.

        Args:
            signals: List of detected intent signals
            reference_date: Reference date for decay calculation (defaults to now)

        Returns:
            INTENTScoreResult with all scores and breakdown
        """
        if reference_date is None:
            reference_date = datetime.now()

        result = INTENTScoreResult()
        result.signal_count = len(signals)

        if not signals:
            return result

        # Process each signal
        category_points = {"growth": 0.0, "refinance": 0.0, "operational": 0.0, "stress": 0.0}

        for signal in signals:
            decayed_signal = self._process_signal(signal, reference_date)
            result.signals.append(decayed_signal)
            result.raw_total += decayed_signal.signal.base_points
            result.time_weighted_total += decayed_signal.effective_points

            # Track category points
            config_entry = self._signal_config.get(signal.signal_type, {})
            category = config_entry.get("category", "growth")
            category_points[category] += decayed_signal.effective_points

        # Store category scores
        result.growth_points = category_points["growth"]
        result.refinance_points = category_points["refinance"]
        result.operational_points = category_points["operational"]
        result.stress_points = category_points["stress"]

        # Scale to 0-100
        result.scaled_score = self._scale_to_100(result.time_weighted_total)

        # Determine pathway
        result.pathway, result.pathway_message = self._determine_pathway(category_points)

        # Build details
        result.details = self._build_details(result, signals)

        return result

    def _process_signal(
        self,
        signal: IntentSignal,
        reference_date: datetime,
    ) -> DecayedSignal:
        """Process a single signal with decay.

        Args:
            signal: The intent signal
            reference_date: Reference date for decay

        Returns:
            DecayedSignal with decay applied
        """
        # Calculate signal age
        signal_age_days = decay_engine.calculate_signal_age(signal.signal_date, reference_date)

        # Get signal config
        config_entry = self._signal_config.get(signal.signal_type, {})
        base_points = signal.base_points or config_entry.get("base_points", 0)
        decay_class = signal.decay_class or config_entry.get("decay_class", DecayClass.STANDARD)

        # Handle UCC signals specially (use window curve)
        if signal.signal_type in [
            IntentSignalType.UCC_OPTIMAL_WINDOW,
            IntentSignalType.UCC_EARLY_WINDOW,
            IntentSignalType.UCC_LATE_WINDOW,
        ] and signal.ucc_months_old is not None:
            decay_result = self._apply_ucc_window_curve(base_points, signal.ucc_months_old)
        else:
            decay_result = decay_engine.apply_decay(base_points, signal_age_days, decay_class)

        return DecayedSignal(
            signal=signal,
            decay_result=decay_result,
            effective_points=decay_result.decayed_value,
        )

    def _apply_ucc_window_curve(
        self,
        base_points: float,
        ucc_months_old: float,
    ) -> DecayResult:
        """Apply UCC refinance window curve instead of simple decay.

        The curve peaks at 4-6 months when merchants feel payment burden.

        Args:
            base_points: Base point value
            ucc_months_old: Months since UCC filing

        Returns:
            DecayResult with window-adjusted value
        """
        # Find matching window
        propensity = 0.15  # Default for very old UCCs
        for window in self._ucc_window_config:
            min_months = window.get("min_months", 0)
            max_months = window.get("max_months", 999)
            if min_months <= ucc_months_old < max_months:
                propensity = window.get("propensity", 0.15)
                break

        decayed_value = base_points * propensity

        return DecayResult(
            base_value=base_points,
            decayed_value=decayed_value,
            decay_factor=propensity,
            signal_age_days=ucc_months_old * 30,  # Approximate
            half_life_days=60,  # Extended decay
            decay_class=DecayClass.EXTENDED,
            is_expired=propensity < 0.2,
        )

    def _determine_pathway(
        self,
        category_points: dict[str, float],
    ) -> tuple[IntentPathway, str]:
        """Determine the dominant intent pathway.

        Args:
            category_points: Points by category

        Returns:
            Tuple of (IntentPathway, message)
        """
        # Find dominant category
        max_category = max(category_points, key=category_points.get)
        max_points = category_points[max_category]

        if max_points == 0:
            pathway = IntentPathway.GENERAL
        else:
            pathway = IntentPathway(max_category)

        # Get message from config
        pathway_entry = self._pathway_config.get(pathway.value, {})
        message = pathway_entry.get("message", "Did you know about MCA?")

        return pathway, message

    def _scale_to_100(self, time_weighted_total: float) -> int:
        """Scale time-weighted total to 0-100.

        Args:
            time_weighted_total: Sum of time-weighted signal points

        Returns:
            Scaled score (0-100)
        """
        if self.MAX_RAW_POINTS == 0:
            return 0
        scaled = (time_weighted_total / self.MAX_RAW_POINTS) * 100
        return min(100, max(0, round(scaled)))

    def _build_details(
        self,
        result: INTENTScoreResult,
        signals: list[IntentSignal],
    ) -> dict[str, Any]:
        """Build details dictionary for explainability."""
        return {
            "signal_count": len(signals),
            "raw_total": result.raw_total,
            "time_weighted_total": result.time_weighted_total,
            "scaled_score": result.scaled_score,
            "pathway": result.pathway.value,
            "pathway_message": result.pathway_message,
            "category_breakdown": {
                "growth": result.growth_points,
                "refinance": result.refinance_points,
                "operational": result.operational_points,
                "stress": result.stress_points,
            },
            "signals": [
                {
                    "type": ds.signal.signal_type.value,
                    "base_points": ds.signal.base_points,
                    "effective_points": round(ds.effective_points, 2),
                    "decay_factor": round(ds.decay_result.decay_factor, 3),
                    "signal_age_days": round(ds.decay_result.signal_age_days, 1),
                }
                for ds in result.signals
            ],
        }

    def create_signal_from_ucc(
        self,
        ucc_filing_date: datetime,
        is_mca_related: bool = True,
        ucc_months_old: float | None = None,
    ) -> IntentSignal | None:
        """Create an intent signal from a UCC filing.

        Args:
            ucc_filing_date: Date of the UCC filing
            is_mca_related: Whether the UCC is MCA-related
            ucc_months_old: Months since filing (calculated if not provided)

        Returns:
            IntentSignal if applicable, None otherwise
        """
        if not is_mca_related:
            return None

        # Calculate months old if not provided
        if ucc_months_old is None:
            delta = datetime.now() - ucc_filing_date
            ucc_months_old = delta.days / 30.0

        # Determine signal type based on age
        if 4 <= ucc_months_old < 6:
            signal_type = IntentSignalType.UCC_OPTIMAL_WINDOW
            base_points = 25
        elif 3 <= ucc_months_old < 4:
            signal_type = IntentSignalType.UCC_EARLY_WINDOW
            base_points = 10
        elif 6 <= ucc_months_old < 9:
            signal_type = IntentSignalType.UCC_LATE_WINDOW
            base_points = 18
        else:
            # Outside actionable window
            return None

        return IntentSignal(
            signal_type=signal_type,
            signal_date=ucc_filing_date,
            base_points=base_points,
            decay_class=DecayClass.EXTENDED,
            ucc_months_old=ucc_months_old,
        )


# Singleton instance
intent_scorer = INTENTScorer()
