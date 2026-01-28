"""Base harvester class - abstract interface for all data harvesters."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Iterator

from pydantic import BaseModel, Field

from src.models.signal import SignalCreate, SignalType


class HarvestResult(BaseModel):
    """Result of a harvest operation."""

    source: str
    state: str
    start_time: datetime
    end_time: datetime | None = None
    signals_found: int = 0
    signals_stored: int = 0
    signals_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate harvest duration in seconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.signals_found == 0:
            return 0.0
        return (self.signals_stored / self.signals_found) * 100


class BaseHarvester(ABC):
    """Abstract base class for data harvesters.

    All harvesters must implement:
    - harvest(): Main harvesting method that yields signals
    - get_source_name(): Return the source identifier
    - get_state(): Return the state code
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize the harvester.

        Args:
            logger: Optional logger instance. Creates one if not provided.
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._result: HarvestResult | None = None

    @abstractmethod
    def get_source_name(self) -> str:
        """Return the source identifier (e.g., 'FL_SOS').

        Returns:
            Source name string
        """
        pass

    @abstractmethod
    def get_state(self) -> str:
        """Return the state code (e.g., 'FL').

        Returns:
            Two-letter state code
        """
        pass

    @abstractmethod
    def get_supported_signal_types(self) -> list[SignalType]:
        """Return list of signal types this harvester can produce.

        Returns:
            List of SignalType enum values
        """
        pass

    @abstractmethod
    def harvest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        """Harvest signals from the data source.

        Args:
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            **kwargs: Additional harvester-specific parameters

        Yields:
            SignalCreate objects ready for database insertion
        """
        pass

    def run(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        **kwargs: Any,
    ) -> HarvestResult:
        """Run the harvest operation and return results.

        This is the main entry point for running a harvest. It wraps
        the harvest() method with result tracking and error handling.

        Args:
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            **kwargs: Additional harvester-specific parameters

        Returns:
            HarvestResult with statistics about the harvest
        """
        self._result = HarvestResult(
            source=self.get_source_name(),
            state=self.get_state(),
            start_time=datetime.now(),
        )

        try:
            self.logger.info(
                f"Starting harvest from {self.get_source_name()} "
                f"({self.get_state()})"
            )

            for signal in self.harvest(start_date, end_date, **kwargs):
                self._result.signals_found += 1
                yield signal

        except Exception as e:
            self.logger.error(f"Harvest error: {e}")
            self._result.errors.append(str(e))
            raise

        finally:
            self._result.end_time = datetime.now()
            self.logger.info(
                f"Harvest complete: {self._result.signals_found} signals found "
                f"in {self._result.duration_seconds:.2f}s"
            )

    @property
    def result(self) -> HarvestResult | None:
        """Get the result of the last harvest run."""
        return self._result

    def validate_date_range(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> tuple[datetime | None, datetime | None]:
        """Validate and normalize date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Tuple of (start_date, end_date) normalized

        Raises:
            ValueError: If date range is invalid
        """
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be before end_date")

        return start_date, end_date


class MockHarvester(BaseHarvester):
    """Mock harvester for testing purposes."""

    def __init__(
        self,
        signals: list[SignalCreate] | None = None,
        source: str = "MOCK",
        state: str = "XX",
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize mock harvester.

        Args:
            signals: List of signals to return during harvest
            source: Mock source name
            state: Mock state code
            logger: Optional logger
        """
        super().__init__(logger)
        self._signals = signals or []
        self._source = source
        self._state = state

    def get_source_name(self) -> str:
        return self._source

    def get_state(self) -> str:
        return self._state

    def get_supported_signal_types(self) -> list[SignalType]:
        return list(SignalType)

    def harvest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        **kwargs: Any,
    ) -> Iterator[SignalCreate]:
        for signal in self._signals:
            yield signal
