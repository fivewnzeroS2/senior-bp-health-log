# 어르신 혈압 건강 기록 서비스

어르신 한 명의 혈압과 맥박을 기록하고, 최근 기록과 주간 변화 추이를 확인하며 가족 또는 의료진에게 기간 제한 공유 링크를 제공하는 FastAPI 기반 웹 서비스입니다.

> 이 서비스의 혈압 상태 표시는 학습용 화면 기준이며 의료 진단을 대신하지 않습니다.

## 주요 기능

- 혈압 기록 등록·조회·수정·삭제
- 최근 기록, 최고 기록, 최저 기록 요약
- 최근 7일·30일·전체 기간 및 상태별 필터
- 최근 7일 평균 혈압·맥박과 상태별 건수
- 수축기·이완기 라인 그래프와 높은 값 강조
- 가족용·의료진용 공유 링크 생성
- 공유 기간, 메모, 출생 연도, 만료일 설정
- 공유 링크 종료 및 만료·폐기 링크 접근 제한
- 어르신 기본 정보 조회·수정
- SQLite 수정 이력 내부 저장

## 혈압 상태 표시 기준

| 상태 | 프로젝트 표시 기준 |
|---|---|
| 정상 | 수축기 90~119이면서 이완기 60~79 |
| 높음 | 수축기 140 이상 또는 이완기 90 이상 |
| 주의 | 위 두 조건에 포함되지 않는 나머지 값 |

## 기술 스택

- Backend: Python, FastAPI, SQLAlchemy, Pydantic, SQLite
- Frontend: HTML, CSS, JavaScript, SVG
- Runtime: Uvicorn
- Packaging: Docker, Docker Compose
- Deployment target: AWS Lightsail 또는 EC2

## 프로젝트 구조

```text
senior-bp-health-log/
├── backend/
│   ├── __init__.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   └── services.py
├── frontend/
│   ├── css/
│   ├── js/
│   ├── index.html
│   └── share.html
├── data/
│   └── .gitkeep
├── .dockerignore
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 로컬 실행

Python 3.12 기준입니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

접속 주소:

- 관리 화면: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`
- 공유 화면: `http://127.0.0.1:8000/share/{token}`

## Docker 실행

### Docker Compose 권장

```bash
docker compose up -d --build
```

상태와 로그 확인:

```bash
docker compose ps
docker compose logs -f
```

중지:

```bash
docker compose down
```

`./data`가 `/app/data`에 마운트되므로 컨테이너를 다시 만들어도 SQLite 데이터가 유지됩니다.

### Docker 명령으로 직접 실행

```bash
docker build -t senior-bp-health-log:latest .
docker rm -f senior-bp-health-log 2>/dev/null || true
docker run -d \
  --name senior-bp-health-log \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  --restart unless-stopped \
  senior-bp-health-log:latest
```

## 주요 API

기본 경로는 `/api/v1`입니다.

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/v1/profile` | 어르신 정보 조회 |
| PUT | `/api/v1/profile` | 어르신 정보 수정 |
| POST | `/api/v1/records` | 혈압 기록 등록 |
| GET | `/api/v1/records` | 혈압 기록 목록 조회 |
| PUT | `/api/v1/records/{record_id}` | 혈압 기록 수정 |
| DELETE | `/api/v1/records/{record_id}` | 혈압 기록 삭제 |
| GET | `/api/v1/reports/weekly` | 최근 7일 리포트 조회 |
| POST | `/api/v1/shares` | 공유 링크 생성 |
| GET | `/api/v1/shares` | 공유 링크 목록 조회 |
| DELETE | `/api/v1/shares/{share_id}` | 공유 종료 |
| GET | `/api/v1/shared/{token}` | 공유 리포트 조회 |

## 공통 응답 형식

성공:

```json
{
  "success": true,
  "message": "요청을 처리했습니다.",
  "data": {},
  "meta": null,
  "error": null
}
```

실패:

```json
{
  "success": false,
  "message": "요청을 처리하지 못했습니다.",
  "data": null,
  "meta": null,
  "error": {
    "code": "ERROR_CODE",
    "details": []
  }
}
```

## 공유 링크 처리

- 존재하지 않는 토큰: 404
- 만료되거나 사용자가 종료한 링크: 410
- 출생 연도와 메모는 링크 생성 옵션에 따라 선택적으로 노출
- 내부 수정 이력과 관리용 식별자는 공유 화면에서 제외

## 검증 항목

- 등록·수정·삭제 후 목록과 새로고침 결과 확인
- 상태·기간 필터 확인
- 주간 평균과 그래프 확인
- 높은 수축기·이완기 점의 개별 강조 확인
- 가족용·의료진용 공유 링크 확인
- 공유 종료 후 410 확인
- Docker 재시작 후 SQLite 데이터 유지 확인

## 현재 상태

- [x] 혈압 기록 CRUD
- [x] 상태 분류 및 필터
- [x] 주간 리포트와 그래프
- [x] 공유 링크 생성·종료·조회
- [x] 어르신 정보 관리
- [x] Docker 설정
- [ ] AWS 서버 배포
- [ ] PRD 문서화
- [ ] ERD 문서화

## 저장소 운영 주의사항

실제 SQLite 데이터베이스, 가상환경, 환경변수 파일, 캐시와 백업 파일은 Git에 포함하지 않습니다. `data/.gitkeep`만 저장소에 포함됩니다.
