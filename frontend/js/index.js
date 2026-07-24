"use strict";

const state = {
  range: "7",
  status: "all",
  records: [],
  profile: null,
  editingRecordId: null,
};

const pageTitles = {
  "record-create": "기록하기",
  "record-list": "혈압 기록",
  "weekly-report": "주간 리포트",
  "share-management": "공유 관리",
  "elder-profile": "어르신 정보",
};

function icon(id) {
  return `<svg aria-hidden="true"><use href="#${id}"></use></svg>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setText(name, value) {
  const element = document.querySelector(`[data-field="${name}"]`);
  if (element) element.textContent = value;
}

function showToast(message) {
  const toast = document.querySelector('[data-view="toast"]');
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.hidden = true;
  }, 2600);
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });

  let body = null;
  try {
    body = await response.json();
  } catch {
    throw new Error(`서버 응답을 읽지 못했습니다. (${response.status})`);
  }

  if (!response.ok || body?.success === false) {
    const details = body?.error?.details;
    const detailText = Array.isArray(details) && details.length
      ? ` ${details.map((item) => item.reason).filter(Boolean).join(" ")}`
      : "";
    throw new Error(`${body?.message || "요청을 처리하지 못했습니다."}${detailText}`);
  }

  return body;
}

function openTab(tabName) {
  document.querySelectorAll('[data-view="tab-panel"]').forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.tabPanel === tabName);
  });
  document.querySelectorAll('[data-action="open-tab"]').forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tab === tabName);
  });
  setText("page-title", pageTitles[tabName] || "관리 화면");
  history.replaceState(null, "", `#${tabName}`);

  if (tabName === "record-list") loadRecords();
  if (tabName === "weekly-report") loadWeeklyReport();
  if (tabName === "share-management") loadShares();
  if (tabName === "elder-profile") loadProfile();
}

function setDefaultDateTime() {
  const now = new Date();
  const dateInput = document.querySelector('[data-field="measured-date"]');
  const timeInput = document.querySelector('[data-field="measured-time"]');
  if (dateInput && !dateInput.value) {
    dateInput.value = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, "0"),
      String(now.getDate()).padStart(2, "0"),
    ].join("-");
  }
  if (timeInput && !timeInput.value) {
    timeInput.value = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  }
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).replace("T", " ").slice(0, 16);
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatShortDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric" }).format(date);
}

function statusBadge(record) {
  const status = record.bp_category || record.status || "caution";
  const label = record.bp_category_label || record.status_label || "주의";
  const iconId = status === "normal" ? "icon-check" : status === "caution" ? "icon-alert" : "icon-arrow-up";
  return `<span class="status-badge ${escapeHtml(status)}">${icon(iconId)}${escapeHtml(label)}</span>`;
}

function buildRecordsUrl() {
  const params = new URLSearchParams({ sort: "latest", limit: "100", offset: "0" });
  if (state.range === "7" || state.range === "30") {
    params.set("days", state.range);
  } else {
    params.set("start_date", "1900-01-01");
    params.set("end_date", new Date().toISOString().slice(0, 10));
  }
  if (state.status !== "all") params.set("category", state.status);
  return `/api/v1/records?${params.toString()}`;
}

async function loadRecords() {
  try {
    const body = await apiRequest(buildRecordsUrl());
    state.records = body?.data?.items || [];
    renderRecords(state.records);
    renderRecordSummary(state.records);
  } catch (error) {
    console.error(error);
    state.records = [];
    renderRecords([]);
    renderRecordSummary([]);
    showToast(error.message);
  }
}

