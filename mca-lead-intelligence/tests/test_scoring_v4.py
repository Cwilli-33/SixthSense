"""Tests for Scoring Model v4.0.

Covers:
- Decay engine (exponential decay with signal-specific half-lives)
- Freshness calculator (HOT through EXPIRED flags)
- INTENT scorer (time-weighted intent signals)
- TIMING scorer (seasonal and recency scoring)
- Composite scorer (v4.0 formula integration)
"""

import pytest
import math
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scoring.decay import DecayEngine, DecayClass, DecayResult, decay_engine
from src.scoring.freshness import FreshnessCalculator, FreshnessFlag, FreshnessResult
from src.scoring.intent import (
    INTENTScorer,
    IntentSignal,
    IntentSignalType,
    IntentPathway,
    intent_scorer,
)
from src.scoring.timing import TIMINGScorer, timing_scorer
from src.scoring.composite import CompositeScorer, CompositeScoreResult, composite_scorer


class TestDecayEngine:
    """Tests for exponential decay engine."""

    @pytest.fixture
    def engine(self) -> DecayEngine:
        """Create decay engine instance."""
        return DecayEngine()

    def test_decay_classes_defined(self, engine: DecayEngine) -> None:
        """Test that all decay classes are defined."""
        assert DecayClass.RAPID is not None
        assert DecayClass.STANDARD is not None
        assert DecayClass.EXTENDED is not None
        assert DecayClass.STRUCTURAL is not None

    def test_lambda_values(self, engine: DecayEngine) -> None:
        """Test lambda values for decay classes."""
        lambdas = engine._lambdas

        # RAPID should have highest lambda (fastest decay)
        assert lambdas[DecayClass.RAPID] > lambdas[DecayClass.STANDARD]
        assert lambdas[DecayClass.STANDARD] > lambdas[DecayClass.EXTENDED]
        assert lambdas[DecayClass.EXTENDED] > lambdas[DecayClass.STRUCTURAL]

    def test_decay_at_zero_days(self, engine: DecayEngine) -> None:
        """Test decay factor is 1.0 at time zero."""
        factor = engine.calculate_decay_factor(0, DecayClass.STANDARD)
        assert factor == pytest.approx(1.0)

    def test_decay_at_half_life(self, engine: DecayEngine) -> None:
        """Test decay factor is ~0.5 at half-life."""
        # STANDARD has 21-day half-life
        factor = engine.calculate_decay_factor(21, DecayClass.STANDARD)
        assert factor == pytest.approx(0.5, rel=0.05)

    def test_decay_approaches_zero(self, engine: DecayEngine) -> None:
        """Test decay approaches zero at long times."""
        # After ~5 half-lives, should be very small
        factor = engine.calculate_decay_factor(105, DecayClass.STANDARD)  # 5 * 21 days
        assert factor < 0.1

    def test_rapid_decay_faster_than_standard(self, engine: DecayEngine) -> None:
        """Test RAPID decays faster than STANDARD."""
        days = 14

        rapid_factor = engine.calculate_decay_factor(days, DecayClass.RAPID)
        standard_factor = engine.calculate_decay_factor(days, DecayClass.STANDARD)

        assert rapid_factor < standard_factor

    def test_structural_decay_slower_than_extended(self, engine: DecayEngine) -> None:
        """Test STRUCTURAL decays slower than EXTENDED."""
        days = 60

        structural_factor = engine.calculate_decay_factor(days, DecayClass.STRUCTURAL)
        extended_factor = engine.calculate_decay_factor(days, DecayClass.EXTENDED)

        assert structural_factor > extended_factor

    def test_calculate_decay_returns_result(self, engine: DecayEngine) -> None:
        """Test calculate_decay returns DecayResult."""
        signal_date = datetime.now() - timedelta(days=10)
        result = engine.calculate_decay(signal_date, DecayClass.STANDARD)

        assert isinstance(result, DecayResult)
        assert result.decay_factor > 0
        assert result.decay_factor <= 1
        assert result.age_days == pytest.approx(10, abs=1)

    def test_apply_decay_to_value(self, engine: DecayEngine) -> None:
        """Test applying decay to a base value."""
        base_value = 100
        signal_date = datetime.now() - timedelta(days=21)  # 1 half-life

        result = engine.calculate_decay(signal_date, DecayClass.STANDARD, base_value)

        assert result.original_value == 100
        assert result.decayed_value == pytest.approx(50, rel=0.1)

    def test_decay_factor_bounded(self, engine: DecayEngine) -> None:
        """Test decay factor stays in [0, 1] bounds."""
        # Very old signal
        factor = engine.calculate_decay_factor(1000, DecayClass.RAPID)
        assert 0 <= factor <= 1

        # Future date (negative age)
        factor = engine.calculate_decay_factor(-10, DecayClass.STANDARD)
        assert 0 <= factor <= 1


