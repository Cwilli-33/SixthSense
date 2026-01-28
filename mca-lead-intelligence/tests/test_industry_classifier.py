"""Tests for industry classification."""

import pytest

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scoring.industry_classifier import IndustryClassifier


class TestIndustryClassifier:
    """Tests for industry classification from business names."""

    @pytest.fixture
    def classifier(self) -> IndustryClassifier:
        """Create classifier instance."""
        return IndustryClassifier()

    # Restaurant tests
    def test_classify_restaurant(self, classifier: IndustryClassifier) -> None:
        """Test restaurant classification."""
        result = classifier.classify("Mario's Italian Restaurant LLC")
        assert result.industry == "restaurants"
        assert result.propensity == 10

    def test_classify_pizza(self, classifier: IndustryClassifier) -> None:
        """Test pizza shop classification."""
        result = classifier.classify("Tony's Pizzeria Inc")
        assert result.industry == "restaurants"
        assert result.propensity == 10

    def test_classify_bar(self, classifier: IndustryClassifier) -> None:
        """Test bar classification."""
        result = classifier.classify("The Local Bar and Grill")
        assert result.industry == "restaurants"
        assert result.propensity == 10

    def test_classify_cafe(self, classifier: IndustryClassifier) -> None:
        """Test cafe classification."""
        result = classifier.classify("Sunrise Cafe & Bakery")
        assert result.industry == "restaurants"

    # Trucking tests
    def test_classify_trucking(self, classifier: IndustryClassifier) -> None:
        """Test trucking classification."""
        result = classifier.classify("ABC Trucking Services LLC")
        assert result.industry == "trucking"
        assert result.propensity == 10

    def test_classify_freight(self, classifier: IndustryClassifier) -> None:
        """Test freight company classification."""
        result = classifier.classify("Fast Freight Logistics Inc")
        assert result.industry == "trucking"
        assert result.propensity == 10

    def test_classify_transport(self, classifier: IndustryClassifier) -> None:
        """Test transport company classification."""
        result = classifier.classify("National Transport Company")
        assert result.industry == "trucking"

    # Construction tests
    def test_classify_construction(self, classifier: IndustryClassifier) -> None:
        """Test construction classification."""
        result = classifier.classify("Smith Construction LLC")
        assert result.industry == "construction"
        assert result.propensity == 10

    def test_classify_roofing(self, classifier: IndustryClassifier) -> None:
        """Test roofing contractor classification."""
        result = classifier.classify("Top Quality Roofing Contractors")
        assert result.industry == "construction"

    def test_classify_plumbing(self, classifier: IndustryClassifier) -> None:
        """Test plumbing classification."""
        result = classifier.classify("Expert Plumbing Services LLC")
        assert result.industry == "construction"

    # HVAC tests
    def test_classify_hvac(self, classifier: IndustryClassifier) -> None:
        """Test HVAC classification."""
        result = classifier.classify("Cool Air HVAC Services")
        assert result.industry == "hvac"
        assert result.propensity == 10

    def test_classify_heating_cooling(self, classifier: IndustryClassifier) -> None:
        """Test heating/cooling classification."""
        result = classifier.classify("Superior Heating and Cooling Inc")
        assert result.industry == "hvac"

    # Auto services tests
    def test_classify_auto_repair(self, classifier: IndustryClassifier) -> None:
        """Test auto repair classification."""
        result = classifier.classify("Joe's Auto Repair Shop")
        assert result.industry == "auto_services"
        assert result.propensity == 8

    def test_classify_car_wash(self, classifier: IndustryClassifier) -> None:
        """Test car wash classification."""
        result = classifier.classify("Sparkle Car Wash LLC")
        assert result.industry == "auto_services"

    # Retail tests
    def test_classify_retail_store(self, classifier: IndustryClassifier) -> None:
        """Test retail store classification."""
        result = classifier.classify("Main Street Retail Store")
        assert result.industry == "retail"
        assert result.propensity == 8

    def test_classify_boutique(self, classifier: IndustryClassifier) -> None:
        """Test boutique classification."""
        result = classifier.classify("Fashion Boutique LLC")
        assert result.industry == "retail"

    # Healthcare tests
    def test_classify_dental(self, classifier: IndustryClassifier) -> None:
        """Test dental office classification."""
        result = classifier.classify("Smile Dental Clinic")
        assert result.industry == "healthcare"
        assert result.propensity == 8

    def test_classify_medical(self, classifier: IndustryClassifier) -> None:
        """Test medical clinic classification."""
        result = classifier.classify("City Medical Associates PC")
        assert result.industry == "healthcare"

    # Salon tests
    def test_classify_salon(self, classifier: IndustryClassifier) -> None:
        """Test hair salon classification."""
        result = classifier.classify("Beautiful Hair Salon")
        assert result.industry == "salon_spa"
        assert result.propensity == 8

    def test_classify_spa(self, classifier: IndustryClassifier) -> None:
        """Test spa classification."""
        result = classifier.classify("Serenity Day Spa LLC")
        assert result.industry == "salon_spa"

    # Moderate propensity tests
    def test_classify_landscaping(self, classifier: IndustryClassifier) -> None:
        """Test landscaping classification."""
        result = classifier.classify("Green Thumb Landscaping LLC")
        assert result.industry == "landscaping"
        assert result.propensity == 5

    def test_classify_manufacturing(self, classifier: IndustryClassifier) -> None:
        """Test manufacturing classification."""
        result = classifier.classify("Precision Manufacturing Inc")
        assert result.industry == "manufacturing"
        assert result.propensity == 5

    # Lower propensity tests
    def test_classify_consulting(self, classifier: IndustryClassifier) -> None:
        """Test consulting classification."""
        result = classifier.classify("Strategic Business Consulting LLC")
        assert result.industry == "consulting"
        assert result.propensity == 2

    def test_classify_technology(self, classifier: IndustryClassifier) -> None:
        """Test technology classification."""
        result = classifier.classify("Tech Solutions Software Inc")
        assert result.industry == "technology"
        assert result.propensity == 2

    # Edge cases
    def test_classify_unknown(self, classifier: IndustryClassifier) -> None:
        """Test unknown/other classification."""
        result = classifier.classify("XYZ Holdings Group LLC")
        assert result.industry == "other"
        assert result.propensity == 1

    def test_classify_with_dba(self, classifier: IndustryClassifier) -> None:
        """Test classification using DBA name."""
        result = classifier.classify(
            "ABC Holdings LLC",
            dba_name="Joe's Pizza Palace",
        )
        assert result.industry == "restaurants"

    def test_classify_removes_suffixes(self, classifier: IndustryClassifier) -> None:
        """Test that business suffixes are removed."""
        result = classifier.classify("Best Restaurant LLC")
        assert result.industry == "restaurants"

        result = classifier.classify("Best Restaurant Inc")
        assert result.industry == "restaurants"

        result = classifier.classify("Best Restaurant Corporation")
        assert result.industry == "restaurants"

    def test_confidence_multiple_keywords(self, classifier: IndustryClassifier) -> None:
        """Test that multiple keyword matches increase confidence."""
        result = classifier.classify("Italian Restaurant and Bar LLC")
        assert result.confidence > 0.5
        assert len(result.matched_keywords) >= 2

    def test_propensity_lookup(self, classifier: IndustryClassifier) -> None:
        """Test direct propensity lookup."""
        assert classifier.get_propensity("restaurants") == 10
        assert classifier.get_propensity("trucking") == 10
        assert classifier.get_propensity("consulting") == 2
        assert classifier.get_propensity("unknown_industry") == 1

    def test_list_industries(self, classifier: IndustryClassifier) -> None:
        """Test listing all industries."""
        industries = classifier.list_industries()
        assert len(industries) > 0

        # Should be sorted by propensity (highest first)
        propensities = [p for _, p in industries]
        assert propensities == sorted(propensities, reverse=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