function renderRecords(records) {
  const body = document.querySelector('[data-field="record-table-body"]');
  const empty = document.querySelector('[data-view="record-empty"]');
  if (!body || !empty) return;

  body.innerHTML = records.map((record) => `
    <tr>
      <td>${escapeHtml(formatDateTime(record.measured_at))}</td>
      <td>${escapeHtml(record.measurement_period_label || "기타")}</td>
      <td><strong>${escapeHtml(record.systolic)} / ${escapeHtml(record.diastolic)}</strong></td>
      <td>${record.pulse == null ? "-" : `${escapeHtml(record.pulse)}회/분`}</td>
      <td>${statusBadge(record)}</td>
      <td>${escapeHtml(record.memo || "-")}</td>
      <td>
        <button class="table-action" type="button" data-action="edit-record" data-record-id="${record.id}">수정</button>
        <button class="table-action danger" type="button" data-action="delete-record" data-record-id="${record.id}">삭제</button>
      </td>
    </tr>`).join("");

  empty.hidden = records.length !== 0;
  body.closest("table").hidden = records.length === 0;
}

function renderRecordSummary(records) {
  const latest = records[0] || null;
  const highest = records.length ? records.reduce((a, b) => (b.systolic > a.systolic || (b.systolic === a.systolic && b.diastolic > a.diastolic)) ? b : a) : null;
  const lowest = records.length ? records.reduce((a, b) => (b.systolic < a.systolic || (b.systolic === a.systolic && b.diastolic < a.diastolic)) ? b : a) : null;
  renderSummaryCard("latest", latest);
  renderSummaryCard("highest", highest);
  renderSummaryCard("lowest", lowest);
  setText("last-measured", latest ? `최근 측정 ${formatDateTime(latest.measured_at)}` : "최근 측정 기록 없음");
}

function renderSummaryCard(prefix, record) {
  setText(`${prefix}-systolic`, record?.systolic ?? "-");
  setText(`${prefix}-diastolic`, record?.diastolic ?? "-");
  setText(`${prefix}-meta`, record ? `${formatDateTime(record.measured_at)} · 맥박 ${record.pulse ?? "-"}회/분` : "기록이 없습니다.");
  const status = document.querySelector(`[data-field="${prefix}-status"]`);
  if (status) {
    if (!record) {
      status.className = "status-badge muted";
      status.textContent = "-";
    } else {
      const category = record.bp_category || "caution";
      const label = record.bp_category_label || "주의";
      const iconId = category === "normal" ? "icon-check" : category === "caution" ? "icon-alert" : "icon-arrow-up";
      status.className = `status-badge ${category}`;
      status.innerHTML = `${icon(iconId)}${escapeHtml(label)}`;
    }
  }
}

async function createRecord(event) {
  event.preventDefault();
  const date = document.querySelector('[data-field="measured-date"]')?.value;
  const time = document.querySelector('[data-field="measured-time"]')?.value;
  const systolic = Number(document.querySelector('[data-field="systolic"]')?.value);
  const diastolic = Number(document.querySelector('[data-field="diastolic"]')?.value);
  const pulseValue = document.querySelector('[data-field="pulse"]')?.value;
  const measurementPeriod = document.querySelector('[data-field="measurement-period"]')?.value || null;
  const memo = document.querySelector('[data-field="memo"]')?.value.trim() || null;

  if (!date || !time || !systolic || !diastolic) {
    showToast("측정 날짜, 시간, 수축기, 이완기를 입력해 주세요.");
    return;
  }

  const payload = {
    measured_at: `${date}T${time}:00+09:00`,
    systolic,
    diastolic,
    pulse: pulseValue ? Number(pulseValue) : null,
    measurement_period: measurementPeriod,
    memo,
  };

  try {
  const isEditing =
    state.editingRecordId !== null;

  const url = isEditing
    ? `/api/v1/records/${state.editingRecordId}`
    : "/api/v1/records";

  const method = isEditing
    ? "PUT"
    : "POST";

  const body = await apiRequest(
    url,
    {
      method,
      body: JSON.stringify(payload),
    }
  );

  showToast(
    body.message
    || (
      isEditing
        ? "혈압 기록이 수정되었습니다."
        : "혈압 기록이 저장되었습니다."
    )
  );

  state.editingRecordId = null;

  event.target.reset();

  setDefaultDateTime();

  const submitButton =
    event.target.querySelector(
      'button[type="submit"]'
    );

  if (submitButton) {
    submitButton.textContent =
      "기록 저장";
  }

  await Promise.all([
    loadRecords(),
    loadWeeklyReport(),
  ]);

  openTab("record-list");

} catch (error) {
  console.error(error);
  showToast(error.message);
}
}

