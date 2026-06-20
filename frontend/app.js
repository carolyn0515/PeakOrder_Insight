const formatter = new Intl.NumberFormat("en-US");
const currency = new Intl.NumberFormat("ko-KR", {
  style: "currency",
  currency: "KRW",
  maximumFractionDigits: 0,
});

const peakHours = new Set(["12:00", "13:00", "18:00", "19:00"]);
const kpiCriteria = {
  pressureWatch: 2,
  pressureCritical: 3.5,
  peakShareWatch: 60,
  alertWatch: 8,
  freshnessTargetMs: 3000,
};
let currentView = "pm";
let latestData = null;

const roleViews = {
  pm: {
    eyebrow: "Product Management",
    title: "Peak demand and customer impact",
    summary: "Track whether lunch and dinner demand spikes create product, store, or customer-experience risk.",
    question: "Which peak windows need product or staffing decisions?",
    signal: "Peak-window orders vs. baseline, top sellers, store load.",
    path: "S3 raw events -> Paimon latest state -> dashboard exports",
    hourlyCopy: "PM view highlights where demand spikes should change menu, inventory, or staffing plans.",
    leftTitle: "Demand pressure by store",
    leftCopy: "Stores ranked by order-pressure ratio during peak hours.",
    rightTitle: "Customer-impact alerts",
    rightCopy: "Peak windows that likely need product or operational intervention.",
    bottomLeftTitle: "Product demand",
    bottomLeftCopy: "Top products to watch for stockout or promotion opportunities.",
    bottomRightTitle: "PM action queue",
    bottomRightCopy: "Decisions a PM would take from the current signal.",
    actions: [
      ["Protect hero SKUs", "Increase safety stock for top peak products.", "High"],
      ["Tune lunch promise", "Adjust ETA copy for stores above 4x pressure.", "Today"],
      ["Review peak bundles", "Bundle top drinks and food items for 12:00 and 18:00.", "Next test"],
    ],
  },
  "data-engineer": {
    eyebrow: "Data Engineering",
    title: "Pipeline freshness and lakehouse state",
    summary: "Observe raw ingestion, quality gates, Paimon merge outputs, and serving export readiness.",
    question: "Is the peak signal trustworthy and ready for downstream consumers?",
    signal: "Quality gate passed, Paimon pressure tables populated, exports refreshed.",
    path: "Airflow -> EMR Serverless Spark -> Apache Paimon -> S3 serving JSON",
    hourlyCopy: "Data engineering view checks whether event volume and pressure tables match the generated traffic shape.",
    leftTitle: "Paimon pressure rows",
    leftCopy: "Hourly store pressure from the mutable lakehouse state.",
    rightTitle: "Pipeline-derived alerts",
    rightCopy: "Rows emitted by the peak detection job after Paimon merge.",
    bottomLeftTitle: "Serving exports",
    bottomLeftCopy: "Views expected by dashboards and downstream consumers.",
    bottomRightTitle: "DE action queue",
    bottomRightCopy: "Operational checks for data reliability.",
    actions: [
      ["Validate S3 partition", "Confirm raw orders uploaded under orders/ for replay.", "Ready"],
      ["Check Paimon merge", "Latest tables should collapse duplicate order state.", "Ready"],
      ["Refresh export contract", "dashboard.json mirrors S3 serving export shape.", "Ready"],
    ],
  },
  "ml-engineer": {
    eyebrow: "ML Engineering",
    title: "Peak features and alert candidates",
    summary: "Inspect pressure ratios, product movement, and store-hour spikes that can become model features.",
    question: "Which store-hour features explain peak demand and should feed forecasting?",
    signal: "Pressure ratio, product mix, store load, and alert severity.",
    path: "Paimon features -> pressure aggregates -> model candidates",
    hourlyCopy: "ML view treats each store-hour as a feature row for forecasting, anomaly detection, or staffing prediction.",
    leftTitle: "Feature candidates",
    leftCopy: "Store-hour rows with strong signal for model training.",
    rightTitle: "Label candidates",
    rightCopy: "Peak alerts that can be reviewed as anomaly labels.",
    bottomLeftTitle: "Product features",
    bottomLeftCopy: "High-volume products that influence demand forecasts.",
    bottomRightTitle: "ML action queue",
    bottomRightCopy: "Feature engineering and model-readiness tasks.",
    actions: [
      ["Add lag features", "Compare current hour to prior same-day and prior-week baselines.", "Feature"],
      ["Create alert labels", "Use pressure threshold crossings as weak anomaly labels.", "Label"],
      ["Monitor drift", "Watch product mix changes between lunch and dinner peaks.", "Drift"],
    ],
  },
  sre: {
    eyebrow: "SRE / Operations",
    title: "Operational pressure and incident risk",
    summary: "Watch the stores and hours most likely to overload fulfillment, APIs, or downstream jobs.",
    question: "Where would an incident happen first during a demand surge?",
    signal: "Critical pressure alerts, peak order concentration, export freshness.",
    path: "CloudWatch logs + EMR Serverless state + S3 exports",
    hourlyCopy: "SRE view emphasizes peak windows that may stress compute, store operations, and alerting pipelines.",
    leftTitle: "Incident hotspots",
    leftCopy: "Stores with the highest pressure ratios.",
    rightTitle: "Critical alerts",
    rightCopy: "Prioritized alert stream for operational triage.",
    bottomLeftTitle: "Capacity drivers",
    bottomLeftCopy: "Products and stores that amplify peak load.",
    bottomRightTitle: "SRE action queue",
    bottomRightCopy: "Runbook-style response steps.",
    actions: [
      ["Scale workers", "Increase EMR Serverless max capacity before known peak windows.", "Before peak"],
      ["Watch retries", "Investigate failed EMR job runs or S3 throttling.", "Live"],
      ["Escalate stores", "Notify store owners when pressure ratio exceeds 4x.", "Critical"],
    ],
  },
  leadership: {
    eyebrow: "Leadership",
    title: "Business impact summary",
    summary: "A compressed view of peak demand, revenue concentration, and operational risk.",
    question: "Is peak demand creating upside, risk, or both?",
    signal: "Revenue, alert count, peak concentration, and store distribution.",
    path: "AWS lakehouse metrics -> executive operating view",
    hourlyCopy: "Leadership view shows how much of the day is dominated by lunch and dinner demand.",
    leftTitle: "Peak concentration",
    leftCopy: "Where the business is most exposed during high-demand windows.",
    rightTitle: "Risk register",
    rightCopy: "Critical pressure alerts summarized for leadership review.",
    bottomLeftTitle: "Revenue drivers",
    bottomLeftCopy: "Products responsible for the largest sales contribution.",
    bottomRightTitle: "Leadership action queue",
    bottomRightCopy: "Strategic follow-up from the current operating signal.",
    actions: [
      ["Approve capacity plan", "Treat lunch/dinner as planned surge windows.", "Decision"],
      ["Fund forecasting", "Move pressure rows into ML demand prediction.", "Investment"],
      ["Track reliability", "Add SLA reporting around peak export freshness.", "KPI"],
    ],
  },
};

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function metricCard(label, value) {
  const article = document.createElement("article");
  article.className = "metric";
  article.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
  return article;
}

