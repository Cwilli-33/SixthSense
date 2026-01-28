"""Scoring modules for MCA Lead Intelligence.

Version 4.0: Time-Weighted Scoring Engine

Components:
- FIT: Revenue capacity and business fit scoring
- INTENT: Time-weighted signal decay scoring
- TIMING: Seasonal and recency scoring
- Composite: Combined scoring with freshness multiplier
- Decay: Exponential decay engine for signals
- Freshness: Lead freshness flags and multipliers
"""

from src.scoring.composite import CompositeScorer, CompositeScoreResult, composite_scorer
from src.scoring.decay import DecayClass, DecayEngine, DecayResult, decay_engine
from src.scoring.fit import FITScorer, FITScoreResult, fit_scorer
from src.scoring.freshness import (
    FreshnessCalculator,
    FreshnessFlag,
    FreshnessResult,
    freshness_calculator,
)
from src.scoring.industry_classifier import (
    IndustryClassification,
    IndustryClassifier,
    industry_classifier,
)
from src.scoring.intent import (
    DecayedSignal,
    INTENTScorer,
    INTENTScoreResult,
    IntentPathway,
    IntentSignal,
    IntentSignalType,
    intent_scorer,
)
from src.scoring.timing import (
    SeasonalTiming,
    TIMINGScorer,
    TIMINGScoreResult,
    timing_scorer,
)

__all__ = [
    # FIT
    "FITScorer",
    "FITScoreResult",
    "fit_scorer",
    # INTENT
    "INTENTScorer",
    "INTENTScoreResult",
    "IntentSignal",
    "IntentSignalType",
    "IntentPathway",
    "DecayedSignal",
    "intent_scorer",
    # TIMING
    "TIMINGScorer",
    "TIMINGScoreResult",
    "SeasonalTiming",
    "timing_scorer",
    # Composite
    "CompositeScorer",
    "CompositeScoreResult",
    "composite_scorer",
    # Decay
    "DecayEngine",
    "DecayClass",
    "DecayResult",
    "decay_engine",
    # Freshness
    "FreshnessCalculator",
    "FreshnessFlag",
    "FreshnessResult",
    "freshness_calculator",
    # Industry
    "IndustryClassifier",
    "IndustryClassification",
    "industry_classifier",
]