class TestFreshnessCalculator:
    """Tests for lead freshness calculator."""

    @pytest.fixture
    def calculator(self) -> FreshnessCalculator:
        """Create freshness calculator instance."""
        return FreshnessCalculator()

    def test_freshness_flags_defined(self) -> None:
        """Test all freshness flags are defined."""
        assert FreshnessFlag.HOT is not None
        assert FreshnessFlag.WARM is not None
        assert FreshnessFlag.RECENT is not None
        assert FreshnessFlag.AGING is not None
        assert FreshnessFlag.STALE is not None
        assert FreshnessFlag.EXPIRED is not None

    def test_hot_lead(self, calculator: FreshnessCalculator) -> None:
        """Test HOT lead detection (< 48 hours)."""
        signal_date = datetime.now() - timedelta(hours=24)
        result = calculator.calculate_freshness(signal_date)

        assert result.flag == FreshnessFlag.HOT
        assert result.multiplier == pytest.approx(1.30, rel=0.01)
        assert "🔥" in result.label

    def test_warm_lead(self, calculator: FreshnessCalculator) -> None:
        """Test WARM lead detection (48h - 7 days)."""
        signal_date = datetime.now() - timedelta(days=4)
        result = calculator.calculate_freshness(signal_date)

        assert result.flag == FreshnessFlag.WARM
        assert result.multiplier == pytest.approx(1.15, rel=0.01)

    def test_recent_lead(self, calculator: FreshnessCalculator) -> None:
        """Test RECENT lead detection (7-14 days)."""
        signal_date = datetime.now() - timedelta(days=10)
        result = calculator.calculate_freshness(signal_date)

        assert result.flag == FreshnessFlag.RECENT
        assert result.multiplier == pytest.approx(1.00, rel=0.01)

    def test_aging_lead(self, calculator: FreshnessCalculator) -> None:
        """Test AGING lead detection (14-30 days)."""
        signal_date = datetime.now() - timedelta(days=21)
        result = calculator.calculate_freshness(signal_date)

        assert result.flag == FreshnessFlag.AGING
        assert result.multiplier == pytest.approx(0.80, rel=0.01)

    def test_stale_lead(self, calculator: FreshnessCalculator) -> None:
        """Test STALE lead detection (30-60 days)."""
        signal_date = datetime.now() - timedelta(days=45)
        result = calculator.calculate_freshness(signal_date)

        assert result.flag == FreshnessFlag.STALE
        assert result.multiplier == pytest.approx(0.50, rel=0.01)

    def test_expired_lead(self, calculator: FreshnessCalculator) -> None:
        """Test EXPIRED lead detection (> 60 days)."""
        signal_date = datetime.now() - timedelta(days=90)
        result = calculator.calculate_freshness(signal_date)

        assert result.flag == FreshnessFlag.EXPIRED
        assert result.multiplier == pytest.approx(0.10, rel=0.01)
        assert "∅" in result.label

    def test_freshness_result_properties(self, calculator: FreshnessCalculator) -> None:
        """Test FreshnessResult properties."""
        signal_date = datetime.now() - timedelta(days=3)
        result = calculator.calculate_freshness(signal_date)

        assert isinstance(result, FreshnessResult)
        assert result.age_hours > 0
        assert result.flag is not None
        assert result.multiplier > 0
        assert result.label != ""


