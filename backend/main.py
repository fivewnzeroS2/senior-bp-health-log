"""어르신 혈압 헬스 로그 FastAPI 애플리케이션."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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

    response_data = BloodPressureRecordData(
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

    return BloodPressureRecordCreateResponse(
        message="혈압 기록이 저장되었습니다.",
        data=response_data,
    )