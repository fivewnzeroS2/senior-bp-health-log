"""FastAPI 요청 및 응답 데이터 형식."""

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
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

    bp_category: Literal[
        "normal",
        "caution",
        "high",
    ]

    bp_category_label: str

    memo: str | None
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
    revision_count: int
    is_modified: bool
    is_deleted: bool


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
    """삭제 처리된 혈압 기록 정보."""

    deleted_id: int
    deleted_at: datetime
    is_deleted: bool = True


class BloodPressureRecordDeleteResponse(BaseModel):
    """혈압 기록 삭제 성공 응답."""

    success: Literal[True] = True
    message: str
    data: BloodPressureRecordDeleteData
    meta: None = None
    error: None = None


class BloodPressureRecordChangeItem(BaseModel):
    """수정 전후 값 하나."""

    field: str
    label: str
    before: Any
    after: Any


class BloodPressureRecordHistoryItem(BaseModel):
    """수정 또는 삭제 이력 하나."""

    id: int
    action_type: Literal["update", "delete"]
    action_type_label: str
    revision_number: int | None
    changed_at: datetime
    changes: list[BloodPressureRecordChangeItem]


class BloodPressureRecordHistoryData(BaseModel):
    """혈압 기록의 전체 변경 이력."""

    record_id: int
    revision_count: int
    updated_at: datetime | None
    deleted_at: datetime | None
    is_deleted: bool
    items: list[BloodPressureRecordHistoryItem]


class BloodPressureRecordHistoryResponse(BaseModel):
    """혈압 기록 변경 이력 조회 응답."""

    success: Literal[True] = True
    message: str
    data: BloodPressureRecordHistoryData
    meta: None = None
    error: None = None


class WeeklyReportPeriod(BaseModel):
    """리포트 조회 기간."""

    start_date: date
    end_date: date


class WeeklyReportAverage(BaseModel):
    """기간 내 평균 혈압과 맥박."""

    systolic: float | None
    diastolic: float | None
    pulse: float | None


class WeeklyReportCategoryCounts(BaseModel):
    """기간 내 혈압 상태별 기록 개수."""

    normal: int = Field(
        default=0,
        ge=0,
        description="정상 상태 기록 개수",
    )

    caution: int = Field(
        default=0,
        ge=0,
        description="주의 상태 기록 개수",
    )

    high: int = Field(
        default=0,
        ge=0,
        description="높음 상태 기록 개수",
    )


class WeeklyReportRecordPoint(BaseModel):
    """리포트에 표시할 혈압 기록 하나."""

    record_id: int
    measured_at: datetime
    systolic: int
    diastolic: int
    pulse: int | None

    bp_category: Literal[
        "normal",
        "caution",
        "high",
    ]

    bp_category_label: str


class WeeklyReportSummary(BaseModel):
    """한 기간의 혈압 통계 요약."""

    measurement_count: int

    category_counts: WeeklyReportCategoryCounts

    average: WeeklyReportAverage
    highest: WeeklyReportRecordPoint | None
    lowest: WeeklyReportRecordPoint | None


class WeeklyReportComparison(BaseModel):
    """현재 7일과 이전 7일의 비교 결과."""

    available: bool

    systolic_change: float | None = None
    systolic_direction: (
        Literal["increase", "decrease", "same"] | None
    ) = None

    diastolic_change: float | None = None
    diastolic_direction: (
        Literal["increase", "decrease", "same"] | None
    ) = None

    pulse_change: float | None = None
    pulse_direction: (
        Literal["increase", "decrease", "same"] | None
    ) = None

    measurement_count_change: int | None = None
    measurement_count_direction: (
        Literal["increase", "decrease", "same"] | None
    ) = None

    messages: list[str] = Field(
        default_factory=list,
    )

    reason: str | None = None


class WeeklyReportData(BaseModel):
    """최근 7일 리포트 전체 데이터."""

    period: WeeklyReportPeriod
    previous_period: WeeklyReportPeriod
    summary: WeeklyReportSummary
    previous_summary: WeeklyReportSummary
    comparison: WeeklyReportComparison
    trend: list[WeeklyReportRecordPoint]


class WeeklyReportResponse(BaseModel):
    """최근 7일 리포트 성공 응답."""

    success: Literal[True] = True
    message: str
    data: WeeklyReportData
    meta: None = None
    error: None = None


class ElderProfileUpdate(BaseModel):
    """어르신 프로필 등록 및 수정 요청."""

    name: str = Field(
        min_length=1,
        max_length=100,
        description="어르신 이름",
    )

    honorific: str = Field(
        default="어르신",
        min_length=1,
        max_length=50,
        description="이름 뒤에 표시할 호칭",
    )

    birth_year: int | None = Field(
        default=None,
        ge=1900,
        description="출생 연도",
    )

    @field_validator("name", "honorific")
    @classmethod
    def normalize_profile_text(
        cls,
        value: str,
    ) -> str:
        """이름과 호칭의 앞뒤 공백을 제거합니다."""

        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError(
                "공백만 입력할 수 없습니다."
            )

        return cleaned_value

    @field_validator("birth_year")
    @classmethod
    def validate_birth_year(
        cls,
        value: int | None,
    ) -> int | None:
        """출생 연도가 미래 연도인지 검사합니다."""

        if value is None:
            return None

        current_year = datetime.now(KST).year

        if value > current_year:
            raise ValueError(
                "출생 연도는 현재 연도보다 클 수 없습니다."
            )

        return value


