"""Hiring Signals Harvester for detecting business growth.

Harvests job posting data to identify businesses that are actively hiring,
which indicates growth and potential capital needs.

Growth signals by hiring intensity:
- 5+ active postings: Strong growth signal (85 points)
- 2-4 active postings: Moderate growth signal (60 points)
- 1 active posting: Weak growth signal (30 points)
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterator
from urllib.parse import quote_plus, urljoin

from src.harvesters.base import BaseHarvester, HarvestResult
from src.harvesters.http_client import HarvestHTTPClient, RateLimiter
from src.harvesters.mca_detector import mca_detector
from src.models.signal import SignalCreate, SignalMetadata


@dataclass
class JobPosting:
    """Represents a job posting."""

    title: str
    company: str
    location: str
    posted_date: datetime | None = None
    salary_range: str | None = None
    job_type: str | None = None  # full-time, part-time, contract
    description: str | None = None
    source_url: str | None = None


@dataclass
class HiringSignal:
    """Aggregated hiring signal for a business."""

    company_name: str
    total_postings: int
    posting_types: dict[str, int] = field(default_factory=dict)
    locations: list[str] = field(default_factory=list)
    earliest_posting: datetime | None = None
    latest_posting: datetime | None = None
    postings: list[JobPosting] = field(default_factory=list)

    @property
    def signal_strength(self) -> str:
        """Get signal strength based on posting count."""
        if self.total_postings >= 5:
            return "strong"
        elif self.total_postings >= 2:
            return "moderate"
        else:
            return "weak"

    @property
    def base_points(self) -> int:
        """Get base intent points."""
        if self.total_postings >= 5:
            return 85
        elif self.total_postings >= 2:
            return 60
        else:
            return 30


class HiringSignalsHarvester(BaseHarvester):
    """Harvester for job posting / hiring signals.

    Detects businesses with active hiring, indicating growth and
    potential capital needs for expansion, equipment, etc.

    Sources:
    - Google Jobs API (via scraping)
    - Indeed (public listings)
    - Company career pages
    """

    SOURCE_NAME = "HIRING_SIGNALS"

    # Industries with high MCA propensity
    TARGET_INDUSTRIES = [
        "restaurant",
        "retail",
        "construction",
        "trucking",
        "transportation",
        "medical",
        "dental",
        "automotive",
        "manufacturing",
        "wholesale",
        "hospitality",
        "hotel",
        "salon",
        "spa",
        "fitness",
        "gym",
    ]

    # Job titles indicating growth/expansion
    GROWTH_INDICATORS = [
        "manager",
        "supervisor",
        "lead",
        "director",
        "coordinator",
        "assistant manager",
        "shift lead",
        "team lead",
        "general manager",
        "operations",
        "expansion",
    ]

    def __init__(
        self,
        logger: logging.Logger | None = None,
        requests_per_minute: int = 20,
        search_locations: list[str] | None = None,
    ) -> None:
        """Initialize the hiring signals harvester.

        Args:
            logger: Logger instance
            requests_per_minute: Rate limit for requests
            search_locations: Locations to search (defaults to major metros)
        """
        super().__init__(logger=logger)
        self.http_client = HarvestHTTPClient(
            rate_limiter=RateLimiter(
                requests_per_minute=requests_per_minute,
                min_delay_seconds=2.0,
            ),
            logger=logger,
        )

        # Default to major metro areas with high MCA activity
        self.search_locations = search_locations or [
            "Miami, FL",
            "New York, NY",
            "Los Angeles, CA",
            "Houston, TX",
            "Chicago, IL",
            "Dallas, TX",
            "Atlanta, GA",
            "Phoenix, AZ",
            "Philadelphia, PA",
            "San Antonio, TX",
        ]

    def harvest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        mca_only: bool = False,
        locations: list[str] | None = None,
        industries: list[str] | None = None,
        min_postings: int = 1,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Harvest hiring signals from job boards.

        Args:
            start_date: Start date for job postings
            end_date: End date for job postings
            mca_only: Filter to MCA-relevant industries only
            locations: Override search locations
            industries: Specific industries to search
            min_postings: Minimum postings to generate signal
            **kwargs: Additional arguments

        Yields:
            SignalCreate objects for businesses with hiring activity
        """
        self.logger.info("Starting hiring signals harvest")

        search_locations = locations or self.search_locations
        search_industries = industries or (self.TARGET_INDUSTRIES if mca_only else None)

        # Track companies we've already processed
        processed_companies: set[str] = set()

        for location in search_locations:
            self.logger.info(f"Searching hiring signals in {location}")

            try:
                # Search by industry if specified
                if search_industries:
                    for industry in search_industries:
                        for signal in self._search_industry_hiring(
                            location=location,
                            industry=industry,
                            start_date=start_date,
                            end_date=end_date,
                            min_postings=min_postings,
                            processed=processed_companies,
                        ):
                            yield signal
                else:
                    # General hiring search
                    for signal in self._search_general_hiring(
                        location=location,
                        start_date=start_date,
                        end_date=end_date,
                        min_postings=min_postings,
                        processed=processed_companies,
                    ):
                        yield signal

            except Exception as e:
                self.logger.error(f"Error searching {location}: {e}")
                continue

        self.logger.info(
            f"Hiring harvest complete: {len(processed_companies)} companies found"
        )

    def _search_industry_hiring(
        self,
        location: str,
        industry: str,
        start_date: datetime | None,
        end_date: datetime | None,
        min_postings: int,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Search for hiring in a specific industry.

        Args:
            location: Search location
            industry: Industry to search
            start_date: Start date filter
            end_date: End date filter
            min_postings: Minimum postings threshold
            processed: Set of already processed companies

        Yields:
            SignalCreate objects
        """
        # Build search query
        query = f"{industry} jobs"

        # Use Google Jobs search (public)
        search_url = self._build_google_jobs_url(query, location)

        try:
            response = self.http_client.get(search_url)
            if response.status_code != 200:
                return

            # Parse job listings
            hiring_signals = self._parse_job_listings(
                response.text,
                location,
                start_date,
                end_date,
            )

            # Aggregate by company and yield signals
            for signal in self._aggregate_and_yield(
                hiring_signals,
                min_postings,
                processed,
                industry,
            ):
                yield signal

        except Exception as e:
            self.logger.error(f"Error searching {industry} in {location}: {e}")

    def _search_general_hiring(
        self,
        location: str,
        start_date: datetime | None,
        end_date: datetime | None,
        min_postings: int,
        processed: set[str],
    ) -> Iterator[SignalCreate]:
        """Search for general hiring activity.

        Args:
            location: Search location
            start_date: Start date filter
            end_date: End date filter
            min_postings: Minimum postings threshold
            processed: Set of already processed companies

        Yields:
            SignalCreate objects
        """
        # Search for growth-indicating job titles
        for title in self.GROWTH_INDICATORS[:5]:  # Limit to avoid rate limits
            query = f"{title} jobs"
            search_url = self._build_google_jobs_url(query, location)

            try:
                response = self.http_client.get(search_url)
                if response.status_code != 200:
                    continue

                hiring_signals = self._parse_job_listings(
                    response.text,
                    location,
                    start_date,
                    end_date,
                )

                for signal in self._aggregate_and_yield(
                    hiring_signals,
                    min_postings,
                    processed,
                ):
                    yield signal

            except Exception as e:
                self.logger.error(f"Error searching {title} in {location}: {e}")
                continue

    def _build_google_jobs_url(self, query: str, location: str) -> str:
        """Build Google Jobs search URL.

        Args:
            query: Search query
            location: Location string

        Returns:
            Search URL
        """
        encoded_query = quote_plus(f"{query} near {location}")
        return f"https://www.google.com/search?q={encoded_query}&ibp=htl;jobs"

    def _parse_job_listings(
        self,
        html: str,
        location: str,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[JobPosting]:
        """Parse job listings from HTML.

        Args:
            html: HTML content
            location: Search location
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of JobPosting objects
        """
        postings = []

        # Extract job data from Google Jobs HTML
        # Look for structured data patterns
        company_pattern = r'"employer_name"\s*:\s*"([^"]+)"'
        title_pattern = r'"title"\s*:\s*"([^"]+)"'
        date_pattern = r'"date_posted"\s*:\s*"([^"]+)"'

        companies = re.findall(company_pattern, html)
        titles = re.findall(title_pattern, html)
        dates = re.findall(date_pattern, html)

        # Also try alternate patterns for different page structures
        if not companies:
            # Try alternate HTML structure
            company_alt = r'data-company-name="([^"]+)"'
            companies = re.findall(company_alt, html)

        if not titles:
            title_alt = r'class="[^"]*job[^"]*title[^"]*"[^>]*>([^<]+)'
            titles = re.findall(title_alt, html, re.IGNORECASE)

        # Create job postings
        for i, company in enumerate(companies):
            title = titles[i] if i < len(titles) else "Unknown Position"

            # Parse date if available
            posted_date = None
            if i < len(dates):
                try:
                    posted_date = datetime.fromisoformat(dates[i].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    posted_date = datetime.now()
            else:
                posted_date = datetime.now()

            # Apply date filters
            if start_date and posted_date < start_date:
                continue
            if end_date and posted_date > end_date:
                continue

            posting = JobPosting(
                title=title,
                company=company,
                location=location,
                posted_date=posted_date,
            )
            postings.append(posting)

        return postings

    def _aggregate_and_yield(
        self,
        postings: list[JobPosting],
        min_postings: int,
        processed: set[str],
        industry: str | None = None,
    ) -> Iterator[SignalCreate]:
        """Aggregate postings by company and yield signals.

        Args:
            postings: List of job postings
            min_postings: Minimum postings to generate signal
            processed: Set of already processed companies
            industry: Industry context

        Yields:
            SignalCreate objects
        """
        # Group by company
        company_postings: dict[str, list[JobPosting]] = {}
        for posting in postings:
            company = self._normalize_company_name(posting.company)
            if company not in company_postings:
                company_postings[company] = []
            company_postings[company].append(posting)

        # Generate signals for companies meeting threshold
        for company, posts in company_postings.items():
            if len(posts) < min_postings:
                continue

            if company in processed:
                continue
            processed.add(company)

            # Create hiring signal
            hiring_signal = HiringSignal(
                company_name=company,
                total_postings=len(posts),
                postings=posts,
            )

            # Aggregate posting data
            for post in posts:
                if post.job_type:
                    hiring_signal.posting_types[post.job_type] = (
                        hiring_signal.posting_types.get(post.job_type, 0) + 1
                    )
                if post.location and post.location not in hiring_signal.locations:
                    hiring_signal.locations.append(post.location)
                if post.posted_date:
                    if (
                        hiring_signal.earliest_posting is None
                        or post.posted_date < hiring_signal.earliest_posting
                    ):
                        hiring_signal.earliest_posting = post.posted_date
                    if (
                        hiring_signal.latest_posting is None
                        or post.posted_date > hiring_signal.latest_posting
                    ):
                        hiring_signal.latest_posting = post.posted_date

            # Detect MCA relevance
            mca_result = mca_detector.detect(
                business_name=company,
                metadata={"industry": industry} if industry else {},
            )

            # Create signal
            signal_date = hiring_signal.latest_posting or datetime.now()
            location_str = hiring_signal.locations[0] if hiring_signal.locations else ""

            # Extract state from location
            state = None
            if location_str:
                state_match = re.search(r",\s*([A-Z]{2})\b", location_str)
                if state_match:
                    state = state_match.group(1)

            yield SignalCreate(
                signal_type="HIRING",
                business_identifier=f"HIRING:{company}",
                business_name=company,
                signal_date=signal_date,
                source=self.SOURCE_NAME,
                state=state,
                raw_data={
                    "total_postings": hiring_signal.total_postings,
                    "posting_types": hiring_signal.posting_types,
                    "locations": hiring_signal.locations,
                    "signal_strength": hiring_signal.signal_strength,
                    "base_points": hiring_signal.base_points,
                    "earliest_posting": (
                        hiring_signal.earliest_posting.isoformat()
                        if hiring_signal.earliest_posting
                        else None
                    ),
                    "latest_posting": (
                        hiring_signal.latest_posting.isoformat()
                        if hiring_signal.latest_posting
                        else None
                    ),
                    "industry": industry,
                },
                metadata_=SignalMetadata(
                    is_mca_related=mca_result.is_mca_related,
                    mca_confidence=mca_result.confidence,
                    signal_strength=hiring_signal.signal_strength,
                    intent_points=hiring_signal.base_points,
                ),
            )

    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for deduplication.

        Args:
            name: Raw company name

        Returns:
            Normalized name
        """
        # Remove common suffixes
        suffixes = [
            " Inc",
            " Inc.",
            " LLC",
            " L.L.C.",
            " Corp",
            " Corp.",
            " Co",
            " Co.",
            " Ltd",
            " Ltd.",
            " LP",
            " L.P.",
        ]

        normalized = name.strip()
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]

        return normalized.strip()

    def search_company(
        self,
        company_name: str,
        location: str | None = None,
    ) -> HiringSignal | None:
        """Search for hiring activity at a specific company.

        Args:
            company_name: Company to search
            location: Optional location filter

        Returns:
            HiringSignal or None if no postings found
        """
        query = f"{company_name} jobs"
        if location:
            query += f" {location}"

        search_url = self._build_google_jobs_url(query, location or "")

        try:
            response = self.http_client.get(search_url)
            if response.status_code != 200:
                return None

            postings = self._parse_job_listings(
                response.text,
                location or "",
                None,
                None,
            )

            # Filter to matching company
            company_postings = [
                p
                for p in postings
                if self._normalize_company_name(p.company).lower()
                == self._normalize_company_name(company_name).lower()
            ]

            if not company_postings:
                return None

            signal = HiringSignal(
                company_name=company_name,
                total_postings=len(company_postings),
                postings=company_postings,
            )

            return signal

        except Exception as e:
            self.logger.error(f"Error searching {company_name}: {e}")
            return None

    def close(self) -> None:
        """Close the HTTP client."""
        self.http_client.close()
