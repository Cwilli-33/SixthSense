"""Industry classification based on business name analysis."""

import re
from dataclasses import dataclass
from typing import Optional

from src.utils.config import config


@dataclass
class IndustryClassification:
    """Result of industry classification."""

    industry: str
    propensity: int
    confidence: float
    matched_keywords: list[str]


class IndustryClassifier:
    """Classify businesses into industry verticals based on name analysis."""

    def __init__(self) -> None:
        """Initialize the classifier with industry configuration."""
        self._industries = config.get_industry_keywords()
        self._default_propensity = config.get_default_propensity()
        self._min_confidence = config.industries.get("min_confidence", 0.5)

        # Build keyword lookup for efficiency
        self._keyword_to_industry: dict[str, tuple[str, int]] = {}
        for industry_name, industry_data in self._industries.items():
            propensity = industry_data.get("propensity", self._default_propensity)
            for keyword in industry_data.get("keywords", []):
                keyword_lower = keyword.lower()
                # Store industry with highest propensity for keyword conflicts
                if keyword_lower not in self._keyword_to_industry:
                    self._keyword_to_industry[keyword_lower] = (industry_name, propensity)
                elif propensity > self._keyword_to_industry[keyword_lower][1]:
                    self._keyword_to_industry[keyword_lower] = (industry_name, propensity)

    def classify(
        self,
        business_name: str,
        dba_name: str | None = None,
    ) -> IndustryClassification:
        """Classify a business into an industry vertical.

        Args:
            business_name: Legal business name
            dba_name: DBA/trade name if available

        Returns:
            IndustryClassification with industry and propensity
        """
        # Combine names for analysis
        names_to_check = [business_name]
        if dba_name:
            names_to_check.append(dba_name)

        combined_text = " ".join(names_to_check).lower()

        # Remove common business suffixes for cleaner matching
        combined_text = self._clean_business_name(combined_text)

        # Find all matching keywords
        matches: dict[str, list[str]] = {}  # industry -> matched keywords

        for keyword, (industry, propensity) in self._keyword_to_industry.items():
            # Use word boundary matching for better accuracy
            pattern = rf"\b{re.escape(keyword)}\b"
            if re.search(pattern, combined_text):
                if industry not in matches:
                    matches[industry] = []
                matches[industry].append(keyword)

        if not matches:
            # No match found, return "other" with default propensity
            return IndustryClassification(
                industry="other",
                propensity=self._default_propensity,
                confidence=0.0,
                matched_keywords=[],
            )

        # Find best match (most keywords matched, highest propensity as tiebreaker)
        best_industry = None
        best_propensity = 0
        best_keywords: list[str] = []

        for industry, keywords in matches.items():
            industry_data = self._industries.get(industry, {})
            propensity = industry_data.get("propensity", self._default_propensity)

            # Score by: number of matches * propensity
            score = len(keywords) * propensity
            best_score = len(best_keywords) * best_propensity if best_keywords else 0

            if score > best_score or (score == best_score and propensity > best_propensity):
                best_industry = industry
                best_propensity = propensity
                best_keywords = keywords

        # Calculate confidence based on match quality
        confidence = self._calculate_confidence(best_keywords, combined_text)

        return IndustryClassification(
            industry=best_industry or "other",
            propensity=best_propensity,
            confidence=confidence,
            matched_keywords=best_keywords,
        )

    def _clean_business_name(self, name: str) -> str:
        """Remove common business suffixes and noise from name.

        Args:
            name: Business name to clean

        Returns:
            Cleaned name
        """
        # Common suffixes to remove
        suffixes = [
            r"\bllc\b",
            r"\bl\.l\.c\.\b",
            r"\binc\b",
            r"\bincorporated\b",
            r"\bcorp\b",
            r"\bcorporation\b",
            r"\bco\b",
            r"\bcompany\b",
            r"\bltd\b",
            r"\blimited\b",
            r"\bplc\b",
            r"\bllp\b",
            r"\blp\b",
            r"\bpc\b",
            r"\bpa\b",
            r"\bpllc\b",
            r"\bdba\b",
            r"\bd/b/a\b",
        ]

        cleaned = name
        for suffix in suffixes:
            cleaned = re.sub(suffix, "", cleaned)

        # Remove extra whitespace
        cleaned = " ".join(cleaned.split())

        return cleaned

    def _calculate_confidence(
        self,
        matched_keywords: list[str],
        text: str,
    ) -> float:
        """Calculate confidence score for classification.

        Args:
            matched_keywords: Keywords that matched
            text: Original text being classified

        Returns:
            Confidence score (0-1)
        """
        if not matched_keywords:
            return 0.0

        # Base confidence from number of matches
        base_confidence = min(0.5 + (len(matched_keywords) * 0.15), 0.95)

        # Bonus for longer keyword matches
        avg_keyword_len = sum(len(kw) for kw in matched_keywords) / len(matched_keywords)
        length_bonus = min(avg_keyword_len / 20, 0.2)

        # Penalty if text is very short (might be ambiguous)
        if len(text) < 10:
            base_confidence *= 0.8

        return min(base_confidence + length_bonus, 1.0)

    def get_propensity(self, industry: str) -> int:
        """Get propensity score for an industry.

        Args:
            industry: Industry name

        Returns:
            Propensity score (0-10)
        """
        industry_data = self._industries.get(industry.lower(), {})
        return industry_data.get("propensity", self._default_propensity)

    def list_industries(self) -> list[tuple[str, int]]:
        """List all configured industries with propensity scores.

        Returns:
            List of (industry_name, propensity) tuples sorted by propensity
        """
        industries = [
            (name, data.get("propensity", self._default_propensity))
            for name, data in self._industries.items()
        ]
        return sorted(industries, key=lambda x: x[1], reverse=True)


# Singleton instance
industry_classifier = IndustryClassifier()
