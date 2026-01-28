#!/usr/bin/env python3
"""Command-line interface for MCA Lead Intelligence."""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from src.pipeline import LeadPipeline, run_pipeline
from src.utils.database import init_db


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def harvest_command(args: argparse.Namespace) -> int:
    """Run the harvest command."""
    setup_logging(args.verbose)

    logger = logging.getLogger("cli")
    logger.info("Starting harvest...")

    # Initialize database if persisting
    if args.persist:
        logger.info("Initializing database...")
        init_db()

    # Parse dates
    start_date = None
    end_date = None

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")

    # Generate output path
    output_path = args.output
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"output/leads_{timestamp}.csv"

    try:
        leads = run_pipeline(
            file_path=args.input,
            output_path=output_path,
            start_date=start_date,
            end_date=end_date,
            mca_only=args.mca_only,
            persist=args.persist,
        )

        logger.info(f"Generated {len(leads)} leads")
        logger.info(f"Output written to: {output_path}")

        # Print summary
        if leads:
            priority_counts = {}
            for lead in leads:
                priority_counts[lead.priority_level] = (
                    priority_counts.get(lead.priority_level, 0) + 1
                )

            print("\nLead Summary:")
            print("-" * 30)
            for priority in ["P1", "P2", "P3", "P4", "P5"]:
                count = priority_counts.get(priority, 0)
                print(f"  {priority}: {count} leads")
            print(f"  Total: {len(leads)} leads")

            # MCA breakdown
            mca_count = sum(1 for l in leads if l.is_mca_related)
            print(f"\nMCA-Related: {mca_count} ({mca_count/len(leads)*100:.1f}%)")

        return 0

    except Exception as e:
        logger.error(f"Harvest failed: {e}")
        return 1


def score_command(args: argparse.Namespace) -> int:
    """Run the score command (re-score existing leads)."""
    setup_logging(args.verbose)

    logger = logging.getLogger("cli")
    logger.info("Scoring functionality not yet implemented")
    logger.info("Use 'harvest' command to generate scored leads")

    return 0


def export_command(args: argparse.Namespace) -> int:
    """Run the export command."""
    setup_logging(args.verbose)

    logger = logging.getLogger("cli")
    logger.info("Export functionality for database leads not yet implemented")
    logger.info("Use 'harvest' command with --output to generate exports")

    return 0


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="MCA Lead Intelligence - Generate scored MCA leads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Harvest from CSV file
  python -m src.cli harvest -i data/ucc_filings.csv -o output/leads.csv

  # Harvest MCA-related only
  python -m src.cli harvest -i data/ucc_filings.csv --mca-only

  # Harvest with date range
  python -m src.cli harvest -i data/ucc_filings.csv --start 2024-01-01 --end 2024-01-31

  # Harvest and persist to database
  python -m src.cli harvest -i data/ucc_filings.csv --persist
        """,
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Harvest command
    harvest_parser = subparsers.add_parser(
        "harvest",
        help="Harvest signals and generate leads",
    )
    harvest_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Input file path (CSV or JSON)",
    )
    harvest_parser.add_argument(
        "-o", "--output",
        help="Output file path (default: output/leads_TIMESTAMP.csv)",
    )
    harvest_parser.add_argument(
        "--start-date",
        dest="start_date",
        help="Start date filter (YYYY-MM-DD)",
    )
    harvest_parser.add_argument(
        "--end-date",
        dest="end_date",
        help="End date filter (YYYY-MM-DD)",
    )
    harvest_parser.add_argument(
        "--mca-only",
        dest="mca_only",
        action="store_true",
        help="Only output MCA-related leads",
    )
    harvest_parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist leads to database",
    )
    harvest_parser.set_defaults(func=harvest_command)

    # Score command
    score_parser = subparsers.add_parser(
        "score",
        help="Re-score existing leads",
    )
    score_parser.set_defaults(func=score_command)

    # Export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export leads from database",
    )
    export_parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output file path",
    )
    export_parser.add_argument(
        "--format",
        choices=["csv", "excel"],
        default="csv",
        help="Output format",
    )
    export_parser.add_argument(
        "--priority",
        nargs="+",
        choices=["P1", "P2", "P3", "P4", "P5"],
        help="Filter by priority levels",
    )
    export_parser.set_defaults(func=export_command)

    # Parse args
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Ensure verbose is available
    if not hasattr(args, "verbose"):
        args.verbose = False

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
