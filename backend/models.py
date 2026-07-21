"""SQLAlchemy 데이터베이스 테이블 모델."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def utc_now() -> datetime:
    """현재 UTC 시각을 반환합니다."""

    return datetime.now(timezone.utc)


class ElderProfile(Base):
    """관리 대상 어르신 정보."""

    __tablename__ = "elder_profile"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    honorific: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="어르신",
    )

    birth_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    blood_pressure_records: Mapped[list[BloodPressureRecord]] = relationship(
        back_populates="elder",
        cascade="all, delete-orphan",
    )

    share_links: Mapped[list[ShareLink]] = relationship(
        back_populates="elder",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "birth_year IS NULL OR birth_year BETWEEN 1900 AND 2100",
            name="ck_elder_profile_birth_year",
        ),
    )


class BloodPressureRecord(Base):
    """혈압 측정 기록."""

    __tablename__ = "blood_pressure_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    elder_id: Mapped[int] = mapped_column(
        ForeignKey(
            "elder_profile.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    systolic: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    diastolic: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    pulse: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    measurement_period: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    memo: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    revision_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    elder: Mapped[ElderProfile] = relationship(
        back_populates="blood_pressure_records",
    )

    __table_args__ = (
        CheckConstraint(
            "systolic BETWEEN 60 AND 250",
            name="ck_bp_systolic_range",
        ),
        CheckConstraint(
            "diastolic BETWEEN 40 AND 150",
            name="ck_bp_diastolic_range",
        ),
        CheckConstraint(
            "pulse IS NULL OR pulse BETWEEN 30 AND 220",
            name="ck_bp_pulse_range",
        ),
        CheckConstraint(
            "diastolic < systolic",
            name="ck_bp_diastolic_less_than_systolic",
        ),
        CheckConstraint(
            """
            measurement_period IS NULL
            OR measurement_period IN (
                'morning',
                'afternoon',
                'evening',
                'before_sleep',
                'other'
            )
            """,
            name="ck_bp_measurement_period",
        ),
        Index(
            "idx_bp_records_elder_measured_at",
            "elder_id",
            "measured_at",
        ),
    )


class ShareLink(Base):
    """가족·의료진에게 제공하는 공유 링크."""

    __tablename__ = "share_links"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    elder_id: Mapped[int] = mapped_column(
        ForeignKey(
            "elder_profile.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    token: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )

    target_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    range_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    include_memo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    include_birth_year: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    elder: Mapped[ElderProfile] = relationship(
        back_populates="share_links",
    )

    __table_args__ = (
        CheckConstraint(
            "target_type IN ('family', 'medical')",
            name="ck_share_target_type",
        ),
        CheckConstraint(
            "range_days IN (7, 30)",
            name="ck_share_range_days",
        ),
    )