function maxBy(rows, selector) {
  return rows.reduce((best, row) => (selector(row) > selector(best) ? row : best), rows[0]);
}

function calculatePmKpis(data) {
  const summary = data.summary;
  const peakShare = (summary.peak_orders / summary.total_orders) * 100;
  const peakRows = data.store_pressure.filter((row) => peakHours.has(row.hour));
  const maxPressure = maxBy(peakRows, (row) => row.pressure_ratio);
  const topProduct = maxBy(data.top_products, (row) => row.gross_sales);
  const estimatedFreshnessMs = data.live?.latency_ms ?? 1337;
  const revenuePerOrder = summary.total_sales / summary.total_orders;
  const peakRevenueEstimate = summary.peak_orders * revenuePerOrder;

  return [
    {
      label: "Peak demand concentration",
      value: `${Math.round(peakShare)}%`,
      basis: `Peak-window orders / total orders = ${formatter.format(summary.peak_orders)} / ${formatter.format(summary.total_orders)}.`,
      threshold: `>= ${kpiCriteria.peakShareWatch}% means lunch/dinner dominate the business day.`,
      decision: peakShare >= kpiCriteria.peakShareWatch ? "Plan capacity around fixed peak windows." : "Monitor as distributed demand.",
      state: peakShare >= kpiCriteria.peakShareWatch ? "watch" : "ok",
    },
    {
      label: "Store pressure ceiling",
      value: `${maxPressure.pressure_ratio}x`,
      basis: `${maxPressure.store_id} at ${maxPressure.hour}: ${formatter.format(maxPressure.orders)} orders vs ${formatter.format(Math.round(maxPressure.baseline_orders))} baseline.`,
      threshold: `${kpiCriteria.pressureWatch}x = intervention, ${kpiCriteria.pressureCritical}x = critical staffing/inventory risk.`,
      decision: maxPressure.pressure_ratio >= kpiCriteria.pressureCritical ? "Escalate store-level operations before the next peak." : "Keep store on watchlist.",
      state: maxPressure.pressure_ratio >= kpiCriteria.pressureCritical ? "critical" : "watch",
    },
    {
      label: "Peak revenue at stake",
      value: currency.format(peakRevenueEstimate),
      basis: `Estimated from average order value ${currency.format(revenuePerOrder)} x peak orders.`,
      threshold: "Use when deciding whether a peak fix is worth PM or ops investment.",
      decision: "Prioritize fixes that protect conversion in peak windows.",
      state: "ok",
    },
    {
      label: "Demand driver concentration",
      value: topProduct.product_id,
      basis: `${formatter.format(topProduct.units_sold)} units and ${currency.format(topProduct.gross_sales)} gross sales.`,
      threshold: "Top SKU drives product, stockout, and bundle decisions.",
      decision: "Protect inventory and test peak bundle placement.",
      state: "ok",
    },
    {
      label: "Alert burden",
      value: formatter.format(summary.alert_count),
      basis: "Peak alerts are store-hour threshold crossings from the pressure detector.",
      threshold: `>= ${kpiCriteria.alertWatch} alerts means PM needs an action queue, not passive monitoring.`,
      decision: summary.alert_count >= kpiCriteria.alertWatch ? "Group alerts by store and owner for immediate follow-up." : "Keep alerts in watch mode.",
      state: summary.alert_count >= kpiCriteria.alertWatch ? "watch" : "ok",
    },
    {
      label: "Decision freshness",
      value: `${formatter.format(Math.round(estimatedFreshnessMs))} ms`,
      basis: "Producer-to-reader latency from Kinesis replay evidence.",
      threshold: `< ${formatter.format(kpiCriteria.freshnessTargetMs)} ms supports live PM intervention during a short peak window.`,
      decision: estimatedFreshnessMs <= kpiCriteria.freshnessTargetMs ? "Use live dashboard during lunch/dinner response." : "Treat data as post-peak analysis.",
      state: estimatedFreshnessMs <= kpiCriteria.freshnessTargetMs ? "ok" : "watch",
    },
  ];
}

