"""Tests for FIT scoring."""

import pytest
from datetime import date
from dateutil.relativedelta import relativedelta

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scoring.fit import FITScorer


class TestFITScorer:
    """Tests for FIT dimension scoring."""

    @pytest.fixture
    def scorer(self) -> FITScorer:
        """Create scorer instance."""
        return FITScorer()

    # Industry scoring tests
    def test_score_high_propensity_industry(self, scorer: FITScorer) -> None:
        """Test scoring for high propensity industry."""
        result = scorer.score(
            business_name="Mario's Restaurant LLC",
            time_in_business_months=60,
        )
        assert result.industry_propensity == 10
        assert result.industry_name == "restaurants"

    def test_score_moderate_propensity_industry(self, scorer: FITScorer) -> None:
        """Test scoring for moderate propensity industry."""
        result = scorer.score(
            business_name="ABC Manufacturing Inc",
            time_in_business_months=60,
        )
        assert result.industry_propensity == 5
        assert result.industry_name == "manufacturing"

    def test_score_low_propensity_industry(self, scorer: FITScorer) -> None:
        """Test scoring for low propensity industry."""
        result = scorer.score(
            business_name="Tech Consulting Group LLC",
            time_in_business_months=60,
        )
        assert result.industry_propensity <= 2

    def test_score_unknown_industry(self, scorer: FITScorer) -> None:
        """Test scoring for unclassified business."""
        result = scorer.score(
            business_name="XYZ Holdings LLC",
            time_in_business_months=60,
        )
        assert result.industry_propensity == 1
        assert result.industry_name == "other"

    def test_score_pre_classified_industry(self, scorer: FITScorer) -> None:
        """Test scoring with pre-classified industry."""
        result = scorer.score(
            business_name="ABC Holdings LLC",  # Would be "other"
            industry="restaurants",  # Override
            time_in_business_months=60,
        )
        assert result.industry_propensity == 10
        assert result.industry_name == "restaurants"

    # Time in business scoring tests
    def test_tib_5_plus_years(self, scorer: FITScorer) -> None:
        """Test TIB scoring for 5+ years."""
        result = scorer.score(
            business_name="Test Business LLC",
            time_in_business_months=60,  # 5 years
        )
        assert result.time_in_business_score == 5

    def test_tib_3_to_5_years(self, scorer: FITScorer) -> None:
        """Test TIB scoring for 3-5 years."""
        result = scorer.score(
            business_name="Test Business LLC",
            time_in_business_months=42,  # 3.5 years
        )
        assert result.time_in_business_score == 4

    def test_tib_2_to_3_years(self, scorer: FITScorer) -> None:
        """Test TIB scoring for 2-3 years."""
        result = scorer.score(
            business_name="Test Business LLC",
            time_in_business_months=30,  # 2.5 years
        )
        assert result.time_in_business_score == 3

    def test_tib_1_to_2_years(self, scorer: FITScorer) -> None:
        """Test TIB scoring for 1-2 years."""
        result = scorer.score(
            business_name="Test Business LLC",
            time_in_business_months=18,  # 1.5 years
        )
        assert result.time_in_business_score == 2

    def test_tib_under_1_year_nurture(self, scorer: FITScorer) -> None:
        """Test TIB scoring for <1 year (nurture flag)."""
        result = scorer.score(
            business_name="Test Business LLC",
            time_in_business_months=6,  # 6 months
        )
        assert result.time_in_business_score == 0
        assert result.is_nurture is True
        assert result.nurture_reason is not None

    def test_tib_from_formation_date(self, scorer: FITScorer) -> None:
        """Test TIB calculation from formation date."""
        # 3 years ago
        formation_date = date.today() - relativedelta(years=3)

        result = scorer.score(
            business_name="Test Business LLC",
            formation_date=formation_date,
        )
        assert result.time_in_business_months >= 36
        assert result.time_in_business_score >= 3

    def test_tib_unknown(self, scorer: FITScorer) -> None:
        """Test TIB scoring when unknown."""
        result = scorer.score(
            business_name="Test Business LLC",
            # No TIB or formation date
        )
        assert result.time_in_business_months is None
        assert result.time_in_business_score == 2  # Middle score for unknown

    # Composite FIT score tests
    def test_maximum_fit_score(self, scorer: FITScorer) -> None:
        """Test maximum possible FIT score."""
        result = scorer.score(
            business_name="Best Restaurant LLC",  # 10 industry points
            time_in_business_months=120,  # 5 TIB points
        )
        assert result.raw_total == 15
        assert result.scaled_score == 100

    def test_minimum_fit_score(self, scorer: FITScorer) -> None:
        """Test minimum FIT score."""
        result = scorer.score(
            business_name="XYZ Holdings LLC",  # 1 industry point
            time_in_business_months=3,  # 0 TIB points (nurture)
        )
        assert result.raw_total == 1
        assert result.scaled_score == 7  # 1/15 * 100 rounded

    def test_fit_score_scaling(self, scorer: FITScorer) -> None:
        """Test FIT score scaling to 0-100."""
        # 10 industry + 3 TIB = 13 raw
        # 13/15 * 100 = 86.67 -> 87
        result = scorer.score(
            business_name="ABC Trucking LLC",  # 10 points
            time_in_business_months=30,  # 3 points (2-3 years)
        )
        assert result.raw_total == 13
        assert result.scaled_score == 87

    # Details/explainability tests
    def test_score_details(self, scorer: FITScorer) -> None:
        """Test score breakdown details."""
        result = scorer.score(
            business_name="Test Restaurant LLC",
            time_in_business_months=60,
        )

        assert "industry_propensity" in result.details
        assert "time_in_business" in result.details
        assert "scaling" in result.details

        assert result.details["industry_propensity"]["raw_score"] == 10
        assert result.details["time_in_business"]["raw_score"] == 5

    def test_fit_score_property(self, scorer: FITScorer) -> None:
        """Test fit_score property."""
        result = scorer.score(
            business_name="Test LLC",
            time_in_business_months=60,
        )
        assert result.fit_score == result.scaled_score

    # Batch scoring tests
    def test_score_batch(self, scorer: FITScorer) -> None:
        """Test batch scoring."""
        businesses = [
            {"business_name": "Restaurant A LLC", "time_in_business_months": 60},
            {"business_name": "Trucking B Inc", "time_in_business_months": 36},
            {"business_name": "Consulting C LLC", "time_in_business_months": 24},
        ]

        results = scorer.score_batch(businesses)

        assert len(results) == 3
        assert results[0].industry_name == "restaurants"
        assert results[1].industry_name == "trucking"
        assert results[2].industry_name == "consulting"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
