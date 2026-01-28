"""Tests for Florida UCC Harvester."""

import pytest
from datetime import datetime
from pathlib import Path

import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.harvesters.ucc import FloridaUCCHarvester
from src.models.signal import SignalType


class TestFloridaUCCHarvester:
    """Tests for Florida UCC harvester."""

    @pytest.fixture
    def harvester(self) -> FloridaUCCHarvester:
        """Create harvester instance."""
        return FloridaUCCHarvester()

    @pytest.fixture
    def sample_csv_path(self) -> Path:
        """Get path to sample CSV file."""
        return Path(__file__).parent.parent / "data" / "sample_ucc_filings.csv"

    def test_source_name(self, harvester: FloridaUCCHarvester) -> None:
        """Test source name."""
        assert harvester.get_source_name() == "FL_SOS"

    def test_state(self, harvester: FloridaUCCHarvester) -> None:
        """Test state code."""
        assert harvester.get_state() == "FL"

    def test_supported_signal_types(self, harvester: FloridaUCCHarvester) -> None:
        """Test supported signal types."""
        types = harvester.get_supported_signal_types()
        assert SignalType.UCC_FILING in types
        assert SignalType.UCC_TERMINATION in types
        assert SignalType.UCC_AMENDMENT in types

    def test_harvest_from_csv(
        self,
        harvester: FloridaUCCHarvester,
        sample_csv_path: Path,
    ) -> None:
        """Test harvesting from CSV file."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        signals = list(harvester.harvest(file_path=str(sample_csv_path)))

        assert len(signals) > 0

        # Check first signal
        first = signals[0]
        assert first.source == "FL_SOS"
        assert first.state == "FL"
        assert first.business_name != ""
        assert first.signal_date is not None

    def test_harvest_detects_mca_lenders(
        self,
        harvester: FloridaUCCHarvester,
        sample_csv_path: Path,
    ) -> None:
        """Test that MCA lenders are detected."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        signals = list(harvester.harvest(file_path=str(sample_csv_path)))

        mca_signals = [
            s for s in signals
            if s.metadata_.is_mca_related
        ]

        assert len(mca_signals) > 0

        # Check that known MCA lenders are detected
        lender_matches = [s.metadata_.mca_lender_match for s in mca_signals]
        assert any("OnDeck" in (m or "") for m in lender_matches)

    def test_harvest_mca_only_filter(
        self,
        harvester: FloridaUCCHarvester,
        sample_csv_path: Path,
    ) -> None:
        """Test MCA-only filtering."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        all_signals = list(harvester.harvest(file_path=str(sample_csv_path)))
        mca_signals = list(harvester.harvest(
            file_path=str(sample_csv_path),
            mca_only=True,
        ))

        # MCA-only should be subset
        assert len(mca_signals) <= len(all_signals)
        assert len(mca_signals) > 0

        # All should be MCA-related
        for signal in mca_signals:
            assert signal.metadata_.is_mca_related is True

    def test_harvest_date_filter(
        self,
        harvester: FloridaUCCHarvester,
        sample_csv_path: Path,
    ) -> None:
        """Test date filtering."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        start_date = datetime(2024, 1, 20)
        end_date = datetime(2024, 1, 25)

        signals = list(harvester.harvest(
            file_path=str(sample_csv_path),
            start_date=start_date,
            end_date=end_date,
        ))

        for signal in signals:
            assert start_date <= signal.signal_date <= end_date

    def test_filing_type_mapping(self, harvester: FloridaUCCHarvester) -> None:
        """Test filing type to signal type mapping."""
        assert harvester._map_filing_type("UCC-1") == SignalType.UCC_FILING
        assert harvester._map_filing_type("UCC-3 TERMINATION") == SignalType.UCC_TERMINATION
        assert harvester._map_filing_type("UCC-3 AMENDMENT") == SignalType.UCC_AMENDMENT
        assert harvester._map_filing_type("UCC-3 CONTINUATION") == SignalType.UCC_CONTINUATION

    def test_date_parsing(self, harvester: FloridaUCCHarvester) -> None:
        """Test date parsing for various formats."""
        # MM/DD/YYYY
        result = harvester._parse_date("01/15/2024")
        assert result == datetime(2024, 1, 15)

        # YYYY-MM-DD
        result = harvester._parse_date("2024-01-15")
        assert result == datetime(2024, 1, 15)

        # Invalid
        result = harvester._parse_date("invalid")
        assert result is None

        # None
        result = harvester._parse_date(None)
        assert result is None

    def test_record_normalization(self, harvester: FloridaUCCHarvester) -> None:
        """Test field name normalization."""
        record = {
            "UCC_Number": "123",
            "File_Date": "01/15/2024",
            "Debtor_Name": "Test LLC",
            "Secured_Party": "Lender Inc",
            "Collateral_Description": "All assets",
        }

        normalized = harvester._normalize_record(record)

        assert normalized.get("filing_number") == "123"
        assert normalized.get("filing_date") == "01/15/2024"
        assert normalized.get("debtor_name") == "Test LLC"
        assert normalized.get("secured_party") == "Lender Inc"
        assert normalized.get("collateral") == "All assets"

    def test_raw_data_preserved(
        self,
        harvester: FloridaUCCHarvester,
        sample_csv_path: Path,
    ) -> None:
        """Test that raw data is preserved in signal."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        signals = list(harvester.harvest(file_path=str(sample_csv_path)))

        for signal in signals:
            assert signal.raw_data is not None
            assert isinstance(signal.raw_data, dict)
            # Raw data should have original field names
            assert len(signal.raw_data) > 0

    def test_invalid_file_raises_error(self, harvester: FloridaUCCHarvester) -> None:
        """Test that invalid file path raises error."""
        with pytest.raises(FileNotFoundError):
            list(harvester.harvest(file_path="/nonexistent/path.csv"))

    def test_invalid_date_range_raises_error(
        self,
        harvester: FloridaUCCHarvester,
    ) -> None:
        """Test that invalid date range raises error."""
        with pytest.raises(ValueError):
            harvester.validate_date_range(
                start_date=datetime(2024, 1, 31),
                end_date=datetime(2024, 1, 1),
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