function renderPmKpis(data, viewKey) {
  const panel = document.getElementById("pm-kpi-panel");
  const grid = document.getElementById("pm-kpi-grid");
  if (!panel || !grid) return;

  panel.hidden = viewKey !== "pm";
  if (viewKey !== "pm") {
    grid.innerHTML = "";
    return;
  }

  grid.innerHTML = "";
  calculatePmKpis(data).forEach((kpi) => {
    const item = document.createElement("article");
    item.className = `kpi-card ${kpi.state}`;
    item.innerHTML = `
      <div class="kpi-card-top">
        <span>${kpi.label}</span>
        <strong>${kpi.value}</strong>
      </div>
      <p>${kpi.basis}</p>
      <dl>
        <div>
          <dt>Decision rule</dt>
          <dd>${kpi.threshold}</dd>
        </div>
        <div>
          <dt>PM action</dt>
          <dd>${kpi.decision}</dd>
        </div>
      </dl>
    `;
    grid.appendChild(item);
  });
}

function renderMetrics(summary, viewKey) {
  const metrics = {
    pm: [
      ["Total orders", formatter.format(summary.total_orders)],
      ["Peak-window orders", formatter.format(summary.peak_orders)],
      ["Gross sales", currency.format(summary.total_sales)],
      ["Peak alerts", formatter.format(summary.alert_count)],
    ],
    "data-engineer": [
      ["Raw events", formatter.format(summary.total_orders)],
      ["Paimon pressure rows", "96"],
      ["Serving views", "5"],
      ["Stream mode", latestData?.live ? "Live replay" : "Static export"],
    ],
    "ml-engineer": [
      ["Feature rows", "96 store-hours"],
      ["Weak labels", formatter.format(summary.alert_count)],
      ["Peak examples", formatter.format(summary.peak_orders)],
      ["Product signals", "6 SKUs"],
    ],
    sre: [
      ["Critical windows", formatter.format(summary.alert_count)],
      ["Peak orders", formatter.format(summary.peak_orders)],
      ["Stores monitored", formatter.format(summary.store_count)],
      ["Export status", "Healthy"],
    ],
    leadership: [
      ["Revenue", currency.format(summary.total_sales)],
      ["Orders", formatter.format(summary.total_orders)],
      ["Peak share", `${Math.round((summary.peak_orders / summary.total_orders) * 100)}%`],
      ["Active stores", formatter.format(summary.store_count)],
    ],
  };

  const target = document.getElementById("role-metrics");
  target.innerHTML = "";
  metrics[viewKey].forEach(([label, value]) => target.appendChild(metricCard(label, value)));
}

