const state = {
  allRows: [],
  latestRows: [],
  scope: "latest",
  chip: "all",
  currentRows: [],
};

const naturalQueryState = {
  context: null,
  awaitingClarification: false,
  clarificationRounds: 0,
  conversation: [],
  page: 1,
  pageSize: 10,
  totalPages: 1,
};

const apiBase = "";
const tableColumns = ["学部", "期次", "线索渠道二级分类", "价体", "年级", "target_time", "下单日期", "目标", "现状", "差距", "完成率", "进度"];
const metricDepartments = ["小学", "初中", "高中"];

function fmtNumber(value) {
  return Number(value || 0).toLocaleString("zh-CN");
}

function fmtPercent(value) {
  if (value === null || value === undefined || value === "") return "";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2400);
}

function uploadStatus(kind, type, message) {
  const el = document.getElementById(`${kind}UploadStatus`);
  el.textContent = message;
  el.className = `upload-status show ${type}`;
}

async function requestJson(url, options) {
  const res = await fetch(`${apiBase}${url}`, options);
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("服务返回的不是 JSON，请确认本地看板服务已启动并刷新页面。");
  }
  if (!res.ok || data.error) {
    throw new Error(data.error || data.message || data.dingtalk?.errmsg || "请求失败");
  }
  return data;
}

async function loadState() {
  try {
    const response = await fetch("/outputs/tongji_summary/summary_payload.json");
    if (!response.ok) throw new Error("无法读取数据文件");
    const data = await response.json();
    state.allRows = rowsFromPayload(data.summary);
    state.latestRows = rowsFromPayload(data.latest_summary);
    renderFileInfo({ demo: { name: "tongji_demo.xlsx", updated_at: "已内置" }, target: { name: "tongji_target.xlsx", updated_at: "已内置" } });
    renderMetrics(data.metrics.latest);
    buildFilters();
    render();
  } catch (error) {
    toast(error.message || "加载数据失败");
  }
}

function rowsFromPayload(payload) {
  const headers = payload.headers;
  return payload.rows.map(row => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
}

function renderFileInfo(files) {
  document.getElementById("demoInfo").innerHTML = `当前：${files.demo?.name || "-"}<br>更新时间：${files.demo?.updated_at || "-"}`;
  document.getElementById("targetInfo").innerHTML = `当前：${files.target?.name || "-"}<br>更新时间：${files.target?.updated_at || "-"}`;
}

function isBehindProgress(row) {
  const progress = row["进度"];
  return progress !== null
    && progress !== undefined
    && progress !== ""
    && Number(row["完成率"] || 0) < Number(progress);
}

function metricsForRows(rows) {
  const targetTotal = rows.reduce((sum, row) => sum + Number(row["目标"] || 0), 0);
  const currentTotal = rows.reduce((sum, row) => sum + Number(row["现状"] || 0), 0);
  const progressValues = rows
    .map(row => row["进度"])
    .filter(value => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)))
    .map(Number);
  const behindCount = rows.filter(isBehindProgress).length;
  return {
    target_total: targetTotal,
    current_total: currentTotal,
    completion: targetTotal ? currentTotal / targetTotal : null,
    avg_progress: progressValues.length
      ? progressValues.reduce((sum, value) => sum + value, 0) / progressValues.length
      : null,
    behind_count: behindCount,
  };
}

