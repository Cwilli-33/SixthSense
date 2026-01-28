"""MCA Lead Intelligence - Detect business events indicating MCA capital need.

This package provides tools for:
- Harvesting business signals (UCC filings, permits, etc.)
- Detecting MCA-related activity
- Scoring leads based on FIT, INTENT, and TIMING dimensions
- Exporting broker-ready lead lists
"""

__version__ = "0.1.0"

from src.pipeline import LeadPipeline, run_pipeline

__all__ = [
    "__version__",
    "LeadPipeline",
    "run_pipeline",
]
