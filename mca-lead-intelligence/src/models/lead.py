"""Lead model - represents scored, actionable leads."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import GUID, Base, TimestampMixin
from src.models.business import Business


class PriorityLevel(str, enum.Enum):
    """Lead priority levels based on composite score."""

    P1 = "P1"  # 75-100: Hot leads, immediate outreach
    P2 = "P2"  # 60-74: Strong leads, high priority
    P3 = "P3"  # 45-59: Good leads, standard follow-up
    P4 = "P4"  # 30-44: Moderate leads, nurture
    P5 = "P5"  # 0-29: Low priority, long-term nurture


class LeadStatus(str, enum.Enum):
    """Lead workflow status."""

    NEW = "new"
    EXPORTED = "exported"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class Lead(Base, TimestampMixin):
    """Database model for scored leads."""

    __tablename__ = "leads"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("businesses.business_id"),
        nullable=False,
        index=True,
    )
    # Store signal IDs as JSON array for SQLite compatibility
    signal_ids: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(Text, "sqlite"),
        nullable=False,
        default=list,
        comment="List of signal UUIDs that generated this lead",
    )

    # Scoring fields
    fit_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="FIT dimension score (0-100)",
    )
    intent_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="INTENT dimension score (0-100) - Phase 2",
    )
    timing_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="TIMING dimension score (0-100) - Phase 3",
    )
    composite_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Weighted composite score (0-100)",
    )
    priority_level: Mapped[PriorityLevel] = mapped_column(
        Enum(PriorityLevel),
        nullable=False,
        index=True,
    )

    # Score breakdown for explainability
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(Text, "sqlite"),
        nullable=False,
        default=dict,
        comment="Detailed breakdown of all score components",
    )

    # Workflow fields
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus),
        nullable=False,
        default=LeadStatus.NEW,
        index=True,
    )
    exported_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business", lazy="joined")

    __table_args__ = (
        Index("ix_leads_priority_status", "priority_level", "status"),
        Index("ix_leads_composite_score", "composite_score", postgresql_using="btree"),
    )

    def __repr__(self) -> str:
        return f"<Lead {self.priority_level.value}: {self.composite_score}>"


# Pydantic models for validation and serialization

class ScoreBreakdown(BaseModel):
    """Detailed breakdown of score components."""

    # FIT components
    industry_propensity: int = Field(0, ge=0, le=10)
    industry_name: Optional[str] = None
    time_in_business_score: int = Field(0, ge=0, le=5)
    time_in_business_months: Optional[int] = None

    # Intent components (Phase 2)
    ucc_refinance_score: int = Field(0, ge=0, le=15)
    ucc_age_months: Optional[int] = None
    mca_stack_count: int = Field(0, ge=0)

    # Timing components (Phase 3)
    signal_freshness_score: int = Field(0, ge=0, le=10)
    signal_age_days: Optional[int] = None

    # Flags
    is_mca_related: bool = False
    mca_lender: Optional[str] = None
    is_nurture: bool = False
    nurture_reason: Optional[str] = None

    class Config:
        extra = "allow"


class LeadCreate(BaseModel):
    """Schema for creating a new lead."""

    business_id: uuid.UUID
    signal_ids: list[uuid.UUID] = Field(default_factory=list)
    fit_score: int = Field(0, ge=0, le=100)
    intent_score: int = Field(0, ge=0, le=100)
    timing_score: int = Field(0, ge=0, le=100)
    composite_score: Decimal = Field(Decimal("0.00"), ge=0, le=100)
    priority_level: PriorityLevel
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    status: LeadStatus = LeadStatus.NEW


class LeadResponse(BaseModel):
    """Schema for lead response."""

    lead_id: uuid.UUID
    business_id: uuid.UUID
    signal_ids: list[str]
    fit_score: int
    intent_score: int
    timing_score: int
    composite_score: Decimal
    priority_level: PriorityLevel
    score_breakdown: dict[str, Any]
    status: LeadStatus
    exported_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def total_signals(self) -> int:
        """Return count of signals."""
        return len(self.signal_ids)

    class Config:
        from_attributes = True


class LeadExport(BaseModel):
    """Schema for CSV export."""

    business_name: str
    dba_name: Optional[str] = None
    industry: Optional[str] = None
    state: str
    fit_score: int
    composite_score: Decimal
    priority_level: str
    signal_type: str
    signal_date: datetime
    signal_age_days: int
    is_mca_related: bool = False
    mca_lender: Optional[str] = None
    time_in_business_months: Optional[int] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
