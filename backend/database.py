"""SQLite 데이터베이스 연결 설정."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


# 프로젝트 최상위 폴더
# database.py → backend → 프로젝트 최상위 폴더
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# SQLite 파일을 저장할 data 폴더
DATA_DIR = PROJECT_ROOT / "data"

# data 폴더가 없을 경우 자동 생성
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 실제 SQLite 데이터베이스 파일 경로
DB_PATH = DATA_DIR / "health_log.db"

# SQLAlchemy가 사용하는 SQLite 연결 주소
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"


# 데이터베이스 연결 엔진
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection,
    connection_record,
) -> None:
    """SQLite 외래키 검사를 활성화합니다."""

    del connection_record

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


# API 요청마다 사용할 DB 세션 생성기
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# 앞으로 모든 DB 테이블 모델이 상속할 기본 클래스
class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI API 요청에서 사용할 데이터베이스 세션을 제공합니다.

    요청 처리가 끝나면 데이터베이스 연결을 자동으로 닫습니다.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    SQLite 연결이 정상인지 SELECT 1 쿼리로 확인합니다.
    """
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True