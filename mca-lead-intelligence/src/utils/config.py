"""Configuration loader for YAML config files."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    # Check for environment variable override
    config_dir = os.getenv("MCA_CONFIG_DIR")
    if config_dir:
        return Path(config_dir)

    # Default to project config directory
    return Path(__file__).parent.parent.parent / "config"


@lru_cache(maxsize=10)
def load_config(config_name: str) -> dict[str, Any]:
    """Load a YAML configuration file.

    Args:
        config_name: Name of config file (with or without .yaml extension)

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    config_dir = get_config_dir()

    # Add .yaml extension if not present
    if not config_name.endswith(".yaml"):
        config_name = f"{config_name}.yaml"

    config_path = config_dir / config_name

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def reload_config(config_name: str) -> dict[str, Any]:
    """Reload a configuration file, clearing the cache.

    Args:
        config_name: Name of config file

    Returns:
        Freshly loaded configuration dictionary
    """
    load_config.cache_clear()
    return load_config(config_name)


def get_mca_lenders_config() -> dict[str, Any]:
    """Get MCA lenders configuration."""
    return load_config("mca_lenders")


def get_industries_config() -> dict[str, Any]:
    """Get industries configuration."""
    return load_config("industries")


def get_scoring_config() -> dict[str, Any]:
    """Get scoring configuration."""
    return load_config("scoring")


class ConfigManager:
    """Centralized configuration management."""

    def __init__(self) -> None:
        self._mca_lenders: dict[str, Any] | None = None
        self._industries: dict[str, Any] | None = None
        self._scoring: dict[str, Any] | None = None

    @property
    def mca_lenders(self) -> dict[str, Any]:
        """Get MCA lenders config, loading if necessary."""
        if self._mca_lenders is None:
            self._mca_lenders = get_mca_lenders_config()
        return self._mca_lenders

    @property
    def industries(self) -> dict[str, Any]:
        """Get industries config, loading if necessary."""
        if self._industries is None:
            self._industries = get_industries_config()
        return self._industries

    @property
    def scoring(self) -> dict[str, Any]:
        """Get scoring config, loading if necessary."""
        if self._scoring is None:
            self._scoring = get_scoring_config()
        return self._scoring

    def reload_all(self) -> None:
        """Reload all configuration files."""
        load_config.cache_clear()
        self._mca_lenders = None
        self._industries = None
        self._scoring = None

    def get_mca_lender_names(self) -> list[str]:
        """Get list of known MCA lender names (lowercase for matching)."""
        return [name.lower() for name in self.mca_lenders.get("mca_lenders", [])]

    def get_mca_detection_patterns(self) -> dict[str, list[str]]:
        """Get MCA detection patterns."""
        patterns = self.mca_lenders.get("detection_patterns", {})
        return {
            "secured_party": [p.lower() for p in patterns.get("secured_party_patterns", [])],
            "collateral": [p.lower() for p in patterns.get("collateral_patterns", [])],
        }

    def get_exclusion_patterns(self) -> list[str]:
        """Get patterns that indicate NOT MCA-related."""
        return [p.lower() for p in self.mca_lenders.get("exclusion_patterns", [])]

    def get_refinance_scoring(self) -> dict[str, dict[str, Any]]:
        """Get refinance timing windows and scores."""
        return self.mca_lenders.get("refinance_scoring", {})

    def get_industry_keywords(self) -> dict[str, dict[str, Any]]:
        """Get industry classification keywords and propensity scores."""
        return self.industries.get("industries", {})

    def get_default_propensity(self) -> int:
        """Get default propensity score for unclassified industries."""
        return self.industries.get("default_propensity", 1)

    def get_priority_thresholds(self) -> dict[str, dict[str, Any]]:
        """Get priority level thresholds."""
        return self.scoring.get("priority_thresholds", {})

    def get_fit_components(self) -> dict[str, Any]:
        """Get FIT scoring components configuration."""
        return self.scoring.get("fit_components", {})

    def get_tib_thresholds(self) -> list[dict[str, Any]]:
        """Get time-in-business scoring thresholds."""
        fit_components = self.get_fit_components()
        tib_config = fit_components.get("time_in_business", {})
        return tib_config.get("thresholds", [])


# Global config manager instance
config = ConfigManager()