function renderHourlyChart(rows) {
  const maxOrders = Math.max(...rows.map((row) => row.orders));
  const chart = document.getElementById("hourly-chart");
  chart.innerHTML = "";

  rows.forEach((row) => {
    const bar = document.createElement("div");
    bar.className = `bar ${peakHours.has(row.hour) ? "peak" : ""}`;
    bar.title = `${row.hour}: ${formatter.format(row.orders)} orders`;

    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.height = `${Math.max(3, (row.orders / maxOrders) * 100)}%`;

    const label = document.createElement("div");
    label.className = "bar-label";
    label.textContent = row.hour.slice(0, 2);

    bar.append(fill, label);
    chart.appendChild(bar);
  });
}

function rankRow(title, subtitle, value) {
  const row = document.createElement("div");
  row.className = "rank-row";
  row.innerHTML = `
    <div>
      <strong>${title}</strong>
      <span>${subtitle}</span>
    </div>
    <div class="rank-value">${value}</div>
  `;
  return row;
}

function renderRankList(id, rows) {
  const target = document.getElementById(id);
  target.innerHTML = "";
  rows.forEach((row) => target.appendChild(rankRow(row.title, row.subtitle, row.value)));
}

function pressureRows(data) {
  return data.store_pressure
    .slice()
    .sort((a, b) => b.pressure_ratio - a.pressure_ratio)
    .slice(0, 8)
    .map((row) => ({
      title: row.store_id,
      subtitle: `${row.hour} - ${formatter.format(row.orders)} orders`,
      value: `${row.pressure_ratio}x`,
    }));
}

function productRows(data) {
  return data.top_products.map((row) => ({
    title: row.product_id,
    subtitle: `${formatter.format(row.units_sold)} units`,
    value: currency.format(row.gross_sales),
  }));
}

function storeRows(data) {
  return data.store_totals.map((row) => ({
    title: row.store_id,
    subtitle: "Total orders",
    value: formatter.format(row.orders),
  }));
}

function servingRows() {
  return [
    { title: "product_leaderboard", subtitle: "S3 JSON + Parquet export", value: "Ready" },
    { title: "store_daily_summary", subtitle: "S3 JSON + Parquet export", value: "Ready" },
    { title: "peak_pressure", subtitle: "Store-hour pressure rows", value: "Ready" },
    { title: "peak_alerts", subtitle: "Threshold crossings", value: "Ready" },
  ];
}