function renderDepartmentMetrics() {
  const tbody = document.getElementById("departmentMetricsBody");
  tbody.innerHTML = "";
  metricDepartments.forEach(department => {
    const metrics = metricsForRows(state.latestRows.filter(row => row["学部"] === department));
    const behindCount = fmtNumber(metrics.behind_count);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <th scope="row">${department}</th>
      <td>${fmtNumber(metrics.target_total)}</td>
      <td>${fmtNumber(metrics.current_total)}</td>
      <td class="red">${fmtPercent(metrics.completion) || "-"}</td>
      <td>${fmtPercent(metrics.avg_progress) || "-"}</td>
      <td class="red">
        <button
          class="metric-drilldown"
          type="button"
          aria-label="查看${department}${behindCount}个落后项"
          ${metrics.behind_count ? "" : "disabled"}
        >${behindCount}</button>
      </td>
    `;
    tr.querySelector(".metric-drilldown").addEventListener("click", () => showBehindDetails(department));
    tbody.appendChild(tr);
  });
}

function renderMetrics(metrics) {
  renderDepartmentMetrics();
  document.getElementById("chipBehind").textContent = `落后进度 ${metrics.behind_count}`;
}

function uniqueOptions(rows, key) {
  return [...new Set(rows.map(row => row[key]).filter(v => v !== null && v !== undefined && v !== ""))]
    .sort((a, b) => String(a).localeCompare(String(b), "zh-CN", { numeric: true }));
}

function fillSelect(id, values, firstLabel = "全部") {
  const select = document.getElementById(id);
  const current = select.value;
  select.innerHTML = "";
  const all = document.createElement("option");
  all.value = "";
  all.textContent = firstLabel;
  select.appendChild(all);
  values.forEach(value => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
  if ([...select.options].some(option => option.value === current)) select.value = current;
}

function buildFilters() {
  fillSelect("filterDepartment", uniqueOptions(state.allRows, "学部"));
  fillSelect("filterTerm", uniqueOptions(state.allRows, "期次"), state.scope === "latest" ? "最新期次（默认）" : "全部期次");
  fillSelect("filterChannel", uniqueOptions(state.allRows, "线索渠道二级分类"));
  fillSelect("filterPayment", uniqueOptions(state.allRows, "价体").map(String));
  fillSelect("filterOrderDate", uniqueOptions(state.allRows, "下单日期"), "全部日期");
}

function rowStatus(row) {
  if (Number(row["目标"]) > 0 && Number(row["现状"]) === 0) return { text: "未开单", cls: "empty" };
  if (row["进度"] !== null && Number(row["完成率"] || 0) < Number(row["进度"])) return { text: "落后", cls: "late" };
  if (Number(row["目标"]) > 0 && Number(row["完成率"] || 0) >= 1) return { text: "已完成", cls: "done" };
  if (Number(row["目标"]) === 0 && Number(row["现状"]) > 0) return { text: "仅现状", cls: "current-only" };
  if (row["进度"] !== null && Number(row["完成率"] || 0) - Number(row["进度"]) + 1e-9 >= 0.1) {
    return { text: "快", cls: "normal" };
  }
  return { text: "正常", cls: "normal" };
}

function activeRows() {
  return state.scope === "latest" ? state.latestRows : state.allRows;
}

function filteredRows() {
  const rows = activeRows();
  const filters = {
    "学部": document.getElementById("filterDepartment").value,
    "期次": document.getElementById("filterTerm").value,
    "线索渠道二级分类": document.getElementById("filterChannel").value,
    "价体": document.getElementById("filterPayment").value,
    "下单日期": document.getElementById("filterOrderDate").value,
  };
  const keyword = document.getElementById("filterKeyword").value.trim();

  return rows.filter(row => {
    for (const [key, value] of Object.entries(filters)) {
      if (value && String(row[key]) !== String(value)) return false;
    }
    if (keyword) {
      const haystack = tableColumns.map(key => row[key]).join(" ");
      if (!haystack.includes(keyword)) return false;
    }
    if (state.chip === "behind" && !isBehindProgress(row)) return false;
    if (state.chip === "fast" && rowStatus(row).text !== "快") return false;
    return true;
  });
}

function render() {
  document.getElementById("chipAll").textContent = `${state.scope === "latest" ? "最新期次" : "全部期次"} ${activeRows().length}`;
  document.getElementById("chipFast").textContent = `快 ${activeRows().filter(row => rowStatus(row).text === "快").length}`;
  const rows = filteredRows();
  state.currentRows = rows;
  const department = document.getElementById("filterDepartment").value;
  document.getElementById("tableTitle").textContent = state.chip === "behind"
    ? `${department ? `${department} · ` : ""}落后项明细（${rows.length}）`
    : state.chip === "fast"
      ? `${department ? `${department} · ` : ""}快项明细（${rows.length}）`
      : `${department ? `${department} · ` : ""}${state.scope === "latest" ? "最新期次" : "全部期次"}明细（${rows.length}）`;
  const tbody = document.getElementById("summaryBody");
  tbody.innerHTML = "";

  rows.forEach(row => {
    const status = rowStatus(row);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row["学部"] ?? ""}</td>
      <td>${row["期次"] ?? ""}</td>
      <td>${row["线索渠道二级分类"] ?? ""}</td>
      <td class="num">${row["价体"] ?? ""}</td>
      <td>${row["年级"] ?? ""}</td>
      <td>${row["target_time"] ?? ""}</td>
      <td>${row["下单日期"] ?? ""}</td>
      <td class="num">${fmtNumber(row["目标"])}</td>
      <td class="num">${fmtNumber(row["现状"])}</td>
      <td class="num">${fmtNumber(row["差距"])}</td>
      <td class="num">${fmtPercent(row["完成率"])}</td>
      <td class="num">${fmtPercent(row["进度"])}</td>
      <td><span class="status ${status.cls}">${status.text}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function showBehindDetails(department) {
  state.scope = "latest";
  state.chip = "behind";
  buildFilters();
  document.getElementById("filterDepartment").value = department;
  ["filterTerm", "filterChannel", "filterPayment", "filterOrderDate", "filterKeyword"].forEach(id => {
    document.getElementById(id).value = "";
  });
  document.querySelectorAll(".chip").forEach(el => el.classList.toggle("active", el.dataset.chip === "behind"));
  document.getElementById("toggleScopeButton").textContent = "切换到全部期次";
  render();
  document.getElementById("summary").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function uploadFile(kind, file) {
  const form = new FormData();
  form.append(kind, file);
  const button = document.getElementById(`${kind}UploadButton`);
  const label = kind === "demo" ? "demo" : "target";
  toast("正在上传并重算...");
  uploadStatus(kind, "pending", `正在上传 ${label} 并重算 summary...`);
  button.disabled = true;
  try {
    const data = await requestJson("/api/upload", { method: "POST", body: form });
    state.allRows = data.state.summary;
    state.latestRows = data.state.latestSummary;
    renderFileInfo(data.state.files);
    renderMetrics(data.state.metrics.latest);
    buildFilters();
    render();
    const fileInfo = data.state.files[kind];
    const updatedAt = fileInfo?.updated_at ? `更新时间：${fileInfo.updated_at}` : "已完成重算";
    uploadStatus(kind, "success", `${label} 上传成功，summary 已更新。${updatedAt}`);
    toast("上传成功，summary 已更新");
  } catch (error) {
    uploadStatus(kind, "error", `${label} 上传失败：${error.message}`);
    toast(error.message);
  } finally {
    button.disabled = false;
    document.getElementById(`${kind}File`).value = "";
  }
}

async function reloadDemoFile() {
  const button = document.getElementById("demoUploadButton");
  toast("正在读取固定 demo 并重算...");
  uploadStatus("demo", "pending", "正在读取固定 demo 并重算 summary...");
  button.disabled = true;
  try {
    const data = await requestJson("/api/reload-demo", { method: "POST" });
    state.allRows = data.state.summary;
    state.latestRows = data.state.latestSummary;
    renderFileInfo(data.state.files);
    renderMetrics(data.state.metrics.latest);
    buildFilters();
    render();
    const updatedAt = data.state.files.demo?.updated_at
      ? `更新时间：${data.state.files.demo.updated_at}`
      : "已完成重算";
    uploadStatus("demo", "success", `demo 读取成功，summary 已更新。${updatedAt}`);
    toast("demo 读取成功，summary 已更新");
  } catch (error) {
    uploadStatus("demo", "error", `demo 读取失败：${error.message}`);
    toast(error.message);
  } finally {
    button.disabled = false;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function openNaturalQuery() {
  const panel = document.getElementById("naturalQueryPanel");
  panel.hidden = false;
  document.getElementById("mainContent").classList.add("query-mode");
  document.getElementById("naturalQueryInput").focus();
}

function closeNaturalQuery() {
  document.getElementById("naturalQueryPanel").hidden = true;
  document.getElementById("mainContent").classList.remove("query-mode");
}

function renderQueryConversation() {
  const history = document.getElementById("queryConversationHistory");
  history.innerHTML = "";
  naturalQueryState.conversation.forEach((turn, index) => {
    const row = document.createElement("div");
    row.className = `query-conversation-turn ${turn.role}`;
    if (
      naturalQueryState.awaitingClarification
      && turn.role === "assistant"
      && index === naturalQueryState.conversation.length - 1
    ) {
      row.classList.add("current");
    }

    const label = document.createElement("span");
    label.className = "query-conversation-role";
    label.textContent = turn.role === "user" ? "你" : "系统";

    const message = document.createElement("span");
    message.className = "query-conversation-message";
    message.textContent = turn.message;

    row.append(label, message);
    history.appendChild(row);
  });
}

function appendQueryConversationTurn(role, message) {
  naturalQueryState.conversation.push({ role, message });
  renderQueryConversation();
}

function showQueryClarification(message, role = "assistant") {
  const clarification = document.getElementById("queryClarification");
  appendQueryConversationTurn(role, message);
  clarification.hidden = false;
  document.getElementById("queryResult").hidden = true;
}

function hideQueryClarification() {
  const clarification = document.getElementById("queryClarification");
  clarification.hidden = true;
}

function resetNaturalQueryConversation() {
  naturalQueryState.context = null;
  naturalQueryState.awaitingClarification = false;
  naturalQueryState.clarificationRounds = 0;
  naturalQueryState.conversation = [];
  naturalQueryState.page = 1;
  renderQueryConversation();
  hideQueryClarification();
  document.getElementById("queryResult").hidden = true;
  const input = document.getElementById("naturalQueryInput");
  input.value = "";
  input.placeholder = "例如：6月27日YZY渠道的进量";
  input.focus();
}

function renderQueryPagination(result) {
  naturalQueryState.page = result.page;
  naturalQueryState.totalPages = result.totalPages;

  document.getElementById("queryPreviousPage").disabled = result.page <= 1;
  document.getElementById("queryNextPage").disabled = result.page >= result.totalPages;
  document.getElementById("queryPageSummary").textContent =
    `共 ${fmtNumber(result.matchedRows)} 条，第 ${result.page}/${result.totalPages} 页`;

  const pageSet = new Set([1, result.totalPages, result.page - 1, result.page, result.page + 1]);
  const pages = [...pageSet]
    .filter(page => page >= 1 && page <= result.totalPages)
    .sort((a, b) => a - b);
  const container = document.getElementById("queryPageNumbers");
  container.innerHTML = "";
  pages.forEach((page, index) => {
    if (index > 0 && page - pages[index - 1] > 1) {
      const gap = document.createElement("span");
      gap.textContent = "…";
      container.appendChild(gap);
    }
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = page;
    button.dataset.queryPage = page;
    button.classList.toggle("active", page === result.page);
    button.setAttribute("aria-label", `第${page}页`);
    container.appendChild(button);
  });
}

function renderNaturalQueryResult(result) {
  const conditions = result.conditions;
  naturalQueryState.context = {
    date: conditions.date,
    last_from: conditions.last_from,
    channel_name: conditions.channelName,
    channel_field: conditions.channel_field,
    channel_value: conditions.channel_value,
    payment: conditions.payment,
    metric: conditions.metric,
    filters: conditions.filters,
    group_by: conditions.groupBy,
  };
  naturalQueryState.awaitingClarification = false;
  naturalQueryState.clarificationRounds = 0;

  const conditionList = document.getElementById("queryConditionList");
  const conditionValues = [];
  if (conditions.date) conditionValues.push(`日期：${conditions.date}`);
  Object.entries(conditions.filters || {}).forEach(([field, value]) => {
    conditionValues.push(`${field}：${Array.isArray(value) ? value.join("、") : value}`);
  });
  if (conditions.last_from) conditionValues.push(`last_from：${conditions.last_from}`);
  conditionValues.push(`指标：${conditions.metric}`);
  conditionList.innerHTML = conditionValues
    .map(value => `<span>${escapeHtml(value)}</span>`)
    .join("");

  document.getElementById("queryInterpretation").open = false;
  document.getElementById("queryAnswer").textContent = result.answer;
  document.getElementById("queryResult").hidden = false;
  document.getElementById("naturalQueryInput").placeholder = "例如：6月27日YZY渠道的进量";

  const numericColumns = new Set(["价体", "成单量", "目标"]);
  document.getElementById("queryResultHead").innerHTML = result.columns
    .map(column => `<th class="${numericColumns.has(column) ? "num" : ""}">${escapeHtml(column)}</th>`)
    .join("");

  const tbody = document.getElementById("queryResultBody");
  tbody.innerHTML = result.rows.length
    ? result.rows.map(row => `
      <tr>
        ${result.columns.map(column => `
          <td class="${numericColumns.has(column) ? "num" : ""}">${escapeHtml(row[column])}</td>
        `).join("")}
      </tr>
    `).join("")
    : `<tr><td colspan="${result.columns.length}">没有匹配的查询明细</td></tr>`;

  renderQueryPagination(result);
}

async function requestNaturalQuery(query, page = 1) {
  const submitButton = document.getElementById("naturalQuerySubmit");
  submitButton.disabled = true;
  try {
    const result = await requestJson("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        context: naturalQueryState.context,
        page,
        pageSize: naturalQueryState.pageSize,
      }),
    });

    if (result.status === "needs_clarification") {
      naturalQueryState.clarificationRounds += 1;
      if (naturalQueryState.clarificationRounds > 2) {
        naturalQueryState.context = null;
        naturalQueryState.awaitingClarification = false;
        showQueryClarification("信息仍不完整，请重新输入包含日期和渠道的完整问题。");
        return;
      }
      naturalQueryState.context = result.context;
      naturalQueryState.awaitingClarification = true;
      showQueryClarification(result.question);
      const input = document.getElementById("naturalQueryInput");
      input.value = "";
      input.placeholder = result.question;
      input.focus();
      return;
    }

    hideQueryClarification();
    renderNaturalQueryResult(result);
  } catch (error) {
    showQueryClarification(error.message);
  } finally {
    submitButton.disabled = false;
  }
}

async function submitNaturalQuery() {
  const input = document.getElementById("naturalQueryInput");
  const query = input.value.trim();
  if (!query) {
    toast("请输入查询问题");
    input.focus();
    return;
  }
  if (!naturalQueryState.awaitingClarification) {
    naturalQueryState.context = null;
    naturalQueryState.clarificationRounds = 0;
    naturalQueryState.conversation = [];
  }
  naturalQueryState.awaitingClarification = false;
  appendQueryConversationTurn("user", query);
  await requestNaturalQuery(query, 1);
}

async function loadNaturalQueryPage(page) {
  if (!naturalQueryState.context) return;
  await requestNaturalQuery("", page);
}

async function broadcastReport(dept) {
  const labels = { primary: "小学", middle: "初中", high: "高中", lec1: "1元占比" };
  toast(`正在播报${labels[dept]}图片到钉钉...`);
  try {
    const result = await requestJson("/api/broadcast-report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dept }),
    });
    const warning = result.localOnlyUrl ? "；当前图片地址是本机地址，群内其他人可能无法打开" : "";
    toast(`已发送${result.label}播报图${warning}`);
  } catch (error) {
    toast(error.message);
  }
}

function bindEvents() {
  document.getElementById("demoUploadButton").addEventListener("click", reloadDemoFile);
  document.getElementById("targetUploadButton").addEventListener("click", () => document.getElementById("targetFile").click());
  document.getElementById("targetFile").addEventListener("change", event => event.target.files[0] && uploadFile("target", event.target.files[0]));

  ["filterDepartment", "filterTerm", "filterChannel", "filterPayment", "filterOrderDate", "filterKeyword"].forEach(id => {
    document.getElementById(id).addEventListener("input", render);
  });

  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach(el => el.classList.remove("active"));
      chip.classList.add("active");
      state.chip = chip.dataset.chip;
      render();
    });
  });

  document.getElementById("toggleScopeButton").addEventListener("click", toggleScope);
  document.getElementById("showAllButton").addEventListener("click", () => { if (state.scope !== "all") toggleScope(); });
  document.getElementById("refreshButton").addEventListener("click", loadState);
  document.getElementById("exportLatest").addEventListener("click", () => location.href = `${apiBase}/download/summary?scope=latest`);
  document.getElementById("exportAll").addEventListener("click", () => location.href = `${apiBase}/download/summary?scope=all`);
  document.getElementById("exportCurrent").addEventListener("click", exportCurrentRows);
  document.getElementById("downloadWorkbook").addEventListener("click", () => location.href = `${apiBase}/download/workbook`);
  document.getElementById("exportQuery").addEventListener("click", () => location.href = `${apiBase}/download/query`);
  document.getElementById("naturalQueryButton").addEventListener("click", openNaturalQuery);
  document.getElementById("closeNaturalQuery").addEventListener("click", closeNaturalQuery);
  document.getElementById("restartNaturalQuery").addEventListener("click", resetNaturalQueryConversation);
  document.getElementById("naturalQueryForm").addEventListener("submit", event => {
    event.preventDefault();
    submitNaturalQuery();
  });
  document.querySelectorAll("[data-query-example]").forEach(button => {
    button.addEventListener("click", () => {
      naturalQueryState.context = null;
      naturalQueryState.awaitingClarification = false;
      naturalQueryState.clarificationRounds = 0;
      naturalQueryState.conversation = [];
      renderQueryConversation();
      hideQueryClarification();
      const input = document.getElementById("naturalQueryInput");
      input.value = button.dataset.queryExample;
      input.focus();
    });
  });
  document.getElementById("queryPageSize").addEventListener("change", event => {
    naturalQueryState.pageSize = Number(event.target.value);
    loadNaturalQueryPage(1);
  });
  document.getElementById("queryPreviousPage").addEventListener("click", () => {
    loadNaturalQueryPage(naturalQueryState.page - 1);
  });
  document.getElementById("queryNextPage").addEventListener("click", () => {
    loadNaturalQueryPage(naturalQueryState.page + 1);
  });
  document.getElementById("queryPageNumbers").addEventListener("click", event => {
    const button = event.target.closest("[data-query-page]");
    if (button) loadNaturalQueryPage(Number(button.dataset.queryPage));
  });
  document.getElementById("downloadQueryResult").addEventListener("click", () => {
    location.href = `${apiBase}/download/query`;
  });
  document.getElementById("reportPrimary").addEventListener("click", () => location.href = `${apiBase}/download/report?dept=primary`);
  document.getElementById("reportMiddle").addEventListener("click", () => location.href = `${apiBase}/download/report?dept=middle`);
  document.getElementById("reportHigh").addEventListener("click", () => location.href = `${apiBase}/download/report?dept=high`);
  document.getElementById("reportLec1").addEventListener("click", () => location.href = `${apiBase}/download/report?dept=lec1`);
  document.getElementById("broadcastPrimary").addEventListener("click", () => broadcastReport("primary"));
  document.getElementById("broadcastMiddle").addEventListener("click", () => broadcastReport("middle"));
  document.getElementById("broadcastHigh").addEventListener("click", () => broadcastReport("high"));
  document.getElementById("broadcastLec1").addEventListener("click", () => broadcastReport("lec1"));
}

function toggleScope() {
  state.scope = state.scope === "latest" ? "all" : "latest";
  state.chip = "all";
  document.querySelectorAll(".chip").forEach(el => el.classList.remove("active"));
  document.querySelector('[data-chip="all"]').classList.add("active");
  document.getElementById("tableTitle").textContent = state.scope === "latest" ? "最新期次明细" : "全部期次明细";
  document.getElementById("toggleScopeButton").textContent = state.scope === "latest" ? "切换到全部期次" : "切换到最新期次";
  buildFilters();
  render();
}

bindEvents();
loadState();

function exportCurrentRows() {
  if (!state.currentRows.length) {
    toast("当前视图没有可导出的数据");
    return;
  }
  const headers = tableColumns;
  const escape = value => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const lines = [
    headers.join(","),
    ...state.currentRows.map(row => headers.map(key => escape(row[key])).join(",")),
  ];
  const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `summary_current_view_${state.scope}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