function startEditRecord(recordId) {
  const record = state.records.find(
    (item) => String(item.id) === String(recordId)
  );

  if (!record) {
    showToast("수정할 기록을 찾지 못했습니다.");
    return;
  }

  state.editingRecordId = record.id;

  const measuredAtText =
    String(record.measured_at || "");

  const dateValue = measuredAtText.slice(0, 10);
  const timeValue = measuredAtText.slice(11, 16);

  const dateInput = document.querySelector(
    '[data-field="measured-date"]'
  );

  const timeInput = document.querySelector(
    '[data-field="measured-time"]'
  );

  const systolicInput = document.querySelector(
    '[data-field="systolic"]'
  );

  const diastolicInput = document.querySelector(
    '[data-field="diastolic"]'
  );

  const pulseInput = document.querySelector(
    '[data-field="pulse"]'
  );

  const periodInput = document.querySelector(
    '[data-field="measurement-period"]'
  );

  const memoInput = document.querySelector(
    '[data-field="memo"]'
  );

  if (dateInput) {
    dateInput.value = dateValue;
  }

  if (timeInput) {
    timeInput.value = timeValue;
  }

  if (systolicInput) {
    systolicInput.value = record.systolic;
  }

  if (diastolicInput) {
    diastolicInput.value = record.diastolic;
  }

  if (pulseInput) {
    pulseInput.value =
      record.pulse ?? "";
  }

  if (periodInput) {
    periodInput.value =
      record.measurement_period || "other";
  }

  if (memoInput) {
    memoInput.value =
      record.memo || "";
  }

  const submitButton = document.querySelector(
    '[data-action="record-form"] button[type="submit"]'
  );

  if (submitButton) {
    submitButton.textContent =
      "수정 내용 저장";
  }

  openTab("record-create");

  document
    .querySelector(
      '[data-action="record-form"]'
    )
    ?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });

  showToast(
    "기존 기록을 불러왔습니다. 수정 후 저장하세요."
  );
}


async function deleteRecord(recordId) {
  if (!confirm("이 혈압 기록을 삭제하시겠습니까?")) return;
  try {
    const body = await apiRequest(`/api/v1/records/${recordId}`, { method: "DELETE" });
    showToast(body.message || "기록이 삭제되었습니다.");
    await Promise.all([loadRecords(), loadWeeklyReport()]);
  } catch (error) {
    console.error(error);
    showToast(error.message);
  }
}

function selectFilter(button) {
  const type = button.dataset.filterType;
  const value = button.dataset.filterValue;
  if (!type || !value) return;
  state[type] = value;
  document.querySelectorAll(`[data-action="select-filter"][data-filter-type="${type}"]`).forEach((item) => {
    item.classList.toggle("is-selected", item === button);
  });
  loadRecords();
}

async function loadWeeklyReport() {
  try {
    const body = await apiRequest("/api/v1/reports/weekly");
    const data = body.data || {};
    const summary = data.summary || {};
    const average = summary.average || {};
    const counts = summary.category_counts || {};
    setText("weekly-period", `${data.period?.start_date || "-"} ~ ${data.period?.end_date || "-"}`);
    setText("weekly-count", summary.measurement_count ?? 0);
    setText("weekly-average-systolic", average.systolic ?? "-");
    setText("weekly-average-diastolic", average.diastolic ?? "-");
    setText("weekly-average-pulse", average.pulse ?? "-");
    setText("weekly-normal", counts.normal ?? 0);
    setText("weekly-caution", counts.caution ?? 0);
    setText("weekly-high", counts.high ?? 0);
    renderWeeklyChart(data.trend || []);
  } catch (error) {
    console.error(error);
    showToast(error.message);
    renderWeeklyChart([]);
  }
}

