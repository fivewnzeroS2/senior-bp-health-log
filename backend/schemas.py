"""FastAPI 요청 및 응답 데이터 형식."""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


KST = timezone(timedelta(hours=9))


class MeasurementPeriod(str, Enum):
    """혈압 측정 시간대."""

    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    BEFORE_SLEEP = "before_sleep"
    OTHER = "other"


class BloodPressureRecordCreate(BaseModel):
    """혈압 기록 등록 요청."""

    measured_at: datetime = Field(
        description="혈압을 측정한 날짜와 시간",
    )

    systolic: int = Field(
        ge=60,
        le=250,
        description="수축기 혈압",
    )

    diastolic: int = Field(
        ge=40,
        le=150,
        description="이완기 혈압",
    )

    pulse: int | None = Field(
        default=None,
        ge=30,
        le=220,
        description="맥박",
    )

    measurement_period: MeasurementPeriod | None = Field(
        default=None,
        description="측정 시간대",
    )

    memo: str | None = Field(
        default=None,
        max_length=500,
        description="혈압 측정 메모",
    )

    @field_validator("measured_at")
    @classmethod
    def normalize_measured_at(
        cls,
        value: datetime,
    ) -> datetime:
        """시간대가 없으면 한국 시간으로 처리합니다."""

        if value.tzinfo is None:
            return value.replace(tzinfo=KST)

        return value.astimezone(KST)

    @field_validator("memo")
    @classmethod
    def normalize_memo(
        cls,
        value: str | None,
    ) -> str | None:
        """빈 메모는 null로 처리합니다."""

        if value is None:
            return None

        cleaned_value = value.strip()

        if not cleaned_value:
            return None

        return cleaned_value

    @model_validator(mode="after")
    def validate_blood_pressure_relation(
        self,
    ) -> "BloodPressureRecordCreate":
        """이완기 혈압은 수축기 혈압보다 낮아야 합니다."""

        if self.diastolic >= self.systolic:
            raise ValueError(
                "이완기 혈압은 수축기 혈압보다 낮아야 합니다."
            )

        return self


class BloodPressureRecordData(BaseModel):
    """혈압 기록 응답 데이터."""

    id: int
    measured_at: datetime
    systolic: int
    diastolic: int
    pulse: int | None
    measurement_period: str | None
    measurement_period_label: str | None
    memo: str | None
    created_at: datetime
    updated_at: datetime | None
    revision_count: int
    is_modified: bool


class BloodPressureRecordCreateResponse(BaseModel):
    """혈압 등록 성공 응답."""

    success: Literal[True] = True
    message: str
    data: BloodPressureRecordData
    meta: None = None
    error: None = None


class BloodPressureRecordListData(BaseModel):
    """혈압 기록 목록 데이터."""

    items: list[BloodPressureRecordData]


class BloodPressureRecordListMeta(BaseModel):
    """혈압 기록 목록의 검색 및 페이지 정보."""

    total: int
    count: int
    limit: int
    offset: int
    filters: dict[str, int | str | None]


class BloodPressureRecordListResponse(BaseModel):
    """혈압 기록 목록 조회 성공 응답."""

    success: Literal[True] = True
    message: str
    data: BloodPressureRecordListData
    meta: BloodPressureRecordListMeta
    error: None = None


class BloodPressureRecordDetailResponse(BaseModel):
    """혈압 기록 하나 조회 성공 응답."""

    success: Literal[True] = True
    message: str
    data: BloodPressureRecordData
    meta: None = None
    error: None = None


class BloodPressureRecordUpdate(BloodPressureRecordCreate):
    """
    혈압 기록 수정 요청.

    PUT 방식이므로 등록 요청과 동일한 전체 항목을 받습니다.
    """


class BloodPressureRecordUpdateResponse(BaseModel):
    """혈압 기록 수정 성공 응답."""

    success: Literal[True] = True
    message: str
    data: BloodPressureRecordData
    meta: None = None
    error: None = None


class BloodPressureRecordDeleteData(BaseModel):
    """삭제된 혈압 기록 정보."""

    deleted_id: int


class BloodPressureRecordDeleteResponse(BaseModel):
    """혈압 기록 삭제 성공 응답."""

    success: Literal[True] = True
    message: str
    data: BloodPressureRecordDeleteData
    meta: None = None
    error: None = None