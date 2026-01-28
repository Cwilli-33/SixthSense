"""Multi-State UCC Harvester for comprehensive UCC filing coverage.

Provides unified interface for harvesting UCC filings from multiple states:
- Florida (Sunbiz.org)
- New York (NY DOS)
- Texas (TX SOS)
- California (CA SOS)
- Additional states as needed

Each state has different portal interfaces and data formats, but this
harvester provides a consistent output format for downstream processing.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator
from urllib.parse import quote_plus, urlencode

from src.harvesters.base import BaseHarvester, HarvestResult
from src.harvesters.http_client import HarvestHTTPClient, RateLimiter
from src.harvesters.mca_detector import mca_detector
from src.models.signal import SignalCreate, SignalMetadata


@dataclass
class UCCFiling:
    """Standardized UCC filing record."""

    filing_number: str
    debtor_name: str
    secured_party: str
    filing_date: datetime
    state: str
    filing_type: str = "UCC-1"  # UCC-1, UCC-3, Amendment, Termination
    collateral_description: str | None = None
    lapse_date: datetime | None = None
    status: str = "active"
    debtor_address: str | None = None
    source_url: str | None = None


class StateUCCHarvester(ABC):
    """Abstract base class for state-specific UCC harvesters."""

    STATE_CODE: str = ""
    PORTAL_URL: str = ""

    def __init__(
        self,
        http_client: HarvestHTTPClient,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize state harvester.

        Args:
            http_client: Shared HTTP client
            logger: Logger instance
        """
        self.http_client = http_client
        self.logger = logger or logging.getLogger(__name__)

    @abstractmethod
    def search_filings(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        debtor_name: str | None = None,
        secured_party: str | None = None,
    ) -> Iterator[UCCFiling]:
        """Search for UCC filings.

        Args:
            start_date: Start date filter
            end_date: End date filter
            debtor_name: Debtor name search
            secured_party: Secured party search

        Yields:
            UCCFiling objects
        """
        pass


class NewYorkUCCHarvester(StateUCCHarvester):
    """New York UCC harvester.

    NY Department of State UCC Search:
    https://appext20.dos.ny.gov/pls/ucc_public/web_search.main_frame
    """

    STATE_CODE = "NY"
    PORTAL_URL = "https://appext20.dos.ny.gov/pls/ucc_public/"

    def search_filings(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        debtor_name: str | None = None,
        secured_party: str | None = None,
    ) -> Iterator[UCCFiling]:
        """Search NY UCC filings."""
        search_url = f"{self.PORTAL_URL}web_search.search_type"

        try:
            # Get search page
            response = self.http_client.get(search_url)
            if response.status_code != 200:
                self.logger.warning(f"NY UCC search returned {response.status_code}")
                return

            # Build search parameters
            if secured_party:
                # Search by secured party
                params = {
                    "search_type": "S",  # Secured party search
                    "secured_party_name": secured_party,
                }
            elif debtor_name:
                params = {
                    "search_type": "D",  # Debtor search
                    "debtor_name": debtor_name,
                }
            else:
                # Date range search
                params = {
                    "search_type": "F",  # Filing date search
                    "start_date": start_date.strftime("%m/%d/%Y") if start_date else "",
                    "end_date": end_date.strftime("%m/%d/%Y") if end_date else "",
                }

            # Execute search
            results_url = f"{self.PORTAL_URL}web_search.search_results"
            response = self.http_client.post(results_url, data=params)

            if response.status_code != 200:
                return

            # Parse results
            yield from self._parse_ny_results(response.text)

        except Exception as e:
            self.logger.error(f"Error searching NY UCC: {e}")

    def _parse_ny_results(self, html: str) -> Iterator[UCCFiling]:
        """Parse NY UCC search results."""
        # NY uses table-based display
        pattern = (
            r'filing.*?number[^>]*>(\d+)[^<]*<.*?'
            r'debtor[^>]*>([^<]+)<.*?'
            r'secured.*?party[^>]*>([^<]+)<.*?'
            r'date[^>]*>(\d{1,2}/\d{1,2}/\d{4})<.*?'
            r'type[^>]*>([^<]+)<'
        )

        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            filing_num, debtor, secured, date_str, filing_type = match

            try:
                filing_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                filing_date = datetime.now()

            yield UCCFiling(
                filing_number=filing_num.strip(),
                debtor_name=debtor.strip(),
                secured_party=secured.strip(),
                filing_date=filing_date,
                state="NY",
                filing_type=filing_type.strip(),
            )


