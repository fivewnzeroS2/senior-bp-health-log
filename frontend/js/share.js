"use strict";

const $field = (name) => document.querySelector(`[data-field="${name}"]`);
const $view = (name) => document.querySelector(`[data-view="${name}"]`);

function setText(name, value) {
  const el = $field(name);
  if (el) el.textContent = value;
}

function showView(name) {
  const viewNames = [
    "loading",
    "report",
    "error",
  ];

  for (const viewName of viewNames) {
    const view = document.querySelector(
      `[data-view="${viewName}"]`
    );

    if (!view) {
      console.warn(
        `화면 요소를 찾지 못했습니다: ${viewName}`
      );
      continue;
    }

    view.hidden = viewName !== name;
  }
}

function getToken() {
  const parts = location.pathname.split("/").filter(Boolean);
  if (parts[0] !== "share" || !parts[1]) return null;
  try { return decodeURIComponent(parts[1]); } catch { return null; }
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric" }).format(date);
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
}

function statusClass(category) {
  return `status-${category || "normal"}`;
}

function createRecordRow(record, includeMemo) {
  const tr = document.createElement("tr");
  const values = [
    formatDateTime(record.measured_at),
    record.measurement_period_label || "기타",
    `${record.systolic} mmHg`,
    `${record.diastolic} mmHg`,
    record.pulse == null ? "-" : `${record.pulse}회/분`
  ];

  values.forEach((value) => {
    const td = document.createElement("td");
    td.textContent = value;
    tr.appendChild(td);
  });

  const statusTd = document.createElement("td");
  const badge = document.createElement("span");
  badge.className = `status-badge ${statusClass(record.bp_category)}`;
  badge.textContent = record.bp_category_label || "-";
  statusTd.appendChild(badge);
  tr.appendChild(statusTd);

  if (includeMemo) {
    const td = document.createElement("td");
    td.textContent = record.memo?.trim() || "-";
    tr.appendChild(td);
  }
  return tr;
}

function renderRecords(records, includeMemo) {
  const body = $field("records-body");
  const table = $view("records-table");
  const empty = $view("empty-records");
  const memoHeader = document.querySelector('[data-column="memo"]');
  if (!body || !table || !empty) return;

  body.replaceChildren();
  memoHeader.hidden = !includeMemo;
  setText("record-count-text", `총 ${records.length}건`);

  if (!records.length) {
    table.hidden = true;
    empty.hidden = false;
    return;
  }

  records.forEach((record) => body.appendChild(createRecordRow(record, includeMemo)));
  empty.hidden = true;
  table.hidden = false;
}

function renderExtreme(prefix, record) {
  if (!record) {
    setText(`${prefix}-value`, "기록 없음");
    setText(`${prefix}-meta`, "-");
    return;
  }
  setText(`${prefix}-value`, `${record.systolic} / ${record.diastolic} mmHg`);
  setText(`${prefix}-meta`, `${formatDateTime(record.measured_at)} · ${record.bp_category_label}`);
}

function chartPoint(records, key, index, count) {
  const left = 55, right = 695, top = 30, bottom = 245;
  const x = count <= 1 ? (left + right) / 2 : left + (right - left) * (index / (count - 1));
  const min = 50, max = 170;
  const value = Number(records[index][key]);
  const y = bottom - ((value - min) / (max - min)) * (bottom - top);
  return { x, y, value };
}

function svgEl(tag, attrs = {}) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
  return el;
}