function renderWeeklyChart(records) {
  const svg = document.querySelector('[data-field="weekly-chart-svg"]');
  if (!svg) return;
  const sorted = [...records].sort((a, b) => new Date(a.measured_at) - new Date(b.measured_at));
  if (!sorted.length) {
    svg.innerHTML = '<text x="430" y="180" text-anchor="middle" fill="#64748b">최근 7일 혈압 기록이 없습니다.</text>';
    return;
  }

  const left = 75, right = 820, top = 40, bottom = 290;
  const minY = 50, maxY = 180;
  const x = (index) => sorted.length === 1 ? (left + right) / 2 : left + ((right - left) * index / (sorted.length - 1));
  const y = (value) => bottom - ((value - minY) / (maxY - minY)) * (bottom - top);
  const systolicPoints = sorted.map((r, i) => `${x(i)},${y(r.systolic)}`).join(" ");
  const diastolicPoints = sorted.map((r, i) => `${x(i)},${y(r.diastolic)}`).join(" ");
  const gridValues = [60, 90, 120, 150, 180];

  svg.innerHTML = `
    <g class="chart-grid">${gridValues.map((v) => `<line x1="${left}" y1="${y(v)}" x2="${right}" y2="${y(v)}"/>`).join("")}</g>
    <g class="chart-y-labels">${gridValues.map((v) => `<text x="28" y="${y(v)+5}">${v}</text>`).join("")}</g>
    <polyline class="chart-line systolic-line" points="${systolicPoints}"/>
    <polyline class="chart-line diastolic-line" points="${diastolicPoints}"/>
   <g class="chart-points systolic-points">
  ${sorted.map((record, index) => {
    const isDanger =
      record.bp_category === "high"
      || record.systolic >= 140
      || record.diastolic >= 90;

    return `
      <circle
        class="${isDanger ? "danger-point" : ""}"
        cx="${x(index)}"
        cy="${y(record.systolic)}"
        r="${isDanger ? 8 : 6}"
      >
        <title>
          ${escapeHtml(formatDateTime(record.measured_at))}
          수축기 ${escapeHtml(record.systolic)}
          / 이완기 ${escapeHtml(record.diastolic)}
          ${isDanger ? "· 높은 혈압" : ""}
        </title>
      </circle>
    `;
  }).join("")}
</g>

<g class="chart-points diastolic-points">
  ${sorted.map((record, index) => {
    const isDanger =
      record.bp_category === "high"
      || record.systolic >= 140
      || record.diastolic >= 90;

    return `
      <circle
        class="${isDanger ? "danger-point" : ""}"
        cx="${x(index)}"
        cy="${y(record.diastolic)}"
        r="${isDanger ? 8 : 6}"
      >
        <title>
          ${escapeHtml(formatDateTime(record.measured_at))}
          수축기 ${escapeHtml(record.systolic)}
          / 이완기 ${escapeHtml(record.diastolic)}
          ${isDanger ? "· 높은 혈압" : ""}
        </title>
      </circle>
    `;
  }).join("")}
</g>
    <g class="chart-x-labels">${sorted.map((r, i) => `<text x="${x(i)-18}" y="335">${escapeHtml(formatShortDate(r.measured_at))}</text>`).join("")}</g>`;

  const chart = document.querySelector('[data-view="weekly-chart"]');
  chart?.classList.remove("is-animated");
  void chart?.offsetWidth;
  chart?.classList.add("is-animated");
}

function toggleAdvancedOptions(button) {
  const options = document.querySelector('[data-view="advanced-share-options"]');
  if (!options) return;
  const expanded = button.getAttribute("aria-expanded") === "true";
  button.setAttribute("aria-expanded", String(!expanded));
  options.hidden = expanded;
}

