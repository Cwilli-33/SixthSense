"""Signal event model - represents business signals like UCC filings."""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Enum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import GUID, Base, TimestampMixin


class SignalType(str, enum.Enum):
    """Types of business signals we track."""

    UCC_FILING = "ucc_filing"
    UCC_TERMINATION = "ucc_termination"
    UCC_AMENDMENT = "ucc_amendment"
    UCC_CONTINUATION = "ucc_continuation"
    BUSINESS_FORMATION = "business_formation"
    PERMIT_APPLICATION = "permit_application"
    HIRING_SIGNAL = "hiring_signal"
    EQUIPMENT_PURCHASE = "equipment_purchase"


class Signal(Base, TimestampMixin):
    """Database model for signal events."""

    __tablename__ = "signals"

    signal_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    signal_type: Mapped[SignalType] = mapped_column(
        Enum(SignalType),
        nullable=False,
        index=True,
    )
    business_identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    business_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    signal_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    harvested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Data source identifier, e.g., FL_SOS",
    )
    state: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        index=True,
    )
    raw_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(Text, "sqlite"),
        nullable=False,
        default=dict,
        comment="Complete original record from source",
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB().with_variant(Text, "sqlite"),
        nullable=False,
        default=dict,
        comment="Signal-specific extracted fields",
    )

    __table_args__ = (
        Index("ix_signals_source_date", "source", "signal_date"),
        Index("ix_signals_type_state", "signal_type", "state"),
    )

    def __repr__(self) -> str:
        return f"<Signal {self.signal_type.value}: {self.business_name}>"


# Pydantic models for validation and serialization

class SignalMetadata(BaseModel):
    """Base metadata for all signal types."""

    secured_party: Optional[str] = None
    secured_party_address: Optional[str] = None
    collateral_description: Optional[str] = None
    filing_number: Optional[str] = None
    filing_type: Optional[str] = None
    original_filing_date: Optional[datetime] = None
    lapse_date: Optional[datetime] = None
    is_mca_related: bool = False
    mca_lender_match: Optional[str] = None
    mca_pattern_match: Optional[str] = None

    class Config:
        extra = "allow"


class SignalCreate(BaseModel):
    """Schema for creating a new signal."""

    signal_type: SignalType
    business_identifier: str = Field(..., min_length=1, max_length=255)
    business_name: str = Field(..., min_length=1, max_length=500)
    signal_date: datetime
    source: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    metadata_: SignalMetadata = Field(default_factory=SignalMetadata, alias="metadata")

    class Config:
        populate_by_name = True


class SignalResponse(BaseModel):
    """Schema for signal response."""

    signal_id: uuid.UUID
    signal_type: SignalType
    business_identifier: str
    business_name: str
    signal_date: datetime
    harvested_at: datetime
    source: str
    state: str
    raw_data: dict[str, Any]
    metadata_: SignalMetadata = Field(alias="metadata")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