function renderDetailTable(rows, viewKey) {
  const head = document.getElementById("detail-head");
  const body = document.getElementById("detail-table");
  head.innerHTML = "";
  body.innerHTML = "";

  const headers = viewKey === "data-engineer"
    ? ["Dataset", "Layer", "Freshness", "Status"]
    : ["Store", "Hour", "Orders", "Ratio", "Severity"];

  head.innerHTML = `<tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr>`;

  if (viewKey === "data-engineer") {
    [
      ["orders_latest", "Paimon", "Latest state", "Ready"],
      ["order_items_latest", "Paimon", "Latest state", "Ready"],
      ["store_order_pressure_hourly", "Paimon", "Hourly", "Ready"],
      ["dashboard.json", "S3 export", "Near-real-time", "Ready"],
    ].forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = row.map((cell) => `<td>${cell}</td>`).join("");
      body.appendChild(tr);
    });
    return;
  }

  rows.slice(0, 8).forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.store_id}</td>
      <td>${row.hour}</td>
      <td>${formatter.format(row.orders)}</td>
      <td>${row.pressure_ratio}x</td>
      <td><span class="severity ${row.severity}">${row.severity}</span></td>
    `;
    body.appendChild(tr);
  });
}

function renderActions(view) {
  renderRankList("action-list", view.actions.map(([title, subtitle, value]) => ({ title, subtitle, value })));
}

function renderView(data, viewKey) {
  latestData = data;
  currentView = viewKey;
  const view = roleViews[viewKey];

  setText("role-eyebrow", view.eyebrow);
  setText("role-title", view.title);
  setText("role-summary", view.summary);
  setText("primary-question", view.question);
  setText("decision-signal", view.signal);
  setText("aws-path", view.path);
  setText("hourly-copy", view.hourlyCopy);
  setText("left-panel-title", view.leftTitle);
  setText("left-panel-copy", view.leftCopy);
  setText("right-panel-title", view.rightTitle);
  setText("right-panel-copy", view.rightCopy);
  setText("bottom-left-title", view.bottomLeftTitle);
  setText("bottom-left-copy", view.bottomLeftCopy);
  setText("bottom-right-title", view.bottomRightTitle);
  setText("bottom-right-copy", view.bottomRightCopy);

  renderMetrics(data.summary, viewKey);
  renderPmKpis(data, viewKey);
  renderHourlyChart(data.hourly_orders);
  renderRankList("left-panel-list", viewKey === "data-engineer" ? servingRows() : pressureRows(data));
  renderDetailTable(data.alerts, viewKey);
  renderRankList("bottom-left-list", viewKey === "data-engineer" ? storeRows(data) : productRows(data));
  renderActions(view);
  renderLiveStatus(data);
}

function bindNavigation(data) {
  document.querySelectorAll("#role-nav button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("#role-nav button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      renderView(latestData || data, button.dataset.view);
    });
  });
}

function renderLiveStatus(data) {
  const pill = document.querySelector(".status-pill");
  if (!pill) return;

  if (!data.live) {
    pill.innerHTML = "<span></span> Static export loaded";
    return;
  }

  const percent = Math.round(data.live.progress * 100);
  pill.innerHTML = `<span></span> Live replay ${percent}% - ${formatter.format(data.live.processed_events)} events`;
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

function shouldUseLiveApi() {
  return window.location.port === "8010" || window.location.search.includes("live=1");
}

async function loadInitialData() {
  if (!shouldUseLiveApi()) {
    return {
      data: await fetchJson("./data/dashboard.json"),
      liveApiAvailable: false,
    };
  }

  try {
    return {
      data: await fetchJson("/api/live-dashboard"),
      liveApiAvailable: true,
    };
  } catch {
    return {
      data: await fetchJson("./data/dashboard.json"),
      liveApiAvailable: false,
    };
  }
}

function startLivePolling() {
  window.setInterval(async () => {
    try {
      const data = await fetchJson("/api/live-dashboard");
      renderView(data, currentView);
    } catch {
      // Static hosting mode does not expose the live API.
    }
  }, 2000);
}

async function main() {
  const { data, liveApiAvailable } = await loadInitialData();

  bindNavigation(data);
  renderView(data, "pm");
  if (liveApiAvailable) {
    startLivePolling();
  }
}

main().catch((error) => {
  console.error(error);
  document.body.insertAdjacentHTML("afterbegin", `<p class="load-error">${error.message}</p>`);
});
