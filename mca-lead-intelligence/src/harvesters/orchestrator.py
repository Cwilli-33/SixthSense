"""Harvester Orchestrator for coordinating multiple data sources.

The orchestrator manages multiple harvesters and provides:
- Unified interface for harvesting from multiple sources
- Parallel harvesting support
- Deduplication across sources
- Progress tracking and statistics
- Error handling and recovery
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterator

from src.harvesters.base import BaseHarvester, HarvestResult
from src.harvesters.mca_detector import mca_detector
from src.harvesters.sec_edgar import SECEdgarHarvester
from src.harvesters.ucc import FloridaUCCHarvester
from src.harvesters.ucc_multistate import MultiStateUCCHarvester
from src.harvesters.hiring import HiringSignalsHarvester
from src.harvesters.tax_liens import TaxLienHarvester
from src.harvesters.permits import PermitsHarvester
from src.models.signal import SignalCreate


@dataclass
class OrchestratorResult:
    """Result of orchestrated harvesting."""

    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    total_signals: int = 0
    signals_by_source: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    harvesters_run: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def success(self) -> bool:
        """Check if harvest was successful (no fatal errors)."""
        return len(self.errors) == 0 or self.total_signals > 0


@dataclass
class HarvesterConfig:
    """Configuration for a harvester."""

    harvester_class: type[BaseHarvester]
    enabled: bool = True
    priority: int = 1  # Lower = higher priority
    kwargs: dict[str, Any] = field(default_factory=dict)


class HarvesterOrchestrator:
    """Orchestrate harvesting from multiple data sources.

    Example usage:
        orchestrator = HarvesterOrchestrator()
        orchestrator.register_harvester("florida_ucc", FloridaUCCHarvester)
        orchestrator.register_harvester("sec_edgar", SECEdgarHarvester)

        for signal in orchestrator.harvest_all(start_date=start, mca_only=True):
            process_signal(signal)
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        max_workers: int = 3,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            logger: Logger instance
            max_workers: Maximum parallel harvester threads
        """
        self.logger = logger or logging.getLogger(__name__)
        self.max_workers = max_workers
        self._harvesters: dict[str, HarvesterConfig] = {}
        self._active_instances: dict[str, BaseHarvester] = {}
        self._result: OrchestratorResult | None = None

        # Register default harvesters
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default harvesters."""
        # Core UCC harvesters (highest priority - most valuable signals)
        self.register_harvester(
            "florida_ucc",
            FloridaUCCHarvester,
            priority=1,
            kwargs={"requests_per_minute": 20},
        )
        self.register_harvester(
            "multistate_ucc",
            MultiStateUCCHarvester,
            priority=1,
            kwargs={"requests_per_minute": 15, "states": ["NY", "TX", "CA"]},
        )

        # SEC filings (public companies)
        self.register_harvester(
            "sec_edgar",
            SECEdgarHarvester,
            priority=2,
            kwargs={"requests_per_minute": 30},
        )

        # Growth signals
        self.register_harvester(
            "hiring",
            HiringSignalsHarvester,
            priority=3,
            kwargs={"requests_per_minute": 20},
        )
        self.register_harvester(
            "permits",
            PermitsHarvester,
            priority=3,
            kwargs={"requests_per_minute": 15},
        )

        # Stress signals
        self.register_harvester(
            "tax_liens",
            TaxLienHarvester,
            priority=4,
            kwargs={"requests_per_minute": 15},
        )

    def register_harvester(
        self,
        name: str,
        harvester_class: type[BaseHarvester],
        enabled: bool = True,
        priority: int = 1,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Register a harvester.

        Args:
            name: Unique name for the harvester
            harvester_class: Harvester class to instantiate
            enabled: Whether harvester is enabled
            priority: Priority (lower = higher priority)
            kwargs: Additional kwargs to pass to harvester constructor
        """
        self._harvesters[name] = HarvesterConfig(
            harvester_class=harvester_class,
            enabled=enabled,
            priority=priority,
            kwargs=kwargs or {},
        )
        self.logger.info(f"Registered harvester: {name}")

    def enable_harvester(self, name: str) -> None:
        """Enable a harvester."""
        if name in self._harvesters:
            self._harvesters[name].enabled = True

    def disable_harvester(self, name: str) -> None:
        """Disable a harvester."""
        if name in self._harvesters:
            self._harvesters[name].enabled = False

    def get_harvester(self, name: str) -> BaseHarvester | None:
        """Get or create a harvester instance.

        Args:
            name: Harvester name

        Returns:
            Harvester instance or None if not found
        """
        if name not in self._harvesters:
            return None

        if name not in self._active_instances:
            config = self._harvesters[name]
            self._active_instances[name] = config.harvester_class(
                logger=self.logger,
                **config.kwargs,
            )

        return self._active_instances[name]

    def harvest_all(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        sources: list[str] | None = None,
        mca_only: bool = False,
        deduplicate: bool = True,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Harvest from all enabled sources.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            sources: Specific sources to harvest from (None = all enabled)
            mca_only: Only return MCA-related signals
            deduplicate: Remove duplicate signals
            **kwargs: Additional kwargs passed to harvesters

        Yields:
            SignalCreate objects from all sources
        """
        self._result = OrchestratorResult()
        seen_identifiers = set()

        # Get enabled harvesters sorted by priority
        enabled = self._get_enabled_harvesters(sources)

        self.logger.info(f"Starting orchestrated harvest from {len(enabled)} sources")

        for name in enabled:
            self._result.harvesters_run.append(name)
            harvester = self.get_harvester(name)

            if harvester is None:
                continue

            self.logger.info(f"Harvesting from {name}...")
            source_count = 0

            try:
                for signal in harvester.harvest(
                    start_date=start_date,
                    end_date=end_date,
                    mca_only=mca_only,
                    **kwargs,
                ):
                    # Deduplication
                    if deduplicate:
                        identifier = f"{signal.business_name}:{signal.signal_date.date()}"
                        if identifier in seen_identifiers:
                            continue
                        seen_identifiers.add(identifier)

                    source_count += 1
                    self._result.total_signals += 1
                    yield signal

            except Exception as e:
                self.logger.error(f"Error harvesting from {name}: {e}")
                self._result.errors.append({
                    "source": name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })

            self._result.signals_by_source[name] = source_count
            self.logger.info(f"Harvested {source_count} signals from {name}")

        self._result.end_time = datetime.now()
        self.logger.info(
            f"Orchestrated harvest complete: {self._result.total_signals} signals "
            f"in {self._result.duration_seconds:.1f}s"
        )

    def harvest_parallel(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        sources: list[str] | None = None,
        mca_only: bool = False,
        deduplicate: bool = True,
        callback: Callable[[SignalCreate], None] | None = None,
        **kwargs: Any,
    ) -> OrchestratorResult:
        """Harvest from sources in parallel.

        Note: This method uses threads and a callback instead of yielding.
        Use harvest_all() for sequential iteration.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            sources: Specific sources to harvest from
            mca_only: Only return MCA-related signals
            deduplicate: Remove duplicate signals
            callback: Function to call for each signal
            **kwargs: Additional kwargs passed to harvesters

        Returns:
            OrchestratorResult with statistics
        """
        self._result = OrchestratorResult()
        seen_identifiers = set()

        enabled = self._get_enabled_harvesters(sources)

        self.logger.info(f"Starting parallel harvest from {len(enabled)} sources")

        def harvest_source(name: str) -> tuple[str, int, list[SignalCreate]]:
            """Harvest from a single source."""
            harvester = self.get_harvester(name)
            if harvester is None:
                return name, 0, []

            signals = []
            try:
                for signal in harvester.harvest(
                    start_date=start_date,
                    end_date=end_date,
                    mca_only=mca_only,
                    **kwargs,
                ):
                    signals.append(signal)
            except Exception as e:
                self.logger.error(f"Error in parallel harvest from {name}: {e}")
                self._result.errors.append({
                    "source": name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })

            return name, len(signals), signals

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(harvest_source, name): name for name in enabled}

            for future in as_completed(futures):
                name, count, signals = future.result()
                self._result.harvesters_run.append(name)
                self._result.signals_by_source[name] = count

                for signal in signals:
                    # Deduplication
                    if deduplicate:
                        identifier = f"{signal.business_name}:{signal.signal_date.date()}"
                        if identifier in seen_identifiers:
                            continue
                        seen_identifiers.add(identifier)

                    self._result.total_signals += 1

                    if callback:
                        callback(signal)

                self.logger.info(f"Completed {name}: {count} signals")

        self._result.end_time = datetime.now()
        return self._result

    def _get_enabled_harvesters(self, sources: list[str] | None) -> list[str]:
        """Get list of enabled harvesters sorted by priority.

        Args:
            sources: Specific sources to include (None = all enabled)

        Returns:
            List of harvester names sorted by priority
        """
        if sources:
            # Filter to specified sources
            enabled = [
                name for name in sources
                if name in self._harvesters and self._harvesters[name].enabled
            ]
        else:
            # All enabled harvesters
            enabled = [
                name for name, config in self._harvesters.items()
                if config.enabled
            ]

        # Sort by priority
        enabled.sort(key=lambda n: self._harvesters[n].priority)

        return enabled

    def harvest_ucc(
        self,
        state: str = "FL",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        mca_only: bool = True,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Convenience method to harvest UCC filings.

        Args:
            state: State to harvest from (currently only FL supported)
            start_date: Start date
            end_date: End date
            mca_only: Only MCA-related filings
            **kwargs: Additional kwargs

        Yields:
            SignalCreate objects
        """
        if state.upper() == "FL":
            harvester = self.get_harvester("florida_ucc")
            if harvester:
                yield from harvester.harvest(
                    start_date=start_date,
                    end_date=end_date,
                    mca_only=mca_only,
                    **kwargs,
                )

    def harvest_sec(
        self,
        company_name: str | None = None,
        cik: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Convenience method to harvest SEC filings.

        Args:
            company_name: Company name to search
            cik: CIK number
            start_date: Start date
            end_date: End date
            **kwargs: Additional kwargs

        Yields:
            SignalCreate objects
        """
        harvester = self.get_harvester("sec_edgar")
        if harvester:
            yield from harvester.harvest(
                start_date=start_date,
                end_date=end_date,
                company_name=company_name,
                cik=cik,
                **kwargs,
            )

    def search_mca_lenders(
        self,
        lenders: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Iterator[SignalCreate]:
        """Search for UCC filings from specific MCA lenders.

        Args:
            lenders: List of MCA lender names (None = use defaults)
            start_date: Start date
            end_date: End date

        Yields:
            SignalCreate objects for MCA lender filings
        """
        harvester = self.get_harvester("florida_ucc")
        if harvester:
            yield from harvester.harvest(
                start_date=start_date,
                end_date=end_date,
                known_mca_lenders=lenders,
                mca_only=True,
            )

    @property
    def result(self) -> OrchestratorResult | None:
        """Get the result of the last harvest operation."""
        return self._result

    def get_statistics(self) -> dict[str, Any]:
        """Get current statistics.

        Returns:
            Dictionary with harvest statistics
        """
        if self._result is None:
            return {"status": "no harvest performed"}

        return {
            "status": "success" if self._result.success else "failed",
            "total_signals": self._result.total_signals,
            "signals_by_source": self._result.signals_by_source,
            "harvesters_run": self._result.harvesters_run,
            "duration_seconds": self._result.duration_seconds,
            "errors": len(self._result.errors),
        }

    def close(self) -> None:
        """Close all active harvester instances."""
        for name, harvester in self._active_instances.items():
            if hasattr(harvester, "close"):
                harvester.close()
        self._active_instances.clear()


# Singleton instance for convenience
harvester_orchestrator = HarvesterOrchestrator()
