"use strict";


/**
 * data-field 속성을 가진 요소를 찾습니다.
 */
function getField(name) {
    return document.querySelector(
        `[data-field="${name}"]`
    );
}


/**
 * data-view 속성을 가진 요소를 찾습니다.
 */
function getView(name) {
    return document.querySelector(
        `[data-view="${name}"]`
    );
}


/**
 * 요소의 텍스트를 안전하게 변경합니다.
 */
function setText(fieldName, value) {
    const element = getField(fieldName);

    if (!element) {
        console.warn(
            `화면 요소를 찾지 못했습니다: ${fieldName}`
        );
        return;
    }

    element.textContent = value;
}


/**
 * 로딩·리포트·오류 화면 중 하나만 표시합니다.
 */
function showMainView(viewName) {
    const viewNames = [
        "loading",
        "report",
        "error",
    ];

    for (const name of viewNames) {
        const view = getView(name);

        if (!view) {
            continue;
        }

        view.hidden = name !== viewName;
    }
}


/**
 * 주소에서 공유 토큰을 추출합니다.
 *
 * 예:
 * /share/abc123
 * → abc123
 */
function getTokenFromPath() {
    const pathParts = window.location.pathname
        .split("/")
        .filter(Boolean);

    if (
        pathParts.length < 2
        || pathParts[0] !== "share"
    ) {
        return null;
    }

    const token = pathParts[1];

    if (!token) {
        return null;
    }

    try {
        return decodeURIComponent(token);
    } catch {
        return null;
    }
}


/**
 * 날짜만 표시합니다.
 */
function formatDate(dateValue) {
    if (!dateValue) {
        return "-";
    }

    const date = new Date(dateValue);

    if (Number.isNaN(date.getTime())) {
        return String(dateValue);
    }

    return new Intl.DateTimeFormat(
        "ko-KR",
        {
            year: "numeric",
            month: "long",
            day: "numeric",
        }
    ).format(date);
}


/**
 * 날짜와 시간을 함께 표시합니다.
 */
function formatDateTime(dateValue) {
    if (!dateValue) {
        return "-";
    }

    const date = new Date(dateValue);

    if (Number.isNaN(date.getTime())) {
        return String(dateValue);
    }

    return new Intl.DateTimeFormat(
        "ko-KR",
        {
            year: "numeric",
            month: "long",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        }
    ).format(date);
}


/**
 * 평균값을 화면 문자열로 변환합니다.
 */
function formatAverage(value, unit) {
    if (
        value === null
        || value === undefined
    ) {
        return "-";
    }

    return `${value} ${unit}`;
}


/**
 * 최고·최저 기록을 문자열로 변환합니다.
 */
function formatRangeRecord(record) {
    if (!record) {
        return "기록 없음";
    }

    const measuredAt = formatDateTime(
        record.measured_at
    );

    return (
        `${record.systolic}/${record.diastolic} mmHg`
        + ` · ${measuredAt}`
        + ` · ${record.bp_category_label}`
    );
}


/**
 * 혈압 상태 표시 요소를 생성합니다.
 */
function createStatusBadge(record) {
    const badge = document.createElement("span");

    badge.className = [
        "status-badge",
        `status-${record.bp_category}`,
    ].join(" ");

    badge.textContent = record.bp_category_label;

    return badge;
}


/**
 * 일반 테이블 셀을 생성합니다.
 */
function createCell(text) {
    const cell = document.createElement("td");

    cell.textContent = text;

    return cell;
}


/**
 * 혈압 기록 행 하나를 생성합니다.
 */
function createRecordRow(
    record,
    includeMemo
) {
    const row = document.createElement("tr");

    row.appendChild(
        createCell(
            formatDateTime(record.measured_at)
        )
    );

    row.appendChild(
        createCell(
            record.measurement_period_label
            ?? "기타"
        )
    );

    row.appendChild(
        createCell(
            `${record.systolic} mmHg`
        )
    );

    row.appendChild(
        createCell(
            `${record.diastolic} mmHg`
        )
    );

    row.appendChild(
        createCell(
            record.pulse === null
                || record.pulse === undefined
                ? "-"
                : `${record.pulse}회/분`
        )
    );

    const statusCell = document.createElement("td");

    statusCell.appendChild(
        createStatusBadge(record)
    );

    row.appendChild(statusCell);

    if (includeMemo) {
        row.appendChild(
            createCell(
                record.memo?.trim()
                    ? record.memo
                    : "-"
            )
        );
    }

    return row;
}


/**
 * 공유 설정에 따라 메모 열을 표시하거나 숨깁니다.
 */
function updateMemoColumn(includeMemo) {
    const memoHeaders = document.querySelectorAll(
        '[data-column="memo"]'
    );

    for (const header of memoHeaders) {
        header.hidden = !includeMemo;
    }
}


/**
 * 혈압 기록 목록을 테이블에 표시합니다.
 */
