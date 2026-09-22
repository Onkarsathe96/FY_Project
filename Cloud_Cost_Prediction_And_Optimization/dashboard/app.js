const API_URL = "/api/v1";
const HISTORY_DAYS = 30;
const $ = (id) => document.getElementById(id);
let dashboardData = { accounts: [], costs: [], forecasts: [], anomalies: [], resources: [] };

async function apiGet(path, params = {}) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== ""));
  const response = await fetch(`${API_URL}${path}${query.size ? `?${query}` : ""}`);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

async function apiPost(path, payload) {
  const response = await fetch(`${API_URL}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

function showToast(message, isError = false) {
  const toast = $("toast");
  toast.textContent = message;
  toast.style.background = isError ? "#b44d5d" : "#24304b";
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 4000);
}

function money(value, currency = "") {
  const amount = Number(value || 0);
  return `${currency ? `${currency} ` : ""}${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function setLoading(button, loading) {
  button.disabled = loading;
  if (loading) button.dataset.original = button.innerHTML;
  button.innerHTML = loading ? "Working..." : (button.dataset.original || button.innerHTML);
}

function lineChart(values, color, fillColor) {
  if (!values.length) return '<div class="empty-state">No data available for this period.</div>';
  const width = 640, height = 195, pad = { top: 10, right: 8, bottom: 26, left: 8 };
  const max = Math.max(...values.map(([, value]) => value), 1);
  const min = Math.min(...values.map(([, value]) => value), 0);
  const x = (index) => pad.left + index * (width - pad.left - pad.right) / Math.max(values.length - 1, 1);
  const y = (value) => pad.top + (max - value) * (height - pad.top - pad.bottom) / Math.max(max - min, 1);
  const points = values.map(([, value], index) => `${x(index)},${y(value)}`).join(" ");
  const area = `${pad.left},${height - pad.bottom} ${points} ${x(values.length - 1)},${height - pad.bottom}`;
  const labels = values.filter((_, i) => i === 0 || i === values.length - 1 || (values.length > 8 && i === Math.floor(values.length / 2)));
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Spend line chart">
    <defs><linearGradient id="chart-fill-${color.slice(1)}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${fillColor}" stop-opacity=".26"/><stop offset="1" stop-color="${fillColor}" stop-opacity="0"/></linearGradient></defs>
    <line x1="0" y1="45" x2="${width}" y2="45" stroke="#eef1f6"/><line x1="0" y1="105" x2="${width}" y2="105" stroke="#eef1f6"/><line x1="0" y1="165" x2="${width}" y2="165" stroke="#eef1f6"/>
    <polygon points="${area}" fill="url(#chart-fill-${color.slice(1)})"/><polyline points="${points}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    ${labels.map(([label], index) => `<text x="${x(values.indexOf(values.find(([date]) => date === label)))}" y="${height - 5}" text-anchor="${index === 0 ? "start" : index === labels.length - 1 ? "end" : "middle"}" fill="#a4adbc" font-size="10">${label.slice(5)}</text>`).join("")}
  </svg>`;
}

function renderMetrics() {
  $("metric-costs").textContent = dashboardData.costs.length;
  $("metric-forecasts").textContent = dashboardData.forecasts.length;
  $("metric-anomalies").textContent = dashboardData.anomalies.length;
  $("metric-resources").textContent = dashboardData.resources.length;
  $("anomaly-count").textContent = dashboardData.anomalies.length;
  $("resource-count").textContent = `${dashboardData.resources.length} candidates`;
}

function renderSpend() {
  const totals = {};
  dashboardData.costs.forEach((record) => { totals[record.usage_date] = (totals[record.usage_date] || 0) + Number(record.amount); });
  const values = Object.entries(totals).sort(([a], [b]) => a.localeCompare(b));
  $("spend-chart").innerHTML = lineChart(values, "#6575f2", "#6575f2");
  const currencies = [...new Set(dashboardData.costs.map((record) => record.currency).filter(Boolean))];
  $("currency-label").textContent = currencies.length ? currencies.join(", ") : "No currency";
  const awsAccount = dashboardData.accounts.find((account) => account.provider === "aws" && !account.external_account_id.endsWith("-sample"));
  $("spend-range").textContent = values.length ? `Billing dates ${values[0][0]} – ${values[values.length - 1][0]} · AWS UnblendedCost · ${awsAccount ? awsAccount.display_name : "AWS account unavailable"}` : "No AWS billing records available for the selected window.";
}

function renderForecast() {
  const totals = {};
  dashboardData.forecasts.forEach((record) => { totals[record.forecast_date] = (totals[record.forecast_date] || 0) + Number(record.predicted_amount); });
  const values = Object.entries(totals).sort(([a], [b]) => a.localeCompare(b));
  $("forecast-chart").innerHTML = lineChart(values, "#8969dc", "#8969dc");
  $("forecast-range").textContent = values.length ? `Forecast dates ${values[0][0]} – ${values[values.length - 1][0]}` : "Run analysis to create forecasts.";
}

function renderServices() {
  const totals = {}, counts = {};
  dashboardData.costs.forEach((record) => { totals[record.service_name] = (totals[record.service_name] || 0) + Number(record.amount); counts[record.service_name] = (counts[record.service_name] || 0) + 1; });
  const costServices = Object.entries(totals).sort(([, a], [, b]) => b - a).slice(0, 6);
  const usageServices = Object.entries(counts).sort(([, a], [, b]) => a - b).slice(0, 6);
  const costMax = costServices[0]?.[1] || 1;
  const usageMax = usageServices[usageServices.length - 1]?.[1] || 1;
  const rows = (services, max, formatter) => services.length ? services.map(([name, value]) => `<div class="breakdown-row"><span title="${name}">${name}</span><div class="bar-track"><div class="bar-fill" style="width:${value / max * 100}%"></div></div><span class="bar-value">${formatter(value)}</span></div>`).join("") : '<div class="empty-state">No AWS service data available.</div>';
  $("service-usage").innerHTML = rows(usageServices, usageMax, (value) => `${value} records`);
  $("service-cost").innerHTML = rows(costServices, costMax, (value) => money(value));
}

function renderAnomalies() {
  $("anomalies").innerHTML = dashboardData.anomalies.length ? dashboardData.anomalies.slice(0, 5).map((item) => `<div class="anomaly-row"><i class="severity"></i><div class="anomaly-main"><strong>${item.service_name}</strong><span>${item.usage_date} · ${item.severity} · ${accountLabel(item.account_id)}</span></div><span class="anomaly-amount">${money(item.actual_amount, item.currency)}</span></div>`).join("") : '<div class="empty-state">No AWS anomalies detected.</div>';
}

function accountLabel(accountId) {
  const account = dashboardData.accounts.find((item) => item.id === accountId);
  if (!account) return "Account unavailable";
  const isSample = account.external_account_id.endsWith("-sample");
  return `${account.provider.toUpperCase()} · ${isSample ? "Sample data" : account.display_name} · ${account.external_account_id}`;
}

function renderResources() {
  const actionOptions = (resource) => resource.resource_type === "s3_bucket"
    ? '<option value="delete">Delete bucket</option>'
    : resource.resource_type === "ebs_volume"
      ? '<option value="delete">Delete volume</option>'
      : '<option value="stop">Stop</option><option value="delete">Terminate</option>';
  dashboardData.resources = dashboardData.resources.filter((resource) => resource.status !== "terminated");
  const resourceCard = (resource) => `<div class="resource-card" data-resource="${resource.id}"><div><span class="resource-title">${resource.external_resource_id}</span><span class="resource-meta">${resource.resource_type} · ${resource.region || "global"} · ${resource.status}</span><span class="resource-meta">${resource.idle_reason || resource.metadata_json?.reason || "Optimization candidate"}</span></div><div class="resource-cost">${money(resource.estimated_monthly_cost)}<small>estimated monthly cost</small></div><div class="resource-actions"><select aria-label="Remediation action">${actionOptions(resource)}</select><label class="approve-label"><input type="checkbox"> Approve</label><button class="button primary optimize-button">Optimize</button></div></div>`;
  const grouped = dashboardData.resources.reduce((groups, resource) => {
    const account = dashboardData.accounts.find((item) => item.id === resource.account_id);
    const key = account ? `${account.provider}:${account.external_account_id}` : `unknown:${resource.account_id}`;
    (groups[key] ||= []).push(resource);
    return groups;
  }, {});
  $("resources-list").innerHTML = dashboardData.resources.length ? Object.values(grouped).map((resources) => `<section class="resource-account"><div class="resource-account-heading">${accountLabel(resources[0].account_id)}</div>${resources.map(resourceCard).join("")}</section>`).join("") : '<div class="empty-state">No idle resources require approval.</div>';
  document.querySelectorAll(".optimize-button").forEach((button) => button.addEventListener("click", optimizeResource));
}

async function optimizeResource(event) {
  const card = event.currentTarget.closest(".resource-card");
  const approved = card.querySelector("input").checked;
  if (!approved) { showToast("Please approve this cloud mutation first.", true); return; }
  const action = card.querySelector("select").value;
  setLoading(event.currentTarget, true);
  try {
    const result = await apiPost(`/remediation/resources/${card.dataset.resource}`, { action, approved: true, requested_by: "html-dashboard" });
    showToast(`Remediation ${result.status}: ${result.action}`);
    await loadDashboard();
  } catch (error) { showToast(`Remediation failed: ${error.message}`, true); setLoading(event.currentTarget, false); }
}

async function loadDashboard() {
  try {
    const endDate = new Date(); endDate.setDate(endDate.getDate() + 1);
    const startDate = new Date(); startDate.setDate(startDate.getDate() - HISTORY_DAYS);
    const forecastStart = new Date(); forecastStart.setDate(forecastStart.getDate() + 1);
    const forecastEnd = new Date(); forecastEnd.setDate(forecastEnd.getDate() + HISTORY_DAYS + 1);
    dashboardData = {
      accounts: await apiGet("/ingestion/accounts"),
      costs: await apiGet("/ingestion/costs", { provider: "aws", include_sample_data: false, start_date: startDate.toISOString().slice(0, 10), end_date: endDate.toISOString().slice(0, 10), limit: 1000 }),
      forecasts: await apiGet("/analysis/forecasts", { provider: "aws", include_sample_data: false, start_date: forecastStart.toISOString().slice(0, 10), end_date: forecastEnd.toISOString().slice(0, 10), limit: 1000 }),
      anomalies: await apiGet("/analysis/anomalies", { provider: "aws", include_sample_data: false, limit: 1000 }),
      resources: await apiGet("/remediation/resources", { limit: 200 }),
    };
    renderMetrics(); renderSpend(); renderForecast(); renderServices(); renderAnomalies(); renderResources();
    $("last-updated").textContent = `Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  } catch (error) { showToast(`Could not load dashboard: ${error.message}`, true); }
}

async function checkConnection() {
  try {
    const result = await apiGet("/ingestion/connectivity/aws");
    const status = $("connection-status");
    if (result.connected) {
      $("connection-title").textContent = `Connected to AWS account ${result.account_id}`;
      $("connection-detail").textContent = `Using ${result.profile || "default profile"} in ${result.region}`;
      status.textContent = "Connected"; status.className = "status-pill";
      $("sync-button").disabled = false;
    } else {
      $("connection-title").textContent = "AWS account is not connected";
      $("connection-detail").textContent = result.error || "Check your AWS credentials and try again.";
      status.textContent = "Offline"; status.className = "status-pill error";
    }
  } catch (error) { $("connection-title").textContent = "Local API is unavailable"; $("connection-detail").textContent = "Start the FastAPI service before refreshing the dashboard."; $("connection-status").textContent = "Offline"; $("connection-status").className = "status-pill error"; showToast(error.message, true); }
}

async function syncData() {
  const button = $("sync-button"); setLoading(button, true);
  try {
    const endDate = new Date(); endDate.setDate(endDate.getDate() + 1); const startDate = new Date(); startDate.setDate(startDate.getDate() - HISTORY_DAYS);
    const result = await apiPost("/ingestion/sync", { providers: ["aws"], start_date: startDate.toISOString().slice(0, 10), end_date: endDate.toISOString().slice(0, 10), include_resources: true, use_sample_data: false });
    const provider = result.results[0];
    if (provider.status !== "succeeded") throw new Error(provider.errors.join(", "));
    showToast(`AWS sync complete: ${provider.cost_records_ingested} cost records and ${provider.resources_ingested} resources.`);
    await loadDashboard();
  } catch (error) { showToast(`AWS sync failed: ${error.message}`, true); } finally { setLoading(button, false); }
}

async function runAnalysis() {
  const button = $("analysis-button"); setLoading(button, true);
  try { const result = await apiPost("/analysis/run", { providers: ["aws"], forecast_days: 30, prefer_prophet: true, include_sample_data: false }); showToast(`AWS analysis complete: ${result.forecasts_created} forecast points and ${result.anomalies_detected} anomalies.`); await loadDashboard(); }
  catch (error) { showToast(`Analysis failed: ${error.message}`, true); } finally { setLoading(button, false); }
}

$("refresh-button").addEventListener("click", () => { checkConnection(); loadDashboard(); });
$("sync-button").addEventListener("click", syncData);
$("analysis-button").addEventListener("click", runAnalysis);
checkConnection(); loadDashboard();