class TestINTENTScorer:
    """Tests for INTENT dimension scorer."""

    @pytest.fixture
    def scorer(self) -> INTENTScorer:
        """Create INTENT scorer instance."""
        return INTENTScorer()

    def test_intent_signal_types_defined(self) -> None:
        """Test intent signal types are defined."""
        # Growth signals
        assert IntentSignalType.ACTIVE_HIRING_5PLUS is not None
        assert IntentSignalType.NEW_LOCATION is not None

        # Refinance signals
        assert IntentSignalType.UCC_MCA_LENDER is not None
        assert IntentSignalType.UCC_OPTIMAL_WINDOW is not None

        # Stress signals
        assert IntentSignalType.TAX_LIEN is not None

    def test_intent_pathways_defined(self) -> None:
        """Test intent pathways are defined."""
        assert IntentPathway.GROWTH is not None
        assert IntentPathway.REFINANCE is not None
        assert IntentPathway.STRESS is not None
        assert IntentPathway.OPERATIONAL is not None

    def test_intent_signal_creation(self) -> None:
        """Test IntentSignal dataclass creation."""
        signal = IntentSignal(
            signal_type=IntentSignalType.ACTIVE_HIRING_5PLUS,
            signal_date=datetime.now(),
            base_points=85,
            decay_class=DecayClass.RAPID,
        )

        assert signal.signal_type == IntentSignalType.ACTIVE_HIRING_5PLUS
        assert signal.base_points == 85

    def test_score_with_mca_ucc(self, scorer: INTENTScorer) -> None:
        """Test scoring with MCA-related UCC signal."""
        signals = [
            IntentSignal(
                signal_type=IntentSignalType.UCC_MCA_LENDER,
                signal_date=datetime.now() - timedelta(days=7),
                base_points=90,
                decay_class=DecayClass.STANDARD,
            )
        ]

        result = scorer.score(signals)

        assert result.scaled_score > 0
        assert result.raw_total == 90
        assert result.time_weighted_total < 90  # Due to decay

    def test_score_multiple_signals(self, scorer: INTENTScorer) -> None:
        """Test scoring with multiple signals."""
        signals = [
            IntentSignal(
                signal_type=IntentSignalType.ACTIVE_HIRING_5PLUS,
                signal_date=datetime.now(),
                base_points=85,
                decay_class=DecayClass.RAPID,
            ),
            IntentSignal(
                signal_type=IntentSignalType.UCC_MCA_LENDER,
                signal_date=datetime.now() - timedelta(days=5),
                base_points=90,
                decay_class=DecayClass.STANDARD,
            ),
        ]

        result = scorer.score(signals)

        assert result.raw_total == 175  # 85 + 90
        assert result.signals_count == 2

    def test_empty_signals(self, scorer: INTENTScorer) -> None:
        """Test scoring with no signals."""
        result = scorer.score([])

        assert result.scaled_score == 0
        assert result.raw_total == 0

    def test_ucc_refinance_window(self, scorer: INTENTScorer) -> None:
        """Test UCC refinance window curve scoring."""
        # Optimal window is 4-6 months
        result = scorer.calculate_ucc_refinance_score(5.0)  # 5 months old

        assert result > 0
        assert result <= 100  # Max at optimal window


class TestTIMINGScorer:
    """Tests for TIMING dimension scorer."""

    @pytest.fixture
    def scorer(self) -> TIMINGScorer:
        """Create TIMING scorer instance."""
        return TIMINGScorer()

    def test_seasonal_scoring(self, scorer: TIMINGScorer) -> None:
        """Test seasonal scoring."""
        result = scorer.score()

        assert hasattr(result, "seasonal_score")
        assert 0 <= result.seasonal_score <= 100

    def test_recency_scoring(self, scorer: TIMINGScorer) -> None:
        """Test recency scoring based on signal age."""
        signal_date = datetime.now() - timedelta(days=5)
        result = scorer.score(latest_signal_date=signal_date)

        assert hasattr(result, "recency_score")
        assert result.recency_score > 0