class TexasUCCHarvester(StateUCCHarvester):
    """Texas UCC harvester.

    TX Secretary of State UCC Search:
    https://direct.sos.state.tx.us/ucc/
    """

    STATE_CODE = "TX"
    PORTAL_URL = "https://direct.sos.state.tx.us/ucc/"

    def search_filings(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        debtor_name: str | None = None,
        secured_party: str | None = None,
    ) -> Iterator[UCCFiling]:
        """Search TX UCC filings."""
        search_url = f"{self.PORTAL_URL}uccsearch.asp"

        try:
            # Get search page
            response = self.http_client.get(search_url)
            if response.status_code != 200:
                self.logger.warning(f"TX UCC search returned {response.status_code}")
                return

            # Build search
            if secured_party:
                params = {
                    "searchtype": "sp",
                    "spname": secured_party,
                }
            elif debtor_name:
                params = {
                    "searchtype": "db",
                    "dbname": debtor_name,
                }
            else:
                params = {
                    "searchtype": "dt",
                    "fromdate": start_date.strftime("%m/%d/%Y") if start_date else "",
                    "todate": end_date.strftime("%m/%d/%Y") if end_date else "",
                }

            # Execute search
            response = self.http_client.post(search_url, data=params)

            if response.status_code != 200:
                return

            yield from self._parse_tx_results(response.text)

        except Exception as e:
            self.logger.error(f"Error searching TX UCC: {e}")

    def _parse_tx_results(self, html: str) -> Iterator[UCCFiling]:
        """Parse TX UCC search results."""
        pattern = (
            r'file.*?number[^>]*>([^<]+)<.*?'
            r'debtor[^>]*>([^<]+)<.*?'
            r'secured[^>]*>([^<]+)<.*?'
            r'filed[^>]*>(\d{1,2}/\d{1,2}/\d{4})<'
        )

        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            filing_num, debtor, secured, date_str = match

            try:
                filing_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                filing_date = datetime.now()

            yield UCCFiling(
                filing_number=filing_num.strip(),
                debtor_name=debtor.strip(),
                secured_party=secured.strip(),
                filing_date=filing_date,
                state="TX",
            )


class CaliforniaUCCHarvester(StateUCCHarvester):
    """California UCC harvester.

    CA Secretary of State Business Programs:
    https://businesssearch.sos.ca.gov/
    """

    STATE_CODE = "CA"
    PORTAL_URL = "https://bizfileonline.sos.ca.gov/ucc/"

    def search_filings(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        debtor_name: str | None = None,
        secured_party: str | None = None,
    ) -> Iterator[UCCFiling]:
        """Search CA UCC filings."""
        search_url = f"{self.PORTAL_URL}search"

        try:
            # California's system is more complex
            response = self.http_client.get(search_url)
            if response.status_code != 200:
                self.logger.warning(f"CA UCC search returned {response.status_code}")
                return

            # Build search parameters
            if secured_party:
                params = {"searchType": "SP", "name": secured_party}
            elif debtor_name:
                params = {"searchType": "DB", "name": debtor_name}
            else:
                params = {
                    "searchType": "DT",
                    "startDate": start_date.strftime("%Y-%m-%d") if start_date else "",
                    "endDate": end_date.strftime("%Y-%m-%d") if end_date else "",
                }

            response = self.http_client.get(search_url, params=params)

            if response.status_code != 200:
                return

            yield from self._parse_ca_results(response.text)

        except Exception as e:
            self.logger.error(f"Error searching CA UCC: {e}")

    def _parse_ca_results(self, html: str) -> Iterator[UCCFiling]:
        """Parse CA UCC search results."""
        pattern = (
            r'filing[^>]*>([^<]+)<.*?'
            r'debtor[^>]*>([^<]+)<.*?'
            r'secured[^>]*>([^<]+)<.*?'
            r'date[^>]*>(\d{1,2}/\d{1,2}/\d{4})<'
        )

        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            filing_num, debtor, secured, date_str = match

            try:
                filing_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                filing_date = datetime.now()

            yield UCCFiling(
                filing_number=filing_num.strip(),
                debtor_name=debtor.strip(),
                secured_party=secured.strip(),
                filing_date=filing_date,
                state="CA",
            )