class ElderProfileData(BaseModel):
    """어르신 프로필 응답 데이터."""

    id: int
    name: str
    honorific: str
    display_name: str
    birth_year: int | None
    created_at: datetime
    updated_at: datetime | None


class ElderProfileResponse(BaseModel):
    """어르신 프로필 조회·수정 성공 응답."""

    success: Literal[True] = True
    message: str
    data: ElderProfileData
    meta: None = None
    error: None = None


class ShareLinkCreate(BaseModel):
    """공유 링크 생성 요청."""

    model_config = ConfigDict(
        extra="forbid",
    )

    target_type: Literal[
        "family",
        "medical",
    ] = Field(
        description="공유 대상: 가족 또는 의료진",
    )

    range_days: Literal[
        7,
        30,
    ] = Field(
        default=7,
        description="공유할 혈압 기록 기간",
    )

    include_memo: bool = Field(
        default=False,
        description="공유 화면에 메모 포함 여부",
    )

    include_birth_year: bool = Field(
        default=False,
        description="공유 화면에 출생 연도 포함 여부",
    )

    expires_in_days: Literal[
        1,
        7,
        30,
    ] = Field(
        default=7,
        description="공유 링크 유효기간",
    )


class ShareLinkData(BaseModel):
    """공유 링크 응답 데이터."""

    id: int
    token: str
    share_url: str

    target_type: Literal[
        "family",
        "medical",
    ]
    target_type_label: str

    range_days: Literal[
        7,
        30,
    ]

    include_memo: bool
    include_birth_year: bool

    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None

    status: Literal[
        "active",
        "expired",
        "revoked",
    ]
    status_label: str


class ShareLinkCreateResponse(BaseModel):
    """공유 링크 생성 성공 응답."""

    success: Literal[True] = True
    message: str
    data: ShareLinkData
    meta: None = None
    error: None = None


class ShareLinkListData(BaseModel):
    """공유 링크 목록 데이터."""

    items: list[ShareLinkData]


class ShareLinkListMeta(BaseModel):
    """공유 링크 상태별 개수."""

    total: int = Field(ge=0)
    active: int = Field(ge=0)
    expired: int = Field(ge=0)
    revoked: int = Field(ge=0)


class ShareLinkListResponse(BaseModel):
    """공유 링크 목록 성공 응답."""

    success: Literal[True] = True
    message: str
    data: ShareLinkListData
    meta: ShareLinkListMeta
    error: None = None


class ShareLinkEndResponse(BaseModel):
    """공유 링크 종료 성공 응답."""

    success: Literal[True] = True
    message: str
    data: ShareLinkData
    meta: None = None
    error: None = None

class SharedReportProfile(BaseModel):
    """공유 화면에 표시할 최소 어르신 정보."""

    name: str
    honorific: str
    display_name: str
    birth_year: int | None


class SharedReportSettings(BaseModel):
    """공유 링크에 설정된 공개 범위."""

    target_type: Literal[
        "family",
        "medical",
    ]

    target_type_label: str

    range_days: Literal[
        7,
        30,
    ]

    include_memo: bool
    include_birth_year: bool

    created_at: datetime
    expires_at: datetime


class SharedReportPeriod(BaseModel):
    """공유되는 혈압 기록 기간."""

    start_date: date
    end_date: date


class SharedReportRecord(BaseModel):
    """공유 화면에 표시할 혈압 기록."""

    measured_at: datetime
    systolic: int
    diastolic: int
    pulse: int | None

    measurement_period: str | None
    measurement_period_label: str | None

    bp_category: Literal[
        "normal",
        "caution",
        "high",
    ]

    bp_category_label: str

    memo: str | None


class SharedReportSummary(BaseModel):
    """공유 기간의 혈압 통계."""

    measurement_count: int
    category_counts: WeeklyReportCategoryCounts
    average: WeeklyReportAverage

    highest: SharedReportRecord | None
    lowest: SharedReportRecord | None


class SharedReportData(BaseModel):
    """공유 리포트 전체 데이터."""

    settings: SharedReportSettings
    profile: SharedReportProfile
    period: SharedReportPeriod
    summary: SharedReportSummary
    records: list[SharedReportRecord]

    notice: str = (
        "혈압 상태는 기록 확인을 위한 참고 표시이며 "
        "의료 진단 결과가 아닙니다."
    )


class SharedReportResponse(BaseModel):
    """공유 리포트 성공 응답."""

    success: Literal[True] = True
    message: str
    data: SharedReportData
    meta: None = None
    error: None = None