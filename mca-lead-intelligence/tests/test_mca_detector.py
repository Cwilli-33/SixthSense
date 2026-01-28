"""Tests for MCA detection logic."""

import pytest
from datetime import datetime

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.harvesters.mca_detector import MCADetector, MCADetectionResult


class TestMCADetector:
    """Tests for MCA lender detection."""

    @pytest.fixture
    def detector(self) -> MCADetector:
        """Create detector instance."""
        return MCADetector()

    def test_detect_known_lender_ondeck(self, detector: MCADetector) -> None:
        """Test detection of OnDeck Capital."""
        result = detector.detect(
            secured_party="OnDeck Capital Inc",
            collateral_description="All assets",
        )
        assert result.is_mca_related is True
        assert result.lender_match is not None
        assert "ondeck" in result.lender_match.lower()
        assert result.confidence >= 0.9

    def test_detect_known_lender_credibly(self, detector: MCADetector) -> None:
        """Test detection of Credibly."""
        result = detector.detect(
            secured_party="Credibly Inc",
            collateral_description="All accounts receivable",
        )
        assert result.is_mca_related is True
        assert result.lender_match is not None
        assert "credibly" in result.lender_match.lower()

    def test_detect_known_lender_rapid_finance(self, detector: MCADetector) -> None:
        """Test detection of Rapid Finance."""
        result = detector.detect(
            secured_party="Rapid Capital Funding LLC",
            collateral_description="Future receivables",
        )
        assert result.is_mca_related is True

    def test_detect_pattern_merchant_cash(self, detector: MCADetector) -> None:
        """Test detection via 'Merchant Cash' pattern."""
        result = detector.detect(
            secured_party="ABC Merchant Cash Advance LLC",
            collateral_description="All assets",
        )
        assert result.is_mca_related is True
        assert result.pattern_match is not None

    def test_detect_pattern_future_receivables(self, detector: MCADetector) -> None:
        """Test detection via 'Future Receivables' in collateral."""
        result = detector.detect(
            secured_party="Unknown Lender LLC",
            collateral_description="All future receivables and credit card receipts",
        )
        # Future receivables alone indicates MCA
        assert result.confidence >= 0.5

    def test_detect_all_assets_collateral(self, detector: MCADetector) -> None:
        """Test detection of all-assets collateral pattern."""
        result = detector.detect(
            secured_party="Generic Funding Co",
            collateral_description="All assets, inventory, and accounts",
        )
        assert result.is_mca_related is True
        assert "All-assets collateral" in result.reasons

    def test_exclusion_real_estate(self, detector: MCADetector) -> None:
        """Test that real estate collateral is excluded."""
        result = detector.detect(
            secured_party="Some Bank",
            collateral_description="Real estate located at 123 Main St",
        )
        assert result.is_mca_related is False
        assert result.exclusion_match is not None

    def test_exclusion_vehicle(self, detector: MCADetector) -> None:
        """Test that vehicle collateral is excluded."""
        result = detector.detect(
            secured_party="Auto Finance Co",
            collateral_description="2024 Ford F-150 motor vehicle VIN 12345",
        )
        assert result.is_mca_related is False

    def test_non_mca_traditional_bank(self, detector: MCADetector) -> None:
        """Test that traditional bank loans are not flagged as MCA."""
        result = detector.detect(
            secured_party="Wells Fargo Bank NA",
            collateral_description="Equipment: CNC Machine Model XYZ",
        )
        # Should not be flagged as MCA unless all-assets
        assert result.lender_match is None

    def test_refinance_score_optimal_window(self, detector: MCADetector) -> None:
        """Test refinance scoring for optimal 4-5 month window."""
        # Filing from 4.5 months ago
        from datetime import timedelta
        filing_date = datetime.now() - timedelta(days=135)  # ~4.5 months

        result = detector.detect(
            secured_party="OnDeck Capital",
            collateral_description="All assets",
            filing_date=filing_date,
        )
        assert result.refinance_score > 0
        # Optimal window should give highest points

    def test_refinance_score_by_age(self, detector: MCADetector) -> None:
        """Test refinance score lookup by age."""
        # 4-5 months (optimal)
        score, window = detector.get_refinance_score_for_age(4)
        assert score == 15
        assert window == "optimal"

        # 5-6 months (strong)
        score, window = detector.get_refinance_score_for_age(5)
        assert score == 12
        assert window == "strong"

        # 6-7 months (good)
        score, window = detector.get_refinance_score_for_age(6)
        assert score == 8
        assert window == "good"

    def test_case_insensitive_matching(self, detector: MCADetector) -> None:
        """Test that matching is case-insensitive."""
        result = detector.detect(
            secured_party="ONDECK CAPITAL INC",
            collateral_description="ALL ASSETS",
        )
        assert result.is_mca_related is True

        result = detector.detect(
            secured_party="ondeck capital inc",
            collateral_description="all assets",
        )
        assert result.is_mca_related is True

    def test_empty_inputs(self, detector: MCADetector) -> None:
        """Test handling of empty inputs."""
        result = detector.detect(
            secured_party="",
            collateral_description="",
        )
        assert result.is_mca_related is False
        assert result.confidence == 0.0

    def test_none_inputs(self, detector: MCADetector) -> None:
        """Test handling of None inputs."""
        result = detector.detect(
            secured_party=None,
            collateral_description=None,
        )
        assert result.is_mca_related is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
