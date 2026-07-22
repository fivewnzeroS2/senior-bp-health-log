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
    ElderProfile,
)
from backend.schemas import (
    BloodPressureRecordCreate,
    BloodPressureRecordCreateResponse,
    BloodPressureRecordData,
    BloodPressureRecordDetailResponse,
    BloodPressureRecordListData,
    BloodPressureRecordListMeta,
    BloodPressureRecordListResponse,
    KST,
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
        revision_count=record.revision_count,
        is_modified=record.revision_count > 0,
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
        BloodPressureRecord.elder_id == 1
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

    if record is None or record.elder_id != 1:
        return record_not_found_response(record_id)

    return BloodPressureRecordDetailResponse(
        message="혈압 기록을 조회했습니다.",
        data=record_to_response_data(record),
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
        measured_at=payload.measured_at,
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

    return BloodPressureRecordCreateResponse(
        message="혈압 기록이 저장되었습니다.",
        data=response_data,
    )