"""Tax Lien Harvester for detecting business stress signals.

Harvests tax lien data from public records to identify businesses
with tax obligations that may need capital for resolution.

Tax liens are stress signals:
- Federal tax liens indicate IRS debt
- State tax liens indicate state tax debt
- Recent liens are stronger signals than old ones
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterator
from urllib.parse import quote_plus

from src.harvesters.base import BaseHarvester, HarvestResult
from src.harvesters.http_client import HarvestHTTPClient, RateLimiter
from src.harvesters.mca_detector import mca_detector
from src.models.signal import SignalCreate, SignalMetadata


@dataclass
class TaxLien:
    """Represents a tax lien record."""

    business_name: str
    lien_type: str  # federal, state, local
    amount: float | None = None
    filing_date: datetime | None = None
    release_date: datetime | None = None
    jurisdiction: str | None = None
    case_number: str | None = None
    status: str = "active"  # active, released, partial
    source_url: str | None = None

    @property
    def is_active(self) -> bool:
        """Check if lien is still active."""
        return self.status == "active" and self.release_date is None

    @property
    def age_days(self) -> int | None:
        """Get lien age in days."""
        if self.filing_date:
            return (datetime.now() - self.filing_date).days
        return None


@dataclass
class TaxLienSignal:
    """Aggregated tax lien signal for a business."""

    business_name: str
    total_liens: int = 0
    active_liens: int = 0
    total_amount: float = 0.0
    lien_types: dict[str, int] = field(default_factory=dict)
    liens: list[TaxLien] = field(default_factory=list)
    earliest_lien: datetime | None = None
    latest_lien: datetime | None = None

    @property
    def signal_strength(self) -> str:
        """Get signal strength based on lien severity."""
        if self.total_amount >= 100000 or self.active_liens >= 3:
            return "high_stress"
        elif self.total_amount >= 25000 or self.active_liens >= 2:
            return "moderate_stress"
        else:
            return "low_stress"

    @property
    def base_points(self) -> int:
        """Get base intent points (stress signals use different scale)."""
        # Stress signals indicate need but also risk
        if self.signal_strength == "high_stress":
            return 70  # High need but risky
        elif self.signal_strength == "moderate_stress":
            return 55
        else:
            return 35


class TaxLienHarvester(BaseHarvester):
    """Harvester for tax lien records.

    Detects businesses with tax liens, indicating financial stress
    and potential need for capital to resolve obligations.

    Sources:
    - State tax lien databases
    - County recorder offices
    - IRS federal tax lien search
    """

    SOURCE_NAME = "TAX_LIENS"

    # State tax lien portals
    STATE_PORTALS = {
        "FL": "https://www.floridatreasurer.com/lien-search",
        "NY": "https://www.tax.ny.gov/e-services/lien/",
        "CA": "https://www.ftb.ca.gov/pay/collections/liens",
        "TX": "https://comptroller.texas.gov/taxes/warrant/",
        "IL": "https://tax.illinois.gov/taxliens/",
    }

    def __init__(
        self,
        logger: logging.Logger | None = None,
        requests_per_minute: int = 15,
        states: list[str] | None = None,
    ) -> None:
        """Initialize the tax lien harvester.

        Args:
            logger: Logger instance
            requests_per_minute: Rate limit for requests
            states: States to search (defaults to major states)
        """
        super().__init__(logger=logger)
        self.http_client = HarvestHTTPClient(
            rate_limiter=RateLimiter(
                requests_per_minute=requests_per_minute,
                min_delay_seconds=3.0,
            ),
            logger=logger,
        )

        self.states = states or ["FL", "NY", "CA", "TX"]

    def harvest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        mca_only: bool = False,
        states: list[str] | None = None,
        min_amount: float | None = None,
        active_only: bool = True,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Harvest tax lien records.

        Args:
            start_date: Start date for lien filings
            end_date: End date for lien filings
            mca_only: Filter to MCA-relevant businesses
            states: Override search states
            min_amount: Minimum lien amount filter
            active_only: Only include active liens
            **kwargs: Additional arguments

        Yields:
            SignalCreate objects for businesses with tax liens
        """
        self.logger.info("Starting tax lien harvest")

        search_states = states or self.states
        processed_businesses: set[str] = set()

        for state in search_states:
            self.logger.info(f"Searching tax liens in {state}")

            try:
                for signal in self._harvest_state_liens(
                    state=state,
                    start_date=start_date,
                    end_date=end_date,
                    min_amount=min_amount,
                    active_only=active_only,
                    processed=processed_businesses,
                ):
                    # Filter MCA-relevant if requested
                    if mca_only:
                        metadata = (
                            signal.metadata_.model_dump()
                            if hasattr(signal.metadata_, "model_dump")
                            else dict(signal.metadata_)
                        )
                        if not metadata.get("is_mca_related"):
                            continue

                    yield signal

            except Exception as e:
                self.logger.error(f"Error harvesting {state}: {e}")
                continue

        self.logger.info(
            f"Tax lien harvest complete: {len(processed_businesses)} businesses found"
        )

    def _harvest_state_liens(
        self,
        state: str,
        start_date: datetime | None,
        end_date: datetime | None,
        min_amount: float | None,
        active_only: bool,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Harvest tax liens for a specific state.

        Args:
            state: State code
            start_date: Start date filter
            end_date: End date filter
            min_amount: Minimum amount filter
            active_only: Only active liens
            processed: Set of already processed businesses

        Yields:
            SignalCreate objects
        """
        # Use state-specific harvesting method
        if state == "FL":
            yield from self._harvest_florida_liens(
                start_date, end_date, min_amount, active_only, processed
            )
        elif state == "NY":
            yield from self._harvest_ny_liens(
                start_date, end_date, min_amount, active_only, processed
            )
        elif state == "CA":
            yield from self._harvest_california_liens(
                start_date, end_date, min_amount, active_only, processed
            )
        elif state == "TX":
            yield from self._harvest_texas_liens(
                start_date, end_date, min_amount, active_only, processed
            )
        else:
            # Generic search for other states
            yield from self._harvest_generic_liens(
                state, start_date, end_date, min_amount, active_only, processed
            )

    def _harvest_florida_liens(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        min_amount: float | None,
        active_only: bool,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Harvest Florida tax liens.

        Florida Department of Revenue maintains a public lien database.
        """
        base_url = "https://taxapps.floridarevenue.com/taxlien/"

        try:
            # Search for recent liens
            search_url = f"{base_url}LienSearch.aspx"

            response = self.http_client.get(search_url)
            if response.status_code != 200:
                self.logger.warning(f"Florida lien search returned {response.status_code}")
                return

            # Parse lien records
            liens = self._parse_florida_liens(response.text)

            # Filter and yield
            yield from self._process_liens(
                liens, "FL", start_date, end_date, min_amount, active_only, processed
            )

        except Exception as e:
            self.logger.error(f"Error harvesting Florida liens: {e}")

    def _harvest_ny_liens(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        min_amount: float | None,
        active_only: bool,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Harvest New York tax liens.

        NY Department of Taxation provides a warrant lookup.
        """
        base_url = "https://www.tax.ny.gov/e-services/warrant/"

        try:
            response = self.http_client.get(base_url)
            if response.status_code != 200:
                return

            liens = self._parse_ny_liens(response.text)

            yield from self._process_liens(
                liens, "NY", start_date, end_date, min_amount, active_only, processed
            )

        except Exception as e:
            self.logger.error(f"Error harvesting NY liens: {e}")

    def _harvest_california_liens(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        min_amount: float | None,
        active_only: bool,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Harvest California tax liens.

        California FTB provides lien information.
        """
        # California requires more complex interaction
        # Using public records search
        try:
            liens = self._search_public_records_liens("CA")

            yield from self._process_liens(
                liens, "CA", start_date, end_date, min_amount, active_only, processed
            )

        except Exception as e:
            self.logger.error(f"Error harvesting CA liens: {e}")

    def _harvest_texas_liens(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        min_amount: float | None,
        active_only: bool,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Harvest Texas tax liens/warrants.

        Texas Comptroller provides warrant information.
        """
        base_url = "https://comptroller.texas.gov/taxes/warrant/search/"

        try:
            response = self.http_client.get(base_url)
            if response.status_code != 200:
                return

            liens = self._parse_texas_liens(response.text)

            yield from self._process_liens(
                liens, "TX", start_date, end_date, min_amount, active_only, processed
            )

        except Exception as e:
            self.logger.error(f"Error harvesting TX liens: {e}")

    def _harvest_generic_liens(
        self,
        state: str,
        start_date: datetime | None,
        end_date: datetime | None,
        min_amount: float | None,
        active_only: bool,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Generic lien harvest using public records search."""
        try:
            liens = self._search_public_records_liens(state)

            yield from self._process_liens(
                liens, state, start_date, end_date, min_amount, active_only, processed
            )

        except Exception as e:
            self.logger.error(f"Error harvesting {state} liens: {e}")

    def _parse_florida_liens(self, html: str) -> list[TaxLien]:
        """Parse Florida tax lien HTML."""
        liens = []

        # Look for table rows with lien data
        # Pattern: business name, amount, filing date, status
        row_pattern = r'<tr[^>]*>.*?<td[^>]*>([^<]+)</td>.*?<td[^>]*>\$?([\d,]+\.?\d*)</td>.*?<td[^>]*>(\d{1,2}/\d{1,2}/\d{4})</td>.*?<td[^>]*>(\w+)</td>'

        matches = re.findall(row_pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            business_name, amount_str, date_str, status = match

            try:
                amount = float(amount_str.replace(",", ""))
            except ValueError:
                amount = None

            try:
                filing_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                filing_date = None

            lien = TaxLien(
                business_name=business_name.strip(),
                lien_type="state",
                amount=amount,
                filing_date=filing_date,
                jurisdiction="FL",
                status=status.lower() if status else "active",
            )
            liens.append(lien)

        return liens

    def _parse_ny_liens(self, html: str) -> list[TaxLien]:
        """Parse New York tax lien/warrant HTML."""
        liens = []

        # NY uses warrant terminology
        pattern = r'<tr[^>]*>.*?taxpayer[^>]*>([^<]+)<.*?amount[^>]*>\$?([\d,]+\.?\d*)<.*?date[^>]*>(\d{1,2}/\d{1,2}/\d{4})<'

        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            business_name, amount_str, date_str = match

            try:
                amount = float(amount_str.replace(",", ""))
            except ValueError:
                amount = None

            try:
                filing_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                filing_date = None

            lien = TaxLien(
                business_name=business_name.strip(),
                lien_type="state",
                amount=amount,
                filing_date=filing_date,
                jurisdiction="NY",
            )
            liens.append(lien)

        return liens

    def _parse_texas_liens(self, html: str) -> list[TaxLien]:
        """Parse Texas tax warrant HTML."""
        liens = []

        pattern = r'name[^>]*>([^<]+)<.*?warrant.*?amount[^>]*>\$?([\d,]+\.?\d*)<.*?filed[^>]*>(\d{1,2}/\d{1,2}/\d{4})<'

        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            business_name, amount_str, date_str = match

            try:
                amount = float(amount_str.replace(",", ""))
            except ValueError:
                amount = None

            try:
                filing_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                filing_date = None

            lien = TaxLien(
                business_name=business_name.strip(),
                lien_type="state",
                amount=amount,
                filing_date=filing_date,
                jurisdiction="TX",
            )
            liens.append(lien)

        return liens

    def _search_public_records_liens(self, state: str) -> list[TaxLien]:
        """Search public records for tax liens.

        Uses aggregated public records search when state-specific
        portals are not available.
        """
        liens = []

        # This would connect to public records aggregators
        # For now, return empty list as placeholder
        self.logger.info(f"Public records search for {state} liens (placeholder)")

        return liens

    def _process_liens(
        self,
        liens: list[TaxLien],
        state: str,
        start_date: datetime | None,
        end_date: datetime | None,
        min_amount: float | None,
        active_only: bool,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Process liens and yield signals.

        Args:
            liens: List of TaxLien objects
            state: State code
            start_date: Start date filter
            end_date: End date filter
            min_amount: Minimum amount filter
            active_only: Only active liens
            processed: Set of already processed businesses

        Yields:
            SignalCreate objects
        """
        # Group by business
        business_liens: dict[str, list[TaxLien]] = {}

        for lien in liens:
            # Apply filters
            if start_date and lien.filing_date and lien.filing_date < start_date:
                continue
            if end_date and lien.filing_date and lien.filing_date > end_date:
                continue
            if min_amount and lien.amount and lien.amount < min_amount:
                continue
            if active_only and not lien.is_active:
                continue

            key = self._normalize_business_name(lien.business_name)
            if key not in business_liens:
                business_liens[key] = []
            business_liens[key].append(lien)

        # Generate signals
        for business_name, lien_list in business_liens.items():
            if business_name in processed:
                continue
            processed.add(business_name)

            # Aggregate lien data
            lien_signal = TaxLienSignal(
                business_name=business_name,
                total_liens=len(lien_list),
                liens=lien_list,
            )

            for lien in lien_list:
                if lien.is_active:
                    lien_signal.active_liens += 1
                if lien.amount:
                    lien_signal.total_amount += lien.amount
                if lien.lien_type:
                    lien_signal.lien_types[lien.lien_type] = (
                        lien_signal.lien_types.get(lien.lien_type, 0) + 1
                    )
                if lien.filing_date:
                    if (
                        lien_signal.earliest_lien is None
                        or lien.filing_date < lien_signal.earliest_lien
                    ):
                        lien_signal.earliest_lien = lien.filing_date
                    if (
                        lien_signal.latest_lien is None
                        or lien.filing_date > lien_signal.latest_lien
                    ):
                        lien_signal.latest_lien = lien.filing_date

            # MCA detection
            mca_result = mca_detector.detect(business_name=business_name)

            # Create signal
            signal_date = lien_signal.latest_lien or datetime.now()

            yield SignalCreate(
                signal_type="TAX_LIEN",
                business_identifier=f"LIEN:{business_name}:{state}",
                business_name=business_name,
                signal_date=signal_date,
                source=self.SOURCE_NAME,
                state=state,
                raw_data={
                    "total_liens": lien_signal.total_liens,
                    "active_liens": lien_signal.active_liens,
                    "total_amount": lien_signal.total_amount,
                    "lien_types": lien_signal.lien_types,
                    "signal_strength": lien_signal.signal_strength,
                    "earliest_lien": (
                        lien_signal.earliest_lien.isoformat()
                        if lien_signal.earliest_lien
                        else None
                    ),
                    "latest_lien": (
                        lien_signal.latest_lien.isoformat()
                        if lien_signal.latest_lien
                        else None
                    ),
                },
                metadata_=SignalMetadata(
                    is_mca_related=mca_result.is_mca_related,
                    mca_confidence=mca_result.confidence,
                    signal_strength=lien_signal.signal_strength,
                    intent_points=lien_signal.base_points,
                    is_stress_signal=True,
                ),
            )

    def _normalize_business_name(self, name: str) -> str:
        """Normalize business name for grouping."""
        suffixes = [
            " Inc", " Inc.", " LLC", " L.L.C.", " Corp", " Corp.",
            " Co", " Co.", " Ltd", " Ltd.", " LP", " L.P.",
        ]

        normalized = name.strip().upper()
        for suffix in suffixes:
            if normalized.endswith(suffix.upper()):
                normalized = normalized[: -len(suffix)]

        return normalized.strip()

    def search_business(
        self,
        business_name: str,
        states: list[str] | None = None,
    ) -> TaxLienSignal | None:
        """Search for tax liens for a specific business.

        Args:
            business_name: Business name to search
            states: States to search

        Returns:
            TaxLienSignal or None
        """
        search_states = states or self.states
        all_liens: list[TaxLien] = []

        for state in search_states:
            # Would implement specific business search
            pass

        if not all_liens:
            return None

        signal = TaxLienSignal(
            business_name=business_name,
            total_liens=len(all_liens),
            liens=all_liens,
        )

        return signal

    def close(self) -> None:
        """Close the HTTP client."""
        self.http_client.close()
