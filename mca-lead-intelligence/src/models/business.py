"""Business entity model - represents businesses we're tracking."""

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field
from sqlalchemy import Date, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import GUID, Base, TimestampMixin


class Business(Base, TimestampMixin):
    """Database model for business entities."""

    __tablename__ = "businesses"

    business_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    legal_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    dba_name: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    address: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(Text, "sqlite"),
        nullable=False,
        default=dict,
        comment="Full address as JSONB: street, city, state, zip",
    )
    formation_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    time_in_business_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Calculated months since formation",
    )
    industry: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Classified industry vertical",
    )
    industry_confidence: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Confidence score for industry classification (0-1)",
    )
    state: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        index=True,
    )
    ein: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Employer Identification Number if known",
    )
    document_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="State filing/document number",
    )
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="LLC, Corp, Partnership, etc.",
    )
    status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Active, Inactive, Dissolved, etc.",
    )

    __table_args__ = (
        Index("ix_businesses_name_state", "legal_name", "state"),
    )

    def __repr__(self) -> str:
        return f"<Business {self.legal_name} ({self.state})>"

    def calculate_time_in_business(self) -> Optional[int]:
        """Calculate months since formation."""
        if self.formation_date is None:
            return None
        today = date.today()
        months = (today.year - self.formation_date.year) * 12
        months += today.month - self.formation_date.month
        return max(0, months)


# Pydantic models for validation and serialization

class AddressSchema(BaseModel):
    """Schema for business address."""

    street: Optional[str] = None
    street2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "US"


class BusinessCreate(BaseModel):
    """Schema for creating a new business."""

    legal_name: str = Field(..., min_length=1, max_length=500)
    dba_name: Optional[str] = Field(None, max_length=500)
    address: AddressSchema = Field(default_factory=AddressSchema)
    formation_date: Optional[date] = None
    industry: Optional[str] = Field(None, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)
    ein: Optional[str] = Field(None, max_length=20)
    document_number: Optional[str] = Field(None, max_length=100)
    entity_type: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=50)


class BusinessResponse(BaseModel):
    """Schema for business response."""

    business_id: uuid.UUID
    legal_name: str
    dba_name: Optional[str]
    address: dict[str, Any]
    formation_date: Optional[date]
    time_in_business_months: Optional[int]
    industry: Optional[str]
    industry_confidence: Optional[float]
    state: str
    ein: Optional[str]
    document_number: Optional[str]
    entity_type: Optional[str]
    status: Optional[str]
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def time_in_business_years(self) -> Optional[float]:
        """Return time in business as years."""
        if self.time_in_business_months is None:
            return None
        return round(self.time_in_business_months / 12, 1)

    class Config:
        from_attributes = True
