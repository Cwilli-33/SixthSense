"""Florida UCC Filing Harvester.

Harvests UCC filings from Florida Secretary of State (Sunbiz.org).
Supports both web scraping and local file loading modes.
"""

import csv
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urljoin, urlencode

import httpx
from bs4 import BeautifulSoup, Tag

from src.harvesters.base import BaseHarvester
from src.harvesters.http_client import HarvestHTTPClient, RateLimiter, RetryConfig
from src.harvesters.mca_detector import MCADetector, mca_detector
from src.models.signal import SignalCreate, SignalMetadata, SignalType


class FloridaUCCHarvester(BaseHarvester):
    """Harvest UCC filings from Florida Secretary of State.

    This harvester supports two modes:
    1. Web scraping from sunbiz.org (production mode)
    2. Local file loading (development/testing mode)

    The local file mode supports CSV and JSON formats.
    """

    # Sunbiz.org URLs
    SUNBIZ_BASE_URL = "https://search.sunbiz.org"
    SUNBIZ_UCC_SEARCH = f"{SUNBIZ_BASE_URL}/Inquiry/UCCFiling"
    SUNBIZ_UCC_SEARCH_RESULTS = f"{SUNBIZ_BASE_URL}/Inquiry/UCCFilingSearch"
    SUNBIZ_UCC_DETAIL = f"{SUNBIZ_BASE_URL}/Inquiry/UCCFilingDetail"

    # Known date formats in Florida UCC data
    DATE_FORMATS = [
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%m-%d-%Y",
        "%Y/%m/%d",
        "%m/%d/%y",
        "%B %d, %Y",
    ]

    # Search types supported by Sunbiz
    SEARCH_TYPE_DEBTOR = "Debtor"
    SEARCH_TYPE_SECURED_PARTY = "SecuredParty"
    SEARCH_TYPE_FILING_NUMBER = "FilingNumber"

    def __init__(
        self,
        detector: MCADetector | None = None,
        logger: logging.Logger | None = None,
        timeout: float = 30.0,
        requests_per_minute: int = 20,
    ) -> None:
        """Initialize the Florida UCC harvester.

        Args:
            detector: MCA detector instance. Uses default if not provided.
            logger: Logger instance
            timeout: HTTP request timeout in seconds
            requests_per_minute: Rate limit for web requests
        """
        super().__init__(logger)
        self.detector = detector or mca_detector
        self.timeout = timeout
        self.requests_per_minute = requests_per_minute
        self._http_client: HarvestHTTPClient | None = None

    def _get_http_client(self) -> HarvestHTTPClient:
        """Get or create the HTTP client."""
        if self._http_client is None:
            self._http_client = HarvestHTTPClient(
                timeout=self.timeout,
                rate_limiter=RateLimiter(
                    requests_per_minute=self.requests_per_minute,
                    min_delay_seconds=2.0,
                    max_delay_seconds=5.0,
                ),
                retry_config=RetryConfig(
                    max_retries=3,
                    base_delay=5.0,
                ),
                logger=self.logger,
            )
        return self._http_client

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
                - search_term: Search term for web scraping
                - search_type: Type of search ("debtor", "secured_party", "filing_number")
                - known_mca_lenders: List of MCA lenders to search for

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
                **kwargs,
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
        """Parse UCC filings from CSV file."""
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
        """Parse UCC filings from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

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
        """Parse a single UCC record into a SignalCreate."""
        normalized = self._normalize_record(record)

        filing_date = self._parse_date(normalized.get("filing_date"))
        if filing_date is None:
            self.logger.warning(f"Could not parse date for record: {normalized}")
            return None

        if start_date and filing_date < start_date:
            return None
        if end_date and filing_date > end_date:
            return None

        filing_type_str = normalized.get("filing_type", "UCC-1").upper()
        signal_type = self._map_filing_type(filing_type_str)

        if filing_types and signal_type.value not in filing_types:
            return None

        secured_party = normalized.get("secured_party", "")
        collateral = normalized.get("collateral", "")
        business_name = normalized.get("debtor_name", "")
        filing_number = normalized.get("filing_number", "")

        detection = self.detector.detect(
            secured_party=secured_party,
            collateral_description=collateral,
            filing_date=filing_date,
        )

        if mca_only and not detection.is_mca_related:
            return None

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

        business_identifier = filing_number or f"FL-UCC-{business_name[:50]}"

        return SignalCreate(
            signal_type=signal_type,
            business_identifier=business_identifier,
            business_name=business_name,
            signal_date=filing_date,
            source=self.get_source_name(),
            state=self.get_state(),
            raw_data=record,
            metadata=metadata,
        )

    def _normalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Normalize field names from various formats."""
        mappings = {
            "filing_number": ["filing_number", "ucc_number", "file_number", "filingnumber", "number", "ucc_file_number"],
            "filing_date": ["filing_date", "date", "file_date", "filingdate", "filed_date", "date_filed"],
            "filing_type": ["filing_type", "type", "filetype", "ucc_type", "transaction_type"],
            "debtor_name": ["debtor_name", "business_name", "name", "debtor", "debtorname", "debtor_organization_name"],
            "debtor_address": ["debtor_address", "address", "debtoraddress", "debtor_addr", "debtor_mailing_address"],
            "secured_party": ["secured_party", "lender", "creditor", "securedparty", "secured", "secured_party_name"],
            "secured_party_address": ["secured_party_address", "lender_address", "securedpartyaddress", "sp_address"],
            "collateral": ["collateral", "collateral_description", "collateraldescription", "collateral_desc"],
            "lapse_date": ["lapse_date", "expiration_date", "lapsedate", "expires", "expiry_date"],
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
        """Parse a date string in various formats."""
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
        """Map UCC filing type string to SignalType enum."""
        filing_type_upper = filing_type.upper()

        if "TERMINATION" in filing_type_upper or "TERM" in filing_type_upper:
            return SignalType.UCC_TERMINATION
        elif "AMENDMENT" in filing_type_upper or "AMD" in filing_type_upper:
            return SignalType.UCC_AMENDMENT
        elif "CONTINUATION" in filing_type_upper or "CONT" in filing_type_upper:
            return SignalType.UCC_CONTINUATION
        elif "UCC-3" in filing_type_upper or "UCC3" in filing_type_upper:
            return SignalType.UCC_AMENDMENT
        else:
            return SignalType.UCC_FILING

    # =========================================================================
    # WEB SCRAPING METHODS
    # =========================================================================

    def _harvest_from_web(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        mca_only: bool,
        filing_types: list[str] | None,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Harvest UCC filings from Sunbiz.org website.

        This method implements web scraping with the following strategy:
        1. If known_mca_lenders provided, search each lender as secured party
        2. If search_term provided, use that for search
        3. Otherwise, search recent filings by date range

        Args:
            start_date: Start date filter
            end_date: End date filter
            mca_only: Filter for MCA-related only
            filing_types: Filter for specific filing types
            **kwargs: Additional options

        Yields:
            SignalCreate objects
        """
        search_term = kwargs.get("search_term")
        search_type = kwargs.get("search_type", "secured_party")
        known_mca_lenders = kwargs.get("known_mca_lenders")

        self.logger.info("Starting web harvest from Sunbiz.org")

        http_client = self._get_http_client()

        try:
            if known_mca_lenders:
                self.logger.info(f"Searching for {len(known_mca_lenders)} known MCA lenders")
                for lender in known_mca_lenders:
                    self.logger.info(f"Searching secured party: {lender}")
                    yield from self._search_and_parse(
                        http_client,
                        search_term=lender,
                        search_type=self.SEARCH_TYPE_SECURED_PARTY,
                        start_date=start_date,
                        end_date=end_date,
                        mca_only=mca_only,
                        filing_types=filing_types,
                    )

            elif search_term:
                sunbiz_search_type = self._map_search_type(search_type)
                self.logger.info(f"Searching {search_type}: {search_term}")
                yield from self._search_and_parse(
                    http_client,
                    search_term=search_term,
                    search_type=sunbiz_search_type,
                    start_date=start_date,
                    end_date=end_date,
                    mca_only=mca_only,
                    filing_types=filing_types,
                )

            else:
                self.logger.info("No search term provided, using top MCA lenders from config")
                top_lenders = self._get_top_mca_lenders()
                for lender in top_lenders:
                    self.logger.info(f"Searching secured party: {lender}")
                    yield from self._search_and_parse(
                        http_client,
                        search_term=lender,
                        search_type=self.SEARCH_TYPE_SECURED_PARTY,
                        start_date=start_date,
                        end_date=end_date,
                        mca_only=mca_only,
                        filing_types=filing_types,
                    )

        except Exception as e:
            self.logger.error(f"Web harvest failed: {e}")
            raise

    def _map_search_type(self, search_type: str) -> str:
        """Map user-friendly search type to Sunbiz search type."""
        mapping = {
            "debtor": self.SEARCH_TYPE_DEBTOR,
            "secured_party": self.SEARCH_TYPE_SECURED_PARTY,
            "secured": self.SEARCH_TYPE_SECURED_PARTY,
            "lender": self.SEARCH_TYPE_SECURED_PARTY,
            "filing_number": self.SEARCH_TYPE_FILING_NUMBER,
            "filing": self.SEARCH_TYPE_FILING_NUMBER,
            "number": self.SEARCH_TYPE_FILING_NUMBER,
        }
        return mapping.get(search_type.lower(), self.SEARCH_TYPE_DEBTOR)

    def _get_top_mca_lenders(self, limit: int = 20) -> list[str]:
        """Get list of top MCA lenders to search for."""
        top_lenders = [
            "OnDeck Capital",
            "Credibly",
            "Rapid Finance",
            "BlueVine",
            "Kabbage",
            "Forward Financing",
            "Fundbox",
            "Square Capital",
            "CAN Capital",
            "National Funding",
            "Libertas Funding",
            "Pearl Capital",
            "Yellowstone Capital",
            "Merchant Cash and Capital",
            "Capify",
            "Greenbox Capital",
            "Reliant Funding",
            "Everest Business Funding",
            "QuickBridge",
            "Clearview Funding",
        ]
        return top_lenders[:limit]

    def _search_and_parse(
        self,
        http_client: HarvestHTTPClient,
        search_term: str,
        search_type: str,
        start_date: datetime | None,
        end_date: datetime | None,
        mca_only: bool,
        filing_types: list[str] | None,
        max_pages: int = 50,
    ) -> Iterator[SignalCreate]:
        """Execute search and parse results with pagination."""
        page = 1
        seen_filing_numbers = set()

        while page <= max_pages:
            try:
                search_params = {
                    "searchType": search_type,
                    "searchTerm": search_term,
                    "page": page,
                }

                response = http_client.get(
                    self.SUNBIZ_UCC_SEARCH_RESULTS,
                    params=search_params,
                )

                soup = BeautifulSoup(response.text, "html.parser")
                records = self._parse_search_results_page(soup)

                if not records:
                    self.logger.info(f"No more results on page {page}")
                    break

                self.logger.info(f"Found {len(records)} records on page {page}")

                for record in records:
                    filing_number = record.get("filing_number", "")

                    if filing_number in seen_filing_numbers:
                        continue
                    seen_filing_numbers.add(filing_number)

                    if filing_number:
                        try:
                            full_record = self._fetch_filing_details(http_client, filing_number)
                            if full_record:
                                record.update(full_record)
                        except Exception as e:
                            self.logger.warning(f"Could not fetch details for {filing_number}: {e}")

                    signal = self._parse_ucc_record(
                        record,
                        start_date,
                        end_date,
                        mca_only,
                        filing_types,
                    )

                    if signal:
                        yield signal

                if not self._has_next_page(soup):
                    break

                page += 1

            except Exception as e:
                self.logger.error(f"Error fetching page {page}: {e}")
                break

    def _parse_search_results_page(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Parse search results page HTML."""
        records = []

        table = soup.find("table", {"class": re.compile(r"(results|data|filing)", re.I)})
        if not table:
            table = soup.find("table", {"id": re.compile(r"(results|data|filing)", re.I)})
        if not table:
            tables = soup.find_all("table")
            for t in tables:
                if t.find(string=re.compile(r"(filing|debtor|secured)", re.I)):
                    table = t
                    break

        if not table:
            self.logger.debug("No results table found")
            return records

        rows = table.find_all("tr")
        headers = []

        for row in rows:
            header_cells = row.find_all("th")
            if header_cells:
                headers = [self._normalize_header(th.get_text(strip=True)) for th in header_cells]
                continue

            cells = row.find_all("td")
            if not cells:
                continue

            record = {}
            for i, cell in enumerate(cells):
                if i < len(headers):
                    key = headers[i]
                else:
                    key = f"col_{i}"

                text = cell.get_text(strip=True)
                link = cell.find("a")

                record[key] = text
                if link and link.get("href"):
                    record[f"{key}_link"] = link.get("href")

            if record:
                records.append(record)

        return records

    def _normalize_header(self, header: str) -> str:
        """Normalize table header to field name."""
        header_lower = header.lower().strip()
        mappings = {
            "file number": "filing_number",
            "filing number": "filing_number",
            "ucc number": "filing_number",
            "file date": "filing_date",
            "filing date": "filing_date",
            "date": "filing_date",
            "type": "filing_type",
            "filing type": "filing_type",
            "debtor": "debtor_name",
            "debtor name": "debtor_name",
            "secured party": "secured_party",
            "secured": "secured_party",
            "lender": "secured_party",
            "status": "status",
        }

        return mappings.get(header_lower, header_lower.replace(" ", "_"))

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if there's a next page of results."""
        next_link = soup.find("a", string=re.compile(r"(next|>>|>)", re.I))
        if next_link and "disabled" not in next_link.get("class", []):
            return True

        pagination = soup.find(class_=re.compile(r"pagination", re.I))
        if pagination:
            current = pagination.find(class_=re.compile(r"(active|current)", re.I))
            if current and current.find_next_sibling("a"):
                return True

        return False

    def _fetch_filing_details(
        self,
        http_client: HarvestHTTPClient,
        filing_number: str,
    ) -> dict[str, Any] | None:
        """Fetch full details for a specific filing."""
        try:
            response = http_client.get(
                self.SUNBIZ_UCC_DETAIL,
                params={"filingNumber": filing_number},
            )

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_filing_detail_page(soup)

        except Exception as e:
            self.logger.warning(f"Error fetching filing details: {e}")
            return None

    def _parse_filing_detail_page(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Parse filing detail page HTML."""
        details = {}

        for dl in soup.find_all("dl"):
            dt_elements = dl.find_all("dt")
            dd_elements = dl.find_all("dd")
            for dt, dd in zip(dt_elements, dd_elements):
                key = self._normalize_header(dt.get_text(strip=True))
                value = dd.get_text(strip=True)
                details[key] = value

        for div in soup.find_all("div", class_=re.compile(r"(detail|info|field)", re.I)):
            label = div.find(class_=re.compile(r"label", re.I))
            value = div.find(class_=re.compile(r"value", re.I))
            if label and value:
                key = self._normalize_header(label.get_text(strip=True))
                details[key] = value.get_text(strip=True)

        for table in soup.find_all("table", class_=re.compile(r"(detail|info)", re.I)):
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["th", "td"])
                if len(cells) >= 2:
                    key = self._normalize_header(cells[0].get_text(strip=True))
                    value = cells[1].get_text(strip=True)
                    details[key] = value

        collateral_section = soup.find(string=re.compile(r"collateral", re.I))
        if collateral_section:
            parent = collateral_section.find_parent(["div", "section", "td"])
            if parent:
                collateral_text = parent.get_text(strip=True)
                if "Collateral" in collateral_text:
                    collateral_text = collateral_text.split("Collateral", 1)[-1].strip()
                    collateral_text = collateral_text.lstrip(":").strip()
                    details["collateral"] = collateral_text

        return details

    # =========================================================================
    # CONVENIENCE SEARCH METHODS
    # =========================================================================

    def search_by_debtor_name(
        self,
        name: str,
        exact_match: bool = False,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        mca_only: bool = False,
    ) -> Iterator[SignalCreate]:
        """Search for UCC filings by debtor name."""
        self.logger.info(f"Searching for debtor: {name}")

        http_client = self._get_http_client()

        yield from self._search_and_parse(
            http_client,
            search_term=name,
            search_type=self.SEARCH_TYPE_DEBTOR,
            start_date=start_date,
            end_date=end_date,
            mca_only=mca_only,
            filing_types=None,
        )

    def search_by_secured_party(
        self,
        name: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        mca_only: bool = False,
    ) -> Iterator[SignalCreate]:
        """Search for UCC filings by secured party name."""
        self.logger.info(f"Searching for secured party: {name}")

        http_client = self._get_http_client()

        yield from self._search_and_parse(
            http_client,
            search_term=name,
            search_type=self.SEARCH_TYPE_SECURED_PARTY,
            start_date=start_date,
            end_date=end_date,
            mca_only=mca_only,
            filing_types=None,
        )

    def get_filing_details(
        self,
        filing_number: str,
    ) -> SignalCreate | None:
        """Get details for a specific UCC filing."""
        self.logger.info(f"Getting details for filing: {filing_number}")

        http_client = self._get_http_client()

        try:
            record = self._fetch_filing_details(http_client, filing_number)
            if record:
                record["filing_number"] = filing_number
                return self._parse_ucc_record(
                    record,
                    start_date=None,
                    end_date=None,
                    mca_only=False,
                    filing_types=None,
                )
        except Exception as e:
            self.logger.error(f"Error fetching filing details: {e}")

        return None

    def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None
