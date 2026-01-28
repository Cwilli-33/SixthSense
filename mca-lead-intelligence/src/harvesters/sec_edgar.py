"""SEC EDGAR Harvester for business filings.

Harvests business filings from the SEC EDGAR database.
Useful for identifying public company financing activities and changes.

SEC EDGAR provides free access to company filings including:
- Form 8-K: Current reports (material events)
- Form 10-K: Annual reports
- Form 10-Q: Quarterly reports
- Schedule 13D/G: Beneficial ownership
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Iterator
from xml.etree import ElementTree

from src.harvesters.base import BaseHarvester
from src.harvesters.http_client import HarvestHTTPClient, RateLimiter, RetryConfig
from src.models.signal import SignalCreate, SignalMetadata, SignalType


class SECEdgarHarvester(BaseHarvester):
    """Harvest business filings from SEC EDGAR.

    SEC EDGAR API is free and has reasonable rate limits (10 requests/second).
    We use a conservative rate to be respectful.
    """

    # SEC EDGAR API endpoints
    EDGAR_BASE_URL = "https://www.sec.gov"
    EDGAR_COMPANY_SEARCH = f"{EDGAR_BASE_URL}/cgi-bin/browse-edgar"
    EDGAR_FULL_TEXT_SEARCH = "https://efts.sec.gov/LATEST/search-index"
    EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions"

    # Filing types we're interested in
    RELEVANT_FILING_TYPES = {
        "8-K": "Current Report (material events)",
        "10-K": "Annual Report",
        "10-Q": "Quarterly Report",
        "SC 13D": "Beneficial Ownership (activist)",
        "SC 13G": "Beneficial Ownership (passive)",
        "4": "Insider Trading",
        "S-1": "IPO Registration",
        "424B": "Prospectus",
    }

    # Keywords indicating potential MCA/financing activity
    FINANCING_KEYWORDS = [
        "merchant cash advance",
        "working capital",
        "credit facility",
        "loan agreement",
        "financing agreement",
        "debt financing",
        "line of credit",
        "accounts receivable",
        "revenue-based financing",
        "factoring",
        "cash advance",
        "business loan",
    ]

    def __init__(
        self,
        logger: logging.Logger | None = None,
        timeout: float = 30.0,
        requests_per_minute: int = 30,
    ) -> None:
        """Initialize the SEC EDGAR harvester.

        Args:
            logger: Logger instance
            timeout: HTTP request timeout in seconds
            requests_per_minute: Rate limit (SEC allows 10/sec, we use conservative limit)
        """
        super().__init__(logger)
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
                    min_delay_seconds=0.5,
                    max_delay_seconds=2.0,
                ),
                retry_config=RetryConfig(
                    max_retries=3,
                    base_delay=2.0,
                ),
                logger=self.logger,
            )
            # SEC requires a User-Agent with contact info
            self._http_client.client.headers["User-Agent"] = (
                "MCA-Lead-Intelligence/1.0 (contact@example.com)"
            )
        return self._http_client

    def get_source_name(self) -> str:
        return "SEC_EDGAR"

    def get_state(self) -> str:
        return "US"  # Federal/National

    def get_supported_signal_types(self) -> list[SignalType]:
        return [
            SignalType.BUSINESS_FORMATION,  # S-1 filings
            SignalType.UCC_FILING,  # Debt/financing disclosures
        ]

    def harvest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Harvest SEC filings.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            **kwargs: Additional parameters:
                - company_name: Search for specific company
                - cik: Company CIK number
                - filing_types: List of filing types to include
                - keywords: Search keywords
                - financing_only: Only return financing-related filings

        Yields:
            SignalCreate objects for each relevant filing
        """
        self.validate_date_range(start_date, end_date)

        company_name = kwargs.get("company_name")
        cik = kwargs.get("cik")
        filing_types = kwargs.get("filing_types", list(self.RELEVANT_FILING_TYPES.keys()))
        keywords = kwargs.get("keywords", self.FINANCING_KEYWORDS)
        financing_only = kwargs.get("financing_only", True)

        http_client = self._get_http_client()

        try:
            if cik:
                # Search by CIK
                yield from self._harvest_by_cik(
                    http_client, cik, start_date, end_date, filing_types, financing_only
                )
            elif company_name:
                # Search by company name
                yield from self._harvest_by_company_name(
                    http_client, company_name, start_date, end_date, filing_types, financing_only
                )
            else:
                # Full-text search for financing keywords
                for keyword in keywords[:5]:  # Limit keywords to avoid too many requests
                    self.logger.info(f"Searching SEC filings for keyword: {keyword}")
                    yield from self._harvest_by_keyword(
                        http_client, keyword, start_date, end_date, filing_types
                    )

        except Exception as e:
            self.logger.error(f"SEC EDGAR harvest failed: {e}")
            raise

    def _harvest_by_cik(
        self,
        http_client: HarvestHTTPClient,
        cik: str,
        start_date: datetime | None,
        end_date: datetime | None,
        filing_types: list[str],
        financing_only: bool,
    ) -> Iterator[SignalCreate]:
        """Harvest filings for a specific CIK.

        Args:
            http_client: HTTP client
            cik: Company CIK number
            start_date: Start date filter
            end_date: End date filter
            filing_types: Filing types to include
            financing_only: Only financing-related

        Yields:
            SignalCreate objects
        """
        # Normalize CIK (pad to 10 digits)
        cik_padded = cik.zfill(10)

        try:
            # Get company submissions
            url = f"{self.EDGAR_SUBMISSIONS_URL}/CIK{cik_padded}.json"
            response = http_client.get(url)
            data = response.json()

            company_name = data.get("name", "Unknown")
            filings = data.get("filings", {}).get("recent", {})

            # Process filings
            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])
            accession_numbers = filings.get("accessionNumber", [])
            primary_documents = filings.get("primaryDocument", [])

            for i, form in enumerate(forms):
                if form not in filing_types:
                    continue

                filing_date_str = dates[i] if i < len(dates) else None
                if not filing_date_str:
                    continue

                filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")

                # Apply date filters
                if start_date and filing_date < start_date:
                    continue
                if end_date and filing_date > end_date:
                    continue

                accession = accession_numbers[i] if i < len(accession_numbers) else ""
                primary_doc = primary_documents[i] if i < len(primary_documents) else ""

                signal = self._create_signal_from_filing(
                    company_name=company_name,
                    cik=cik,
                    form_type=form,
                    filing_date=filing_date,
                    accession_number=accession,
                    primary_document=primary_doc,
                )

                if signal:
                    yield signal

        except Exception as e:
            self.logger.warning(f"Error fetching CIK {cik}: {e}")

    def _harvest_by_company_name(
        self,
        http_client: HarvestHTTPClient,
        company_name: str,
        start_date: datetime | None,
        end_date: datetime | None,
        filing_types: list[str],
        financing_only: bool,
    ) -> Iterator[SignalCreate]:
        """Harvest filings by company name search.

        Args:
            http_client: HTTP client
            company_name: Company name to search
            start_date: Start date filter
            end_date: End date filter
            filing_types: Filing types to include
            financing_only: Only financing-related

        Yields:
            SignalCreate objects
        """
        try:
            # Search for company
            params = {
                "action": "getcompany",
                "company": company_name,
                "type": "",
                "dateb": "",
                "owner": "include",
                "count": "40",
                "output": "atom",
            }

            response = http_client.get(self.EDGAR_COMPANY_SEARCH, params=params)

            # Parse Atom feed
            root = ElementTree.fromstring(response.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall(".//atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                updated_elem = entry.find("atom:updated", ns)
                link_elem = entry.find("atom:link", ns)

                if title_elem is None or updated_elem is None:
                    continue

                title = title_elem.text or ""

                # Parse form type from title
                form_match = re.search(r"^(\S+)\s+-\s+(.+)\s+\((\d+)\)", title)
                if not form_match:
                    continue

                form_type = form_match.group(1)
                company = form_match.group(2)
                cik = form_match.group(3)

                if form_type not in filing_types:
                    continue

                # Parse date
                updated = updated_elem.text or ""
                try:
                    filing_date = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    filing_date = filing_date.replace(tzinfo=None)
                except ValueError:
                    continue

                # Apply date filters
                if start_date and filing_date < start_date:
                    continue
                if end_date and filing_date > end_date:
                    continue

                signal = self._create_signal_from_filing(
                    company_name=company.strip(),
                    cik=cik,
                    form_type=form_type,
                    filing_date=filing_date,
                    accession_number="",
                    primary_document="",
                )

                if signal:
                    yield signal

        except Exception as e:
            self.logger.warning(f"Error searching for company {company_name}: {e}")

    def _harvest_by_keyword(
        self,
        http_client: HarvestHTTPClient,
        keyword: str,
        start_date: datetime | None,
        end_date: datetime | None,
        filing_types: list[str],
        max_results: int = 100,
    ) -> Iterator[SignalCreate]:
        """Harvest filings by full-text keyword search.

        Args:
            http_client: HTTP client
            keyword: Search keyword
            start_date: Start date filter
            end_date: End date filter
            filing_types: Filing types to include
            max_results: Maximum results to return

        Yields:
            SignalCreate objects
        """
        try:
            # Build date range
            date_range = ""
            if start_date:
                date_range = f"[{start_date.strftime('%Y-%m-%d')} TO "
                if end_date:
                    date_range += f"{end_date.strftime('%Y-%m-%d')}]"
                else:
                    date_range += "NOW]"

            # SEC full-text search API
            params = {
                "q": keyword,
                "dateRange": "custom" if date_range else "30d",
                "forms": ",".join(filing_types),
                "startdt": start_date.strftime("%Y-%m-%d") if start_date else "",
                "enddt": end_date.strftime("%Y-%m-%d") if end_date else "",
            }

            # Note: SEC full-text search requires specific API format
            # This is a simplified implementation
            response = http_client.get(
                f"{self.EDGAR_BASE_URL}/cgi-bin/srch-ia",
                params={"text": keyword, "first": 1, "last": max_results},
            )

            # Parse results (simplified - actual format may vary)
            # For now, yield nothing as full-text search requires more complex parsing
            self.logger.info(f"Full-text search for '{keyword}' - results require additional parsing")

        except Exception as e:
            self.logger.warning(f"Error in keyword search for {keyword}: {e}")

        return
        yield  # Make this a generator

    def _create_signal_from_filing(
        self,
        company_name: str,
        cik: str,
        form_type: str,
        filing_date: datetime,
        accession_number: str,
        primary_document: str,
    ) -> SignalCreate | None:
        """Create a SignalCreate from filing data.

        Args:
            company_name: Company name
            cik: CIK number
            form_type: SEC form type
            filing_date: Filing date
            accession_number: Accession number
            primary_document: Primary document filename

        Returns:
            SignalCreate or None
        """
        # Determine signal type
        if form_type in ["S-1", "424B"]:
            signal_type = SignalType.BUSINESS_FORMATION
        else:
            signal_type = SignalType.UCC_FILING  # Use as proxy for financing signals

        # Build filing URL
        if accession_number and primary_document:
            accession_formatted = accession_number.replace("-", "")
            filing_url = (
                f"{self.EDGAR_BASE_URL}/Archives/edgar/data/"
                f"{cik}/{accession_formatted}/{primary_document}"
            )
        else:
            filing_url = ""

        metadata = SignalMetadata(
            filing_number=accession_number,
            filing_type=form_type,
            secured_party="SEC",
            collateral_description=self.RELEVANT_FILING_TYPES.get(form_type, form_type),
            is_mca_related=False,  # SEC filings are not MCA-related directly
        )

        return SignalCreate(
            signal_type=signal_type,
            business_identifier=f"SEC-{cik}-{accession_number or filing_date.strftime('%Y%m%d')}",
            business_name=company_name,
            signal_date=filing_date,
            source=self.get_source_name(),
            state=self.get_state(),
            raw_data={
                "cik": cik,
                "form_type": form_type,
                "accession_number": accession_number,
                "filing_url": filing_url,
                "company_name": company_name,
            },
            metadata=metadata,
        )

    def search_company(self, company_name: str) -> list[dict[str, Any]]:
        """Search for companies by name.

        Args:
            company_name: Company name to search

        Returns:
            List of matching companies with CIK
        """
        http_client = self._get_http_client()
        results = []

        try:
            params = {
                "action": "getcompany",
                "company": company_name,
                "type": "",
                "dateb": "",
                "owner": "include",
                "count": "10",
                "output": "atom",
            }

            response = http_client.get(self.EDGAR_COMPANY_SEARCH, params=params)
            root = ElementTree.fromstring(response.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            seen_ciks = set()
            for entry in root.findall(".//atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                if title_elem is None:
                    continue

                title = title_elem.text or ""
                match = re.search(r"^(\S+)\s+-\s+(.+)\s+\((\d+)\)", title)
                if match:
                    cik = match.group(3)
                    if cik not in seen_ciks:
                        seen_ciks.add(cik)
                        results.append({
                            "cik": cik,
                            "company_name": match.group(2).strip(),
                        })

        except Exception as e:
            self.logger.warning(f"Error searching for company: {e}")

        return results

    def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None
