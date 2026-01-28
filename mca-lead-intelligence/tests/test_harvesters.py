"""Tests for the harvester system.

Covers:
- HiringSignalsHarvester
- TaxLienHarvester
- PermitsHarvester
- MultiStateUCCHarvester
- HarvesterOrchestrator
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.harvesters.hiring import HiringSignalsHarvester, HiringSignal, JobPosting
from src.harvesters.tax_liens import TaxLienHarvester, TaxLien, TaxLienSignal
from src.harvesters.permits import PermitsHarvester, Permit, PermitSignal, PermitType
from src.harvesters.ucc_multistate import (
    MultiStateUCCHarvester,
    UCCFiling,
    NewYorkUCCHarvester,
    TexasUCCHarvester,
    CaliforniaUCCHarvester,
)
from src.harvesters.orchestrator import (
    HarvesterOrchestrator,
    OrchestratorResult,
    HarvesterConfig,
)
from src.harvesters.base import MockHarvester
from src.models.signal import SignalCreate


class TestHiringSignalsHarvester:
    """Tests for HiringSignalsHarvester."""

    @pytest.fixture
    def harvester(self) -> HiringSignalsHarvester:
        """Create harvester instance."""
        return HiringSignalsHarvester(requests_per_minute=60)

    def test_source_name(self, harvester: HiringSignalsHarvester) -> None:
        """Test source name."""
        assert harvester.SOURCE_NAME == "HIRING_SIGNALS"

    def test_target_industries(self, harvester: HiringSignalsHarvester) -> None:
        """Test target industries are defined."""
        assert len(harvester.TARGET_INDUSTRIES) > 0
        assert "restaurant" in harvester.TARGET_INDUSTRIES
        assert "construction" in harvester.TARGET_INDUSTRIES

    def test_growth_indicators(self, harvester: HiringSignalsHarvester) -> None:
        """Test growth indicator job titles are defined."""
        assert len(harvester.GROWTH_INDICATORS) > 0
        assert "manager" in harvester.GROWTH_INDICATORS

    def test_hiring_signal_strength_strong(self) -> None:
        """Test strong hiring signal (5+ postings)."""
        signal = HiringSignal(
            company_name="Test Corp",
            total_postings=5,
        )
        assert signal.signal_strength == "strong"
        assert signal.base_points == 85

    def test_hiring_signal_strength_moderate(self) -> None:
        """Test moderate hiring signal (2-4 postings)."""
        signal = HiringSignal(
            company_name="Test Corp",
            total_postings=3,
        )
        assert signal.signal_strength == "moderate"
        assert signal.base_points == 60

    def test_hiring_signal_strength_weak(self) -> None:
        """Test weak hiring signal (1 posting)."""
        signal = HiringSignal(
            company_name="Test Corp",
            total_postings=1,
        )
        assert signal.signal_strength == "weak"
        assert signal.base_points == 30

    def test_normalize_company_name(self, harvester: HiringSignalsHarvester) -> None:
        """Test company name normalization."""
        assert harvester._normalize_company_name("Test Inc.") == "Test"
        assert harvester._normalize_company_name("Test LLC") == "Test"
        assert harvester._normalize_company_name("Test Corp.") == "Test"
        assert harvester._normalize_company_name("  Test Co  ") == "Test"

    def test_build_google_jobs_url(self, harvester: HiringSignalsHarvester) -> None:
        """Test Google Jobs URL building."""
        url = harvester._build_google_jobs_url("restaurant jobs", "Miami, FL")
        assert "google.com/search" in url
        assert "ibp=htl;jobs" in url


class TestTaxLienHarvester:
    """Tests for TaxLienHarvester."""

    @pytest.fixture
    def harvester(self) -> TaxLienHarvester:
        """Create harvester instance."""
        return TaxLienHarvester(requests_per_minute=60)

    def test_source_name(self, harvester: TaxLienHarvester) -> None:
        """Test source name."""
        assert harvester.SOURCE_NAME == "TAX_LIENS"

    def test_state_portals_defined(self, harvester: TaxLienHarvester) -> None:
        """Test that state portals are defined."""
        assert len(harvester.STATE_PORTALS) > 0
        assert "FL" in harvester.STATE_PORTALS
        assert "NY" in harvester.STATE_PORTALS

    def test_tax_lien_is_active(self) -> None:
        """Test active lien detection."""
        active_lien = TaxLien(
            business_name="Test Corp",
            lien_type="state",
            status="active",
            release_date=None,
        )
        assert active_lien.is_active is True

        released_lien = TaxLien(
            business_name="Test Corp",
            lien_type="state",
            status="released",
            release_date=datetime.now(),
        )
        assert released_lien.is_active is False

    def test_tax_lien_age_days(self) -> None:
        """Test lien age calculation."""
        lien = TaxLien(
            business_name="Test Corp",
            lien_type="state",
            filing_date=datetime.now() - timedelta(days=30),
        )
        assert lien.age_days is not None
        assert 29 <= lien.age_days <= 31

    def test_tax_lien_signal_strength_high(self) -> None:
        """Test high stress signal."""
        signal = TaxLienSignal(
            business_name="Test Corp",
            total_liens=3,
            active_liens=3,
            total_amount=150000,
        )
        assert signal.signal_strength == "high_stress"
        assert signal.base_points == 70

    def test_tax_lien_signal_strength_moderate(self) -> None:
        """Test moderate stress signal."""
        signal = TaxLienSignal(
            business_name="Test Corp",
            total_liens=2,
            active_liens=2,
            total_amount=50000,
        )
        assert signal.signal_strength == "moderate_stress"
        assert signal.base_points == 55

    def test_tax_lien_signal_strength_low(self) -> None:
        """Test low stress signal."""
        signal = TaxLienSignal(
            business_name="Test Corp",
            total_liens=1,
            active_liens=1,
            total_amount=5000,
        )
        assert signal.signal_strength == "low_stress"
        assert signal.base_points == 35

    def test_normalize_business_name(self, harvester: TaxLienHarvester) -> None:
        """Test business name normalization."""
        assert harvester._normalize_business_name("TEST CORP.") == "TEST"
        assert harvester._normalize_business_name("test llc") == "TEST"


class TestPermitsHarvester:
    """Tests for PermitsHarvester."""

    @pytest.fixture
    def harvester(self) -> PermitsHarvester:
        """Create harvester instance."""
        return PermitsHarvester(requests_per_minute=60)

    def test_source_name(self, harvester: PermitsHarvester) -> None:
        """Test source name."""
        assert harvester.SOURCE_NAME == "PERMITS"

    def test_city_portals_defined(self, harvester: PermitsHarvester) -> None:
        """Test that city portals are defined."""
        assert len(harvester.CITY_PORTALS) > 0
        assert "Miami" in harvester.CITY_PORTALS
        assert "New York" in harvester.CITY_PORTALS

    def test_permit_type_classification(self, harvester: PermitsHarvester) -> None:
        """Test permit type classification."""
        assert harvester._classify_permit_type("Building Permit") == PermitType.BUILDING
        assert harvester._classify_permit_type("Renovation") == PermitType.RENOVATION
        assert harvester._classify_permit_type("Sign Permit") == PermitType.SIGNAGE
        assert harvester._classify_permit_type("Electrical") == PermitType.ELECTRICAL
        assert harvester._classify_permit_type("HVAC System") == PermitType.MECHANICAL
        assert harvester._classify_permit_type("Business License") == PermitType.BUSINESS_LICENSE
        assert harvester._classify_permit_type("Unknown Type") == PermitType.OTHER

    def test_permit_signal_strength_strong(self) -> None:
        """Test strong expansion signal."""
        signal = PermitSignal(
            business_name="Test Corp",
            total_permits=4,
            total_estimated_cost=150000,
        )
        assert signal.signal_strength == "strong_expansion"
        assert signal.base_points == 80

    def test_permit_signal_strength_moderate(self) -> None:
        """Test moderate expansion signal."""
        signal = PermitSignal(
            business_name="Test Corp",
            total_permits=2,
            total_estimated_cost=50000,
        )
        assert signal.signal_strength == "moderate_expansion"
        assert signal.base_points == 55

    def test_permit_signal_strength_minor(self) -> None:
        """Test minor expansion signal."""
        signal = PermitSignal(
            business_name="Test Corp",
            total_permits=1,
            total_estimated_cost=5000,
        )
        assert signal.signal_strength == "minor_expansion"
        assert signal.base_points == 30

    def test_permit_signal_new_location_detection(self) -> None:
        """Test new location indicator."""
        permit = Permit(
            business_name="Test Corp",
            permit_type=PermitType.OCCUPANCY,
        )
        signal = PermitSignal(
            business_name="Test Corp",
            total_permits=1,
            permits=[permit],
        )
        assert signal.indicates_new_location is True

    def test_permit_signal_renovation_detection(self) -> None:
        """Test renovation indicator."""
        permit = Permit(
            business_name="Test Corp",
            permit_type=PermitType.RENOVATION,
        )
        signal = PermitSignal(
            business_name="Test Corp",
            total_permits=1,
            permits=[permit],
        )
        assert signal.indicates_renovation is True


class TestMultiStateUCCHarvester:
    """Tests for MultiStateUCCHarvester."""

    @pytest.fixture
    def harvester(self) -> MultiStateUCCHarvester:
        """Create harvester instance."""
        return MultiStateUCCHarvester(requests_per_minute=60)

    def test_source_name(self, harvester: MultiStateUCCHarvester) -> None:
        """Test source name."""
        assert harvester.SOURCE_NAME == "UCC_MULTISTATE"

    def test_state_harvesters_registered(self, harvester: MultiStateUCCHarvester) -> None:
        """Test that state harvesters are registered."""
        assert "NY" in harvester.state_harvesters
        assert "TX" in harvester.state_harvesters
        assert "CA" in harvester.state_harvesters

    def test_mca_lenders_list(self, harvester: MultiStateUCCHarvester) -> None:
        """Test MCA lenders list is defined."""
        assert len(harvester.TOP_MCA_LENDERS) > 0
        assert "OnDeck Capital" in harvester.TOP_MCA_LENDERS
        assert "Kabbage" in harvester.TOP_MCA_LENDERS

    def test_ucc_filing_creation(self) -> None:
        """Test UCCFiling dataclass."""
        filing = UCCFiling(
            filing_number="123456",
            debtor_name="Test Business LLC",
            secured_party="OnDeck Capital",
            filing_date=datetime.now(),
            state="NY",
        )
        assert filing.filing_number == "123456"
        assert filing.debtor_name == "Test Business LLC"
        assert filing.state == "NY"

    def test_convert_to_signal(self, harvester: MultiStateUCCHarvester) -> None:
        """Test conversion of UCCFiling to SignalCreate."""
        filing = UCCFiling(
            filing_number="123456",
            debtor_name="Test Business LLC",
            secured_party="OnDeck Capital",
            filing_date=datetime.now(),
            state="NY",
        )

        signal = harvester._convert_to_signal(filing, mca_related=True, mca_lender="OnDeck Capital")

        assert signal.signal_type == "UCC"
        assert signal.business_name == "Test Business LLC"
        assert signal.state == "NY"
        assert signal.source == "UCC_NY"
        assert signal.metadata_.is_mca_related is True
        assert signal.metadata_.mca_lender_match == "OnDeck Capital"


class TestHarvesterOrchestrator:
    """Tests for HarvesterOrchestrator."""

    @pytest.fixture
    def orchestrator(self) -> HarvesterOrchestrator:
        """Create orchestrator instance."""
        return HarvesterOrchestrator(max_workers=2)

    def test_default_harvesters_registered(self, orchestrator: HarvesterOrchestrator) -> None:
        """Test that default harvesters are registered."""
        assert "florida_ucc" in orchestrator._harvesters
        assert "multistate_ucc" in orchestrator._harvesters
        assert "sec_edgar" in orchestrator._harvesters
        assert "hiring" in orchestrator._harvesters
        assert "permits" in orchestrator._harvesters
        assert "tax_liens" in orchestrator._harvesters

    def test_harvester_priorities(self, orchestrator: HarvesterOrchestrator) -> None:
        """Test harvester priority ordering."""
        # UCC harvesters should have highest priority
        assert orchestrator._harvesters["florida_ucc"].priority == 1
        assert orchestrator._harvesters["multistate_ucc"].priority == 1

        # SEC should be priority 2
        assert orchestrator._harvesters["sec_edgar"].priority == 2

        # Growth signals priority 3
        assert orchestrator._harvesters["hiring"].priority == 3
        assert orchestrator._harvesters["permits"].priority == 3

        # Stress signals priority 4
        assert orchestrator._harvesters["tax_liens"].priority == 4

    def test_register_harvester(self, orchestrator: HarvesterOrchestrator) -> None:
        """Test registering a custom harvester."""
        orchestrator.register_harvester(
            "custom",
            MockHarvester,
            priority=5,
            kwargs={"test": True},
        )

        assert "custom" in orchestrator._harvesters
        assert orchestrator._harvesters["custom"].priority == 5

    def test_enable_disable_harvester(self, orchestrator: HarvesterOrchestrator) -> None:
        """Test enabling/disabling harvesters."""
        orchestrator.disable_harvester("hiring")
        assert orchestrator._harvesters["hiring"].enabled is False

        orchestrator.enable_harvester("hiring")
        assert orchestrator._harvesters["hiring"].enabled is True

    def test_get_enabled_harvesters(self, orchestrator: HarvesterOrchestrator) -> None:
        """Test getting enabled harvesters sorted by priority."""
        orchestrator.disable_harvester("tax_liens")

        enabled = orchestrator._get_enabled_harvesters(None)

        assert "tax_liens" not in enabled
        # Should be sorted by priority
        assert enabled[0] in ["florida_ucc", "multistate_ucc"]

    def test_get_enabled_harvesters_with_filter(self, orchestrator: HarvesterOrchestrator) -> None:
        """Test getting specific harvesters."""
        enabled = orchestrator._get_enabled_harvesters(["florida_ucc", "hiring"])

        assert len(enabled) == 2
        assert "florida_ucc" in enabled
        assert "hiring" in enabled

    def test_get_harvester_instance(self, orchestrator: HarvesterOrchestrator) -> None:
        """Test getting harvester instance."""
        harvester = orchestrator.get_harvester("florida_ucc")

        assert harvester is not None
        # Should be cached
        harvester2 = orchestrator.get_harvester("florida_ucc")
        assert harvester is harvester2

    def test_get_nonexistent_harvester(self, orchestrator: HarvesterOrchestrator) -> None:
        """Test getting non-existent harvester."""
        harvester = orchestrator.get_harvester("nonexistent")
        assert harvester is None

    def test_orchestrator_result_properties(self) -> None:
        """Test OrchestratorResult properties."""
        result = OrchestratorResult()
        result.end_time = datetime.now()
        result.total_signals = 100
        result.signals_by_source = {"ucc": 50, "sec": 50}

        assert result.duration_seconds >= 0
        assert result.success is True

    def test_orchestrator_result_with_errors(self) -> None:
        """Test OrchestratorResult with errors but signals."""
        result = OrchestratorResult()
        result.total_signals = 50
        result.errors = [{"source": "test", "error": "test error"}]

        # Still success because we got signals
        assert result.success is True

    def test_get_statistics_no_harvest(self, orchestrator: HarvesterOrchestrator) -> None:
        """Test statistics before harvest."""
        stats = orchestrator.get_statistics()
        assert stats["status"] == "no harvest performed"

    def test_close_harvesters(self, orchestrator: HarvesterOrchestrator) -> None:
        """Test closing harvester instances."""
        # Get an instance to add to active instances
        orchestrator.get_harvester("florida_ucc")
        assert len(orchestrator._active_instances) > 0

        orchestrator.close()
        assert len(orchestrator._active_instances) == 0


class TestIntegration:
    """Integration tests for the harvester system."""

    def test_mock_harvester_in_orchestrator(self) -> None:
        """Test using MockHarvester through orchestrator."""
        orchestrator = HarvesterOrchestrator()

        # Disable all default harvesters
        for name in list(orchestrator._harvesters.keys()):
            orchestrator.disable_harvester(name)

        # Register mock harvester
        orchestrator.register_harvester(
            "mock",
            MockHarvester,
            priority=1,
        )

        # Get enabled should only return mock
        enabled = orchestrator._get_enabled_harvesters(None)
        assert enabled == ["mock"]

    def test_harvester_config_dataclass(self) -> None:
        """Test HarvesterConfig dataclass."""
        config = HarvesterConfig(
            harvester_class=MockHarvester,
            enabled=True,
            priority=1,
            kwargs={"test": True},
        )

        assert config.harvester_class == MockHarvester
        assert config.enabled is True
        assert config.priority == 1
        assert config.kwargs == {"test": True}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
