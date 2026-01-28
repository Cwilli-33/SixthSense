"""Business Permits Harvester for detecting expansion signals.

Harvests business permit data from public records to identify
businesses applying for permits, indicating:
- Expansion/renovation activity
- New location openings
- Equipment upgrades
- Change in operations

These are strong growth/operational signals for MCA leads.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterator
from urllib.parse import quote_plus

from src.harvesters.base import BaseHarvester, HarvestResult
from src.harvesters.http_client import HarvestHTTPClient, RateLimiter
from src.harvesters.mca_detector import mca_detector
from src.models.signal import SignalCreate, SignalMetadata


class PermitType(Enum):
    """Types of business permits."""

    BUILDING = "building"
    RENOVATION = "renovation"
    SIGNAGE = "signage"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    MECHANICAL = "mechanical"
    FIRE = "fire"
    HEALTH = "health"
    LIQUOR = "liquor"
    BUSINESS_LICENSE = "business_license"
    OCCUPANCY = "occupancy"
    ZONING = "zoning"
    OTHER = "other"


@dataclass
class Permit:
    """Represents a permit record."""

    business_name: str
    permit_type: PermitType
    permit_number: str | None = None
    application_date: datetime | None = None
    issue_date: datetime | None = None
    expiration_date: datetime | None = None
    status: str = "pending"  # pending, approved, issued, expired, denied
    address: str | None = None
    city: str | None = None
    state: str | None = None
    estimated_cost: float | None = None
    description: str | None = None
    contractor: str | None = None
    source_url: str | None = None


@dataclass
class PermitSignal:
    """Aggregated permit signal for a business."""

    business_name: str
    total_permits: int = 0
    permit_types: dict[str, int] = field(default_factory=dict)
    total_estimated_cost: float = 0.0
    permits: list[Permit] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    earliest_permit: datetime | None = None
    latest_permit: datetime | None = None

    @property
    def signal_strength(self) -> str:
        """Get signal strength based on permit activity."""
        if self.total_estimated_cost >= 100000 or self.total_permits >= 3:
            return "strong_expansion"
        elif self.total_estimated_cost >= 25000 or self.total_permits >= 2:
            return "moderate_expansion"
        else:
            return "minor_expansion"

    @property
    def base_points(self) -> int:
        """Get base intent points."""
        if self.signal_strength == "strong_expansion":
            return 80
        elif self.signal_strength == "moderate_expansion":
            return 55
        else:
            return 30

    @property
    def indicates_new_location(self) -> bool:
        """Check if permits indicate new location."""
        location_types = {PermitType.OCCUPANCY, PermitType.BUSINESS_LICENSE, PermitType.ZONING}
        for permit in self.permits:
            if permit.permit_type in location_types:
                return True
        return False

    @property
    def indicates_renovation(self) -> bool:
        """Check if permits indicate renovation."""
        reno_types = {
            PermitType.BUILDING, PermitType.RENOVATION, PermitType.ELECTRICAL,
            PermitType.PLUMBING, PermitType.MECHANICAL
        }
        for permit in self.permits:
            if permit.permit_type in reno_types:
                return True
        return False


class PermitsHarvester(BaseHarvester):
    """Harvester for business permit records.

    Detects businesses with recent permit activity, indicating
    expansion, renovation, or new location openings.

    Sources:
    - City/county permit databases
    - State licensing portals
    - OpenGov permit data
    """

    SOURCE_NAME = "PERMITS"

    # Major city permit portals
    CITY_PORTALS = {
        "Miami": "https://www.miamigov.com/services/permits",
        "New York": "https://a810-bisweb.nyc.gov/bisweb/",
        "Los Angeles": "https://www.ladbsservices.lacity.org/",
        "Houston": "https://houstonpermittingcenter.org/",
        "Chicago": "https://www.chicago.gov/city/en/depts/bldgs.html",
        "Dallas": "https://developmentservices.dallascityhall.com/",
        "Phoenix": "https://www.phoenix.gov/pdd/permits",
        "San Antonio": "https://www.sanantonio.gov/DSD/Permits",
    }

    # Permit types that indicate capital needs
    HIGH_VALUE_PERMITS = {
        PermitType.BUILDING,
        PermitType.RENOVATION,
        PermitType.OCCUPANCY,
        PermitType.BUSINESS_LICENSE,
    }

    def __init__(
        self,
        logger: logging.Logger | None = None,
        requests_per_minute: int = 15,
        cities: list[str] | None = None,
    ) -> None:
        """Initialize the permits harvester.

        Args:
            logger: Logger instance
            requests_per_minute: Rate limit for requests
            cities: Cities to search (defaults to major metros)
        """
        super().__init__(logger=logger)
        self.http_client = HarvestHTTPClient(
            rate_limiter=RateLimiter(
                requests_per_minute=requests_per_minute,
                min_delay_seconds=3.0,
            ),
            logger=logger,
        )

        self.cities = cities or list(self.CITY_PORTALS.keys())

    def harvest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        mca_only: bool = False,
        cities: list[str] | None = None,
        permit_types: list[PermitType] | None = None,
        min_cost: float | None = None,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Harvest permit records.

        Args:
            start_date: Start date for permits
            end_date: End date for permits
            mca_only: Filter to MCA-relevant businesses
            cities: Override search cities
            permit_types: Specific permit types to search
            min_cost: Minimum estimated cost filter
            **kwargs: Additional arguments

        Yields:
            SignalCreate objects for businesses with permits
        """
        self.logger.info("Starting permits harvest")

        search_cities = cities or self.cities
        processed_businesses: set[str] = set()

        for city in search_cities:
            self.logger.info(f"Searching permits in {city}")

            try:
                for signal in self._harvest_city_permits(
                    city=city,
                    start_date=start_date,
                    end_date=end_date,
                    permit_types=permit_types,
                    min_cost=min_cost,
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
                self.logger.error(f"Error harvesting {city}: {e}")
                continue

        self.logger.info(
            f"Permits harvest complete: {len(processed_businesses)} businesses found"
        )

    def _harvest_city_permits(
        self,
        city: str,
        start_date: datetime | None,
        end_date: datetime | None,
        permit_types: list[PermitType] | None,
        min_cost: float | None,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Harvest permits for a specific city.

        Args:
            city: City name
            start_date: Start date filter
            end_date: End date filter
            permit_types: Permit types filter
            min_cost: Minimum cost filter
            processed: Already processed businesses

        Yields:
            SignalCreate objects
        """
        # Route to city-specific harvester
        if city == "Miami":
            yield from self._harvest_miami_permits(
                start_date, end_date, permit_types, min_cost, processed
            )
        elif city == "New York":
            yield from self._harvest_nyc_permits(
                start_date, end_date, permit_types, min_cost, processed
            )
        elif city == "Los Angeles":
            yield from self._harvest_la_permits(
                start_date, end_date, permit_types, min_cost, processed
            )
        elif city == "Houston":
            yield from self._harvest_houston_permits(
                start_date, end_date, permit_types, min_cost, processed
            )
        else:
            yield from self._harvest_generic_permits(
                city, start_date, end_date, permit_types, min_cost, processed
            )

    def _harvest_miami_permits(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        permit_types: list[PermitType] | None,
        min_cost: float | None,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Harvest Miami-Dade permits."""
        # Miami-Dade County permit search
        base_url = "https://www.miamidade.gov/permits/search.asp"

        try:
            response = self.http_client.get(base_url)
            if response.status_code != 200:
                return

            permits = self._parse_miami_permits(response.text)

            yield from self._process_permits(
                permits, "Miami", "FL",
                start_date, end_date, permit_types, min_cost, processed
            )

        except Exception as e:
            self.logger.error(f"Error harvesting Miami permits: {e}")

    def _harvest_nyc_permits(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        permit_types: list[PermitType] | None,
        min_cost: float | None,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Harvest NYC DOB permits."""
        # NYC Buildings Information System
        base_url = "https://a810-bisweb.nyc.gov/bisweb/bispi00.jsp"

        try:
            # NYC provides a searchable database
            response = self.http_client.get(base_url)
            if response.status_code != 200:
                return

            permits = self._parse_nyc_permits(response.text)

            yield from self._process_permits(
                permits, "New York", "NY",
                start_date, end_date, permit_types, min_cost, processed
            )

        except Exception as e:
            self.logger.error(f"Error harvesting NYC permits: {e}")

    def _harvest_la_permits(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        permit_types: list[PermitType] | None,
        min_cost: float | None,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Harvest Los Angeles permits."""
        base_url = "https://www.ladbsservices.lacity.org/OnlineServices/"

        try:
            response = self.http_client.get(base_url)
            if response.status_code != 200:
                return

            permits = self._parse_la_permits(response.text)

            yield from self._process_permits(
                permits, "Los Angeles", "CA",
                start_date, end_date, permit_types, min_cost, processed
            )

        except Exception as e:
            self.logger.error(f"Error harvesting LA permits: {e}")

    def _harvest_houston_permits(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        permit_types: list[PermitType] | None,
        min_cost: float | None,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Harvest Houston permits."""
        base_url = "https://houstonpermittingcenter.org/hpc/public/"

        try:
            response = self.http_client.get(base_url)
            if response.status_code != 200:
                return

            permits = self._parse_houston_permits(response.text)

            yield from self._process_permits(
                permits, "Houston", "TX",
                start_date, end_date, permit_types, min_cost, processed
            )

        except Exception as e:
            self.logger.error(f"Error harvesting Houston permits: {e}")

    def _harvest_generic_permits(
        self,
        city: str,
        start_date: datetime | None,
        end_date: datetime | None,
        permit_types: list[PermitType] | None,
        min_cost: float | None,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Generic permit harvest using OpenGov or similar."""
        self.logger.info(f"Generic permit search for {city} (placeholder)")
        # Would connect to OpenGov or similar aggregators
        return
        yield  # Make this a generator

    def _parse_miami_permits(self, html: str) -> list[Permit]:
        """Parse Miami permit HTML."""
        permits = []

        # Look for permit records
        pattern = r'<tr[^>]*>.*?applicant[^>]*>([^<]+)<.*?permit.*?type[^>]*>([^<]+)<.*?date[^>]*>(\d{1,2}/\d{1,2}/\d{4})<.*?cost[^>]*>\$?([\d,]+)?'

        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            business_name, permit_type_str, date_str, cost_str = match

            permit_type = self._classify_permit_type(permit_type_str)

            try:
                app_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                app_date = None

            cost = None
            if cost_str:
                try:
                    cost = float(cost_str.replace(",", ""))
                except ValueError:
                    pass

            permit = Permit(
                business_name=business_name.strip(),
                permit_type=permit_type,
                application_date=app_date,
                estimated_cost=cost,
                city="Miami",
                state="FL",
            )
            permits.append(permit)

        return permits

    def _parse_nyc_permits(self, html: str) -> list[Permit]:
        """Parse NYC DOB permit HTML."""
        permits = []

        # NYC has specific patterns
        pattern = r'owner[^>]*>([^<]+)<.*?job.*?type[^>]*>([^<]+)<.*?filed[^>]*>(\d{1,2}/\d{1,2}/\d{4})<.*?cost[^>]*>\$?([\d,]+)?'

        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            business_name, permit_type_str, date_str, cost_str = match

            permit_type = self._classify_permit_type(permit_type_str)

            try:
                app_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                app_date = None

            cost = None
            if cost_str:
                try:
                    cost = float(cost_str.replace(",", ""))
                except ValueError:
                    pass

            permit = Permit(
                business_name=business_name.strip(),
                permit_type=permit_type,
                application_date=app_date,
                estimated_cost=cost,
                city="New York",
                state="NY",
            )
            permits.append(permit)

        return permits

    def _parse_la_permits(self, html: str) -> list[Permit]:
        """Parse LA permits HTML."""
        permits = []

        pattern = r'applicant[^>]*>([^<]+)<.*?permit[^>]*>([^<]+)<.*?date[^>]*>(\d{1,2}/\d{1,2}/\d{4})<'

        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            business_name, permit_type_str, date_str = match

            permit_type = self._classify_permit_type(permit_type_str)

            try:
                app_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                app_date = None

            permit = Permit(
                business_name=business_name.strip(),
                permit_type=permit_type,
                application_date=app_date,
                city="Los Angeles",
                state="CA",
            )
            permits.append(permit)

        return permits

    def _parse_houston_permits(self, html: str) -> list[Permit]:
        """Parse Houston permits HTML."""
        permits = []

        pattern = r'name[^>]*>([^<]+)<.*?type[^>]*>([^<]+)<.*?date[^>]*>(\d{1,2}/\d{1,2}/\d{4})<'

        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            business_name, permit_type_str, date_str = match

            permit_type = self._classify_permit_type(permit_type_str)

            try:
                app_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                app_date = None

            permit = Permit(
                business_name=business_name.strip(),
                permit_type=permit_type,
                application_date=app_date,
                city="Houston",
                state="TX",
            )
            permits.append(permit)

        return permits

    def _classify_permit_type(self, type_str: str) -> PermitType:
        """Classify permit type from string."""
        type_lower = type_str.lower()

        if "build" in type_lower or "construction" in type_lower:
            return PermitType.BUILDING
        elif "renov" in type_lower or "alter" in type_lower or "remodel" in type_lower:
            return PermitType.RENOVATION
        elif "sign" in type_lower:
            return PermitType.SIGNAGE
        elif "electr" in type_lower:
            return PermitType.ELECTRICAL
        elif "plumb" in type_lower:
            return PermitType.PLUMBING
        elif "mechanic" in type_lower or "hvac" in type_lower:
            return PermitType.MECHANICAL
        elif "fire" in type_lower or "sprinkler" in type_lower:
            return PermitType.FIRE
        elif "health" in type_lower or "food" in type_lower:
            return PermitType.HEALTH
        elif "liquor" in type_lower or "alcohol" in type_lower:
            return PermitType.LIQUOR
        elif "business" in type_lower or "license" in type_lower:
            return PermitType.BUSINESS_LICENSE
        elif "occupan" in type_lower or "certificate" in type_lower:
            return PermitType.OCCUPANCY
        elif "zon" in type_lower:
            return PermitType.ZONING
        else:
            return PermitType.OTHER

    def _process_permits(
        self,
        permits: list[Permit],
        city: str,
        state: str,
        start_date: datetime | None,
        end_date: datetime | None,
        permit_types: list[PermitType] | None,
        min_cost: float | None,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Process permits and yield signals.

        Args:
            permits: List of Permit objects
            city: City name
            state: State code
            start_date: Start date filter
            end_date: End date filter
            permit_types: Permit types filter
            min_cost: Minimum cost filter
            processed: Already processed businesses

        Yields:
            SignalCreate objects
        """
        # Group by business
        business_permits: dict[str, list[Permit]] = {}

        for permit in permits:
            # Apply filters
            if start_date and permit.application_date and permit.application_date < start_date:
                continue
            if end_date and permit.application_date and permit.application_date > end_date:
                continue
            if permit_types and permit.permit_type not in permit_types:
                continue
            if min_cost and permit.estimated_cost and permit.estimated_cost < min_cost:
                continue

            key = self._normalize_business_name(permit.business_name)
            if key not in business_permits:
                business_permits[key] = []
            business_permits[key].append(permit)

        # Generate signals
        for business_name, permit_list in business_permits.items():
            if business_name in processed:
                continue
            processed.add(business_name)

            # Aggregate permit data
            permit_signal = PermitSignal(
                business_name=business_name,
                total_permits=len(permit_list),
                permits=permit_list,
            )

            for permit in permit_list:
                permit_signal.permit_types[permit.permit_type.value] = (
                    permit_signal.permit_types.get(permit.permit_type.value, 0) + 1
                )
                if permit.estimated_cost:
                    permit_signal.total_estimated_cost += permit.estimated_cost
                if permit.address and permit.address not in permit_signal.locations:
                    permit_signal.locations.append(permit.address)
                if permit.application_date:
                    if (
                        permit_signal.earliest_permit is None
                        or permit.application_date < permit_signal.earliest_permit
                    ):
                        permit_signal.earliest_permit = permit.application_date
                    if (
                        permit_signal.latest_permit is None
                        or permit.application_date > permit_signal.latest_permit
                    ):
                        permit_signal.latest_permit = permit.application_date

            # MCA detection
            mca_result = mca_detector.detect(business_name=business_name)

            # Determine signal type
            if permit_signal.indicates_new_location:
                signal_subtype = "new_location"
            elif permit_signal.indicates_renovation:
                signal_subtype = "renovation"
            else:
                signal_subtype = "expansion"

            # Create signal
            signal_date = permit_signal.latest_permit or datetime.now()

            yield SignalCreate(
                signal_type="PERMIT",
                business_identifier=f"PERMIT:{business_name}:{city}",
                business_name=business_name,
                signal_date=signal_date,
                source=self.SOURCE_NAME,
                state=state,
                raw_data={
                    "total_permits": permit_signal.total_permits,
                    "permit_types": permit_signal.permit_types,
                    "total_estimated_cost": permit_signal.total_estimated_cost,
                    "locations": permit_signal.locations,
                    "signal_strength": permit_signal.signal_strength,
                    "signal_subtype": signal_subtype,
                    "city": city,
                    "earliest_permit": (
                        permit_signal.earliest_permit.isoformat()
                        if permit_signal.earliest_permit
                        else None
                    ),
                    "latest_permit": (
                        permit_signal.latest_permit.isoformat()
                        if permit_signal.latest_permit
                        else None
                    ),
                },
                metadata_=SignalMetadata(
                    is_mca_related=mca_result.is_mca_related,
                    mca_confidence=mca_result.confidence,
                    signal_strength=permit_signal.signal_strength,
                    intent_points=permit_signal.base_points,
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

    def close(self) -> None:
        """Close the HTTP client."""
        self.http_client.close()
