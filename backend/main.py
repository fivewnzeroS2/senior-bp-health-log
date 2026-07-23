import json

"""어르신 혈압 헬스 로그 FastAPI 애플리케이션."""

from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database import (
    Base,
    SessionLocal,
    engine,
    get_db,
)
from backend.models import (
    BloodPressureRecord,
    BloodPressureRecordHistory,
    ElderProfile,
    utc_now,
)
from backend.schemas import (
    BloodPressureRecordCreate,
    BloodPressureRecordCreateResponse,
    BloodPressureRecordData,
    BloodPressureRecordDeleteData,
    BloodPressureRecordDeleteResponse,
    BloodPressureRecordDetailResponse,
    BloodPressureRecordListData,
    BloodPressureRecordListMeta,
    BloodPressureRecordListResponse,
    BloodPressureRecordUpdate,
    BloodPressureRecordUpdateResponse,
    BloodPressureRecordChangeItem,
    BloodPressureRecordHistoryData,
    BloodPressureRecordHistoryItem,
    BloodPressureRecordHistoryResponse,
    KST,
    WeeklyReportAverage,
    WeeklyReportComparison,
    WeeklyReportData,
    WeeklyReportPeriod,
    WeeklyReportRecordPoint,
    WeeklyReportResponse,
    WeeklyReportSummary,
)
from backend.services import get_measurement_period_label


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def create_default_elder_profile() -> None:
    """
    어르신 정보가 없으면 기본 프로필 한 건을 생성합니다.

    이번 프로젝트는 한 명의 어르신만 관리하므로
    기본 ID를 1로 사용합니다.
    """

    with SessionLocal() as db:
        profile = db.get(ElderProfile, 1)

        if profile is not None:
            return

        db.add(
            ElderProfile(
                id=1,
                name="이름 미등록",
                honorific="어르신",
                birth_year=None,
            )
        )
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI가 시작될 때 DB 테이블을 준비합니다."""

    del app

    Base.metadata.create_all(bind=engine)
    create_default_elder_profile()

    yield


def to_sqlite_datetime(value: datetime) -> datetime:
    """
    날짜와 시간을 한국 시간 기준으로 맞춘 뒤
    SQLite 저장용 datetime으로 변환합니다.
    """

    if value.tzinfo is None:
        return value

    return value.astimezone(KST).replace(tzinfo=None)


RECORD_FIELD_LABELS = {
    "measured_at": "측정 시각",
    "systolic": "수축기 혈압",
    "diastolic": "이완기 혈압",
    "pulse": "맥박",
    "measurement_period": "측정 시간대",
    "memo": "메모",
}


def record_snapshot(
    record: BloodPressureRecord,
) -> dict:
    """현재 혈압 기록을 비교 가능한 값으로 변환합니다."""

    return {
        "measured_at": (
            record.measured_at.isoformat()
            if record.measured_at is not None
            else None
        ),
        "systolic": record.systolic,
        "diastolic": record.diastolic,
        "pulse": record.pulse,
        "measurement_period": record.measurement_period,
        "memo": record.memo,
    }


def build_record_changes(
    before: dict,
    after: dict,
) -> list[dict]:
    """수정 전후 값이 다른 항목만 반환합니다."""

    changes = []

    for field, label in RECORD_FIELD_LABELS.items():
        before_value = before.get(field)
        after_value = after.get(field)

        if before_value == after_value:
            continue

        changes.append(
            {
                "field": field,
                "label": label,
                "before": before_value,
                "after": after_value,
            }
        )

    return changes


def calculate_average(
    values: list[int | None],
) -> float | None:
    """null을 제외하고 평균을 소수점 첫째 자리까지 계산합니다."""

    valid_values = [
        value
        for value in values
        if value is not None
    ]

    if not valid_values:
        return None

    return round(
        sum(valid_values) / len(valid_values),
        1,
    )


def calculate_difference(
    current_value: float | None,
    previous_value: float | None,
) -> float | None:
    """현재 평균에서 이전 평균을 뺀 변화량을 반환합니다."""

    if current_value is None or previous_value is None:
        return None

    return round(
        current_value - previous_value,
        1,
    )


def record_to_weekly_report_point(
    record: BloodPressureRecord,
) -> WeeklyReportRecordPoint:
    """DB 혈압 기록을 리포트용 데이터로 변환합니다."""

    return WeeklyReportRecordPoint(
        record_id=record.id,
        measured_at=record.measured_at,
        systolic=record.systolic,
        diastolic=record.diastolic,
        pulse=record.pulse,
    )


def get_active_records_between(
    db: Session,
    start_date: date,
    end_date: date,
) -> list[BloodPressureRecord]:
    """
    지정한 날짜 범위의 삭제되지 않은 혈압 기록을 조회합니다.
    """

    start_datetime = datetime.combine(
        start_date,
        time.min,
    )

    end_datetime_exclusive = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
    )

    statement = (
        select(BloodPressureRecord)
        .where(
            BloodPressureRecord.elder_id == 1,
            BloodPressureRecord.deleted_at.is_(None),
            BloodPressureRecord.measured_at
            >= start_datetime,
            BloodPressureRecord.measured_at
            < end_datetime_exclusive,
        )
        .order_by(
            BloodPressureRecord.measured_at.asc(),
            BloodPressureRecord.id.asc(),
        )
    )

    return list(
        db.scalars(statement).all()
    )


def build_weekly_report_summary(
    records: list[BloodPressureRecord],
) -> WeeklyReportSummary:
    """혈압 기록 목록으로 기간별 통계를 계산합니다."""

    average = WeeklyReportAverage(
        systolic=calculate_average(
            [record.systolic for record in records]
        ),
        diastolic=calculate_average(
            [record.diastolic for record in records]
        ),
        pulse=calculate_average(
            [record.pulse for record in records]
        ),
    )

    if not records:
        return WeeklyReportSummary(
            measurement_count=0,
            average=average,
            highest=None,
            lowest=None,
        )

    # 이 프로젝트에서는 수축기 혈압을 우선 기준으로
    # 가장 높은 기록과 가장 낮은 기록을 결정합니다.
    highest_record = max(
        records,
        key=lambda record: (
            record.systolic,
            record.diastolic,
            record.measured_at,
        ),
    )

    lowest_record = min(
        records,
        key=lambda record: (
            record.systolic,
            record.diastolic,
            record.measured_at,
        ),
    )

    return WeeklyReportSummary(
        measurement_count=len(records),
        average=average,
        highest=record_to_weekly_report_point(
            highest_record
        ),
        lowest=record_to_weekly_report_point(
            lowest_record
        ),
    )


def record_to_response_data(
    record: BloodPressureRecord,
) -> BloodPressureRecordData:
    """
    DB의 혈압 기록을 API 응답 형식으로 변환합니다.
    """

    return BloodPressureRecordData(
        id=record.id,
        measured_at=record.measured_at,
        systolic=record.systolic,
        diastolic=record.diastolic,
        pulse=record.pulse,
        measurement_period=record.measurement_period,
        measurement_period_label=(
            get_measurement_period_label(
                record.measurement_period
            )
        ),
        memo=record.memo,
        created_at=record.created_at,
        updated_at=record.updated_at,
        deleted_at=record.deleted_at,
        revision_count=record.revision_count,
        is_modified=record.revision_count > 0,
        is_deleted=record.deleted_at is not None,
    )


app = FastAPI(
    title="어르신 혈압 헬스 로그 API",
    description="혈압 기록, 조회, 리포트 및 공유 API",
    version="1.0.0",
    lifespan=lifespan,
)


app.mount(
    "/css",
    StaticFiles(directory=FRONTEND_DIR / "css"),
    name="css",
)

app.mount(
    "/js",
    StaticFiles(directory=FRONTEND_DIR / "js"),
    name="js",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """입력값 오류를 공통 응답 형식으로 반환합니다."""

    del request

    details = []

    for error in exc.errors():
        location = [
            str(item)
            for item in error.get("loc", [])
            if item != "body"
        ]

        field = ".".join(location) or "request"
        reason = error.get(
            "msg",
            "입력값을 확인해 주세요.",
        )

        reason = reason.removeprefix("Value error, ")

        details.append(
            {
                "field": field,
                "reason": reason,
            }
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "입력한 내용을 확인해 주세요.",
            "data": None,
            "meta": None,
            "error": {
                "code": "VALIDATION_ERROR",
                "details": details,
            },
        },
    )


@app.get(
    "/",
    include_in_schema=False,
)
def management_page() -> FileResponse:
    """관리 화면 HTML을 반환합니다."""

    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


@app.get(
    "/share/{token}",
    include_in_schema=False,
)
def shared_report_page(
    token: str,
) -> FileResponse:
    """공유 리포트 화면 HTML을 반환합니다."""

    del token

    return FileResponse(
        FRONTEND_DIR / "share.html"
    )


@app.post(
    "/api/v1/records",
    response_model=BloodPressureRecordCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["혈압 기록"],
)
def create_blood_pressure_record(
    payload: BloodPressureRecordCreate,
    db: Session = Depends(get_db),
) -> BloodPressureRecordCreateResponse | JSONResponse:
    """새로운 혈압 기록을 SQLite에 저장합니다."""

    measurement_period = (
        payload.measurement_period.value
        if payload.measurement_period is not None
        else None
    )

    record = BloodPressureRecord(
        elder_id=1,
        measured_at=to_sqlite_datetime(payload.measured_at),
        systolic=payload.systolic,
        diastolic=payload.diastolic,
        pulse=payload.pulse,
        measurement_period=measurement_period,
        memo=payload.memo,
        revision_count=0,
    )

    try:
        db.add(record)
        db.commit()
        db.refresh(record)

    except SQLAlchemyError:
        db.rollback()

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "혈압 기록을 저장하지 못했습니다.",
                "data": None,
                "meta": None,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "details": [],
                },
            },
        )

    response_data = record_to_response_data(record)
    return BloodPressureRecordCreateResponse(
        success=True,
        message="혈압 기록이 성공적으로 저장되었습니다.",
        data=response_data,
    )


@app.get(
    "/api/v1/records",
    response_model=BloodPressureRecordListResponse,
    status_code=status.HTTP_200_OK,
    tags=["혈압 기록"],
)
def list_blood_pressure_records(
    days: Annotated[
        int | None,
        Query(description="최근 7일 또는 30일 조회"),
    ] = None,
    start_date: Annotated[
        date | None,
        Query(description="직접 지정하는 조회 시작일"),
    ] = None,
    end_date: Annotated[
        date | None,
        Query(description="직접 지정하는 조회 종료일"),
    ] = None,
    sort: Annotated[
        Literal["latest", "oldest"],
        Query(description="최신순 또는 오래된 순"),
    ] = "latest",
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="한 번에 반환할 기록 수",
        ),
    ] = 20,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="건너뛸 기록 수",
        ),
    ] = 0,
    db: Session = Depends(get_db),
) -> BloodPressureRecordListResponse | JSONResponse:
    """
    혈압 기록 목록을 조회합니다.

    검색 조건이 없으면 최근 7일 기록을 조회합니다.
    """

    if days is not None and days not in (7, 30):
        return invalid_date_filter_response(
            "최근 조회 일수는 7일 또는 30일만 사용할 수 있습니다."
        )

    if (start_date is None) != (end_date is None):
        return invalid_date_filter_response(
            "시작일과 종료일을 모두 입력해 주세요."
        )

    if days is not None and start_date is not None:
        return invalid_date_filter_response(
            "최근 일수와 날짜 범위는 동시에 사용할 수 없습니다."
        )

    if (
        start_date is not None
        and end_date is not None
        and start_date > end_date
    ):
        return invalid_date_filter_response(
            "시작일은 종료일보다 늦을 수 없습니다."
        )

    effective_days = days

    if (
        effective_days is None
        and start_date is None
        and end_date is None
    ):
        effective_days = 7

    if (
        effective_days is None
        and start_date is None
        and end_date is None
    ):
        effective_days = 7

    conditions = [
        BloodPressureRecord.elder_id == 1,
        BloodPressureRecord.deleted_at.is_(None),
    ]

    filter_start_date: date | None = None
    filter_end_date: date | None = None

    if effective_days is not None:
        today = datetime.now(KST).date()

        filter_start_date = (
            today - timedelta(days=effective_days - 1)
        )

        filter_end_date = today

    elif start_date is not None and end_date is not None:
        filter_start_date = start_date
        filter_end_date = end_date

    if (
        filter_start_date is not None
        and filter_end_date is not None
    ):
        start_datetime = datetime.combine(
            filter_start_date,
            time.min,
        )

        # 종료일 하루 뒤의 0시보다 작은 기록까지 포함합니다.
        end_datetime_exclusive = datetime.combine(
            filter_end_date + timedelta(days=1),
            time.min,
        )

        conditions.extend(
            [
                BloodPressureRecord.measured_at
                >= start_datetime,

                BloodPressureRecord.measured_at
                < end_datetime_exclusive,
            ]
        )

    count_statement = (
        select(func.count(BloodPressureRecord.id))
        .where(*conditions)
    )

    total = db.scalar(count_statement) or 0

    if sort == "latest":
        order_conditions = [
            BloodPressureRecord.measured_at.desc(),
            BloodPressureRecord.id.desc(),
        ]
    else:
        order_conditions = [
            BloodPressureRecord.measured_at.asc(),
            BloodPressureRecord.id.asc(),
        ]

    list_statement = (
        select(BloodPressureRecord)
        .where(*conditions)
        .order_by(*order_conditions)
        .offset(offset)
        .limit(limit)
    )

    records = db.scalars(list_statement).all()

    items = [
        record_to_response_data(record)
        for record in records
    ]

    if items:
        message = "혈압 기록 목록을 조회했습니다."
    else:
        message = "조회된 혈압 기록이 없습니다."

    return BloodPressureRecordListResponse(
        message=message,
        data=BloodPressureRecordListData(
            items=items,
        ),
        meta=BloodPressureRecordListMeta(
            total=total,
            count=len(items),
            limit=limit,
            offset=offset,
            filters={
                "days": effective_days,
                "start_date": (
                    filter_start_date.isoformat()
                    if filter_start_date is not None
                    else None
                ),
                "end_date": (
                    filter_end_date.isoformat()
                    if filter_end_date is not None
                    else None
                ),
                "sort": sort,
            },
        ),
    )


@app.get(
    "/api/v1/records/{record_id}",
    response_model=BloodPressureRecordDetailResponse,
    status_code=status.HTTP_200_OK,
    tags=["혈압 기록"],
)
def get_blood_pressure_record(
    record_id: int,
    db: Session = Depends(get_db),
) -> BloodPressureRecordDetailResponse | JSONResponse:
    """기록 번호로 혈압 기록 하나를 조회합니다."""

    record = db.get(
        BloodPressureRecord,
        record_id,
    )

    if (
        record is None
        or record.elder_id != 1
        or record.deleted_at is not None
    ):
        return record_not_found_response(record_id)

    return BloodPressureRecordDetailResponse(
        message="혈압 기록을 조회했습니다.",
        data=record_to_response_data(record),
    )


@app.put(
    "/api/v1/records/{record_id}",
    response_model=BloodPressureRecordUpdateResponse,
    status_code=status.HTTP_200_OK,
    tags=["혈압 기록"],
)
def update_blood_pressure_record(
    record_id: int,
    payload: BloodPressureRecordUpdate,
    db: Session = Depends(get_db),
) -> BloodPressureRecordUpdateResponse | JSONResponse:
    """기록 번호에 해당하는 혈압 기록을 수정합니다."""

    record = db.get(
        BloodPressureRecord,
        record_id,
    )

    if (
        record is None
        or record.elder_id != 1
        or record.deleted_at is not None
    ):
        return record_not_found_response(record_id)

    measurement_period = (
        payload.measurement_period.value
        if payload.measurement_period is not None
        else None
    )

    new_measured_at = to_sqlite_datetime(
        payload.measured_at
    )

    current_measured_at = to_sqlite_datetime(
        record.measured_at
    )

    # 실제로 값이 변경되었는지 확인합니다.
    before_snapshot = record_snapshot(record)

    after_snapshot = {
        "measured_at": new_measured_at.isoformat(),
        "systolic": payload.systolic,
        "diastolic": payload.diastolic,
        "pulse": payload.pulse,
        "measurement_period": measurement_period,
        "memo": payload.memo,
    }

    changes = build_record_changes(
        before_snapshot,
        after_snapshot,
    )

    if not changes:
        return BloodPressureRecordUpdateResponse(
            message="변경된 내용이 없어 기존 기록을 반환했습니다.",
            data=record_to_response_data(record),
        )

    record.measured_at = new_measured_at
    record.systolic = payload.systolic
    record.diastolic = payload.diastolic
    record.pulse = payload.pulse
    record.measurement_period = measurement_period
    record.memo = payload.memo


    record.updated_at = utc_now()
    record.revision_count += 1

    history = BloodPressureRecordHistory(
        record_id=record.id,
        action_type="update",
        revision_number=record.revision_count,
        changes_json=json.dumps(
            changes,
            ensure_ascii=False,
        ),
        created_at=record.updated_at,
    )

    db.add(history)

    try:
        db.commit()
        db.refresh(record)

    except SQLAlchemyError:
        db.rollback()

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "혈압 기록을 수정하지 못했습니다.",
                "data": None,
                "meta": None,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "details": [],
                },
            },
        )

    return BloodPressureRecordUpdateResponse(
        message="혈압 기록이 수정되었습니다.",
        data=record_to_response_data(record),
    )


@app.delete(
    "/api/v1/records/{record_id}",
    response_model=BloodPressureRecordDeleteResponse,
    status_code=status.HTTP_200_OK,
    tags=["혈압 기록"],
)
def delete_blood_pressure_record(
    record_id: int,
    db: Session = Depends(get_db),
) -> BloodPressureRecordDeleteResponse | JSONResponse:
    """혈압 기록을 소프트 삭제하고 삭제 시각을 남깁니다."""

    record = db.get(
        BloodPressureRecord,
        record_id,
    )

    if record is None or record.elder_id != 1:
        return record_not_found_response(record_id)

    if record.deleted_at is not None:
        return JSONResponse(
            status_code=status.HTTP_410_GONE,
            content={
                "success": False,
                "message": "이미 삭제된 혈압 기록입니다.",
                "data": None,
                "meta": None,
                "error": {
                    "code": "RECORD_ALREADY_DELETED",
                    "details": [
                        {
                            "field": "record_id",
                            "reason": (
                                f"{record_id}번 기록은 "
                                "이미 삭제되었습니다."
                            ),
                        }
                    ],
                },
            },
        )

    deleted_at = utc_now()
    record.deleted_at = deleted_at

    delete_changes = [
        {
            "field": "deleted_at",
            "label": "삭제 시각",
            "before": None,
            "after": deleted_at.isoformat(),
        }
    ]

    history = BloodPressureRecordHistory(
        record_id=record.id,
        action_type="delete",
        revision_number=None,
        changes_json=json.dumps(
            delete_changes,
            ensure_ascii=False,
        ),
        created_at=deleted_at,
    )

    db.add(history)

    try:
        db.commit()
        db.refresh(record)

    except SQLAlchemyError:
        db.rollback()

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "혈압 기록을 삭제하지 못했습니다.",
                "data": None,
                "meta": None,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "details": [],
                },
            },
        )

    return BloodPressureRecordDeleteResponse(
        message="혈압 기록이 삭제 처리되었습니다.",
        data=BloodPressureRecordDeleteData(
            deleted_id=record.id,
            deleted_at=record.deleted_at,
            is_deleted=True,
        ),
    )





def invalid_date_filter_response(
    message: str,
) -> JSONResponse:
    """잘못된 날짜 검색 조건을 반환합니다."""

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": message,
            "data": None,
            "meta": None,
            "error": {
                "code": "INVALID_DATE_FILTER",
                "details": [
                    {
                        "field": "date_filter",
                        "reason": message,
                    }
                ],
            },
        },
    )


def record_not_found_response(
    record_id: int,
) -> JSONResponse:
    """존재하지 않는 혈압 기록 응답을 반환합니다."""

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "success": False,
            "message": "해당 혈압 기록을 찾을 수 없습니다.",
            "data": None,
            "meta": None,
            "error": {
                "code": "RECORD_NOT_FOUND",
                "details": [
                    {
                        "field": "record_id",
                        "reason": (
                            f"{record_id}번 혈압 기록이 "
                            "존재하지 않습니다."
                        ),
                    }
                ],
            },
        },
    )



@app.get(
    "/api/v1/records/{record_id}/history",
    response_model=BloodPressureRecordHistoryResponse,
    status_code=status.HTTP_200_OK,
    tags=["혈압 기록"],
)
def get_blood_pressure_record_history(
    record_id: int,
    db: Session = Depends(get_db),
) -> BloodPressureRecordHistoryResponse | JSONResponse:
    """혈압 기록의 수정 및 삭제 이력을 조회합니다."""

    record = db.get(
        BloodPressureRecord,
        record_id,
    )

    if record is None or record.elder_id != 1:
        return record_not_found_response(record_id)

    statement = (
        select(BloodPressureRecordHistory)
        .where(
            BloodPressureRecordHistory.record_id
            == record_id
        )
        .order_by(
            BloodPressureRecordHistory.created_at.desc(),
            BloodPressureRecordHistory.id.desc(),
        )
    )

    history_entries = db.scalars(statement).all()

    items = []

    for history in history_entries:
        changes_data = json.loads(
            history.changes_json
        )

        items.append(
            BloodPressureRecordHistoryItem(
                id=history.id,
                action_type=history.action_type,
                action_type_label=(
                    "수정"
                    if history.action_type == "update"
                    else "삭제"
                ),
                revision_number=history.revision_number,
                changed_at=history.created_at,
                changes=[
                    BloodPressureRecordChangeItem(
                        field=change["field"],
                        label=change["label"],
                        before=change.get("before"),
                        after=change.get("after"),
                    )
                    for change in changes_data
                ],
            )
        )

    return BloodPressureRecordHistoryResponse(
        message="혈압 기록 변경 이력을 조회했습니다.",
        data=BloodPressureRecordHistoryData(
            record_id=record.id,
            revision_count=record.revision_count,
            updated_at=record.updated_at,
            deleted_at=record.deleted_at,
            is_deleted=record.deleted_at is not None,
            items=items,
        ),
    )


@app.get(
    "/api/v1/reports/weekly",
    response_model=WeeklyReportResponse,
    status_code=status.HTTP_200_OK,
    tags=["리포트"],
)
def get_weekly_blood_pressure_report(
    end_date: date | None = Query(
        default=None,
        description=(
            "리포트 마지막 날짜. "
            "입력하지 않으면 오늘을 사용합니다."
        ),
    ),
    db: Session = Depends(get_db),
) -> WeeklyReportResponse:
    """최근 7일과 이전 7일의 혈압 기록을 비교합니다."""

    report_end_date = (
        end_date
        if end_date is not None
        else datetime.now(KST).date()
    )

    report_start_date = (
        report_end_date - timedelta(days=6)
    )

    previous_end_date = (
        report_start_date - timedelta(days=1)
    )

    previous_start_date = (
        previous_end_date - timedelta(days=6)
    )

    current_records = get_active_records_between(
        db=db,
        start_date=report_start_date,
        end_date=report_end_date,
    )

    previous_records = get_active_records_between(
        db=db,
        start_date=previous_start_date,
        end_date=previous_end_date,
    )

    current_summary = build_weekly_report_summary(
        current_records
    )

    previous_summary = build_weekly_report_summary(
        previous_records
    )

    if not current_records:
        comparison = WeeklyReportComparison(
            available=False,
            reason=(
                "현재 7일 기간의 혈압 기록이 없습니다."
            ),
        )

    elif not previous_records:
        comparison = WeeklyReportComparison(
            available=False,
            reason=(
                "이전 7일 기간의 혈압 기록이 없습니다."
            ),
        )

    else:
        comparison = WeeklyReportComparison(
            available=True,
            systolic_change=calculate_difference(
                current_summary.average.systolic,
                previous_summary.average.systolic,
            ),
            diastolic_change=calculate_difference(
                current_summary.average.diastolic,
                previous_summary.average.diastolic,
            ),
            pulse_change=calculate_difference(
                current_summary.average.pulse,
                previous_summary.average.pulse,
            ),
            measurement_count_change=(
                current_summary.measurement_count
                - previous_summary.measurement_count
            ),
            reason=None,
        )

    trend = [
        record_to_weekly_report_point(record)
        for record in current_records
    ]

    if current_records:
        message = (
            "최근 7일 혈압 리포트를 조회했습니다."
        )
    else:
        message = (
            "최근 7일 혈압 기록이 없어 "
            "빈 리포트를 반환했습니다."
        )

    return WeeklyReportResponse(
        message=message,
        data=WeeklyReportData(
            period=WeeklyReportPeriod(
                start_date=report_start_date,
                end_date=report_end_date,
            ),
            previous_period=WeeklyReportPeriod(
                start_date=previous_start_date,
                end_date=previous_end_date,
            ),
            summary=current_summary,
            previous_summary=previous_summary,
            comparison=comparison,
            trend=trend,
        ),
    )
