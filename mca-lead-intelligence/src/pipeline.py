"""Lead generation pipeline - orchestrates harvesting, scoring, and export."""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy.orm import Session

from src.harvesters.base import BaseHarvester, HarvestResult
from src.harvesters.orchestrator import HarvesterOrchestrator, harvester_orchestrator
from src.harvesters.ucc import FloridaUCCHarvester
from src.models.business import Business, BusinessCreate
from src.models.lead import Lead, LeadExport
from src.models.signal import Signal, SignalCreate
from src.scoring.composite import CompositeScoreResult, composite_scorer
from src.scoring.intent import IntentSignal, IntentSignalType, intent_scorer
from src.utils.config import config
from src.utils.database import get_db, init_db
from src.utils.exporter import LeadExporter, lead_exporter


class LeadPipeline:
    """Orchestrate the full lead generation pipeline.

    Pipeline stages:
    1. Harvest: Collect signals from data sources (UCC, SEC, etc.)
    2. Process: Create/update business records, detect MCA
    3. Score: Calculate FIT, INTENT, TIMING, and composite scores (v4.0)
    4. Export: Generate CSV/Excel output
    """

    def __init__(
        self,
        harvester: BaseHarvester | None = None,
        orchestrator: HarvesterOrchestrator | None = None,
        exporter: LeadExporter | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            harvester: Single harvester to use (for backward compatibility)
            orchestrator: Harvester orchestrator for multi-source harvesting
            exporter: Exporter to use (defaults to singleton)
            logger: Logger instance
        """
        self.harvester = harvester
        self.orchestrator = orchestrator or harvester_orchestrator
        self.exporter = exporter or lead_exporter
        self.logger = logger or logging.getLogger(__name__)

        self._signals_processed = 0
        self._leads_generated = 0
        self._errors: list[str] = []
        self._signals_by_source: dict[str, int] = {}

    def run(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        output_path: str | Path | None = None,
        mca_only: bool = False,
        persist: bool = False,
        sources: list[str] | None = None,
        use_orchestrator: bool = True,
        parallel: bool = False,
        **harvester_kwargs: Any,
    ) -> list[LeadExport]:
        """Run the full pipeline.

        Args:
            start_date: Start date for harvesting
            end_date: End date for harvesting
            output_path: Path for CSV output (auto-generated if not specified)
            mca_only: Only process MCA-related signals
            persist: Whether to persist to database
            sources: List of sources to harvest from (e.g., ["florida_ucc", "sec_edgar"])
            use_orchestrator: Use orchestrator for multi-source harvesting (default True)
            parallel: Enable parallel harvesting
            **harvester_kwargs: Additional args for harvester

        Returns:
            List of LeadExport records
        """
        self.logger.info("Starting lead pipeline (v4.0)")
        self._signals_processed = 0
        self._leads_generated = 0
        self._errors = []
        self._signals_by_source = {}

        # Initialize database if persisting
        if persist:
            init_db()

        # Collect all leads
        leads: list[LeadExport] = []

        try:
            # Choose harvesting method
            if self.harvester and not use_orchestrator:
                # Use single harvester (backward compatible)
                signal_iterator = self.harvester.run(
                    start_date=start_date,
                    end_date=end_date,
                    mca_only=mca_only,
                    **harvester_kwargs,
                )
            else:
                # Use orchestrator for multi-source harvesting
                if parallel:
                    # Parallel mode collects all signals first
                    self.logger.info("Running parallel harvest from multiple sources")
                    result = self.orchestrator.harvest_parallel(
                        start_date=start_date,
                        end_date=end_date,
                        sources=sources,
                        mca_only=mca_only,
                        **harvester_kwargs,
                    )
                    self._signals_by_source = result.signals_by_source
                    # Process collected signals (callback mode doesn't yield)
                    signal_iterator = iter([])  # Empty, processed via callback
                else:
                    signal_iterator = self.orchestrator.harvest_all(
                        start_date=start_date,
                        end_date=end_date,
                        sources=sources,
                        mca_only=mca_only,
                        **harvester_kwargs,
                    )

            # Process signals
            for signal in signal_iterator:
                try:
                    # Track source
                    source = signal.source
                    self._signals_by_source[source] = self._signals_by_source.get(source, 0) + 1

                    # Process signal into lead
                    lead_export = self._process_signal(signal, persist=persist)
                    if lead_export:
                        leads.append(lead_export)
                        self._leads_generated += 1
                    self._signals_processed += 1

                except Exception as e:
                    self.logger.error(f"Error processing signal: {e}")
                    self._errors.append(str(e))

        except Exception as e:
            self.logger.error(f"Pipeline error: {e}")
            self._errors.append(str(e))
            raise

        # Export results
        if output_path and leads:
            self._export_leads(leads, output_path)

        self.logger.info(
            f"Pipeline complete: {self._signals_processed} signals processed, "
            f"{self._leads_generated} leads generated from {len(self._signals_by_source)} sources"
        )

        return leads

    def _process_signal(
        self,
        signal: SignalCreate,
        persist: bool = False,
    ) -> LeadExport | None:
        """Process a single signal into a lead using v4.0 scoring.

        Args:
            signal: Signal to process
            persist: Whether to persist to database

        Returns:
            LeadExport or None if processing failed
        """
        # Extract metadata
        metadata = signal.metadata_ if hasattr(signal, "metadata_") else {}
        if hasattr(metadata, "model_dump"):
            metadata_dict = metadata.model_dump()
        else:
            metadata_dict = dict(metadata) if metadata else {}

        is_mca_related = metadata_dict.get("is_mca_related", False)
        mca_lender = metadata_dict.get("mca_lender_match")

        # Build intent signals for v4.0 scoring
        intent_signals = self._build_intent_signals(signal, metadata_dict)

        # Calculate UCC months old for refinance window
        ucc_months_old = None
        if signal.signal_date:
            days_old = (datetime.now() - signal.signal_date).days
            ucc_months_old = days_old / 30.0

        # Score the lead with v4.0 time-weighted engine
        score_result = composite_scorer.score(
            business_name=signal.business_name,
            signal=signal,
            is_mca_related=is_mca_related,
            mca_lender=mca_lender,
            intent_signals=intent_signals,
            ucc_months_old=ucc_months_old,
            state=signal.state,
        )

        # Persist if requested
        if persist:
            self._persist_signal_and_lead(signal, score_result)

        # Create export record
        return self.exporter.create_export_record(
            business_name=signal.business_name,
            signal=signal,
            score_result=score_result,
        )

    def _build_intent_signals(
        self,
        signal: SignalCreate,
        metadata_dict: dict[str, Any],
    ) -> list[IntentSignal]:
        """Build intent signals for v4.0 INTENT scoring.

        Args:
            signal: The signal being processed
            metadata_dict: Signal metadata

        Returns:
            List of IntentSignal objects
        """
        from src.scoring.decay import DecayClass

        intent_signals = []

        # Determine signal type and scoring parameters
        is_mca_related = metadata_dict.get("is_mca_related", False)

        if is_mca_related:
            # MCA-related UCC filing - high value, standard decay
            signal_type = IntentSignalType.UCC_MCA_LENDER
            base_points = 90
            decay_class = DecayClass.STANDARD
        elif signal.source == "SEC_EDGAR":
            # SEC filing indicates financing activity - moderate value, extended decay
            signal_type = IntentSignalType.SEC_FINANCING
            base_points = 40
            decay_class = DecayClass.EXTENDED
        else:
            # Standard UCC filing - moderate value, standard decay
            signal_type = IntentSignalType.UCC_GENERAL
            base_points = 50
            decay_class = DecayClass.STANDARD

        intent_signal = IntentSignal(
            signal_type=signal_type,
            signal_date=signal.signal_date,
            base_points=base_points,
            decay_class=decay_class,
            raw_data=metadata_dict,
        )
        intent_signals.append(intent_signal)

        return intent_signals

    def _persist_signal_and_lead(
        self,
        signal: SignalCreate,
        score_result: CompositeScoreResult,
    ) -> tuple[uuid.UUID, uuid.UUID]:
        """Persist signal and lead to database.

        Args:
            signal: Signal to persist
            score_result: Scoring result

        Returns:
            Tuple of (signal_id, lead_id)
        """
        with get_db() as db:
            # Create or get business
            business = self._get_or_create_business(db, signal)

            # Create signal record
            signal_record = Signal(
                signal_type=signal.signal_type,
                business_identifier=signal.business_identifier,
                business_name=signal.business_name,
                signal_date=signal.signal_date,
                source=signal.source,
                state=signal.state,
                raw_data=signal.raw_data,
                metadata_=signal.metadata_.model_dump() if hasattr(
                    signal.metadata_, "model_dump"
                ) else dict(signal.metadata_),
            )
            db.add(signal_record)
            db.flush()

            # Create lead record
            lead_record = Lead(
                business_id=business.business_id,
                signal_ids=[str(signal_record.signal_id)],
                fit_score=score_result.fit_score,
                intent_score=score_result.intent_score,
                timing_score=score_result.timing_score,
                composite_score=score_result.composite_score,
                priority_level=score_result.priority_level,
                score_breakdown=score_result.breakdown.model_dump() if hasattr(
                    score_result.breakdown, "model_dump"
                ) else dict(score_result.breakdown),
            )
            db.add(lead_record)

            return signal_record.signal_id, lead_record.lead_id

    def _get_or_create_business(
        self,
        db: Session,
        signal: SignalCreate,
    ) -> Business:
        """Get or create a business record from signal.

        Args:
            db: Database session
            signal: Signal with business info

        Returns:
            Business record
        """
        # Try to find existing business
        existing = db.query(Business).filter(
            Business.legal_name == signal.business_name,
            Business.state == signal.state,
        ).first()

        if existing:
            return existing

        # Create new business
        business = Business(
            legal_name=signal.business_name,
            state=signal.state,
            address={},
        )
        db.add(business)
        db.flush()

        return business

    def _export_leads(
        self,
        leads: list[LeadExport],
        output_path: str | Path,
    ) -> Path:
        """Export leads to file.

        Args:
            leads: Leads to export
            output_path: Output file path

        Returns:
            Path to created file
        """
        output_path = Path(output_path)

        if output_path.suffix.lower() in [".xlsx", ".xls"]:
            return self.exporter.export_to_excel(leads, output_path)
        else:
            return self.exporter.export_to_csv(leads, output_path)

    @property
    def stats(self) -> dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "signals_processed": self._signals_processed,
            "leads_generated": self._leads_generated,
            "signals_by_source": self._signals_by_source,
            "sources_used": list(self._signals_by_source.keys()),
            "errors": len(self._errors),
            "error_messages": self._errors[:10],  # First 10 errors
        }


def run_pipeline(
    file_path: str | Path | None = None,
    output_path: str | Path | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    mca_only: bool = False,
    persist: bool = False,
    sources: list[str] | None = None,
    parallel: bool = False,
) -> list[LeadExport]:
    """Convenience function to run the pipeline.

    Args:
        file_path: Path to input data file (CSV/JSON)
        output_path: Path for output CSV
        start_date: Start date filter
        end_date: End date filter
        mca_only: Only MCA-related signals
        persist: Persist to database
        sources: List of sources to harvest from (e.g., ["florida_ucc", "sec_edgar"])
        parallel: Enable parallel harvesting from multiple sources

    Returns:
        List of generated leads
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Generate default output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path("output") / f"leads_{timestamp}.csv"

    pipeline = LeadPipeline()
    return pipeline.run(
        start_date=start_date,
        end_date=end_date,
        output_path=output_path,
        mca_only=mca_only,
        persist=persist,
        sources=sources,
        parallel=parallel,
        file_path=file_path,
    )