function syncShareTarget(targetInput) {
  document.querySelectorAll(".choice-card").forEach((label) => {
    label.classList.toggle("is-selected", label.contains(targetInput));
  });
}

function updateShareSummary() {
  const range = document.querySelector('[data-field="share-range"]')?.value || "7";
  const memo = document.querySelector('[data-field="include-memo"]')?.checked;
  const birth = document.querySelector('[data-field="include-birth-year"]')?.checked;
  const expiry = document.querySelector('[data-field="share-expiry"]')?.value || "7";
  const summary = document.querySelector('[data-view="share-default-summary"] strong');
  if (summary) summary.textContent = `최근 ${range}일 · 메모 ${memo ? "포함" : "제외"} · 출생 연도 ${birth ? "포함" : "제외"} · ${expiry}일간 유효`;
}

async function createShare() {
  const target = document.querySelector('input[name="share-target"]:checked')?.value || "family";
  const payload = {
    target_type: target,
    range_days: Number(document.querySelector('[data-field="share-range"]')?.value || 7),
    include_memo: Boolean(document.querySelector('[data-field="include-memo"]')?.checked),
    include_birth_year: Boolean(document.querySelector('[data-field="include-birth-year"]')?.checked),
    expires_in_days: Number(document.querySelector('[data-field="share-expiry"]')?.value || 7),
  };
  try {
    const body = await apiRequest("/api/v1/shares", { method: "POST", body: JSON.stringify(payload) });
    showToast(body.message || "공유 링크가 생성되었습니다.");
    await loadShares();
    if (body?.data?.share_url && confirm("생성된 공유 화면을 새 탭에서 여시겠습니까?")) {
      window.open(body.data.share_url, "_blank", "noopener");
    }
  } catch (error) {
    console.error(error);
    showToast(error.message);
  }
}

async function loadShares() {
  const tableBody = document.querySelector('[data-field="share-table-body"]');
  const empty = document.querySelector('[data-view="share-empty"]');
  if (!tableBody || !empty) return;
  try {
    const body = await apiRequest("/api/v1/shares");
    const shares = body?.data?.items || [];
    tableBody.innerHTML = shares.map((share) => `
      <tr>
        <td>${escapeHtml(formatDateTime(share.created_at))}</td>
        <td>${escapeHtml(share.target_type_label)}</td>
        <td>최근 ${escapeHtml(share.range_days)}일</td>
        <td>${escapeHtml(formatDateTime(share.expires_at))}</td>
        <td><span class="status-badge ${share.status === "active" ? "normal" : "muted"}">${escapeHtml(share.status_label)}</span></td>
        <td>${share.status === "active" ? `
          <button class="table-action" type="button" data-action="copy-share" data-share-url="${escapeHtml(share.share_url)}">${icon("icon-copy")}링크 복사</button>
          <button class="table-action danger" type="button" data-action="end-share" data-share-id="${share.id}">${icon("icon-x")}공유 종료</button>` : '<span class="disabled-text">사용 불가</span>'}</td>
      </tr>`).join("");
    empty.hidden = shares.length !== 0;
    tableBody.closest("table").hidden = shares.length === 0;
  } catch (error) {
    console.error(error);
    tableBody.innerHTML = "";
    empty.hidden = false;
    showToast(error.message);
  }
}

async function copyShare(url) {
  try {
    await navigator.clipboard.writeText(url);
    showToast("공유 링크를 복사했습니다.");
  } catch {
    prompt("아래 링크를 복사해 주세요.", url);
  }
}

async function endShare(shareId) {
  if (!confirm("이 공유 링크를 종료하시겠습니까?")) return;
  try {
    const body = await apiRequest(`/api/v1/shares/${shareId}`, { method: "DELETE" });
    showToast(body.message || "공유가 종료되었습니다.");
    await loadShares();
  } catch (error) {
    console.error(error);
    showToast(error.message);
  }
}

