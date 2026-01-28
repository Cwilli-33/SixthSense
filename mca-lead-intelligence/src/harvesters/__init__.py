"""Data harvesters for MCA Lead Intelligence.

Provides infrastructure for harvesting business signals from various data sources:
- UCC filings from Secretary of State websites (FL, NY, TX, CA)
- SEC EDGAR filings
- Hiring signals
- Permit applications
- Tax liens (stress signals)
"""

from src.harvesters.base import BaseHarvester, HarvestResult, MockHarvester
from src.harvesters.http_client import (
    HarvestHTTPClient,
    RateLimiter,
    RetryConfig,
)
from src.harvesters.mca_detector import MCADetectionResult, MCADetector, mca_detector
from src.harvesters.orchestrator import (
    HarvesterConfig,
    HarvesterOrchestrator,
    OrchestratorResult,
    harvester_orchestrator,
)

# UCC Harvesters
from src.harvesters.ucc import FloridaUCCHarvester
from src.harvesters.ucc_multistate import MultiStateUCCHarvester

# SEC Harvester
from src.harvesters.sec_edgar import SECEdgarHarvester

# Growth Signal Harvesters
from src.harvesters.hiring import HiringSignalsHarvester
from src.harvesters.permits import PermitsHarvester

# Stress Signal Harvesters
from src.harvesters.tax_liens import TaxLienHarvester

__all__ = [
    # Base classes
    "BaseHarvester",
    "HarvestResult",
    "MockHarvester",
    # HTTP client
    "HarvestHTTPClient",
    "RateLimiter",
    "RetryConfig",
    # MCA Detection
    "MCADetector",
    "MCADetectionResult",
    "mca_detector",
    # UCC Harvesters
    "FloridaUCCHarvester",
    "MultiStateUCCHarvester",
    # SEC Harvester
    "SECEdgarHarvester",
    # Growth Signal Harvesters
    "HiringSignalsHarvester",
    "PermitsHarvester",
    # Stress Signal Harvesters
    "TaxLienHarvester",
    # Orchestration
    "HarvesterOrchestrator",
    "HarvesterConfig",
    "OrchestratorResult",
    "harvester_orchestrator",
]
