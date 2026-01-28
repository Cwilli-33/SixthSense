"""MCA detection logic for UCC filings."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.utils.config import config


@dataclass
class MCADetectionResult:
    """Result of MCA detection analysis."""

    is_mca_related: bool
    confidence: float  # 0-1 confidence score
    lender_match: Optional[str] = None
    pattern_match: Optional[str] = None
    exclusion_match: Optional[str] = None
    refinance_score: int = 0
    refinance_window: Optional[str] = None
    reasons: list[str] = None

    def __post_init__(self) -> None:
        if self.reasons is None:
            self.reasons = []


class MCADetector:
    """Detect MCA-related UCC filings."""

    def __init__(self) -> None:
        """Initialize the MCA detector with configuration."""
        self._lender_names = config.get_mca_lender_names()
        self._patterns = config.get_mca_detection_patterns()
        self._exclusions = config.get_exclusion_patterns()
        self._refinance_scoring = config.get_refinance_scoring()

        # Compile regex patterns for efficiency
        self._lender_patterns = [
            re.compile(re.escape(name), re.IGNORECASE)
            for name in self._lender_names
        ]
        self._secured_party_patterns = [
            re.compile(re.escape(p), re.IGNORECASE)
            for p in self._patterns.get("secured_party", [])
        ]
        self._collateral_patterns = [
            re.compile(re.escape(p), re.IGNORECASE)
            for p in self._patterns.get("collateral", [])
        ]
        self._exclusion_patterns = [
            re.compile(re.escape(p), re.IGNORECASE)
            for p in self._exclusions
        ]

    def detect(
        self,
        secured_party: str | None = None,
        collateral_description: str | None = None,
        filing_date: datetime | None = None,
    ) -> MCADetectionResult:
        """Detect if a UCC filing is MCA-related.

        Args:
            secured_party: Name of the secured party/lender
            collateral_description: Description of collateral
            filing_date: Date of the UCC filing (for refinance scoring)

        Returns:
            MCADetectionResult with detection details
        """
        result = MCADetectionResult(
            is_mca_related=False,
            confidence=0.0,
            reasons=[],
        )

        secured_party = secured_party or ""
        collateral_description = collateral_description or ""

        # Check for exclusions first
        exclusion = self._check_exclusions(collateral_description)
        if exclusion:
            result.exclusion_match = exclusion
            result.reasons.append(f"Excluded: matches '{exclusion}'")
            return result

        # Check for known MCA lenders
        lender_match = self._match_lender(secured_party)
        if lender_match:
            result.lender_match = lender_match
            result.is_mca_related = True
            result.confidence = 0.95
            result.reasons.append(f"Known MCA lender: {lender_match}")

        # Check for MCA patterns in secured party name
        party_pattern = self._match_secured_party_pattern(secured_party)
        if party_pattern:
            result.pattern_match = party_pattern
            result.is_mca_related = True
            result.confidence = max(result.confidence, 0.85)
            result.reasons.append(f"Secured party pattern: {party_pattern}")

        # Check for MCA patterns in collateral
        collateral_pattern = self._match_collateral_pattern(collateral_description)
        if collateral_pattern:
            if result.is_mca_related:
                # Strengthens existing MCA signal
                result.confidence = min(result.confidence + 0.05, 1.0)
            else:
                # Collateral pattern alone is weaker signal
                result.pattern_match = collateral_pattern
                result.confidence = 0.6
            result.reasons.append(f"Collateral pattern: {collateral_pattern}")

        # Check for all-assets indicator (strong MCA signal)
        if self._is_all_assets(collateral_description):
            if result.is_mca_related:
                result.confidence = min(result.confidence + 0.1, 1.0)
            else:
                result.is_mca_related = True
                result.confidence = max(result.confidence, 0.7)
            result.reasons.append("All-assets collateral")

        # Calculate refinance score if MCA-related and we have a filing date
        if result.is_mca_related and filing_date:
            refinance_score, window = self._calculate_refinance_score(filing_date)
            result.refinance_score = refinance_score
            result.refinance_window = window

        return result

    def _match_lender(self, secured_party: str) -> str | None:
        """Check if secured party matches a known MCA lender.

        Args:
            secured_party: Name to check

        Returns:
            Matched lender name or None
        """
        secured_party_lower = secured_party.lower()
        for pattern in self._lender_patterns:
            if pattern.search(secured_party_lower):
                # Return the original config name (properly cased)
                for name in config.mca_lenders.get("mca_lenders", []):
                    if name.lower() in secured_party_lower:
                        return name
                return pattern.pattern
        return None

    def _match_secured_party_pattern(self, secured_party: str) -> str | None:
        """Check for MCA patterns in secured party name.

        Args:
            secured_party: Name to check

        Returns:
            Matched pattern or None
        """
        for pattern in self._secured_party_patterns:
            if pattern.search(secured_party):
                return pattern.pattern
        return None

    def _match_collateral_pattern(self, collateral: str) -> str | None:
        """Check for MCA patterns in collateral description.

        Args:
            collateral: Description to check

        Returns:
            Matched pattern or None
        """
        for pattern in self._collateral_patterns:
            if pattern.search(collateral):
                return pattern.pattern
        return None

    def _check_exclusions(self, collateral: str) -> str | None:
        """Check if collateral matches exclusion patterns.

        Args:
            collateral: Description to check

        Returns:
            Matched exclusion pattern or None
        """
        for pattern in self._exclusion_patterns:
            if pattern.search(collateral):
                return pattern.pattern
        return None

    def _is_all_assets(self, collateral: str) -> bool:
        """Check if collateral description indicates all-assets filing.

        Args:
            collateral: Description to check

        Returns:
            True if all-assets indicator found
        """
        collateral_lower = collateral.lower()

        # Strong all-assets indicators
        all_assets_patterns = [
            "all assets",
            "all inventory",
            "all accounts",
            "all equipment",
            "all of debtor",
            "all tangible and intangible",
            "all present and future",
        ]

        return any(pattern in collateral_lower for pattern in all_assets_patterns)

    def _calculate_refinance_score(
        self,
        filing_date: datetime,
    ) -> tuple[int, str | None]:
        """Calculate refinance score based on UCC age.

        Args:
            filing_date: Original UCC filing date

        Returns:
            Tuple of (score, window_name)
        """
        now = datetime.now()
        months_since_filing = (
            (now.year - filing_date.year) * 12 +
            (now.month - filing_date.month)
        )

        for window_name, window_config in self._refinance_scoring.items():
            min_months = window_config.get("min_months", 0)
            max_months = window_config.get("max_months", 999)
            points = window_config.get("points", 0)

            if min_months <= months_since_filing < max_months:
                return points, window_name

        return 0, None

    def get_refinance_score_for_age(self, months: int) -> tuple[int, str | None]:
        """Get refinance score for a specific UCC age in months.

        Args:
            months: Age of UCC filing in months

        Returns:
            Tuple of (score, window_name)
        """
        for window_name, window_config in self._refinance_scoring.items():
            min_months = window_config.get("min_months", 0)
            max_months = window_config.get("max_months", 999)
            points = window_config.get("points", 0)

            if min_months <= months < max_months:
                return points, window_name

        return 0, None


# Singleton instance for convenience
mca_detector = MCADetector()