class MultiStateUCCHarvester(BaseHarvester):
    """Unified multi-state UCC harvester.

    Coordinates harvesting from multiple state UCC databases and
    provides a consistent interface for the pipeline.
    """

    SOURCE_NAME = "UCC_MULTISTATE"

    # Top MCA lenders for secured party searches
    TOP_MCA_LENDERS = [
        "OnDeck Capital",
        "Kabbage",
        "BlueVine",
        "Fundbox",
        "PayPal Working Capital",
        "Square Capital",
        "Amazon Lending",
        "Shopify Capital",
        "Credibly",
        "Rapid Finance",
        "Yellowstone Capital",
        "Pearl Capital",
        "CAN Capital",
        "Funding Circle",
        "Lendio",
        "National Funding",
        "Reliant Funding",
        "Forward Financing",
        "Breakout Capital",
        "Clearco",
    ]

    def __init__(
        self,
        logger: logging.Logger | None = None,
        requests_per_minute: int = 15,
        states: list[str] | None = None,
    ) -> None:
        """Initialize multi-state UCC harvester.

        Args:
            logger: Logger instance
            requests_per_minute: Rate limit for requests
            states: States to harvest (defaults to major states)
        """
        super().__init__(logger=logger)

        self.http_client = HarvestHTTPClient(
            rate_limiter=RateLimiter(
                requests_per_minute=requests_per_minute,
                min_delay_seconds=3.0,
            ),
            logger=logger,
        )

        # Initialize state harvesters
        self.state_harvesters: dict[str, StateUCCHarvester] = {
            "NY": NewYorkUCCHarvester(self.http_client, logger),
            "TX": TexasUCCHarvester(self.http_client, logger),
            "CA": CaliforniaUCCHarvester(self.http_client, logger),
        }

        self.states = states or list(self.state_harvesters.keys())

    def harvest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        mca_only: bool = False,
        states: list[str] | None = None,
        known_mca_lenders: list[str] | None = None,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Harvest UCC filings from multiple states.

        Args:
            start_date: Start date filter
            end_date: End date filter
            mca_only: Only return MCA-related filings
            states: Override states to search
            known_mca_lenders: Specific MCA lenders to search
            **kwargs: Additional arguments

        Yields:
            SignalCreate objects for UCC filings
        """
        self.logger.info("Starting multi-state UCC harvest")

        search_states = states or self.states
        mca_lenders = known_mca_lenders or self.TOP_MCA_LENDERS

        processed_filings: set[str] = set()

        for state in search_states:
            if state not in self.state_harvesters:
                self.logger.warning(f"No harvester for state {state}")
                continue

            harvester = self.state_harvesters[state]
            self.logger.info(f"Harvesting UCC filings from {state}")

            try:
                # Search by known MCA lenders
                for lender in mca_lenders:
                    self.logger.debug(f"Searching {lender} in {state}")

                    for filing in harvester.search_filings(
                        start_date=start_date,
                        end_date=end_date,
                        secured_party=lender,
                    ):
                        # Deduplication
                        filing_key = f"{filing.state}:{filing.filing_number}"
                        if filing_key in processed_filings:
                            continue
                        processed_filings.add(filing_key)

                        # Apply date filters
                        if start_date and filing.filing_date < start_date:
                            continue
                        if end_date and filing.filing_date > end_date:
                            continue

                        # Convert to SignalCreate
                        signal = self._convert_to_signal(filing, mca_related=True, mca_lender=lender)
                        yield signal

                # If not MCA-only, also do general date search
                if not mca_only:
                    for filing in harvester.search_filings(
                        start_date=start_date,
                        end_date=end_date,
                    ):
                        filing_key = f"{filing.state}:{filing.filing_number}"
                        if filing_key in processed_filings:
                            continue
                        processed_filings.add(filing_key)

                        # Check if MCA-related
                        mca_result = mca_detector.detect(
                            secured_party=filing.secured_party,
                            business_name=filing.debtor_name,
                        )

                        signal = self._convert_to_signal(
                            filing,
                            mca_related=mca_result.is_mca_related,
                            mca_lender=mca_result.matched_lender,
                        )
                        yield signal

            except Exception as e:
                self.logger.error(f"Error harvesting {state}: {e}")
                continue

        self.logger.info(
            f"Multi-state UCC harvest complete: {len(processed_filings)} filings"
        )

    def _convert_to_signal(
        self,
        filing: UCCFiling,
        mca_related: bool = False,
        mca_lender: str | None = None,
    ) -> SignalCreate:
        """Convert UCCFiling to SignalCreate.

        Args:
            filing: UCC filing record
            mca_related: Whether filing is MCA-related
            mca_lender: Matched MCA lender name

        Returns:
            SignalCreate object
        """
        return SignalCreate(
            signal_type="UCC",
            business_identifier=f"UCC:{filing.state}:{filing.filing_number}",
            business_name=filing.debtor_name,
            signal_date=filing.filing_date,
            source=f"UCC_{filing.state}",
            state=filing.state,
            raw_data={
                "filing_number": filing.filing_number,
                "debtor_name": filing.debtor_name,
                "secured_party": filing.secured_party,
                "filing_type": filing.filing_type,
                "collateral_description": filing.collateral_description,
                "lapse_date": filing.lapse_date.isoformat() if filing.lapse_date else None,
                "status": filing.status,
            },
            metadata_=SignalMetadata(
                is_mca_related=mca_related,
                mca_lender_match=mca_lender,
                mca_confidence=0.9 if mca_related else 0.0,
            ),
        )

    def search_business(
        self,
        business_name: str,
        states: list[str] | None = None,
    ) -> list[UCCFiling]:
        """Search for UCC filings for a specific business.

        Args:
            business_name: Business/debtor name
            states: States to search

        Returns:
            List of UCCFiling objects
        """
        filings = []
        search_states = states or self.states

        for state in search_states:
            if state not in self.state_harvesters:
                continue

            harvester = self.state_harvesters[state]

            try:
                for filing in harvester.search_filings(debtor_name=business_name):
                    filings.append(filing)
            except Exception as e:
                self.logger.error(f"Error searching {business_name} in {state}: {e}")

        return filings

    def close(self) -> None:
        """Close the HTTP client."""
        self.http_client.close()