function renderChart(records) {
  const chart = document.querySelector("#bp-chart");
  if (!chart) return;
  const grid = chart.querySelector(".chart-grid");
  const axes = chart.querySelector(".chart-axis-labels");
  const dates = chart.querySelector(".chart-dates");
  const sysPoints = chart.querySelector(".systolic-points");
  const diaPoints = chart.querySelector(".diastolic-points");
  const sysLine = chart.querySelector(".systolic-line");
  const diaLine = chart.querySelector(".diastolic-line");

  [grid, axes, dates, sysPoints, diaPoints].forEach((el) => el.replaceChildren());

  [60, 80, 100, 120, 140, 160].forEach((value) => {
    const y = 245 - ((value - 50) / 120) * 215;
    grid.appendChild(svgEl("line", { x1: 55, y1: y, x2: 695, y2: y, class: "grid-line" }));
    const text = svgEl("text", { x: 15, y: y + 4, class: "axis-text" });
    text.textContent = value;
    axes.appendChild(text);
  });

  const ordered = [...records].sort((a, b) => new Date(a.measured_at) - new Date(b.measured_at)).slice(-14);
  if (!ordered.length) {
    sysLine.setAttribute("points", "");
    diaLine.setAttribute("points", "");
    return;
  }

  const sys = ordered.map((_, i) => chartPoint(ordered, "systolic", i, ordered.length));
  const dia = ordered.map((_, i) => chartPoint(ordered, "diastolic", i, ordered.length));
  sysLine.setAttribute("points", sys.map((p) => `${p.x},${p.y}`).join(" "));
  diaLine.setAttribute("points", dia.map((p) => `${p.x},${p.y}`).join(" "));

  ordered.forEach((record, i) => {
    const dateText = svgEl("text", { x: sys[i].x, y: 285, class: "chart-date", "text-anchor": "middle" });
    const date = new Date(record.measured_at);
    dateText.textContent = `${date.getMonth() + 1}/${date.getDate()}`;
    dates.appendChild(dateText);

    [[sys[i], sysPoints, "#2563eb", i * 80], [dia[i], diaPoints, "#16a34a", i * 80 + 120]].forEach(([point, group, color, delay]) => {
      const circle = svgEl("circle", { cx: point.x, cy: point.y, r: 5, fill: color, class: "chart-point" });
      circle.style.animationDelay = `${delay}ms`;
      const label = svgEl("text", { x: point.x, y: point.y - 12, fill: color, class: "chart-label", "text-anchor": "middle" });
      label.textContent = point.value;
      label.style.opacity = "0";
      label.style.animation = `popPoint .35s ease ${delay + 80}ms forwards`;
      group.append(circle, label);
    });
  });

  requestAnimationFrame(() => {
    sysLine.classList.remove("animate");
    diaLine.classList.remove("animate");
    void sysLine.getBoundingClientRect();
    sysLine.classList.add("animate");
    diaLine.classList.add("animate");
    chart.querySelectorAll(".chart-point").forEach((point) => point.classList.add("animate"));
  });
}

function renderReport(data) {
  const { settings, profile, period, summary, records, notice } = data;
  setText("display-name", `${profile.display_name} 혈압 리포트`);
  setText("birth-year", profile.birth_year == null ? "출생 연도 비공개" : `${profile.birth_year}년생`);
  setText("target-type", `${settings.target_type_label} 확인용`);
  setText("period", `${formatDate(period.start_date)} ~ ${formatDate(period.end_date)} · 최근 ${settings.range_days}일`);
  setText("expires-at", formatDateTime(settings.expires_at));
  setText("measurement-count", `${summary.measurement_count}회`);
  setText("average-systolic", summary.average.systolic ?? "-");
  setText("average-diastolic", summary.average.diastolic ?? "-");
  setText("average-pulse", summary.average.pulse ?? "-");
  setText("normal-count", `${summary.category_counts.normal}회`);
  setText("caution-count", `${summary.category_counts.caution}회`);
  setText("high-count", `${summary.category_counts.high}회`);
  setText("notice", notice);
  renderExtreme("highest", summary.highest);
  renderExtreme("lowest", summary.lowest);
  renderRecords(records, settings.include_memo);
  renderChart(records);
  showView("report");
}

function renderError(status, message) {
  setText("error-title", status === 404 ? "유효하지 않은 공유 링크입니다." : status === 410 ? "사용할 수 없는 공유 링크입니다." : "리포트를 불러오지 못했습니다.");
  setText("error-message", message || "공유 링크를 다시 확인해 주세요.");
  showView("error");
}

async function init() {
  showView("loading");
  const token = getToken();
  if (!token) return renderError(404, "공유 주소에서 토큰을 확인하지 못했습니다.");

  try {
    const response = await fetch(`/api/v1/shared/${encodeURIComponent(token)}`, { headers: { Accept: "application/json" }, cache: "no-store" });
    const body = await response.json();
    if (!response.ok) return renderError(response.status, body?.message);
    if (body?.success !== true || !body?.data) throw new Error("공유 리포트 응답 형식이 올바르지 않습니다.");
    renderReport(body.data);
  } catch (error) {
    console.error(error);
    renderError(500, error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.");
  }
}

document.addEventListener("DOMContentLoaded", init);