class TestCompositeScorer:
    """Tests for composite v4.0 scorer."""

    @pytest.fixture
    def scorer(self) -> CompositeScorer:
        """Create composite scorer instance."""
        return CompositeScorer()

    def test_v4_weights(self, scorer: CompositeScorer) -> None:
        """Test v4.0 scoring weights."""
        # Should be FIT 40%, INTENT 40%, TIMING 20%
        weights = scorer.get_weights()

        assert weights["fit"] == pytest.approx(0.40, rel=0.01)
        assert weights["intent"] == pytest.approx(0.40, rel=0.01)
        assert weights["timing"] == pytest.approx(0.20, rel=0.01)

    def test_score_returns_result(self, scorer: CompositeScorer) -> None:
        """Test score method returns CompositeScoreResult."""
        result = scorer.score(
            business_name="Test Business LLC",
        )

        assert isinstance(result, CompositeScoreResult)
        assert hasattr(result, "fit_score")
        assert hasattr(result, "intent_score")
        assert hasattr(result, "timing_score")
        assert hasattr(result, "composite_score")
        assert hasattr(result, "priority_level")

    def test_score_range(self, scorer: CompositeScorer) -> None:
        """Test scores are in valid range."""
        result = scorer.score(
            business_name="Test Business LLC",
            is_mca_related=True,
        )

        assert 0 <= result.fit_score <= 100
        assert 0 <= result.intent_score <= 100
        assert 0 <= result.timing_score <= 100
        assert 0 <= result.composite_score <= 130  # Can exceed 100 with HOT multiplier

    def test_mca_related_boosts_score(self, scorer: CompositeScorer) -> None:
        """Test that MCA-related signals boost score."""
        non_mca_result = scorer.score(
            business_name="Test Business LLC",
            is_mca_related=False,
        )

        mca_result = scorer.score(
            business_name="Test Business LLC",
            is_mca_related=True,
        )

        assert mca_result.intent_score >= non_mca_result.intent_score

    def test_priority_level_assignment(self, scorer: CompositeScorer) -> None:
        """Test priority level assignment."""
        result = scorer.score(
            business_name="Test Business LLC",
        )

        assert result.priority_level in ["A", "B", "C", "D", "F"]

    def test_freshness_multiplier_applied(self, scorer: CompositeScorer) -> None:
        """Test freshness multiplier is applied to final score."""
        from src.models.signal import SignalCreate

        # Fresh signal (< 48 hours)
        fresh_signal = SignalCreate(
            signal_type="UCC",
            business_identifier="test",
            business_name="Test LLC",
            signal_date=datetime.now() - timedelta(hours=12),
            source="FL_SOS",
            state="FL",
        )

        result = scorer.score(
            business_name="Test LLC",
            signal=fresh_signal,
            is_mca_related=True,
        )

        # HOT leads should have multiplier > 1.0
        assert result.freshness_multiplier == pytest.approx(1.30, rel=0.05)


class TestScoringIntegration:
    """Integration tests for the full scoring system."""

    def test_singleton_scorers_exist(self) -> None:
        """Test singleton scorer instances exist."""
        assert decay_engine is not None
        assert intent_scorer is not None
        assert timing_scorer is not None
        assert composite_scorer is not None

    def test_full_scoring_flow(self) -> None:
        """Test complete scoring flow."""
        from src.models.signal import SignalCreate

        # Create a signal
        signal = SignalCreate(
            signal_type="UCC",
            business_identifier="UCC:FL:123456",
            business_name="Test Restaurant LLC",
            signal_date=datetime.now() - timedelta(days=3),
            source="FL_SOS",
            state="FL",
            raw_data={"secured_party": "OnDeck Capital"},
        )

        # Build intent signals
        intent_signals = [
            IntentSignal(
                signal_type=IntentSignalType.UCC_MCA_LENDER,
                signal_date=signal.signal_date,
                base_points=90,
                decay_class=DecayClass.STANDARD,
            )
        ]

        # Score
        result = composite_scorer.score(
            business_name=signal.business_name,
            signal=signal,
            is_mca_related=True,
            mca_lender="OnDeck Capital",
            intent_signals=intent_signals,
            state="FL",
        )

        # Verify all scores present
        assert result.fit_score > 0
        assert result.intent_score > 0
        assert result.timing_score >= 0
        assert result.composite_score > 0
        assert result.priority_level in ["A", "B", "C", "D", "F"]

    def test_decay_affects_intent_score(self) -> None:
        """Test that signal age affects INTENT score through decay."""
        # Recent signal
        recent_signals = [
            IntentSignal(
                signal_type=IntentSignalType.UCC_MCA_LENDER,
                signal_date=datetime.now(),
                base_points=90,
                decay_class=DecayClass.STANDARD,
            )
        ]

        # Old signal
        old_signals = [
            IntentSignal(
                signal_type=IntentSignalType.UCC_MCA_LENDER,
                signal_date=datetime.now() - timedelta(days=60),
                base_points=90,
                decay_class=DecayClass.STANDARD,
            )
        ]

        recent_result = intent_scorer.score(recent_signals)
        old_result = intent_scorer.score(old_signals)

        # Recent should have higher time-weighted score
        assert recent_result.time_weighted_total > old_result.time_weighted_total


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