function renderRecords(
    records,
    includeMemo
) {
    const tableBody = getField("records-body");
    const tableView = getView("records-table");
    const emptyView = getView("empty-records");

    if (
        !tableBody
        || !tableView
        || !emptyView
    ) {
        throw new Error(
            "혈압 기록 화면 요소를 찾지 못했습니다."
        );
    }

    tableBody.replaceChildren();

    setText(
        "record-count-text",
        `총 ${records.length}건`
    );

    updateMemoColumn(includeMemo);

    if (records.length === 0) {
        tableView.hidden = true;
        emptyView.hidden = false;
        return;
    }

    for (const record of records) {
        const row = createRecordRow(
            record,
            includeMemo
        );

        tableBody.appendChild(row);
    }

    emptyView.hidden = true;
    tableView.hidden = false;
}


/**
 * API에서 받은 공유 리포트를 화면에 표시합니다.
 */
function renderReport(reportData) {
    const {
        settings,
        profile,
        period,
        summary,
        records,
        notice,
    } = reportData;

    setText(
        "display-name",
        `${profile.display_name} 혈압 리포트`
    );

    setText(
        "birth-year",
        profile.birth_year === null
            || profile.birth_year === undefined
            ? "출생 연도 비공개"
            : `${profile.birth_year}년생`
    );

    setText(
        "target-type",
        settings.target_type_label
    );

    setText(
        "period",
        (
            `${formatDate(period.start_date)}`
            + ` ~ ${formatDate(period.end_date)}`
            + ` · 최근 ${settings.range_days}일`
        )
    );

    setText(
        "expires-at",
        formatDateTime(settings.expires_at)
    );

    setText(
        "measurement-count",
        `${summary.measurement_count}회`
    );

    setText(
        "average-systolic",
        formatAverage(
            summary.average.systolic,
            "mmHg"
        )
    );

    setText(
        "average-diastolic",
        formatAverage(
            summary.average.diastolic,
            "mmHg"
        )
    );

    setText(
        "average-pulse",
        formatAverage(
            summary.average.pulse,
            "회/분"
        )
    );

    setText(
        "normal-count",
        `${summary.category_counts.normal}회`
    );

    setText(
        "caution-count",
        `${summary.category_counts.caution}회`
    );

    setText(
        "high-count",
        `${summary.category_counts.high}회`
    );

    setText(
        "highest-record",
        formatRangeRecord(summary.highest)
    );

    setText(
        "lowest-record",
        formatRangeRecord(summary.lowest)
    );

    setText(
        "notice",
        notice
    );

    renderRecords(
        records,
        settings.include_memo
    );

    showMainView("report");
}


/**
 * 오류 응답을 화면에 표시합니다.
 */
function renderError(
    statusCode,
    message
) {
    let title = "리포트를 불러오지 못했습니다.";

    if (statusCode === 404) {
        title = "유효하지 않은 공유 링크입니다.";
    }

    if (statusCode === 410) {
        title = "사용할 수 없는 공유 링크입니다.";
    }

    setText("error-title", title);

    setText(
        "error-message",
        message
        || "공유 링크를 다시 확인해 주세요."
    );

    showMainView("error");
}


/**
 * 공유 리포트 API를 호출합니다.
 */
async function fetchSharedReport(token) {
    const apiUrl = (
        `/api/v1/shared/`
        + encodeURIComponent(token)
    );

    const response = await fetch(
        apiUrl,
        {
            method: "GET",
            headers: {
                "Accept": "application/json",
            },
            cache: "no-store",
        }
    );

    let responseBody = null;

    try {
        responseBody = await response.json();
    } catch {
        throw new Error(
            "서버 응답을 읽지 못했습니다."
        );
    }

    if (!response.ok) {
        return {
            ok: false,
            statusCode: response.status,
            message: responseBody?.message,
        };
    }

    if (
        responseBody?.success !== true
        || !responseBody?.data
    ) {
        throw new Error(
            "공유 리포트 응답 형식이 올바르지 않습니다."
        );
    }

    return {
        ok: true,
        statusCode: response.status,
        data: responseBody.data,
    };
}


/**
 * 공유 화면 초기 실행 함수입니다.
 */
async function initializeSharedReport() {
    showMainView("loading");

    const token = getTokenFromPath();

    if (!token) {
        renderError(
            404,
            "공유 주소에서 토큰을 확인하지 못했습니다."
        );
        return;
    }

    try {
        const result = await fetchSharedReport(
            token
        );

        if (!result.ok) {
            renderError(
                result.statusCode,
                result.message
            );
            return;
        }

        renderReport(result.data);

    } catch (error) {
        console.error(error);

        renderError(
            500,
            (
                error instanceof Error
                    ? error.message
                    : "알 수 없는 오류가 발생했습니다."
            )
        );
    }
}


document.addEventListener(
    "DOMContentLoaded",
    initializeSharedReport
);