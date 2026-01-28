"""Data harvesters for MCA Lead Intelligence.

Provides infrastructure for harvesting business signals from various data sources:
- UCC filings from Secretary of State websites
- SEC EDGAR filings
- Hiring signals (planned)
- Permit applications (planned)
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
from src.harvesters.sec_edgar import SECEdgarHarvester
from src.harvesters.ucc import FloridaUCCHarvester

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
    # Harvesters
    "FloridaUCCHarvester",
    "SECEdgarHarvester",
    # Orchestration
    "HarvesterOrchestrator",
    "HarvesterConfig",
    "OrchestratorResult",
    "harvester_orchestrator",
]