async function loadProfile() {
  try {
    const body = await apiRequest("/api/v1/profile");
    state.profile = body.data;
    renderProfile(body.data);
  } catch (error) {
    console.error(error);
    showToast(error.message);
  }
}

function renderProfile(profile) {
  if (!profile) return;
  setText("profile-display-name", profile.display_name || `${profile.name} ${profile.honorific}`.trim());
  setText("profile-birth-year", profile.birth_year ? `${profile.birth_year}년생` : "출생 연도 미등록");
  setText("profile-name", profile.name || "-");
  setText("profile-honorific", profile.honorific || "-");
  setText("profile-detail-birth-year", profile.birth_year ? `${profile.birth_year}년` : "미등록");
  setText("profile-detail-display-name", profile.display_name || "-");
}

async function editProfile() {
  const current = state.profile || {};
  const name = prompt("이름", current.name || "");
  if (name === null) return;
  const honorific = prompt("호칭", current.honorific || "어르신");
  if (honorific === null) return;
  const birthInput = prompt("출생 연도 (모르면 비워두기)", current.birth_year ?? "");
  if (birthInput === null) return;
  const payload = { name: name.trim(), honorific: honorific.trim(), birth_year: birthInput.trim() ? Number(birthInput) : null };
  try {
    const body = await apiRequest("/api/v1/profile", { method: "PUT", body: JSON.stringify(payload) });
    state.profile = body.data;
    renderProfile(body.data);
    showToast(body.message || "어르신 정보를 수정했습니다.");
  } catch (error) {
    console.error(error);
    showToast(error.message);
  }
}

document.addEventListener("click", (event) => {
  const tabButton = event.target.closest('[data-action="open-tab"]');
  if (tabButton) {
    event.preventDefault();
    openTab(tabButton.dataset.tab);
    return;
  }

  const filterButton = event.target.closest('[data-action="select-filter"]');
  if (filterButton) {
    event.preventDefault();
    selectFilter(filterButton);
    return;
  }

  const editButton = event.target.closest('[data-action="edit-record"]');
  if (editButton) {
    event.preventDefault();
    startEditRecord(editButton.dataset.recordId);
    return;
  }

  const deleteButton = event.target.closest('[data-action="delete-record"]');
  if (deleteButton) {
    event.preventDefault();
    deleteRecord(deleteButton.dataset.recordId);
    return;
  }

  const advancedButton = event.target.closest('[data-action="toggle-share-options"]');
  if (advancedButton) {
    event.preventDefault();
    toggleAdvancedOptions(advancedButton);
    return;
  }

  const createShareButton = event.target.closest('[data-action="create-share"]');
  if (createShareButton) {
    event.preventDefault();
    createShare();
    return;
  }

  const copyButton = event.target.closest('[data-action="copy-share"]');
  if (copyButton) {
    event.preventDefault();
    copyShare(copyButton.dataset.shareUrl);
    return;
  }

  const endButton = event.target.closest('[data-action="end-share"]');
  if (endButton) {
    event.preventDefault();
    endShare(endButton.dataset.shareId);
    return;
  }

  const editProfileButton = event.target.closest('[data-action="edit-profile"]');
  if (editProfileButton) {
    event.preventDefault();
    editProfile();
  }
});

document.addEventListener("change", (event) => {
  if (event.target.matches('input[name="share-target"]')) syncShareTarget(event.target);
  if (event.target.matches('[data-field="share-range"],[data-field="include-memo"],[data-field="include-birth-year"],[data-field="share-expiry"]')) updateShareSummary();
});

document.querySelector('[data-action="record-form"]')?.addEventListener("submit", createRecord);

async function initialize() {
  setDefaultDateTime();
  updateShareSummary();
  await loadProfile();
  await Promise.all([loadRecords(), loadWeeklyReport(), loadShares()]);
  const initialTab = location.hash.replace("#", "");
  openTab(pageTitles[initialTab] ? initialTab : "record-create");
}

document.addEventListener("DOMContentLoaded", initialize);

