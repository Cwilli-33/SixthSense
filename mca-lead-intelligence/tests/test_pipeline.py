"""Tests for the lead generation pipeline."""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile

import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import LeadPipeline
from src.models.lead import PriorityLevel


class TestLeadPipeline:
    """Tests for lead generation pipeline."""

    @pytest.fixture
    def pipeline(self) -> LeadPipeline:
        """Create pipeline instance."""
        return LeadPipeline()

    @pytest.fixture
    def sample_csv_path(self) -> Path:
        """Get path to sample CSV file."""
        return Path(__file__).parent.parent / "data" / "sample_ucc_filings.csv"

    def test_pipeline_processes_signals(
        self,
        pipeline: LeadPipeline,
        sample_csv_path: Path,
    ) -> None:
        """Test that pipeline processes signals into leads."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        leads = pipeline.run(
            file_path=str(sample_csv_path),
            persist=False,
        )

        assert len(leads) > 0
        assert pipeline.stats["signals_processed"] > 0
        assert pipeline.stats["leads_generated"] > 0

    def test_pipeline_generates_csv_output(
        self,
        pipeline: LeadPipeline,
        sample_csv_path: Path,
    ) -> None:
        """Test that pipeline generates CSV output."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output.csv"

            leads = pipeline.run(
                file_path=str(sample_csv_path),
                output_path=output_path,
                persist=False,
            )

            assert output_path.exists()

            # Check CSV content
            with open(output_path, "r") as f:
                lines = f.readlines()
                assert len(lines) > 1  # Header + data

    def test_pipeline_mca_only_filter(
        self,
        pipeline: LeadPipeline,
        sample_csv_path: Path,
    ) -> None:
        """Test MCA-only filtering in pipeline."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        all_leads = pipeline.run(
            file_path=str(sample_csv_path),
            mca_only=False,
            persist=False,
        )

        mca_leads = pipeline.run(
            file_path=str(sample_csv_path),
            mca_only=True,
            persist=False,
        )

        assert len(mca_leads) <= len(all_leads)

        # All MCA leads should have is_mca_related=True
        for lead in mca_leads:
            assert lead.is_mca_related is True

    def test_pipeline_assigns_priority_levels(
        self,
        pipeline: LeadPipeline,
        sample_csv_path: Path,
    ) -> None:
        """Test that pipeline assigns priority levels."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        leads = pipeline.run(
            file_path=str(sample_csv_path),
            persist=False,
        )

        priority_levels = [lead.priority_level for lead in leads]

        # Should have valid priority levels
        valid_levels = {"P1", "P2", "P3", "P4", "P5"}
        for level in priority_levels:
            assert level in valid_levels

    def test_pipeline_calculates_scores(
        self,
        pipeline: LeadPipeline,
        sample_csv_path: Path,
    ) -> None:
        """Test that pipeline calculates scores."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        leads = pipeline.run(
            file_path=str(sample_csv_path),
            persist=False,
        )

        for lead in leads:
            # All leads should have scores
            assert 0 <= lead.fit_score <= 100
            assert 0 <= float(lead.composite_score) <= 100

    def test_pipeline_handles_date_range(
        self,
        pipeline: LeadPipeline,
        sample_csv_path: Path,
    ) -> None:
        """Test pipeline date range filtering."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        start_date = datetime(2024, 1, 20)
        end_date = datetime(2024, 1, 25)

        leads = pipeline.run(
            file_path=str(sample_csv_path),
            start_date=start_date,
            end_date=end_date,
            persist=False,
        )

        for lead in leads:
            assert start_date <= lead.signal_date <= end_date

    def test_pipeline_stats(
        self,
        pipeline: LeadPipeline,
        sample_csv_path: Path,
    ) -> None:
        """Test pipeline statistics."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        pipeline.run(
            file_path=str(sample_csv_path),
            persist=False,
        )

        stats = pipeline.stats

        assert "signals_processed" in stats
        assert "leads_generated" in stats
        assert "errors" in stats
        assert stats["errors"] == 0  # No errors for valid input

    def test_lead_export_fields(
        self,
        pipeline: LeadPipeline,
        sample_csv_path: Path,
    ) -> None:
        """Test that exported leads have required fields."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        leads = pipeline.run(
            file_path=str(sample_csv_path),
            persist=False,
        )

        for lead in leads:
            # Check required fields
            assert lead.business_name is not None
            assert lead.state is not None
            assert lead.fit_score is not None
            assert lead.composite_score is not None
            assert lead.priority_level is not None
            assert lead.signal_type is not None
            assert lead.signal_date is not None
            assert lead.signal_age_days >= 0

    def test_high_propensity_businesses_score_higher(
        self,
        pipeline: LeadPipeline,
        sample_csv_path: Path,
    ) -> None:
        """Test that high-propensity industries score higher."""
        if not sample_csv_path.exists():
            pytest.skip("Sample CSV file not found")

        leads = pipeline.run(
            file_path=str(sample_csv_path),
            persist=False,
        )

        # Find leads by industry
        restaurant_leads = [
            l for l in leads
            if l.industry and "restaurant" in l.industry.lower()
        ]
        consulting_leads = [
            l for l in leads
            if l.industry and "consulting" in l.industry.lower()
        ]

        if restaurant_leads and consulting_leads:
            avg_restaurant_score = sum(
                l.fit_score for l in restaurant_leads
            ) / len(restaurant_leads)
            avg_consulting_score = sum(
                l.fit_score for l in consulting_leads
            ) / len(consulting_leads)

            assert avg_restaurant_score > avg_consulting_score


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
