"""CSV and Excel export functionality for leads."""

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from src.models.lead import LeadExport
from src.utils.config import config


class LeadExporter:
    """Export leads to various formats."""

    def __init__(self) -> None:
        """Initialize the exporter with configuration."""
        export_config = config.scoring.get("export", {})
        self._default_columns = export_config.get("columns", [])
        self._sort_config = export_config.get("sort_by", [])

    def export_to_csv(
        self,
        leads: Sequence[LeadExport | dict[str, Any]],
        output_path: str | Path,
        columns: list[str] | None = None,
        include_header: bool = True,
    ) -> Path:
        """Export leads to CSV file.

        Args:
            leads: List of LeadExport objects or dicts
            output_path: Output file path
            columns: Columns to include (uses default if not specified)
            include_header: Whether to include header row

        Returns:
            Path to created file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        columns = columns or self._default_columns

        # Convert to dicts if needed
        rows = []
        for lead in leads:
            if isinstance(lead, LeadExport):
                row = lead.model_dump()
            else:
                row = lead
            rows.append(row)

        # Sort if configured
        rows = self._sort_rows(rows)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=columns,
                extrasaction="ignore",
            )
            if include_header:
                writer.writeheader()
            writer.writerows(rows)

        return output_path

    def export_to_excel(
        self,
        leads: Sequence[LeadExport | dict[str, Any]],
        output_path: str | Path,
        columns: list[str] | None = None,
        sheet_name: str = "Leads",
    ) -> Path:
        """Export leads to Excel file.

        Args:
            leads: List of LeadExport objects or dicts
            output_path: Output file path
            columns: Columns to include
            sheet_name: Name of the Excel sheet

        Returns:
            Path to created file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        columns = columns or self._default_columns

        # Convert to dicts
        rows = []
        for lead in leads:
            if isinstance(lead, LeadExport):
                row = lead.model_dump()
            else:
                row = lead
            rows.append(row)

        # Sort if configured
        rows = self._sort_rows(rows)

        # Create DataFrame
        df = pd.DataFrame(rows)

        # Select and reorder columns
        available_columns = [c for c in columns if c in df.columns]
        df = df[available_columns]

        # Write to Excel with formatting
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets[sheet_name]
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).map(len).max(),
                    len(col),
                ) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)

        return output_path

    def _sort_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort rows according to configuration.

        Args:
            rows: List of row dicts

        Returns:
            Sorted list
        """
        if not self._sort_config or not rows:
            return rows

        # Build sort key function
        def sort_key(row: dict[str, Any]) -> tuple:
            keys = []
            for sort_spec in self._sort_config:
                field = sort_spec.get("field")
                order = sort_spec.get("order", "asc")

                value = row.get(field)

                # Handle None values
                if value is None:
                    value = "" if isinstance(row.get(field, ""), str) else 0

                # Handle Decimal
                if isinstance(value, Decimal):
                    value = float(value)

                # Handle datetime
                if isinstance(value, datetime):
                    value = value.timestamp()

                # Reverse for descending
                if order == "desc" and isinstance(value, (int, float)):
                    value = -value

                keys.append(value)

            return tuple(keys)

        return sorted(rows, key=sort_key)

    def create_export_record(
        self,
        business_name: str,
        signal: Any,
        score_result: Any,
        business: Any = None,
    ) -> LeadExport:
        """Create a LeadExport record from components.

        Args:
            business_name: Business name
            signal: Signal object or dict
            score_result: CompositeScoreResult
            business: Optional Business object

        Returns:
            LeadExport ready for export
        """
        # Extract signal data
        if hasattr(signal, "model_dump"):
            signal_data = signal.model_dump()
        elif hasattr(signal, "__dict__"):
            signal_data = vars(signal)
        else:
            signal_data = signal if isinstance(signal, dict) else {}

        # Get metadata
        metadata = signal_data.get("metadata_", signal_data.get("metadata", {}))
        if hasattr(metadata, "model_dump"):
            metadata = metadata.model_dump()

        # Calculate signal age
        signal_date = signal_data.get("signal_date")
        if isinstance(signal_date, str):
            signal_date = datetime.fromisoformat(signal_date)
        signal_age_days = (datetime.now() - signal_date).days if signal_date else 0

        # Extract address info
        address = {}
        if business and hasattr(business, "address"):
            address = business.address if isinstance(business.address, dict) else {}

        # Get breakdown
        breakdown = score_result.breakdown
        if hasattr(breakdown, "model_dump"):
            breakdown = breakdown.model_dump()

        return LeadExport(
            business_name=business_name,
            dba_name=business.dba_name if business and hasattr(business, "dba_name") else None,
            industry=breakdown.get("industry_name"),
            state=signal_data.get("state", ""),
            fit_score=score_result.fit_score,
            composite_score=score_result.composite_score,
            priority_level=score_result.priority_level.value,
            signal_type=signal_data.get("signal_type", "").value if hasattr(
                signal_data.get("signal_type", ""), "value"
            ) else str(signal_data.get("signal_type", "")),
            signal_date=signal_date,
            signal_age_days=signal_age_days,
            is_mca_related=metadata.get("is_mca_related", False),
            mca_lender=metadata.get("mca_lender_match"),
            time_in_business_months=breakdown.get("time_in_business_months"),
            address_city=address.get("city"),
            address_state=address.get("state"),
            address_zip=address.get("zip_code"),
        )


# Singleton instance
lead_exporter = LeadExporter()
