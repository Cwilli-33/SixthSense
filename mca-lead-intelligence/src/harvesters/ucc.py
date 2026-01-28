"""Florida UCC Filing Harvester.

Harvests UCC filings from Florida Secretary of State (Sunbiz.org).
Supports both web scraping and local file loading modes.
"""

import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import httpx
from bs4 import BeautifulSoup, Tag

from src.harvesters.base import BaseHarvester
from src.harvesters.mca_detector import MCADetector, mca_detector
from src.models.signal import SignalCreate, SignalMetadata, SignalType


class FloridaUCCHarvester(BaseHarvester):
    """Harvest UCC filings from Florida Secretary of State.

    This harvester supports two modes:
    1. Web scraping from sunbiz.org (production mode)
    2. Local file loading (development/testing mode)

    The local file mode supports CSV and JSON formats.
    """

    SUNBIZ_BASE_URL = "https://search.sunbiz.org"
    SUNBIZ_UCC_SEARCH = f"{SUNBIZ_BASE_URL}/Inquiry/UCCFiling"

    # Known date formats in Florida UCC data
    DATE_FORMATS = [
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%m-%d-%Y",
        "%Y/%m/%d",
    ]

    def __init__(
        self,
        detector: MCADetector | None = None,
        logger: logging.Logger | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the Florida UCC harvester.

        Args:
            detector: MCA detector instance. Uses default if not provided.
            logger: Logger instance
            timeout: HTTP request timeout in seconds
        """
        super().__init__(logger)
        self.detector = detector or mca_detector
        self.timeout = timeout
        self._client: httpx.Client | None = None

    def get_source_name(self) -> str:
        return "FL_SOS"

    def get_state(self) -> str:
        return "FL"

    def get_supported_signal_types(self) -> list[SignalType]:
        return [
            SignalType.UCC_FILING,
            SignalType.UCC_TERMINATION,
            SignalType.UCC_AMENDMENT,
            SignalType.UCC_CONTINUATION,
        ]

    def harvest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Harvest UCC filings.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            **kwargs: Additional parameters:
                - file_path: Path to local data file (CSV/JSON)
                - mca_only: If True, only yield MCA-related filings
                - filing_types: List of filing types to include

        Yields:
            SignalCreate objects for each UCC filing
        """
        self.validate_date_range(start_date, end_date)

        file_path = kwargs.get("file_path")
        mca_only = kwargs.get("mca_only", False)
        filing_types = kwargs.get("filing_types")

        if file_path:
            # Local file mode
            yield from self._harvest_from_file(
                file_path,
                start_date,
                end_date,
                mca_only,
                filing_types,
            )
        else:
            # Web scraping mode
            yield from self._harvest_from_web(
                start_date,
                end_date,
                mca_only,
                filing_types,
            )

    def _harvest_from_file(
        self,
        file_path: str | Path,
        start_date: datetime | None,
        end_date: datetime | None,
        mca_only: bool,
        filing_types: list[str] | None,
    ) -> Iterator[SignalCreate]:
        """Harvest from a local data file.

        Args:
            file_path: Path to CSV or JSON file
            start_date: Start date filter
            end_date: End date filter
            mca_only: Filter for MCA-related only
            filing_types: Filter for specific filing types

        Yields:
            SignalCreate objects
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        self.logger.info(f"Harvesting from local file: {path}")

        if path.suffix.lower() == ".csv":
            yield from self._parse_csv_file(
                path, start_date, end_date, mca_only, filing_types
            )
        elif path.suffix.lower() == ".json":
            yield from self._parse_json_file(
                path, start_date, end_date, mca_only, filing_types
            )
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

    def _parse_csv_file(
        self,
        path: Path,
        start_date: datetime | None,
        end_date: datetime | None,
        mca_only: bool,
        filing_types: list[str] | None,
    ) -> Iterator[SignalCreate]:
        """Parse UCC filings from CSV file.

        Expected CSV columns (flexible naming):
        - filing_number / ucc_number / file_number
        - filing_date / date / file_date
        - filing_type / type
        - debtor_name / business_name / name
        - debtor_address / address
        - secured_party / lender / creditor
        - collateral / collateral_description

        Args:
            path: Path to CSV file
            start_date: Start date filter
            end_date: End date filter
            mca_only: Filter for MCA-related only
            filing_types: Filter for specific filing types

        Yields:
            SignalCreate objects
        """
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    signal = self._parse_ucc_record(row, start_date, end_date, mca_only, filing_types)
                    if signal:
                        yield signal
                except Exception as e:
                    self.logger.warning(f"Error parsing row: {e}")
                    continue

    def _parse_json_file(
        self,
        path: Path,
        start_date: datetime | None,
        end_date: datetime | None,
        mca_only: bool,
        filing_types: list[str] | None,
    ) -> Iterator[SignalCreate]:
        """Parse UCC filings from JSON file.

        Args:
            path: Path to JSON file
            start_date: Start date filter
            end_date: End date filter
            mca_only: Filter for MCA-related only
            filing_types: Filter for specific filing types

        Yields:
            SignalCreate objects
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle both list of records and dict with "filings" key
        records = data if isinstance(data, list) else data.get("filings", [])

        for record in records:
            try:
                signal = self._parse_ucc_record(record, start_date, end_date, mca_only, filing_types)
                if signal:
                    yield signal
            except Exception as e:
                self.logger.warning(f"Error parsing record: {e}")
                continue

    def _parse_ucc_record(
        self,
        record: dict[str, Any],
        start_date: datetime | None,
        end_date: datetime | None,
        mca_only: bool,
        filing_types: list[str] | None,
    ) -> SignalCreate | None:
        """Parse a single UCC record into a SignalCreate.

        Args:
            record: Raw UCC record data
            start_date: Start date filter
            end_date: End date filter
            mca_only: Filter for MCA-related only
            filing_types: Filter for specific filing types

        Returns:
            SignalCreate or None if filtered out
        """
        # Normalize field names (handle various CSV column names)
        normalized = self._normalize_record(record)

        # Parse filing date
        filing_date = self._parse_date(normalized.get("filing_date"))
        if filing_date is None:
            self.logger.warning(f"Could not parse date for record: {normalized}")
            return None

        # Apply date filters
        if start_date and filing_date < start_date:
            return None
        if end_date and filing_date > end_date:
            return None

        # Determine signal type
        filing_type_str = normalized.get("filing_type", "UCC-1").upper()
        signal_type = self._map_filing_type(filing_type_str)

        # Apply filing type filter
        if filing_types and signal_type.value not in filing_types:
            return None

        # Extract key fields
        secured_party = normalized.get("secured_party", "")
        collateral = normalized.get("collateral", "")
        business_name = normalized.get("debtor_name", "")
        filing_number = normalized.get("filing_number", "")

        # Run MCA detection
        detection = self.detector.detect(
            secured_party=secured_party,
            collateral_description=collateral,
            filing_date=filing_date,
        )

        # Apply MCA filter
        if mca_only and not detection.is_mca_related:
            return None

        # Build metadata
        metadata = SignalMetadata(
            filing_number=filing_number,
            filing_type=filing_type_str,
            secured_party=secured_party,
            secured_party_address=normalized.get("secured_party_address"),
            collateral_description=collateral,
            original_filing_date=filing_date,
            lapse_date=self._parse_date(normalized.get("lapse_date")),
            is_mca_related=detection.is_mca_related,
            mca_lender_match=detection.lender_match,
            mca_pattern_match=detection.pattern_match,
        )

        # Create business identifier from filing number or generate one
        business_identifier = filing_number or f"FL-UCC-{business_name[:50]}"

        return SignalCreate(
            signal_type=signal_type,
            business_identifier=business_identifier,
            business_name=business_name,
            signal_date=filing_date,
            source=self.get_source_name(),
            state=self.get_state(),
            raw_data=record,  # Store original record
            metadata=metadata,
        )

    def _normalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Normalize field names from various formats.

        Args:
            record: Raw record with potentially varying field names

        Returns:
            Normalized record with standard field names
        """
        # Field name mappings
        mappings = {
            "filing_number": ["filing_number", "ucc_number", "file_number", "filingnumber", "number"],
            "filing_date": ["filing_date", "date", "file_date", "filingdate", "filed_date"],
            "filing_type": ["filing_type", "type", "filetype", "ucc_type"],
            "debtor_name": ["debtor_name", "business_name", "name", "debtor", "debtorname"],
            "debtor_address": ["debtor_address", "address", "debtoraddress", "debtor_addr"],
            "secured_party": ["secured_party", "lender", "creditor", "securedparty", "secured"],
            "secured_party_address": ["secured_party_address", "lender_address", "securedpartyaddress"],
            "collateral": ["collateral", "collateral_description", "collateraldescription", "collateral_desc"],
            "lapse_date": ["lapse_date", "expiration_date", "lapsedate", "expires"],
        }

        normalized = {}
        record_lower = {k.lower().replace(" ", "_"): v for k, v in record.items()}

        for standard_name, variations in mappings.items():
            for variant in variations:
                if variant in record_lower:
                    normalized[standard_name] = record_lower[variant]
                    break

        return normalized

    def _parse_date(self, date_str: Any) -> datetime | None:
        """Parse a date string in various formats.

        Args:
            date_str: Date string or datetime object

        Returns:
            Parsed datetime or None if invalid
        """
        if date_str is None:
            return None

        if isinstance(date_str, datetime):
            return date_str

        date_str = str(date_str).strip()
        if not date_str:
            return None

        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        self.logger.warning(f"Could not parse date: {date_str}")
        return None

    def _map_filing_type(self, filing_type: str) -> SignalType:
        """Map UCC filing type string to SignalType enum.

        Args:
            filing_type: Filing type string (e.g., "UCC-1", "UCC-3")

        Returns:
            Corresponding SignalType
        """
        filing_type_upper = filing_type.upper()

        if "TERMINATION" in filing_type_upper or "TERM" in filing_type_upper:
            return SignalType.UCC_TERMINATION
        elif "AMENDMENT" in filing_type_upper or "AMD" in filing_type_upper:
            return SignalType.UCC_AMENDMENT
        elif "CONTINUATION" in filing_type_upper or "CONT" in filing_type_upper:
            return SignalType.UCC_CONTINUATION
        elif "UCC-3" in filing_type_upper or "UCC3" in filing_type_upper:
            # UCC-3 can be termination, amendment, or continuation
            # Default to amendment if not specified
            return SignalType.UCC_AMENDMENT
        else:
            # UCC-1 or unknown -> new filing
            return SignalType.UCC_FILING

    def _harvest_from_web(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        mca_only: bool,
        filing_types: list[str] | None,
    ) -> Iterator[SignalCreate]:
        """Harvest UCC filings from Sunbiz.org website.

        Note: This is a placeholder for web scraping functionality.
        Full implementation requires:
        1. Session management and rate limiting
        2. Search form submission
        3. Result pagination handling
        4. Anti-bot detection handling

        Args:
            start_date: Start date filter
            end_date: End date filter
            mca_only: Filter for MCA-related only
            filing_types: Filter for specific filing types

        Yields:
            SignalCreate objects
        """
        self.logger.warning(
            "Web harvesting from Sunbiz.org is not fully implemented. "
            "Use file_path parameter to load local data files."
        )

        # Placeholder: In production, this would:
        # 1. Create HTTP session with proper headers
        # 2. Navigate to search page
        # 3. Submit search parameters
        # 4. Parse and paginate results
        # 5. Yield SignalCreate for each record

        # For now, yield nothing and log a warning
        return
        yield  # Make this a generator

    def search_by_debtor_name(
        self,
        name: str,
        exact_match: bool = False,
    ) -> Iterator[SignalCreate]:
        """Search for UCC filings by debtor name.

        Args:
            name: Debtor/business name to search
            exact_match: If True, require exact name match

        Yields:
            SignalCreate objects matching the search
        """
        self.logger.info(f"Searching for debtor: {name}")

        # This would implement name-based search
        # Currently a placeholder
        return
        yield

    def search_by_secured_party(
        self,
        name: str,
    ) -> Iterator[SignalCreate]:
        """Search for UCC filings by secured party name.

        Useful for finding all filings from a specific MCA lender.

        Args:
            name: Secured party name to search

        Yields:
            SignalCreate objects matching the search
        """
        self.logger.info(f"Searching for secured party: {name}")

        # This would implement secured party search
        # Currently a placeholder
        return
        yield

    def get_filing_details(
        self,
        filing_number: str,
    ) -> SignalCreate | None:
        """Get details for a specific UCC filing.

        Args:
            filing_number: UCC filing number

        Returns:
            SignalCreate with filing details or None if not found
        """
        self.logger.info(f"Getting details for filing: {filing_number}")

        # This would implement single filing lookup
        # Currently a placeholder
        return None
