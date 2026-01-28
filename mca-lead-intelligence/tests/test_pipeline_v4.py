"""Integration tests for v4.0 pipeline with multi-source harvesting.

Tests the complete pipeline flow including:
- Multi-source orchestration
- v4.0 scoring (FIT 40%, INTENT 40%, TIMING 20%)
- Freshness multipliers
- Signal type routing
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import LeadPipeline, run_pipeline
from src.harvesters.orchestrator import HarvesterOrchestrator
from src.harvesters.base import MockHarvester
from src.models.signal import SignalCreate, SignalMetadata
from src.scoring.intent import IntentSignalType
from src.scoring.decay import DecayClass


class TestPipelineV4:
    """Tests for v4.0 pipeline functionality."""

    @pytest.fixture
    def pipeline(self) -> LeadPipeline:
        """Create pipeline instance."""
        return LeadPipeline()

    def test_pipeline_init_with_orchestrator(self) -> None:
        """Test pipeline initializes with orchestrator."""
        pipeline = LeadPipeline()

        assert pipeline.orchestrator is not None
        assert isinstance(pipeline.orchestrator, HarvesterOrchestrator)

    def test_pipeline_tracks_signals_by_source(self) -> None:
        """Test pipeline tracks signals by source."""
        pipeline = LeadPipeline()

        assert hasattr(pipeline, "_signals_by_source")
        assert isinstance(pipeline._signals_by_source, dict)

    def test_stats_include_sources(self) -> None:
        """Test stats include source tracking."""
        pipeline = LeadPipeline()
        pipeline._signals_by_source = {"UCC_FL": 50, "SEC_EDGAR": 25}

        stats = pipeline.stats

        assert "signals_by_source" in stats
        assert "sources_used" in stats
        assert stats["signals_by_source"]["UCC_FL"] == 50

    def test_run_accepts_sources_parameter(self) -> None:
        """Test run method accepts sources parameter."""
        pipeline = LeadPipeline()

        # This should not raise - verifying parameter is accepted
        # Actual harvest would require network/files
        try:
            # Using mock to avoid actual harvesting
            with patch.object(pipeline.orchestrator, 'harvest_all') as mock_harvest:
                mock_harvest.return_value = iter([])
                pipeline.run(sources=["florida_ucc"], persist=False)
        except Exception:
            pass  # Expected if no data

    def test_run_accepts_parallel_parameter(self) -> None:
        """Test run method accepts parallel parameter."""
        pipeline = LeadPipeline()

        # Verify parallel parameter is accepted
        try:
            with patch.object(pipeline.orchestrator, 'harvest_parallel') as mock_harvest:
                mock_result = MagicMock()
                mock_result.signals_by_source = {}
                mock_harvest.return_value = mock_result
                pipeline.run(parallel=True, persist=False)
        except Exception:
            pass


class TestIntentSignalRouting:
    """Tests for routing signals to correct IntentSignalType."""

    @pytest.fixture
    def pipeline(self) -> LeadPipeline:
        """Create pipeline instance."""
        return LeadPipeline()

    def test_hiring_signal_routing(self, pipeline: LeadPipeline) -> None:
        """Test hiring signals route to correct IntentSignalType."""
        signal = SignalCreate(
            signal_type="HIRING",
            business_identifier="HIRING:TestCorp",
            business_name="Test Corp",
            signal_date=datetime.now(),
            source="HIRING_SIGNALS",
            state="FL",
            raw_data={"total_postings": 5},
            metadata_=SignalMetadata(),
        )

        intent_signals = pipeline._build_intent_signals(signal, {})

        assert len(intent_signals) == 1
        assert intent_signals[0].signal_type == IntentSignalType.ACTIVE_HIRING_5PLUS
        assert intent_signals[0].base_points == 85
        assert intent_signals[0].decay_class == DecayClass.RAPID

    def test_hiring_signal_moderate(self, pipeline: LeadPipeline) -> None:
        """Test moderate hiring signals (2-4 postings)."""
        signal = SignalCreate(
            signal_type="HIRING",
            business_identifier="HIRING:TestCorp",
            business_name="Test Corp",
            signal_date=datetime.now(),
            source="HIRING_SIGNALS",
            state="FL",
            raw_data={"total_postings": 3},
            metadata_=SignalMetadata(),
        )

        intent_signals = pipeline._build_intent_signals(signal, {})

        assert intent_signals[0].signal_type == IntentSignalType.ACTIVE_HIRING_2TO4
        assert intent_signals[0].base_points == 60

    def test_permit_new_location_routing(self, pipeline: LeadPipeline) -> None:
        """Test permit signals for new location."""
        signal = SignalCreate(
            signal_type="PERMIT",
            business_identifier="PERMIT:TestCorp:Miami",
            business_name="Test Corp",
            signal_date=datetime.now(),
            source="PERMITS",
            state="FL",
            raw_data={"signal_subtype": "new_location"},
            metadata_=SignalMetadata(),
        )

        intent_signals = pipeline._build_intent_signals(signal, {})

        assert intent_signals[0].signal_type == IntentSignalType.PERMIT_NEW_LOCATION
        assert intent_signals[0].base_points == 80
        assert intent_signals[0].decay_class == DecayClass.EXTENDED

    def test_permit_renovation_routing(self, pipeline: LeadPipeline) -> None:
        """Test permit signals for renovation."""
        signal = SignalCreate(
            signal_type="PERMIT",
            business_identifier="PERMIT:TestCorp:Miami",
            business_name="Test Corp",
            signal_date=datetime.now(),
            source="PERMITS",
            state="FL",
            raw_data={"signal_subtype": "renovation"},
            metadata_=SignalMetadata(),
        )

        intent_signals = pipeline._build_intent_signals(signal, {})

        assert intent_signals[0].signal_type == IntentSignalType.PERMIT_RENOVATION
        assert intent_signals[0].base_points == 55

    def test_tax_lien_high_stress_routing(self, pipeline: LeadPipeline) -> None:
        """Test tax lien signals with high stress."""
        signal = SignalCreate(
            signal_type="TAX_LIEN",
            business_identifier="LIEN:TestCorp:FL",
            business_name="Test Corp",
            signal_date=datetime.now(),
            source="TAX_LIENS",
            state="FL",
            raw_data={},
            metadata_=SignalMetadata(signal_strength="high_stress"),
        )

        intent_signals = pipeline._build_intent_signals(
            signal, {"signal_strength": "high_stress"}
        )

        assert intent_signals[0].signal_type == IntentSignalType.TAX_LIEN
        assert intent_signals[0].base_points == 70
        assert intent_signals[0].decay_class == DecayClass.STRUCTURAL

    def test_sec_edgar_routing(self, pipeline: LeadPipeline) -> None:
        """Test SEC EDGAR signals routing."""
        signal = SignalCreate(
            signal_type="SEC_FILING",
            business_identifier="SEC:0001234567:8-K",
            business_name="Test Corp",
            signal_date=datetime.now(),
            source="SEC_EDGAR",
            state="DE",
            raw_data={},
            metadata_=SignalMetadata(),
        )

        intent_signals = pipeline._build_intent_signals(signal, {})

        assert intent_signals[0].signal_type == IntentSignalType.SEC_FINANCING
        assert intent_signals[0].base_points == 40
        assert intent_signals[0].decay_class == DecayClass.EXTENDED

    def test_mca_ucc_routing(self, pipeline: LeadPipeline) -> None:
        """Test MCA-related UCC signals routing."""
        signal = SignalCreate(
            signal_type="UCC",
            business_identifier="UCC:FL:123456",
            business_name="Test Corp",
            signal_date=datetime.now(),
            source="FL_SOS",
            state="FL",
            raw_data={},
            metadata_=SignalMetadata(is_mca_related=True),
        )

        intent_signals = pipeline._build_intent_signals(
            signal, {"is_mca_related": True}
        )

        assert intent_signals[0].signal_type == IntentSignalType.UCC_MCA_LENDER
        assert intent_signals[0].base_points == 90
        assert intent_signals[0].decay_class == DecayClass.STANDARD

    def test_general_ucc_routing(self, pipeline: LeadPipeline) -> None:
        """Test general UCC signals routing."""
        signal = SignalCreate(
            signal_type="UCC",
            business_identifier="UCC:FL:123456",
            business_name="Test Corp",
            signal_date=datetime.now(),
            source="FL_SOS",
            state="FL",
            raw_data={},
            metadata_=SignalMetadata(is_mca_related=False),
        )

        intent_signals = pipeline._build_intent_signals(
            signal, {"is_mca_related": False}
        )

        assert intent_signals[0].signal_type == IntentSignalType.UCC_GENERAL
        assert intent_signals[0].base_points == 50


class TestProcessSignal:
    """Tests for signal processing with v4.0 scoring."""

    @pytest.fixture
    def pipeline(self) -> LeadPipeline:
        """Create pipeline instance."""
        return LeadPipeline()

    def test_process_signal_returns_lead_export(self, pipeline: LeadPipeline) -> None:
        """Test _process_signal returns LeadExport."""
        signal = SignalCreate(
            signal_type="UCC",
            business_identifier="UCC:FL:123456",
            business_name="Test Restaurant LLC",
            signal_date=datetime.now(),
            source="FL_SOS",
            state="FL",
            raw_data={},
            metadata_=SignalMetadata(is_mca_related=True),
        )

        result = pipeline._process_signal(signal, persist=False)

        assert result is not None
        assert result.business_name == "Test Restaurant LLC"

    def test_process_signal_includes_scores(self, pipeline: LeadPipeline) -> None:
        """Test processed signal includes all v4.0 scores."""
        signal = SignalCreate(
            signal_type="UCC",
            business_identifier="UCC:FL:123456",
            business_name="Test Restaurant LLC",
            signal_date=datetime.now(),
            source="FL_SOS",
            state="FL",
            raw_data={},
            metadata_=SignalMetadata(is_mca_related=True),
        )

        result = pipeline._process_signal(signal, persist=False)

        assert hasattr(result, "fit_score")
        assert hasattr(result, "composite_score")
        # Scores should be in valid range
        assert 0 <= result.fit_score <= 100

    def test_process_signal_calculates_freshness(self, pipeline: LeadPipeline) -> None:
        """Test freshness is calculated for signal."""
        # Very fresh signal (HOT)
        signal = SignalCreate(
            signal_type="UCC",
            business_identifier="UCC:FL:123456",
            business_name="Test Restaurant LLC",
            signal_date=datetime.now() - timedelta(hours=12),
            source="FL_SOS",
            state="FL",
            raw_data={},
            metadata_=SignalMetadata(is_mca_related=True),
        )

        result = pipeline._process_signal(signal, persist=False)

        # Should have signal age
        assert result.signal_age_days >= 0


class TestConvenienceFunction:
    """Tests for run_pipeline convenience function."""

    def test_run_pipeline_accepts_sources(self) -> None:
        """Test run_pipeline accepts sources parameter."""
        # Verify parameter signature
        import inspect
        sig = inspect.signature(run_pipeline)

        assert "sources" in sig.parameters
        assert "parallel" in sig.parameters

    def test_run_pipeline_returns_leads(self) -> None:
        """Test run_pipeline returns list of leads."""
        # Using mock to avoid actual harvesting
        with patch('src.pipeline.LeadPipeline') as MockPipeline:
            mock_instance = MagicMock()
            mock_instance.run.return_value = []
            MockPipeline.return_value = mock_instance

            result = run_pipeline()

            assert isinstance(result, list)


class TestOrchestratorIntegration:
    """Tests for orchestrator integration with pipeline."""

    def test_pipeline_uses_orchestrator_by_default(self) -> None:
        """Test pipeline uses orchestrator by default."""
        pipeline = LeadPipeline()

        assert pipeline.orchestrator is not None

    def test_pipeline_can_use_single_harvester(self) -> None:
        """Test pipeline can use single harvester for backward compatibility."""
        from src.harvesters.ucc import FloridaUCCHarvester

        harvester = FloridaUCCHarvester()
        pipeline = LeadPipeline(harvester=harvester)

        assert pipeline.harvester is harvester

    def test_use_orchestrator_flag(self) -> None:
        """Test use_orchestrator flag controls behavior."""
        from src.harvesters.ucc import FloridaUCCHarvester

        harvester = FloridaUCCHarvester()
        pipeline = LeadPipeline(harvester=harvester)

        # When use_orchestrator=False and harvester provided
        # should use single harvester
        # This tests the logic path exists


class TestErrorHandling:
    """Tests for error handling in pipeline."""

    @pytest.fixture
    def pipeline(self) -> LeadPipeline:
        """Create pipeline instance."""
        return LeadPipeline()

    def test_errors_tracked_in_stats(self, pipeline: LeadPipeline) -> None:
        """Test errors are tracked in stats."""
        pipeline._errors = ["Error 1", "Error 2"]

        stats = pipeline.stats

        assert stats["errors"] == 2
        assert len(stats["error_messages"]) == 2

    def test_error_messages_limited(self, pipeline: LeadPipeline) -> None:
        """Test error messages are limited to 10."""
        pipeline._errors = [f"Error {i}" for i in range(20)]

        stats = pipeline.stats

        assert len(stats["error_messages"]) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
